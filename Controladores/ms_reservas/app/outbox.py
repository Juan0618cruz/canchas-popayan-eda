"""
app/outbox.py — Transactional Outbox helper.

save_outbox_event() MUST be called inside the SAME SQLAlchemy session/transaction
as the business-logic state change.  The background publisher (outbox_publisher.py)
polls this table and delivers the events to RabbitMQ asynchronously.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OutboxEvent


def _build_envelope(
    event_type: str,
    aggregate_id: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Construct the canonical event envelope used across all services."""
    return {
        "eventId": str(uuid.uuid4()),
        "eventType": event_type,
        "aggregateId": aggregate_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
        "data": data,
    }


async def save_outbox_event(
    session: AsyncSession,
    event_type: str,
    aggregate_id: str,
    data: dict[str, Any],
) -> OutboxEvent:
    """
    Persist a domain event to the outbox within the caller's transaction.

    Parameters
    ----------
    session:       The active async SQLAlchemy session (transaction must be open).
    event_type:    Domain event name, e.g. "ReservaSolicitada".
    aggregate_id:  String identifier of the aggregate root (usually reserva UUID).
    data:          Arbitrary dict that becomes ``envelope["data"]``.

    Returns
    -------
    The persisted OutboxEvent ORM instance (not yet committed).
    """
    envelope = _build_envelope(event_type, aggregate_id, data)
    outbox_event = OutboxEvent(
        id=uuid.uuid4(),
        event_type=event_type,
        aggregate_id=aggregate_id,
        payload=json.dumps(envelope, default=str),
        published=False,
    )
    session.add(outbox_event)
    return outbox_event
