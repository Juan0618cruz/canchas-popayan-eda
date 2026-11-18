"""
app/rabbitmq.py - RabbitMQ integration for ms_canchas using aio-pika.

Publisher:
  - publish_event(event_type, aggregate_id, data) → sends to topic exchange
    "canchas_events" with the standard envelope.

Consumer (queue "canchas_queue"):
  Binds routing keys:
    * reserva.solicitada   → handle_reserva_solicitada
    * reserva.cancelada    → handle_reserva_cancelada
    * reserva.reprogramada → handle_reserva_reprogramada
    * pago.aprobado        → handle_pago_aprobado
"""
import asyncio
import json
import logging
import uuid
from datetime import date, datetime, time

import aio_pika
from aio_pika import ExchangeType, Message
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import BloqueHorario, Cancha, EstadoBloque
from app.seed import _generate_slots

logger = logging.getLogger(__name__)

EXCHANGE_NAME = settings.EXCHANGE_NAME
QUEUE_NAME = "canchas_queue"

# ---------------------------------------------------------------------------
# Module-level shared connection / channel (lazy-initialised)
# ---------------------------------------------------------------------------
_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None


async def _get_connection() -> aio_pika.abc.AbstractRobustConnection:
    global _connection
    if _connection is None or _connection.is_closed:
        _connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    return _connection


async def get_channel() -> aio_pika.abc.AbstractChannel:
    """Return (or create) a shared channel for publishing."""
    global _channel
    conn = await _get_connection()
    if _channel is None or _channel.is_closed:
        _channel = await conn.channel()
        await _channel.declare_exchange(
            EXCHANGE_NAME,
            ExchangeType.TOPIC,
            durable=True,
        )
    return _channel


