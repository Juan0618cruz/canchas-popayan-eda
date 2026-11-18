"""
Real SMTP email delivery service for ms_notificaciones using smtplib + email.mime.
Includes IPv4 resolution preference, exponential retry backoff, and graceful
console simulation fallback for local / Docker environments.
"""

import asyncio
import logging
import smtplib
import socket
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional

from app.config import settings

logger = logging.getLogger("ms_notificaciones.smtp")


def _log_console_email(
    to_email: str,
    to_name: str,
    subject: str,
    plain_body: str,
    reason: str,
) -> None:
    """Print clean simulated email to container stdout logs in development / backup mode."""
    sep = "=" * 70
    banner = (
        f"\n{sep}\n"
        "📬 [MODO CONTINGENCIA EMAIL - NOTIFICACIONES]\n"
        f"Para    : {to_name} <{to_email}>\n"
        f"De      : {settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL or settings.SMTP_USER}>\n"
        f"Asunto  : {subject}\n"
        f"Motivo  : {reason}\n"
        f"{'-' * 70}\n"
        f"{plain_body.strip()}\n"
        f"{sep}\n"
    )
    print(banner, flush=True)
    logger.info(banner)


def _try_smtp_connect(host: str, port: int, timeout: int) -> smtplib.SMTP:
    """
    Crea la conexión SMTP asegurando compatibilidad con:
      - Puerto 465: SSL directo (smtplib.SMTP_SSL)
      - Puerto 587 (o estándar): STARTTLS (smtplib.SMTP + starttls)
    Garantiza que el server_hostname se mantenga como el FQDN para la verificación
    del certificado SSL/TLS (SNI), resolviendo IPv4 si es necesario.
    """
    is_ssl = (port == 465)
    smtp_cls = smtplib.SMTP_SSL if is_ssl else smtplib.SMTP

    try:
        # 1. Intentar conexión directa estándar con el host
        server = smtp_cls(host, port, timeout=timeout)
    except Exception as direct_exc:
        logger.warning(
            "[SMTP] Conexión directa a %s:%d falló (%s). Intentando con resolución IPv4...",
            host,
            port,
            direct_exc,
        )
        # 2. Respaldo IPv4 para entornos Docker con red IPv6 no enrutada
        try:
            addr_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
            if not addr_info:
                raise direct_exc
            target_ip = addr_info[0][4][0]
            server = smtp_cls(target_ip, port, timeout=timeout)
            # CRUCIAL: Establecer el hostname original para validación TLS/SSL (SNI)
            server._host = host
        except Exception:
            raise direct_exc

    server.ehlo()
    if not is_ssl:
        server.starttls()
        server.ehlo()

    return server


