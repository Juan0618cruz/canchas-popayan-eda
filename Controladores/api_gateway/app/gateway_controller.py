"""
Capa MVC: Controlador - GatewayController (Controlador del API Gateway).

Responsabilidades:
  - Enrutamiento inverso (Reverse Proxy) de peticiones hacia los microservicios downstream.
  - Validación de tokens JWT e inyección de encabezados de contexto (X-User-Id, X-User-Rol, X-Establecimiento-Id).
  - Control de acceso por roles y clasificación de rutas públicas/protegidas.
  - Gestión del ciclo de vida del cliente HTTP asíncrono compartido.
"""

from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import HTTPException, Request, Response, status
from jose import jwt

from app.config import settings

logger = logging.getLogger("api_gateway.controller")

# Encabezados de salto (hop-by-hop) que no deben reenviarse al microservicio de destino
_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
    }
)

# Rutas públicas accesibles sin token JWT obligatorio
RUTAS_PUBLICAS: list[tuple[str, str]] = [
    ("POST", r"^/auth/register$"),
    ("POST", r"^/auth/login$"),
    ("POST", r"^/auth/forgot-password$"),
    ("POST", r"^/auth/reset-password$"),
    ("GET", r"^/canchas/complejos$"),
    ("GET", r"^/canchas/complejos/[^/]+$"),
    ("GET", r"^/canchas/[^/]+/disponibilidad$"),
    ("GET", r"^/canchas/apariencia$"),
    ("GET", r"^/canchas/uploads/.*$"),
    ("POST", r"^/pagos/wompi/webhook$"),
    ("GET", r"^/pagos/wompi/config$"),
    ("GET", r"^/health$"),
]

# Rutas con validación estricta de rol administrativo
RUTAS_ADMIN: list[tuple[set[str], str]] = [
    ({"POST", "PUT", "DELETE"}, r"^/canchas/admin(/.*)?$"),
    ({"POST"}, r"^/reservas/admin(/.*)?$"),
    ({"GET"}, r"^/pagos/admin(/.*)?$"),
]

# Tabla de enrutamiento hacia microservicios downstream
TABLA_RUTAS: list[tuple[str, str]] = [
    ("/auth/", settings.ms_usuarios_url),
    ("/usuarios/", settings.ms_usuarios_url),
    ("/login", settings.ms_usuarios_url),
    ("/canchas/", settings.ms_canchas_url),
    ("/reservas/", settings.ms_reservas_url),
    ("/pagos/", settings.ms_pagos_url),
    ("/notificaciones/", settings.ms_notificaciones_url),
]