# ---------------------------------------------------------------------------
# Publisher
# ---------------------------------------------------------------------------
async def publish_event(
    event_type: str,
    aggregate_id: str,
    data: dict,
    routing_key: str | None = None,
) -> None:
    """
    Publish an event to the topic exchange using the standard envelope.

    Args:
        event_type:   e.g. "CanchaActualizada"
        aggregate_id: UUID string of the main entity
        data:         Arbitrary payload dict
        routing_key:  Defaults to a snake_case version derived from event_type
                      e.g. "cancha.actualizada"
    """
    if routing_key is None:
        # Convert "CanchaActualizada" → "cancha.actualizada"
        import re
        words = re.findall(r"[A-Z][a-z]*", event_type)
        routing_key = ".".join(w.lower() for w in words) if words else event_type.lower()

    envelope = {
        "eventId": str(uuid.uuid4()),
        "eventType": event_type,
        "aggregateId": aggregate_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0",
        "data": data,
    }

    try:
        channel = await get_channel()
        exchange = await channel.declare_exchange(
            EXCHANGE_NAME,
            ExchangeType.TOPIC,
            durable=True,
        )
        await exchange.publish(
            Message(
                body=json.dumps(envelope).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
        )
        logger.info(
            "[rabbitmq] Published %s → routing_key=%s aggregateId=%s",
            event_type,
            routing_key,
            aggregate_id,
        )
    except Exception as exc:
        logger.error("[rabbitmq] Failed to publish %s: %s", event_type, exc)
        raise


# ---------------------------------------------------------------------------
# Consumer handlers
# ---------------------------------------------------------------------------
async def _ensure_day_blocks(
    session: AsyncSession,
    cancha_id: uuid.UUID,
    fecha: date,
) -> list[BloqueHorario]:
    """Ensure BloqueHorario rows exist for (cancha_id, fecha), generating them if missing."""
    existing = (
        await session.execute(
            select(BloqueHorario).where(
                and_(BloqueHorario.cancha_id == cancha_id, BloqueHorario.fecha == fecha)
            )
        )
    ).scalars().all()
    if existing:
        return list(existing)

    cancha = (
        await session.execute(select(Cancha).where(Cancha.id == cancha_id))
    ).scalar_one_or_none()
    if cancha is None:
        return []

    generated = _generate_slots(
        cancha_id=cancha.id,
        fecha=fecha,
        hora_apertura=cancha.hora_apertura,
        hora_cierre=cancha.hora_cierre,
    )
    if generated:
        session.add_all(generated)
        await session.flush()
    return generated


async def sync_rescheduled_slot(
    session: AsyncSession,
    reserva_id: uuid.UUID,
    cancha_id_ant: uuid.UUID,
    fecha_ant: date,
    hora_ant: time,
    cancha_id_new: uuid.UUID,
    fecha_new: date,
    hora_new: time,
    estado_bloque: EstadoBloque = EstadoBloque.OCUPADO,
) -> None:
    """
    Atomically free the previous slot (and any leftover blocks for reserva_id)
    and occupy the newly scheduled slot.
    """
    # 1. Free old block + any stale blocks previously linked to this reserva_id
    old_blocks = (
        await session.execute(
            select(BloqueHorario).where(
                or_(
                    BloqueHorario.reserva_id == reserva_id,
                    and_(
                        BloqueHorario.cancha_id == cancha_id_ant,
                        BloqueHorario.fecha == fecha_ant,
                        BloqueHorario.hora_inicio == hora_ant,
                    ),
                )
            )
        )
    ).scalars().all()

    freed_count = 0
    for bloque_old in old_blocks:
        if (
            bloque_old.cancha_id == cancha_id_new
            and bloque_old.fecha == fecha_new
            and bloque_old.hora_inicio == hora_new
        ):
            continue
        bloque_old.estado = EstadoBloque.LIBRE
        bloque_old.reserva_id = None
        bloque_old.updated_at = datetime.utcnow()
        freed_count += 1

    # 2. Ensure target date has day blocks and occupy the new block
    await _ensure_day_blocks(session, cancha_id_new, fecha_new)
    bloque_new = (
        await session.execute(
            select(BloqueHorario).where(
                and_(
                    BloqueHorario.cancha_id == cancha_id_new,
                    BloqueHorario.fecha == fecha_new,
                    BloqueHorario.hora_inicio == hora_new,
                )
            )
        )
    ).scalar_one_or_none()

    if bloque_new is not None:
        bloque_new.estado = estado_bloque
        bloque_new.reserva_id = reserva_id
        bloque_new.updated_at = datetime.utcnow()
        logger.info(
            "[sync_rescheduled_slot] reserva=%s freed=%d old=(%s %s %s) -> occupied=(%s %s %s state=%s)",
            reserva_id,
            freed_count,
            cancha_id_ant,
            fecha_ant,
            hora_ant,
            cancha_id_new,
            fecha_new,
            hora_new,
            estado_bloque.value,
        )
    else:
        logger.warning(
            "[sync_rescheduled_slot] new bloque not found cancha=%s fecha=%s hora=%s",
            cancha_id_new,
            fecha_new,
            hora_new,
        )


def _parse_time_hhmm(raw: str) -> time:
    parts = str(raw).split(":")
    return time(int(parts[0]), int(parts[1]))


async def handle_reserva_solicitada(payload: dict) -> None:
    """
    reserva.solicitada:
      Sets BloqueHorario estado=BLOQUEADO_TEMPORAL, reserva_id=reserva_id.

    Expected data keys: cancha_id, fecha (YYYY-MM-DD), hora_inicio (HH:MM),
                        reserva_id
    """
    data = payload.get("data", {})
    cancha_id_raw = data.get("cancha_id")
    fecha_raw = data.get("fecha")
    hora_inicio_raw = data.get("hora_inicio")
    reserva_id_raw = payload.get("aggregateId") or data.get("reserva_id")

    if not all([cancha_id_raw, fecha_raw, hora_inicio_raw, reserva_id_raw]):
        logger.warning("[consumer] reserva.solicitada: missing fields in payload %s", data)
        return

    try:
        cancha_id = uuid.UUID(str(cancha_id_raw))
        fecha = date.fromisoformat(str(fecha_raw))
        hora_inicio = _parse_time_hhmm(str(hora_inicio_raw))
        reserva_id = uuid.UUID(str(reserva_id_raw))
    except (ValueError, IndexError) as exc:
        logger.error("[consumer] reserva.solicitada: parse error %s", exc)
        return

    async with AsyncSessionLocal() as session:
        await _ensure_day_blocks(session, cancha_id, fecha)
        result = await session.execute(
            select(BloqueHorario).where(
                and_(
                    BloqueHorario.cancha_id == cancha_id,
                    BloqueHorario.fecha == fecha,
                    BloqueHorario.hora_inicio == hora_inicio,
                )
            )
        )
        bloque = result.scalar_one_or_none()

        if bloque is None:
            logger.warning(
                "[consumer] reserva.solicitada: BloqueHorario not found "
                "cancha=%s fecha=%s hora=%s",
                cancha_id, fecha, hora_inicio,
            )
            return

        if bloque.estado != EstadoBloque.LIBRE:
            logger.warning(
                "[consumer] reserva.solicitada: bloque not LIBRE (estado=%s) "
                "cancha=%s fecha=%s hora=%s",
                bloque.estado, cancha_id, fecha, hora_inicio,
            )
            return

        bloque.estado = EstadoBloque.BLOQUEADO_TEMPORAL
        bloque.reserva_id = reserva_id
        bloque.updated_at = datetime.utcnow()
        await session.commit()
        logger.info(
            "[consumer] reserva.solicitada: bloque=%s → BLOQUEADO_TEMPORAL reserva=%s",
            bloque.id, reserva_id,
        )


async def handle_reserva_cancelada(payload: dict) -> None:
    """
    reserva.cancelada:
      Sets BloqueHorario estado=LIBRE, reserva_id=None.

    Expected data keys: cancha_id, fecha, hora_inicio  (or looks up by reserva_id)
    """
    data = payload.get("data", {})
    reserva_id_raw = payload.get("aggregateId") or data.get("reserva_id")

    if not reserva_id_raw:
        logger.warning("[consumer] reserva.cancelada: missing reserva_id")
        return

    try:
        reserva_id = uuid.UUID(str(reserva_id_raw))
    except ValueError as exc:
        logger.error("[consumer] reserva.cancelada: parse error %s", exc)
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(BloqueHorario).where(BloqueHorario.reserva_id == reserva_id)
        )
        bloque = result.scalar_one_or_none()

        if bloque is None:
            logger.warning(
                "[consumer] reserva.cancelada: BloqueHorario not found for reserva=%s",
                reserva_id,
            )
            return

        bloque.estado = EstadoBloque.LIBRE
        bloque.reserva_id = None
        bloque.updated_at = datetime.utcnow()
        await session.commit()
        logger.info(
            "[consumer] reserva.cancelada: bloque=%s → LIBRE reserva=%s",
            bloque.id, reserva_id,
        )