def send_email_sync(
    to_email: str,
    to_name: str,
    subject: str,
    plain_body: str,
    html_body: str,
) -> tuple[str, Optional[str]]:
    """
    Despacha un correo electrónico multipart (texto plano + HTML) sobre SMTP (TLS/SSL).
    Retorna (status, error_detail):
      - ('ENVIADO_SMTP', None) en entrega exitosa real
      - ('ENVIADO_CONSOLA', reason) en modo contingencia/desarrollo o fallo de red
      - ('SIN_CREDENCIALES_SMTP', reason) si falta configuración en .env
      - ('ERROR_SMTP', error_message) si el fallo persiste y no hay contingencia
    """
    smtp_host = (settings.SMTP_HOST or "").strip() or "smtp.gmail.com"
    smtp_port = int(str(settings.SMTP_PORT).strip() or 587)
    smtp_user = (settings.SMTP_USER or "").strip()
    smtp_password = (settings.SMTP_PASSWORD or "").strip().replace(" ", "")
    smtp_from_name = (settings.SMTP_FROM_NAME or "").strip() or "Canchas Popayan"
    smtp_from_email = (settings.SMTP_FROM_EMAIL or "").strip() or smtp_user
    recipient_email = (to_email or "").strip()
    dev_mode = str(getattr(settings, "SMTP_DEV_MODE", "auto")).strip().lower()

    if not recipient_email or "@" not in recipient_email:
        reason = f"Correo destinatario inválido o vacío: '{recipient_email}'"
        logger.warning("[SMTP] %s", reason)
        return "ERROR_SMTP", reason

    # 1. Modo desarrollo forzado explícito
    if dev_mode in ("true", "1", "yes"):
        reason = "Modo desarrollo activo (SMTP_DEV_MODE=true). Correo simulado en consola."
        _log_console_email(recipient_email, to_name, subject, plain_body, reason)
        return "ENVIADO_CONSOLA", reason

    # 2. Credenciales faltantes en .env
    if not smtp_user or not smtp_password:
        reason = (
            "Credenciales SMTP vacías (SMTP_USER / SMTP_PASSWORD). "
            "Se registra entrega en consola de desarrollo."
        )
        logger.info("[SMTP] %s Destinatario: %s", reason, recipient_email)
        _log_console_email(recipient_email, to_name, subject, plain_body, reason)
        return "SIN_CREDENCIALES_SMTP", reason

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((smtp_from_name, smtp_from_email))
    msg["To"] = formataddr((to_name or recipient_email, recipient_email))
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    max_retries = max(1, getattr(settings, "SMTP_MAX_RETRIES", 2))
    timeout = max(3, getattr(settings, "SMTP_TIMEOUT", 8))
    backoff = getattr(settings, "SMTP_RETRY_BACKOFF_SECONDS", 1.0)
    last_err: Optional[Exception] = None

    # 3. Intentos de envío SMTP con diagnóstico y capturas precisas
    for attempt in range(1, max_retries + 1):
        try:
            with _try_smtp_connect(smtp_host, smtp_port, timeout=timeout) as server:
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from_email, [recipient_email], msg.as_string())

            success_msg = f"✅ [SMTP ÉXITO] Correo entregado exitosamente a {recipient_email} | Asunto: {subject} (Intento {attempt}/{max_retries})"
            print(f"\n{'=' * 70}\n{success_msg}\n{'=' * 70}\n", flush=True)
            logger.info(success_msg)
            return "ENVIADO_SMTP", None

        except smtplib.SMTPAuthenticationError as auth_err:
            error_code = getattr(auth_err, "smtp_code", 535)
            error_detail = auth_err.smtp_error if hasattr(auth_err, "smtp_error") else str(auth_err)
            reason = (
                f"❌ [ERROR DE AUTENTICACIÓN SMTP] (Código {error_code}):\n"
                f"   El servidor '{smtp_host}:{smtp_port}' rechazó las credenciales para '{smtp_user}'.\n"
                f"   Detalle del servidor: {error_detail}\n"
                f"   💡 DIAGNÓSTICO: Si usas Gmail, verifica que la 'Contraseña de Aplicación' (App Password)\n"
                f"   de 16 dígitos esté activa en Google Accounts y configurada en SMTP_PASSWORD.\n"
                f"   Activando Modo Contingencia para no bloquear el flujo del usuario."
            )
            print(f"\n{'=' * 70}\n{reason}\n{'=' * 70}\n", flush=True)
            logger.error(reason)
            _log_console_email(recipient_email, to_name, subject, plain_body, reason)
            return "ENVIADO_CONSOLA", reason

        except (smtplib.SMTPConnectError, ConnectionRefusedError, socket.timeout, TimeoutError) as conn_err:
            error_msg = (
                f"❌ [CONEXIÓN SMTP RECHAZADA O TIMEOUT] (Intento {attempt}/{max_retries}):\n"
                f"   No fue posible conectar con '{smtp_host}:{smtp_port}'.\n"
                f"   Detalle: {conn_err}\n"
                f"   💡 DIAGNÓSTICO: Verifica si tu conexión a Internet o red bloquea el puerto {smtp_port}."
            )
            print(f"\n{error_msg}\n", flush=True)
            logger.warning(error_msg)
            last_err = conn_err
            if attempt < max_retries:
                time.sleep(backoff * attempt)

        except smtplib.SMTPException as smtp_err:
            error_msg = (
                f"❌ [ERROR DE PROTOCOLO SMTP] (Intento {attempt}/{max_retries}):\n"
                f"   Detalle: {smtp_err}"
            )
            print(f"\n{error_msg}\n", flush=True)
            logger.error(error_msg)
            last_err = smtp_err
            if attempt < max_retries:
                time.sleep(backoff * attempt)

        except Exception as exc:
            error_msg = (
                f"❌ [ERROR INESPERADO SMTP] (Intento {attempt}/{max_retries}):\n"
                f"   Detalle: {exc}"
            )
            print(f"\n{error_msg}\n", flush=True)
            logger.error(error_msg)
            last_err = exc
            if attempt < max_retries:
                time.sleep(backoff * attempt)

    # 4. Todos los reintentos fallaron
    err_msg = f"Fallo al enviar correo por SMTP ({smtp_host}:{smtp_port}): {last_err}"

    # Respaldo automático en modo consola
    if dev_mode != "false":
        backup_reason = (
            f"Conexión o red SMTP externa no disponible ({last_err}). "
            "Modo Contingencia activado para garantizar la continuidad del flujo."
        )
        logger.info("[SMTP] %s", backup_reason)
        _log_console_email(recipient_email, to_name, subject, plain_body, backup_reason)
        return "ENVIADO_CONSOLA", backup_reason

    logger.error("[SMTP] %s", err_msg)
    return "ERROR_SMTP", err_msg


async def send_email_async(
    to_email: str,
    to_name: str,
    subject: str,
    plain_body: str,
    html_body: str,
) -> tuple[str, Optional[str]]:
    """Run blocking smtplib delivery off the asyncio event loop."""
    return await asyncio.to_thread(
        send_email_sync,
        to_email,
        to_name,
        subject,
        plain_body,
        html_body,
    )