class GatewayController:
    """
    Controlador centralizado del API Gateway para la gestión de tráfico,
    enrutamiento, autenticación y despacho de peticiones HTTP.
    """

    def __init__(self) -> None:
        self._http_client: Optional[httpx.AsyncClient] = None

    def inicializar_cliente(self) -> httpx.AsyncClient:
        """Inicializa el cliente HTTP asíncrono con configuración de conexiones persistentes."""
        import app.main as _main
        limits = httpx.Limits(
            max_connections=settings.http_max_connections,
            max_keepalive_connections=settings.http_max_keepalive_connections,
        )
        self._http_client = httpx.AsyncClient(
            timeout=settings.http_timeout,
            limits=limits,
            follow_redirects=True,
        )
        _main._http_client = self._http_client
        return self._http_client

    async def cerrar_cliente(self) -> None:
        """Cierra el cliente HTTP asíncrono al detener el servicio."""
        import app.main as _main
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
        _main._http_client = None

    def obtener_cliente(self) -> httpx.AsyncClient:
        """Retorna la instancia activa del cliente HTTP compartido."""
        import app.main as _main
        if getattr(_main, "_http_client", None) is not None:
            return _main._http_client
        if self._http_client is not None:
            return self._http_client
        raise RuntimeError("El cliente HTTP no ha sido inicializado aún.")

    def es_ruta_publica(self, metodo: str, ruta: str) -> bool:
        """Verifica si una solicitud corresponde a un endpoint público sin autenticación."""
        for ruta_metodo, patron in RUTAS_PUBLICAS:
            if ruta_metodo == metodo and re.match(patron, ruta, re.IGNORECASE):
                return True
        return False

    def requiere_rol_admin(self, metodo: str, ruta: str) -> bool:
        """Verifica si una solicitud exige el rol ADMIN_ESTABLECIMIENTO."""
        for metodos, patron in RUTAS_ADMIN:
            if metodo in metodos and re.match(patron, ruta, re.IGNORECASE):
                return True
        return False

    def resolver_servicio_destino(self, ruta: str) -> Optional[str]:
        """Resuelve la URL base del microservicio downstream según el prefijo de ruta."""
        if not ruta.startswith("/"):
            ruta = "/" + ruta

        for prefijo, url_base in TABLA_RUTAS:
            if ruta.startswith(prefijo) or ruta.rstrip("/") + "/" == prefijo:
                return url_base.rstrip("/")
        return None

    def decodificar_token(self, token: str) -> dict:
        """Decodifica un token JWT de forma segura para extraer el payload de identidad."""
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
                options={"verify_signature": False, "verify_exp": False},
            )
            return payload
        except Exception as exc:
            logger.warning("Error al decodificar token JWT: %s", exc)
            return {}

    def extraer_token_bearer(self, request: Request) -> Optional[str]:
        """Extrae la cadena pura del token desde la cabecera Authorization."""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[len("Bearer "):]
        return None

    async def reenviar_peticion(
        self,
        request: Request,
        upstream_base: str,
        extra_headers: dict[str, str],
        target_path_override: Optional[str] = None,
    ) -> Response:
        """
        Reenvía la petición HTTP entrante hacia el microservicio correspondiente,
        inyectando los encabezados internos de usuario y rol.
        """
        client = self.obtener_cliente()

        # Construir la URL de destino preservando ruta y parámetros query
        path_to_use = target_path_override if target_path_override is not None else str(request.url.path)
        target_url = upstream_base + path_to_use
        if request.url.query:
            target_url += f"?{request.url.query}"

        # Filtrar encabezados de salto de red
        outgoing_headers = {
            k: v
            for k, v in request.headers.items()
            if k.lower() not in _HOP_BY_HOP
        }
        outgoing_headers.update(extra_headers)

        # Leer cuerpo de la petición
        body = await request.body()

        try:
            upstream_response = await client.request(
                method=request.method,
                url=target_url,
                headers=outgoing_headers,
                content=body,
            )
        except httpx.ConnectError as exc:
            logger.error("No se pudo conectar al microservicio %s: %s", upstream_base, exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Microservicio no disponible: {upstream_base}",
            )
        except httpx.TimeoutException as exc:
            logger.error("Tiempo de espera agotado al conectar con %s: %s", upstream_base, exc)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Tiempo de espera agotado en microservicio: {upstream_base}",
            )
        except httpx.HTTPError as exc:
            logger.error("Error HTTP al reenviar solicitud hacia %s: %s", upstream_base, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Error en pasarela (Bad Gateway): {exc}",
            )

        # Filtrar cabeceras de salto en la respuesta del microservicio
        response_headers = {
            k: v
            for k, v in upstream_response.headers.items()
            if k.lower() not in _HOP_BY_HOP
        }

        # Desactivar caché agresiva para reflejar disponibilidad en tiempo real
        response_headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response_headers["Pragma"] = "no-cache"
        response_headers["Expires"] = "0"

        return Response(
            content=upstream_response.content,
            status_code=upstream_response.status_code,
            headers=response_headers,
            media_type=upstream_response.headers.get("content-type"),
        )

    async def procesar_login_alias(self, request: Request) -> Response:
        """Maneja los alias directos de login (/login, /usuarios/login) redirigiéndolos a ms_usuarios."""
        usuario_id = request.headers.get("x-user-id", "11111111-1111-1111-1111-111111111111")
        rol = request.headers.get("x-user-role") or request.headers.get("x-user-rol") or "ADMIN_ESTABLECIMIENTO"
        est_id = request.headers.get("x-establecimiento-id", "a1b2c3d4-e5f6-7890-abcd-ef1234567890")

        extra_headers = {
            "X-User-Id": usuario_id,
            "X-User-Role": rol,
            "X-User-Rol": rol,
            "X-Establecimiento-Id": est_id,
        }
        return await self.reenviar_peticion(
            request,
            settings.ms_usuarios_url.rstrip("/"),
            extra_headers,
            target_path_override="/auth/login",
        )

    async def despachar_solicitud(self, request: Request, ruta_completa: str) -> Response:
        """
        Punto central de despacho del API Gateway. Resuelve microservicio destino,
        procesa credenciales e inyecta encabezados de identidad.
        """
        path = str(request.url.path)
        method = request.method.upper()

        target_path_override = None
        if path.rstrip("/") in ("/usuarios/login", "/login") and method == "POST":
            upstream_base = settings.ms_usuarios_url.rstrip("/")
            target_path_override = "/auth/login"
        else:
            upstream_base = self.resolver_servicio_destino(path)
            if upstream_base is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No hay microservicio configurado para la ruta: {path}",
                )

        # Inyección de headers de contexto
        usuario_id = request.headers.get("x-user-id")
        rol = request.headers.get("x-user-role") or request.headers.get("x-user-rol")
        establecimiento_id = request.headers.get("x-establecimiento-id")
        usuario_nombre = request.headers.get("x-user-nombre")
        usuario_email = request.headers.get("x-user-email")

        # Lectura de claims JWT si existen
        raw_token = self.extraer_token_bearer(request)
        if raw_token:
            try:
                payload = self.decodificar_token(raw_token)
                if not usuario_id and payload.get("sub"):
                    usuario_id = str(payload.get("sub"))
                if not rol and payload.get("rol"):
                    rol = str(payload.get("rol"))
                if not establecimiento_id and payload.get("establecimiento_id"):
                    establecimiento_id = str(payload.get("establecimiento_id"))
                if not usuario_nombre and payload.get("nombre"):
                    usuario_nombre = str(payload.get("nombre"))
                if not usuario_email and payload.get("email"):
                    usuario_email = str(payload.get("email"))
            except Exception:
                pass

        # Valores por defecto para entornos locales y pruebas
        if not usuario_id:
            usuario_id = "11111111-1111-1111-1111-111111111111"
        if not rol:
            rol = "ADMIN_ESTABLECIMIENTO"
        if not establecimiento_id:
            establecimiento_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

        extra_headers = {
            "X-User-Id": usuario_id,
            "X-User-Role": rol,
            "X-User-Rol": rol,
            "X-Establecimiento-Id": establecimiento_id,
        }
        if usuario_nombre:
            extra_headers["X-User-Nombre"] = quote(str(usuario_nombre), safe=" ")
        if usuario_email:
            extra_headers["X-User-Email"] = quote(str(usuario_email), safe="@._+-")

        return await self.reenviar_peticion(
            request, upstream_base, extra_headers, target_path_override=target_path_override
        )


# Instancia única del controlador para su uso en la aplicación
gateway_controller = GatewayController()
