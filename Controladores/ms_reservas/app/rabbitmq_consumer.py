"""
app/rabbitmq_consumer.py — Saga event consumer for ms_reservas.

Subscribes to the following routing keys on exchange "canchas_events":
  - pago.aprobado            → handle_pago_aprobado
  - pago.rechazado           → handle_pago_rechazado
  - pago.presencial.validado → handle_pago_presencial_validado

Saga state transitions:
  PENDIENTE_PAGO --[pago.aprobado]--> CONFIRMADA
  PENDIENTE_PAGO --[pago.rechazado]--> CANCELADA  (triggers slot-free outbox event)
  CONFIRMADA_PRESENCIAL is set directly on creation; pago.presencial.validado just
  emits a "ReservaConfirmada" outbox event for downstream consumers.
"""
import asyncio
import json
import logging
import uuid
from typing import Any

import aio_pika
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import EstadoReserva, Reserva
from app.outbox import save_outbox_event

logger = logging.getLogger(__name__)

EXCHANGE_NAME = "canchas_events"
QUEUE_NAME = "reservas_saga_queue"

BINDING_KEYS = [
    "pago.aprobado",
    "pago.rechazado",
    "pago.presencial.validado",
    "pago.#",
    "pagos.#",
]


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------


async def handle_pago_aprobado(event: dict[str, Any]) -> None:
    """
    Transition Reserva from PENDIENTE_PAGO → CONFIRMADA.
    Saves a 'ReservaConfirmada' outbox event so downstream services
    (e.g., notifications) can react.
    """
    data = event.get("data", {})
    reserva_id_raw = data.get("reserva_id")
    if not reserva_id_raw:
        logger.warning("pago.aprobado event missing reserva_id: %s", event)
        return

    try:
        reserva_id = uuid.UUID(str(reserva_id_raw))
    except ValueError:
        logger.error("pago.aprobado: invalid reserva_id '%s'", reserva_id_raw)
        return

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Reserva)
                .where(Reserva.id == reserva_id)
                .with_for_update()
            )
            reserva: Reserva | None = result.scalar_one_or_none()

            if reserva is None:
                logger.error(
                    "pago.aprobado: Reserva %s not found.", reserva_id
                )
                return

            if reserva.estado not in (
                EstadoReserva.PENDIENTE_PAGO,
                EstadoReserva.CONFIRMADA,  # idempotency guard
            ):
                logger.warning(
                    "pago.aprobado: Reserva %s in unexpected state %s — skipping.",
                    reserva_id,
                    reserva.estado,
                )
                return

            reserva.estado = EstadoReserva.CONFIRMADA

            print(
                f"\n🔄 [MS_RESERVAS SAGA CONSUMER] Evento PagoAprobado recibido para Reserva {reserva.codigo_uid} ({reserva_id}).\n"
                f"✅ [MS_RESERVAS SAGA CONSUMER] Transición de estado: CONFIRMADA.\n"
                f"📝 [MS_RESERVAS SAGA CONSUMER] Registrando evento 'ReservaConfirmada' en Transactional Outbox...",
                flush=True,
            )

            await save_outbox_event(
                session=session,
                event_type="ReservaConfirmada",
                aggregate_id=str(reserva.id),
                data={
                    "reserva_id": str(reserva.id),
                    "codigo_uid": reserva.codigo_uid,
                    "cancha_id": str(reserva.cancha_id),
                    "complejo_id": str(reserva.complejo_id),
                    "usuario_id": str(reserva.usuario_id) if reserva.usuario_id else None,
                    "fecha": str(reserva.fecha),
                    "hora_inicio": str(reserva.hora_inicio),
                    "hora_fin": str(reserva.hora_fin),
                    "monto": str(reserva.monto),
                    "precio_total": str(reserva.monto),
                    "email_usuario": data.get("email_usuario"),
                    "nombre_usuario": data.get("nombre_usuario"),
                    "nombre_complejo": data.get("nombre_complejo"),
                    "nombre_cancha": data.get("nombre_cancha"),
                    "metodo_pago": data.get("metodo_pago") or data.get("metodo"),
                    "referencia_wompi": data.get("referencia_externa") or data.get("pago_id"),
                },
            )

            await session.commit()
            print(
                f"🚀 [MS_RESERVAS SAGA CONSUMER] Reserva {reserva.codigo_uid} CONFIRMADA en base de datos. "
                f"Evento 'ReservaConfirmada' listo para publicación Outbox.\n",
                flush=True,
            )
            logger.info("Reserva %s → CONFIRMADA (pago aprobado).", reserva_id)

        except Exception as err:
            await session.rollback()
            logger.exception("handle_pago_aprobado error for %s: %s", reserva_id, err)
            raise


