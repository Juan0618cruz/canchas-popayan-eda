"""
RabbitMQ consumer for ms_notificaciones.

Subscribes to the ``canchas_events`` topic exchange, enriches reservation/user/court
context when needed, sends real HTML emails over SMTP (smtplib + email.mime),
and persists every notification record + delivery status in SQLite.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable

import aio_pika
import httpx
from aio_pika.abc import AbstractIncomingMessage

from app.config import settings
from app.email_store import EmailLog, save_email
from app.email_templates import (
    template_admin_registrado,
    template_clave_restablecimiento,
    template_pago_aprobado,
    template_pago_rechazado,
    template_reserva_cancelada,
    template_reserva_reprogramada,
    template_reserva_solicitada,
    template_usuario_registrado,
)
from app.smtp_service import send_email_async

logger = logging.getLogger("ms_notificaciones.consumer")

EXCHANGE_NAME = "canchas_events"
QUEUE_NAME = "notificaciones_queue"

ROUTING_KEYS = [
    "reserva.creada",
    "reserva.solicitada",
    "reserva.confirmada",
    "pago.aprobado",
    "pago.rechazado",
    "reserva.cancelada",
    "reserva.reprogramada",
    "clave.restablecimiento.solicitada",
    "#",
]


async def _enrich_notification_data(data: dict[str, Any]) -> dict[str, Any]:
    """
    Ensure user email, reservation code/schedule, court name, and complex name are
    populated even if the originating RabbitMQ event only emitted UUIDs.
    """
    enriched = dict(data)
    reserva_id = enriched.get("reserva_id")
    usuario_id = enriched.get("usuario_id")
    complejo_id = enriched.get("complejo_id")
    cancha_id = enriched.get("cancha_id")

    async with httpx.AsyncClient(timeout=2.5) as client:
        # 1. Enrich missing reservation fields
        if reserva_id and (
            not enriched.get("codigo_uid")
            or not enriched.get("fecha")
            or not usuario_id
            or not cancha_id
            or not complejo_id
        ):
            try:
                r = await client.get(f"{settings.MS_RESERVAS_URL}/reservas/internal/{reserva_id}")
                if r.status_code == 200:
                    rdata = r.json()
                    enriched.setdefault("codigo_uid", rdata.get("codigo_uid"))
                    enriched.setdefault("fecha", rdata.get("fecha"))
                    enriched.setdefault("hora_inicio", rdata.get("hora_inicio"))
                    enriched.setdefault("hora_fin", rdata.get("hora_fin"))
                    enriched.setdefault("precio_total", rdata.get("monto"))
                    enriched.setdefault("monto", rdata.get("monto"))
                    enriched.setdefault("estado", rdata.get("estado"))
                    usuario_id = usuario_id or rdata.get("usuario_id")
                    complejo_id = complejo_id or rdata.get("complejo_id")
                    cancha_id = cancha_id or rdata.get("cancha_id")
            except Exception as exc:
                logger.debug("Enrich reservation skipped (%s): %s", reserva_id, exc)

        # 2. Enrich real user email & name from ms_usuarios
        if usuario_id and (
            not enriched.get("email_usuario")
            or enriched.get("email_usuario") == "usuario@test.com"
        ):
            try:
                r = await client.get(f"{settings.MS_USUARIOS_URL}/usuarios/{usuario_id}")
                if r.status_code == 200:
                    udata = r.json()
                    if udata.get("email"):
                        enriched["email_usuario"] = udata["email"]
                    if udata.get("nombre"):
                        enriched["nombre_usuario"] = udata["nombre"]
            except Exception as exc:
                logger.debug("Enrich user skipped (%s): %s", usuario_id, exc)

        # 3. Enrich complex and court name from ms_canchas
        if complejo_id and (
            not enriched.get("nombre_complejo") or not enriched.get("nombre_cancha")
        ):
            try:
                r = await client.get(
                    f"{settings.MS_CANCHAS_URL}/canchas/complejos/{complejo_id}"
                )
                if r.status_code == 200:
                    cdata = r.json()
                    enriched.setdefault("nombre_complejo", cdata.get("nombre"))
                    for cancha in cdata.get("canchas") or []:
                        if str(cancha.get("id")) == str(cancha_id):
                            enriched.setdefault("nombre_cancha", cancha.get("nombre"))
                            break
            except Exception as exc:
                logger.debug("Enrich complejo skipped (%s): %s", complejo_id, exc)

    return enriched


async def _dispatch_and_deliver(
    event_type: str,
    aggregate_id: str,
    data: dict[str, Any],
) -> None:
    """Resolve template, enrich context, send real SMTP email, and persist in DB."""
    template_map: dict[str, Callable[[dict], tuple[str, str, str]]] = {
        "UsuarioRegistrado": template_usuario_registrado,
        "AdminEstablecimientoRegistrado": template_admin_registrado,
        "ReservaCreada": template_reserva_solicitada,
        "ReservaSolicitada": template_reserva_solicitada,
        "ReservaConfirmada": template_pago_aprobado,
        "ReservaPresencialConfirmada": template_pago_aprobado,
        "PagoAprobado": template_pago_aprobado,
        "PagoRechazado": template_pago_rechazado,
        "ReservaCancelada": template_reserva_cancelada,
        "ReservaReprogramada": template_reserva_reprogramada,
        "ClaveRestablecimientoSolicitada": template_clave_restablecimiento,
        "RecuperarContrasenaSolicitada": template_clave_restablecimiento,
        "TokenGenerado": template_clave_restablecimiento,
    }

    builder = template_map.get(event_type)
    if builder is None:
        logger.info(
            "[NOTIFICACION] Evento sin handler de email: %s | %s",
            event_type,
            aggregate_id,
        )
        print(f"ℹ️ [MS_NOTIFICACIONES] Evento sin plantilla de email: {event_type} | {aggregate_id}", flush=True)
        return

    if event_type in (
        "UsuarioRegistrado",
        "AdminEstablecimientoRegistrado",
        "ClaveRestablecimientoSolicitada",
        "RecuperarContrasenaSolicitada",
        "TokenGenerado",
    ):
        enriched = dict(data)
        to_email = str(enriched.get("email") or "").strip()
        to_name = str(enriched.get("nombre") or "Usuario")
    else:
        enriched = await _enrich_notification_data(data)
        to_email = str(enriched.get("email_usuario") or enriched.get("email") or "").strip()
        to_name = str(enriched.get("nombre_usuario") or enriched.get("nombre") or "Deportista")

    subject, text_body, html_body = builder(enriched)

    print(
        f"📧 [MS_NOTIFICACIONES] Despachando correo para evento '{event_type}' hacia '{to_email}' (Asunto: {subject})...",
        flush=True,
    )

    delivery_status, error_detail = await send_email_async(
        to_email=to_email,
        to_name=to_name,
        subject=subject,
        plain_body=text_body,
        html_body=html_body,
    )

    print(
        f"🎉 [MS_NOTIFICACIONES] Notificación de '{event_type}' enviada a {to_email}. "
        f"Resultado: {delivery_status}\n",
        flush=True,
    )

    log = EmailLog(
        to_email=to_email or "sin-correo@canchas-popayan.local",
        to_name=to_name,
        subject=subject,
        body=text_body,
        event_type=event_type,
        aggregate_id=aggregate_id,
        status=delivery_status,
        error_detail=error_detail,
    )
    save_email(log)
    logger.info(
        "[NOTIFICACION] Evento=%s | Para=%s | Estado=%s",
        event_type,
        log.to_email,
        delivery_status,
    )


async def _on_message(message: AbstractIncomingMessage) -> None:
    """Process a single incoming RabbitMQ message safely."""
    async with message.process(requeue=False):
        try:
            raw = message.body.decode("utf-8")
            envelope: dict = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.error("[CONSUMER] Mensaje con formato inválido: %s", exc)
            return

        event_type: str = envelope.get("eventType", "Desconocido")
        aggregate_id: str = envelope.get("aggregateId", "N/A")
        timestamp: str = envelope.get(
            "timestamp", datetime.now(timezone.utc).isoformat()
        )
        data: dict = envelope.get("data", {})

        logger.info("[CONSUMER] %s | %s | %s", event_type, aggregate_id, timestamp)
        print(
            f"\n📬 [MS_NOTIFICACIONES CONSUMER] Mensaje recibido desde RabbitMQ: "
            f"eventType='{event_type}', aggregateId='{aggregate_id}'",
            flush=True,
        )

        try:
            await _dispatch_and_deliver(event_type, aggregate_id, data)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "[CONSUMER] Error procesando evento %s: %s", event_type, exc
            )


async def start_consumer() -> None:
    """
    Connect to RabbitMQ, declare exchange + queue, bind routing keys and
    begin consuming messages. Retries indefinitely on connection errors.
    """
    retry_delay = 5

    while True:
        try:
            logger.info("[CONSUMER] Conectando a RabbitMQ: %s", settings.RABBITMQ_URL)
            connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)

            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=10)

                exchange = await channel.declare_exchange(
                    EXCHANGE_NAME,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True,
                )
                queue = await channel.declare_queue(QUEUE_NAME, durable=True)

                for routing_key in ROUTING_KEYS:
                    await queue.bind(exchange, routing_key=routing_key)
                    logger.info(
                        "[CONSUMER] Cola '%s' vinculada a routing key '%s'",
                        QUEUE_NAME,
                        routing_key,
                    )

                logger.info(
                    "[CONSUMER] Esperando mensajes en la cola '%s' ...", QUEUE_NAME
                )
                await queue.consume(_on_message)
                await asyncio.Future()

        except aio_pika.exceptions.AMQPConnectionError as exc:
            logger.warning(
                "[CONSUMER] No se pudo conectar a RabbitMQ: %s. Reintentando en %ds ...",
                exc,
                retry_delay,
            )
            await asyncio.sleep(retry_delay)
        except asyncio.CancelledError:
            logger.info("[CONSUMER] Consumer cancelado. Cerrando.")
            break
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "[CONSUMER] Error inesperado: %s. Reintentando en %ds ...",
                exc,
                retry_delay,
            )
            await asyncio.sleep(retry_delay)
