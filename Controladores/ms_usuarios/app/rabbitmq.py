"""
RabbitMQ publisher for ms_usuarios.

Manages a single persistent connection and channel to a topic exchange
named "canchas_events". Provides reconnect logic and a high-level
publish_event() helper that wraps messages in the standard event envelope.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import aio_pika
from aio_pika import ExchangeType, Message
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractExchange

from app.config import settings

logger = logging.getLogger(__name__)

EXCHANGE_NAME = "canchas_events"

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_connection: AbstractConnection | None = None
_channel: AbstractChannel | None = None
_exchange: AbstractExchange | None = None
_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

async def _connect() -> None:
    """Establish a connection to RabbitMQ and declare the topic exchange."""
    global _connection, _channel, _exchange

    logger.info("Connecting to RabbitMQ at %s …", settings.RABBITMQ_URL)
    _connection = await aio_pika.connect_robust(
        settings.RABBITMQ_URL,
        reconnect_interval=5,
    )
    _channel = await _connection.channel()
    await _channel.set_qos(prefetch_count=10)
    _exchange = await _channel.declare_exchange(
        EXCHANGE_NAME,
        ExchangeType.TOPIC,
        durable=True,
    )
    logger.info("RabbitMQ connection established. Exchange '%s' ready.", EXCHANGE_NAME)


async def get_rabbitmq_channel() -> AbstractChannel:
    """
    Return the active RabbitMQ channel, reconnecting if necessary.

    Thread-safe via an asyncio lock so that concurrent callers during
    startup do not create multiple connections.
    """
    global _connection, _channel, _exchange

    async with _lock:
        if _connection is None or _connection.is_closed:
            await _connect()
        elif _channel is None or _channel.is_closed:
            _channel = await _connection.channel()
            _exchange = await _channel.declare_exchange(
                EXCHANGE_NAME,
                ExchangeType.TOPIC,
                durable=True,
            )

    return _channel  # type: ignore[return-value]


async def close_rabbitmq() -> None:
    """Cleanly close the RabbitMQ connection (called on app shutdown)."""
    global _connection, _channel, _exchange

    if _channel and not _channel.is_closed:
        await _channel.close()
    if _connection and not _connection.is_closed:
        await _connection.close()

    _connection = None
    _channel = None
    _exchange = None
    logger.info("RabbitMQ connection closed.")


# ---------------------------------------------------------------------------
# Event publishing
# ---------------------------------------------------------------------------

def _build_envelope(
    event_type: str,
    aggregate_id: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Construct the standard event envelope used across all microservices."""
    return {
        "eventId": str(uuid.uuid4()),
        "eventType": event_type,
        "aggregateId": aggregate_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
        "data": data,
    }


async def publish_event(
    event_type: str,
    aggregate_id: str,
    data: dict[str, Any],
    routing_key: str | None = None,
) -> None:
    """
    Publish a domain event to the "canchas_events" topic exchange.

    Args:
        event_type:   e.g. "UsuarioRegistrado", "ClaveRestablecimientoSolicitada"
        aggregate_id: The UUID of the entity this event is about.
        data:         Arbitrary payload (must be JSON-serialisable).
        routing_key:  Defaults to "usuarios.<event_type>" if not supplied.
    """
    global _exchange

    envelope = _build_envelope(event_type, aggregate_id, data)
    body = json.dumps(envelope, default=str).encode()

    rk = routing_key or f"usuarios.{event_type}"

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            # Ensure connection is alive
            await get_rabbitmq_channel()

            if _exchange is None:
                raise RuntimeError("RabbitMQ exchange is not initialised.")

            await _exchange.publish(
                Message(
                    body=body,
                    content_type="application/json",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=rk,
            )
            logger.info(
                "Event published → exchange=%s routing_key=%s eventType=%s aggregateId=%s",
                EXCHANGE_NAME,
                rk,
                event_type,
                aggregate_id,
            )
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to publish event (attempt %d/%d): %s",
                attempt,
                max_attempts,
                exc,
            )
            if attempt < max_attempts:
                await asyncio.sleep(1 * attempt)  # back-off
            else:
                logger.error(
                    "Could not publish event '%s' for aggregate '%s' after %d attempts.",
                    event_type,
                    aggregate_id,
                    max_attempts,
                )
                # Do NOT raise – a failed publish must not break the HTTP response.


async def start_publisher() -> None:
    """
    Background task started on application startup.
    Establishes the initial connection so the first request does not pay
    the connection-setup cost.
    """
    try:
        await _connect()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Initial RabbitMQ connection failed (%s). "
            "Will retry on first publish.",
            exc,
        )
