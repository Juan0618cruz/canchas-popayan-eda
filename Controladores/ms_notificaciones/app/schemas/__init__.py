"""
MVC Layer: View / DTO Schemas (Vista) — Pydantic schemas for ms_notificaciones.
"""

from typing import Optional

from pydantic import BaseModel


class EmailLogDto(BaseModel):
    id: str
    to_email: str
    to_name: str
    subject: str
    body: str
    event_type: str
    aggregate_id: str
    timestamp: str
    status: str
    error_detail: Optional[str] = None


class NotificationLogsResponse(BaseModel):
    total: int
    filtro_event_type: Optional[str] = None
    correos: list[EmailLogDto]


class NotificationStatsResponse(BaseModel):
    total_correos: int
    por_evento: dict[str, int]
    mensaje: Optional[str] = None


__all__ = [
    "EmailLogDto",
    "NotificationLogsResponse",
    "NotificationStatsResponse",
]