async def handle_pago_presencial_validado(event: dict[str, Any]) -> None:
    """
    Confirm a presencial reservation after cash/terminal payment validated by admin.
    Saves 'ReservaConfirmada' outbox event.
    """
    data = event.get("data", {})
    reserva_id_raw = data.get("reserva_id")
    if not reserva_id_raw:
        logger.warning(
            "pago.presencial.validado event missing reserva_id: %s", event
        )
        return

    try:
        reserva_id = uuid.UUID(str(reserva_id_raw))
    except ValueError:
        logger.error(
            "pago.presencial.validado: invalid reserva_id '%s'", reserva_id_raw
        )
        return

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Reserva)
                .where(Reserva.id == reserva_id)
                .with_for_update()
            )
            reserva: Reserva | None = result.scalar_one_or_none()

            if reserva is None:
                logger.error(
                    "pago.presencial.validado: Reserva %s not found.", reserva_id
                )
                return

            if reserva.estado == EstadoReserva.CONFIRMADA:
                logger.info(
                    "pago.presencial.validado: Reserva %s already CONFIRMADA (idempotent).",
                    reserva_id,
                )
                return

            # Presencial reservations are already CONFIRMADA_PRESENCIAL; we move to CONFIRMADA
            reserva.estado = EstadoReserva.CONFIRMADA

            await save_outbox_event(
                session=session,
                event_type="ReservaConfirmada",
                aggregate_id=str(reserva.id),
                data={
                    "reserva_id": str(reserva.id),
                    "codigo_uid": reserva.codigo_uid,
                    "cancha_id": str(reserva.cancha_id),
                    "complejo_id": str(reserva.complejo_id),
                    "usuario_id": str(reserva.usuario_id) if reserva.usuario_id else None,
                    "nombre_cliente": reserva.nombre_cliente,
                    "fecha": str(reserva.fecha),
                    "hora_inicio": str(reserva.hora_inicio),
                    "hora_fin": str(reserva.hora_fin),
                    "monto": str(reserva.monto),
                    "tipo": "PRESENCIAL",
                },
            )

            await session.commit()
            logger.info(
                "Reserva %s → CONFIRMADA (pago presencial validado).", reserva_id
            )

        except Exception as err:
            await session.rollback()
            logger.exception(
                "handle_pago_presencial_validado error for %s: %s", reserva_id, err
            )
            raise


async def handle_pago_rechazado(event: dict[str, Any]) -> None:
    """
    SAGA ROLLBACK: Payment rejected → cancel the reservation and emit
    'ReservaCancelada' so ms_canchas can free the blocked slot.
    """
    data = event.get("data", {})
    reserva_id_raw = data.get("reserva_id")
    if not reserva_id_raw:
        logger.warning("pago.rechazado event missing reserva_id: %s", event)
        return

    try:
        reserva_id = uuid.UUID(str(reserva_id_raw))
    except ValueError:
        logger.error("pago.rechazado: invalid reserva_id '%s'", reserva_id_raw)
        return

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Reserva)
                .where(Reserva.id == reserva_id)
                .with_for_update()
            )
            reserva: Reserva | None = result.scalar_one_or_none()

            if reserva is None:
                logger.error(
                    "pago.rechazado: Reserva %s not found.", reserva_id
                )
                return

            if reserva.estado in (
                EstadoReserva.CANCELADA,
                EstadoReserva.CANCELADA_ADMIN,
            ):
                logger.info(
                    "pago.rechazado: Reserva %s already cancelled (idempotent).",
                    reserva_id,
                )
                return

            motivo = data.get("motivo", "Pago rechazado por la pasarela de pagos")
            reserva.estado = EstadoReserva.CANCELADA
            reserva.motivo_cancelacion = motivo

            # This event is consumed by ms_canchas to free the slot (Saga rollback)
            await save_outbox_event(
                session=session,
                event_type="ReservaCancelada",
                aggregate_id=str(reserva.id),
                data={
                    "reserva_id": str(reserva.id),
                    "codigo_uid": reserva.codigo_uid,
                    "cancha_id": str(reserva.cancha_id),
                    "complejo_id": str(reserva.complejo_id),
                    "usuario_id": str(reserva.usuario_id) if reserva.usuario_id else None,
                    "fecha": str(reserva.fecha),
                    "hora_inicio": str(reserva.hora_inicio),
                    "hora_fin": str(reserva.hora_fin),
                    "motivo": motivo,
                    "origen": "PAGO_RECHAZADO",
                },
            )

            await session.commit()
            logger.info(
                "Reserva %s → CANCELADA (pago rechazado — saga rollback).", reserva_id
            )

        except Exception as err:
            await session.rollback()
            logger.exception(
                "handle_pago_rechazado error for %s: %s", reserva_id, err
            )
            raise