async def handle_reserva_reprogramada(payload: dict) -> None:
    """
    reserva.reprogramada:
      Frees old block (LIBRE, reserva_id=None).
      Occupies new block (OCUPADO or BLOQUEADO_TEMPORAL, reserva_id=reserva_id).

    Accepts both legacy (*_anterior / *_nuevo) and ms_reservas (cancha_id / nueva_*) keys.
    """
    data = payload.get("data", {})
    reserva_id_raw = payload.get("aggregateId") or data.get("reserva_id")

    try:
        reserva_id = uuid.UUID(str(reserva_id_raw))
        cancha_id_ant = uuid.UUID(str(data.get("cancha_id_anterior") or data["cancha_id"]))
        fecha_ant = date.fromisoformat(str(data["fecha_anterior"]))
        hora_ant = _parse_time_hhmm(str(data["hora_inicio_anterior"]))

        cancha_id_new = uuid.UUID(str(data.get("cancha_id_nuevo") or data["cancha_id"]))
        fecha_new = date.fromisoformat(str(data.get("fecha_nuevo") or data["nueva_fecha"]))
        hora_new = _parse_time_hhmm(str(data.get("hora_inicio_nuevo") or data["nueva_hora_inicio"]))

        raw_estado_reserva = str(data.get("estado") or "").upper()
        estado_bloque = (
            EstadoBloque.BLOQUEADO_TEMPORAL
            if raw_estado_reserva == "PENDIENTE_PAGO"
            else EstadoBloque.OCUPADO
        )
    except (KeyError, ValueError, IndexError) as exc:
        logger.error("[consumer] reserva.reprogramada: parse error %s (data=%s)", exc, data)
        return

    async with AsyncSessionLocal() as session:
        await sync_rescheduled_slot(
            session=session,
            reserva_id=reserva_id,
            cancha_id_ant=cancha_id_ant,
            fecha_ant=fecha_ant,
            hora_ant=hora_ant,
            cancha_id_new=cancha_id_new,
            fecha_new=fecha_new,
            hora_new=hora_new,
            estado_bloque=estado_bloque,
        )
        await session.commit()


