"""
API Gateway — Punto de entrada principal y enrutador del sistema Canchas Popayán.

Responsabilidades según la arquitectura MVC:
  - Enrutamiento inverso hacia los microservicios downstream mediante GatewayController.
  - Gestión del ciclo de vida de la aplicación FastAPI y cliente HTTP.
  - Exposición de endpoints de sondeo de estado (/health).
  - Manejo global de excepciones y respuestas HTTP estándar.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.gateway_controller import gateway_controller

# ---------------------------------------------------------------------------
# Configuración del registro de eventos (Logging)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api_gateway")


# ---------------------------------------------------------------------------
# Cliente HTTP compartido y adaptadores de compatibilidad para pruebas
# ---------------------------------------------------------------------------
_http_client = None

_requires_admin = gateway_controller.requiere_rol_admin
_is_public = gateway_controller.es_ruta_publica
_resolve_upstream = gateway_controller.resolver_servicio_destino
_decode_token = gateway_controller.decodificar_token
_extract_bearer = gateway_controller.extraer_token_bearer
_proxy_request = gateway_controller.reenviar_peticion


# ---------------------------------------------------------------------------
# Ciclo de vida de la aplicación (Lifespan)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Gestiona la inicialización y el cierre ordenado de los recursos del API Gateway."""
    gateway_controller.inicializar_cliente()
    logger.info("API Gateway iniciado exitosamente — Cliente HTTP preparado.")
    yield
    await gateway_controller.cerrar_cliente()
    logger.info("API Gateway detenido — Conexiones HTTP cerradas.")


# ---------------------------------------------------------------------------
# Aplicación FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Canchas Popayán — API Gateway",
    version="1.0.0",
    description="Punto de entrada único para la arquitectura de microservicios de Canchas Popayán.",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Configuración de CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoint de Verificación de Salud (/health)
# ---------------------------------------------------------------------------
@app.api_route("/health", methods=["GET", "HEAD"], tags=["Salud"])
async def health_check() -> dict:
    """Verificación de operatividad del API Gateway (Liveness Probe)."""
    return {"status": "ok", "service": "api_gateway"}


# ---------------------------------------------------------------------------
# Rutas de alias para inicio de sesión
# ---------------------------------------------------------------------------
@app.post("/usuarios/login", tags=["Autenticación - Alias"])
@app.post("/login", tags=["Autenticación - Alias"])
async def login_alias(request: Request) -> Response:
    """Redirige peticiones de login al microservicio ms_usuarios mediante el controlador."""
    return await gateway_controller.procesar_login_alias(request)


# ---------------------------------------------------------------------------
# Despachador principal (Catch-all Proxy Route)
# ---------------------------------------------------------------------------
@app.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    tags=["Pasarela"],
    include_in_schema=False,
)
async def gateway(request: Request, full_path: str) -> Response:  # noqa: ARG001
    """Despacha todas las solicitudes HTTP hacia los microservicios downstream."""
    return await gateway_controller.despachar_solicitud(request, full_path)


# ---------------------------------------------------------------------------
# Manejadores globales de excepciones
# ---------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:  # noqa: ARG001
    """Manejo controlado de excepciones HTTP de FastAPI."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None) or {},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001
    """Captura de errores no controlados para evitar fugas de información interna."""
    logger.exception("Excepción no controlada procesando %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor en API Gateway."},
    )