# ---------------------------------------------------------------------------
# Consumer bootstrap
# ---------------------------------------------------------------------------

HANDLER_MAP = {
    "pago.aprobado": handle_pago_aprobado,
    "pago.rechazado": handle_pago_rechazado,
    "pago.presencial.validado": handle_pago_presencial_validado,
}


async def _process_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    """Dispatch an incoming RabbitMQ message to the appropriate handler."""
    async with message.process(requeue=False):
        try:
            body = json.loads(message.body.decode())
            routing_key = message.routing_key or ""
            event_type = body.get("eventType") or ""

            print(
                f"\n📥 [MS_RESERVAS SAGA CONSUMER] Mensaje recibido de RabbitMQ: "
                f"routing_key='{routing_key}', eventType='{event_type}'",
                flush=True,
            )

            handler = (
                HANDLER_MAP.get(routing_key)
                or HANDLER_MAP.get(event_type)
                or (handle_pago_aprobado if event_type in ("PagoAprobado", "pago.aprobado") else None)
                or (handle_pago_rechazado if event_type in ("PagoRechazado", "pago.rechazado") else None)
                or (handle_pago_presencial_validado if event_type in ("PagoPresencialValidado", "pago.presencial.validado") else None)
            )

            if handler is None:
                logger.warning("No handler for routing_key '%s' / eventType '%s'", routing_key, event_type)
                print(f"⚠️ [MS_RESERVAS SAGA CONSUMER] Sin handler para {routing_key} / {event_type}", flush=True)
                return

            await handler(body)
        except json.JSONDecodeError as err:
            logger.error("Failed to parse message body: %s", err)
        except Exception as err:
            logger.exception("Error processing message in ms_reservas saga: %s", err)


async def run_rabbitmq_consumer() -> None:
    """
    Connect to RabbitMQ, declare exchange/queue/bindings, and start consuming.
    Retries indefinitely on connection failures.
    Designed to be launched as an asyncio background task on startup.
    """
    logger.info("RabbitMQ consumer starting...")
    while True:
        try:
            connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=10)

                exchange = await channel.declare_exchange(
                    EXCHANGE_NAME,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True,
                )

                queue = await channel.declare_queue(
                    QUEUE_NAME,
                    durable=True,
                    arguments={"x-message-ttl": 86400000},  # 24 hours TTL
                )

                for key in BINDING_KEYS:
                    await queue.bind(exchange, routing_key=key)
                    logger.info("Queue '%s' bound to '%s'", QUEUE_NAME, key)

                logger.info(
                    "RabbitMQ consumer ready. Listening on queue '%s'.", QUEUE_NAME
                )
                await queue.consume(_process_message)

                # Keep alive until connection drops
                await asyncio.Future()

        except asyncio.CancelledError:
            logger.info("RabbitMQ consumer cancelled.")
            break
        except Exception as err:
            logger.error(
                "RabbitMQ consumer error: %s — retrying in 5s.", err
            )
            await asyncio.sleep(5)


# Alias for backward compatibility with imports expecting run_consumer
run_consumer = run_rabbitmq_consumer