async def handle_slot_liberado(payload: dict) -> None:
    """
    slot.liberado:
      Idempotently frees the indicated time slot (estado=LIBRE, reserva_id=None)
      when it belongs to the same reservation or is not held by another booking.
    """
    data = payload.get("data", {})
    try:
        cancha_id = uuid.UUID(str(data["cancha_id"]))
        fecha = date.fromisoformat(str(data["fecha"]))
        hora_inicio = _parse_time_hhmm(str(data["hora_inicio"]))
        reserva_id_raw = data.get("reserva_id") or payload.get("aggregateId")
        reserva_id = uuid.UUID(str(reserva_id_raw)) if reserva_id_raw else None
    except (KeyError, ValueError, IndexError) as exc:
        logger.error("[consumer] slot.liberado: parse error %s", exc)
        return

    async with AsyncSessionLocal() as session:
        bloque = (
            await session.execute(
                select(BloqueHorario).where(
                    and_(
                        BloqueHorario.cancha_id == cancha_id,
                        BloqueHorario.fecha == fecha,
                        BloqueHorario.hora_inicio == hora_inicio,
                    )
                )
            )
        ).scalar_one_or_none()
        if bloque is None:
            return
        if reserva_id and bloque.reserva_id and bloque.reserva_id != reserva_id:
            return
        bloque.estado = EstadoBloque.LIBRE
        bloque.reserva_id = None
        bloque.updated_at = datetime.utcnow()
        await session.commit()


async def handle_slot_ocupado(payload: dict) -> None:
    """
    slot.ocupado:
      Idempotently ensures the target time slot is occupied for reserva_id.
    """
    data = payload.get("data", {})
    try:
        cancha_id = uuid.UUID(str(data["cancha_id"]))
        fecha = date.fromisoformat(str(data["fecha"]))
        hora_inicio = _parse_time_hhmm(str(data["hora_inicio"]))
        reserva_id_raw = data.get("reserva_id") or payload.get("aggregateId")
        reserva_id = uuid.UUID(str(reserva_id_raw)) if reserva_id_raw else None
        raw_estado = str(data.get("estado") or "OCUPADO").upper()
        estado_bloque = (
            EstadoBloque.BLOQUEADO_TEMPORAL
            if raw_estado == "BLOQUEADO_TEMPORAL"
            else EstadoBloque.OCUPADO
        )
    except (KeyError, ValueError, IndexError) as exc:
        logger.error("[consumer] slot.ocupado: parse error %s", exc)
        return

    async with AsyncSessionLocal() as session:
        await _ensure_day_blocks(session, cancha_id, fecha)
        bloque = (
            await session.execute(
                select(BloqueHorario).where(
                    and_(
                        BloqueHorario.cancha_id == cancha_id,
                        BloqueHorario.fecha == fecha,
                        BloqueHorario.hora_inicio == hora_inicio,
                    )
                )
            )
        ).scalar_one_or_none()
        if bloque is None:
            return
        if bloque.estado == EstadoBloque.LIBRE or (reserva_id and bloque.reserva_id == reserva_id):
            bloque.estado = estado_bloque
            bloque.reserva_id = reserva_id
            bloque.updated_at = datetime.utcnow()
            await session.commit()


