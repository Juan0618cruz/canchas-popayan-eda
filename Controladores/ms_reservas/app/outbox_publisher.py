"""
app/outbox_publisher.py — Transactional Outbox background publisher.

Polls the outbox_events table every OUTBOX_POLL_INTERVAL seconds for unpublished
events, publishes each one to RabbitMQ topic exchange "canchas_events", then marks
the row as published=True.  Guarantees at-least-once delivery.
"""
import asyncio
import json
import logging
from typing import Optional

import aio_pika
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import OutboxEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Routing key mapping  (eventType -> routing_key)
# ---------------------------------------------------------------------------
ROUTING_KEY_MAP: dict[str, str] = {
    "ReservaSolicitada": "reserva.solicitada",
    "ReservaConfirmada": "reserva.confirmada",
    "ReservaCancelada": "reserva.cancelada",
    "ReservaReprogramada": "reserva.reprogramada",
    "ReservaPresencialConfirmada": "reserva.presencial.confirmada",
    "SlotLiberado": "slot.liberado",
    "SlotOcupado": "slot.ocupado",
    # Saga compensation re-publication
    "PagoAprobado": "pago.aprobado",
}

EXCHANGE_NAME = "canchas_events"

# Module-level RabbitMQ connection/channel (re-created on failure)
_connection: Optional[aio_pika.abc.AbstractRobustConnection] = None
_channel: Optional[aio_pika.abc.AbstractChannel] = None
_exchange: Optional[aio_pika.abc.AbstractExchange] = None


async def _get_exchange() -> aio_pika.abc.AbstractExchange:
    """Return (or lazily create) a RabbitMQ channel and exchange handle."""
    global _connection, _channel, _exchange

    if _exchange is not None:
        return _exchange

    _connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    _channel = await _connection.channel()
    _exchange = await _channel.declare_exchange(
        EXCHANGE_NAME,
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )
    logger.info("OutboxPublisher: RabbitMQ exchange '%s' ready.", EXCHANGE_NAME)
    return _exchange


async def _reset_connection() -> None:
    """Tear down the current connection so it gets recreated on next attempt."""
    global _connection, _channel, _exchange
    _exchange = None
    _channel = None
    if _connection and not _connection.is_closed:
        try:
            await _connection.close()
        except Exception:
            pass
    _connection = None


async def _publish_pending_events() -> None:
    """
    Fetch all unpublished outbox events (oldest first) and publish them.
    Each event is published atomically: publish to MQ, then mark as published
    in the DB.  If the DB commit fails the event will be re-published on the
    next iteration (idempotency must be handled by consumers).
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.published == False)  # noqa: E712
                .order_by(OutboxEvent.created_at)
                .limit(50)  # process up to 50 per tick to bound latency
                .with_for_update(skip_locked=True)
            )
            events: list[OutboxEvent] = list(result.scalars().all())

            if not events:
                return

            exchange = await _get_exchange()

            for event in events:
                routing_key = ROUTING_KEY_MAP.get(
                    event.event_type,
                    # Fallback: convert CamelCase to dot.case
                    _camel_to_dot(event.event_type),
                )
                try:
                    message = aio_pika.Message(
                        body=event.payload.encode(),
                        content_type="application/json",
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    )
                    await exchange.publish(message, routing_key=routing_key)
                    event.published = True
                    print(
                        f"\n📤 [MS_RESERVAS OUTBOX] Evento publicado a RabbitMQ: {event.event_type} "
                        f"(aggregateId={event.aggregate_id}, routing_key='{routing_key}')",
                        flush=True,
                    )
                    logger.info(
                        "Published event %s (type=%s) -> %s",
                        event.id,
                        event.event_type,
                        routing_key,
                    )
                except Exception as pub_err:
                    logger.error(
                        "Failed to publish event %s: %s", event.id, pub_err
                    )
                    await _reset_connection()
                    # Stop processing this batch; will retry next tick
                    break

            await session.commit()

        except Exception as err:
            logger.error("OutboxPublisher tick error: %s", err)
            await session.rollback()


def _camel_to_dot(name: str) -> str:
    """Convert 'ReservaCancelada' -> 'reserva.cancelada' as a best-effort fallback."""
    import re
    # Insert a dot before each uppercase letter that follows a lowercase letter
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", ".", name)
    return s.lower()


async def run_outbox_publisher() -> None:
    """
    Infinite loop — poll the outbox every OUTBOX_POLL_INTERVAL seconds.
    Designed to be launched as an asyncio background task on startup.
    """
    logger.info(
        "OutboxPublisher started (interval=%ds).", settings.OUTBOX_POLL_INTERVAL
    )
    while True:
        try:
            await _publish_pending_events()
        except Exception as err:
            # Catch-all so the task never dies silently
            logger.exception("Unexpected error in outbox publisher: %s", err)
        await asyncio.sleep(settings.OUTBOX_POLL_INTERVAL)
