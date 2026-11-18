"""
RabbitMQ publisher for ms_pagos.

Connects to the shared topic exchange "canchas_events" and publishes
domain events using the platform-wide envelope format:

    {
        "eventId":      <uuid>,
        "eventType":    <str>,
        "aggregateId":  <str>,
        "timestamp":    <ISO-8601>,
        "version":      "1.0",
        "data":         { ... }
    }

Routing key mapping:
    PagoAprobado            -> pago.aprobado
    PagoRechazado           -> pago.rechazado
    PagoPresencialValidado  -> pago.presencial.validado
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import aio_pika
from aio_pika import ExchangeType, Message

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state — connection + channel reused across requests
# ---------------------------------------------------------------------------
_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None

EXCHANGE_NAME = "canchas_events"

# Maps domain event types to their AMQP routing keys
ROUTING_KEY_MAP: dict[str, str] = {
    "PagoAprobado": "pago.aprobado",
    "PagoRechazado": "pago.rechazado",
    "PagoPresencialValidado": "pago.presencial.validado",
}


async def init_rabbitmq() -> None:
    """
    Establish a robust AMQP connection and declare the topic exchange.
    Called once at application startup with retry loop.
    """
    global _connection, _channel, _exchange

    logger.info("Connecting to RabbitMQ at %s …", settings.RABBITMQ_URL)
    for attempt in range(15):
        try:
            _connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            _channel = await _connection.channel()
            await _channel.set_qos(prefetch_count=10)

            _exchange = await _channel.declare_exchange(
                EXCHANGE_NAME,
                ExchangeType.TOPIC,
                durable=True,
            )
            logger.info("RabbitMQ exchange '%s' ready.", EXCHANGE_NAME)
            return
        except Exception as e:
            if attempt == 14:
                logger.error("Failed to connect to RabbitMQ after 15 attempts: %s", e)
                raise
            logger.warning("RabbitMQ not ready (attempt %d/15): %s. Retrying in 3s...", attempt + 1, e)
            await asyncio.sleep(3)


async def close_rabbitmq() -> None:
    """Gracefully close the AMQP connection on application shutdown."""
    global _connection, _channel, _exchange

    if _channel and not _channel.is_closed:
        await _channel.close()
    if _connection and not _connection.is_closed:
        await _connection.close()

    _channel = None
    _connection = None
    _exchange = None
    logger.info("RabbitMQ connection closed.")


async def get_exchange() -> aio_pika.abc.AbstractExchange:
    """
    Return the cached exchange, re-initialising the connection if needed.
    Provides lightweight self-healing in case the connection was lost.
    """
    global _exchange

    if _exchange is None:
        await init_rabbitmq()

    return _exchange  # type: ignore[return-value]


async def publish_event(
    event_type: str,
    aggregate_id: str,
    data: dict[str, Any],
) -> None:
    """
    Build the standard platform envelope and publish it to the topic exchange.

    Args:
        event_type:    One of the keys defined in ROUTING_KEY_MAP
                       (e.g. "PagoAprobado").
        aggregate_id:  The primary UUID of the aggregate that raised the event
                       (usually the pago_id).
        data:          Arbitrary payload dict placed under the "data" key.

    Raises:
        ValueError:    If event_type is not registered in ROUTING_KEY_MAP.
        RuntimeError:  If the exchange is unavailable and cannot be recovered.
    """
    if event_type not in ROUTING_KEY_MAP:
        raise ValueError(
            f"Unknown event type '{event_type}'. "
            f"Register it in ROUTING_KEY_MAP first."
        )

    routing_key = ROUTING_KEY_MAP[event_type]

    envelope = {
        "eventId": str(uuid.uuid4()),
        "eventType": event_type,
        "aggregateId": aggregate_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
        "data": data,
    }

    body = json.dumps(envelope, default=str).encode("utf-8")

    exchange = await get_exchange()
    message = Message(
        body=body,
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        message_id=envelope["eventId"],
        type=event_type,
    )

    await exchange.publish(message, routing_key=routing_key)
    logger.info(
        "Published event '%s' (aggregateId=%s) → routing_key='%s'",
        event_type,
        aggregate_id,
        routing_key,
    )