async def handle_pago_aprobado(payload: dict) -> None:
    """
    pago.aprobado:
      Sets BloqueHorario estado=OCUPADO (payment confirmed).

    Expected data keys: reserva_id  (or aggregateId = reserva_id)
    """
    data = payload.get("data", {})
    reserva_id_raw = data.get("reserva_id") or payload.get("aggregateId")

    if not reserva_id_raw:
        logger.warning("[consumer] pago.aprobado: missing reserva_id")
        return

    try:
        reserva_id = uuid.UUID(str(reserva_id_raw))
    except ValueError as exc:
        logger.error("[consumer] pago.aprobado: parse error %s", exc)
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(BloqueHorario).where(BloqueHorario.reserva_id == reserva_id)
        )
        bloque = result.scalar_one_or_none()

        if bloque is None:
            logger.warning(
                "[consumer] pago.aprobado: BloqueHorario not found for reserva=%s",
                reserva_id,
            )
            return

        bloque.estado = EstadoBloque.OCUPADO
        bloque.updated_at = datetime.utcnow()
        await session.commit()
        logger.info(
            "[consumer] pago.aprobado: bloque=%s → OCUPADO reserva=%s",
            bloque.id, reserva_id,
        )


# ---------------------------------------------------------------------------
# Routing table
# ---------------------------------------------------------------------------
HANDLERS: dict[str, any] = {
    "reserva.solicitada": handle_reserva_solicitada,
    "reserva.cancelada": handle_reserva_cancelada,
    "reserva.reprogramada": handle_reserva_reprogramada,
    "slot.liberado": handle_slot_liberado,
    "slot.ocupado": handle_slot_ocupado,
    "pago.aprobado": handle_pago_aprobado,
}


# ---------------------------------------------------------------------------
# Consumer
# ---------------------------------------------------------------------------
async def _process_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    """Dispatch an incoming RabbitMQ message to the appropriate handler."""
    async with message.process(ignore_processed=True):
        try:
            payload = json.loads(message.body.decode())
            routing_key = message.routing_key or ""
            handler = HANDLERS.get(routing_key)

            if handler is None:
                logger.warning(
                    "[consumer] No handler for routing_key='%s'", routing_key
                )
                return

            logger.info(
                "[consumer] Processing routing_key='%s' eventId=%s",
                routing_key,
                payload.get("eventId", "?"),
            )
            await handler(payload)
        except json.JSONDecodeError as exc:
            logger.error("[consumer] JSON decode error: %s", exc)
        except Exception as exc:
            logger.exception("[consumer] Unhandled error processing message: %s", exc)
            # We ack anyway to avoid infinite requeue loops — dead-letter queue
            # should be configured at the infrastructure level.


async def start_consumer() -> None:
    """
    Connect to RabbitMQ, declare exchange + queue, bind routing keys and
    start consuming messages.  Runs indefinitely as a background coroutine.
    """
    retry_delay = 5  # seconds

    while True:
        try:
            logger.info("[consumer] Connecting to RabbitMQ…")
            connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)

            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=10)

                exchange = await channel.declare_exchange(
                    EXCHANGE_NAME,
                    ExchangeType.TOPIC,
                    durable=True,
                )

                queue = await channel.declare_queue(
                    QUEUE_NAME,
                    durable=True,
                    arguments={"x-queue-type": "classic"},
                )

                # Bind all routing keys
                for routing_key in HANDLERS:
                    await queue.bind(exchange, routing_key=routing_key)
                    logger.info(
                        "[consumer] Bound queue '%s' ← routing_key='%s'",
                        QUEUE_NAME,
                        routing_key,
                    )

                logger.info(
                    "[consumer] ✅  Started consuming from queue '%s'", QUEUE_NAME
                )
                await queue.consume(_process_message)

                # Keep alive until connection drops
                await asyncio.Future()

        except asyncio.CancelledError:
            logger.info("[consumer] Consumer task cancelled — shutting down.")
            break
        except Exception as exc:
            logger.error(
                "[consumer] Connection error: %s — retrying in %ds…",
                exc,
                retry_delay,
            )
            await asyncio.sleep(retry_delay)
