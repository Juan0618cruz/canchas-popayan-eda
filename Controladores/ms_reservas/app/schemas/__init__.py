"""
MVC Layer: View / DTO Schemas (Vista) — Pydantic v2 schemas for ms_reservas.
"""
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models import EstadoReserva


class SolicitarReservaRequest(BaseModel):
    """HU-06 — Online reservation request by an authenticated user."""

    cancha_id: uuid.UUID = Field(..., description="ID de la cancha a reservar")
    complejo_id: uuid.UUID = Field(..., description="ID del complejo deportivo")
    fecha: date = Field(..., description="Fecha de la reserva (YYYY-MM-DD)")
    hora_inicio: time = Field(..., description="Hora de inicio (HH:MM)")
    hora_fin: time = Field(..., description="Hora de fin (HH:MM)")
    monto: Decimal = Field(..., gt=0, decimal_places=2, description="Monto a pagar (COP)")
    nombre_cliente: Optional[str] = Field(None, max_length=255)
    cliente_nombre: Optional[str] = Field(None, max_length=255)
    cliente_email: Optional[str] = Field(None, max_length=255)
    telefono_cliente: Optional[str] = Field(None, max_length=32)

    @field_validator("hora_fin")
    @classmethod
    def hora_fin_after_hora_inicio(cls, v: time, info) -> time:
        hora_inicio = info.data.get("hora_inicio")
        if hora_inicio is not None and v <= hora_inicio:
            raise ValueError("hora_fin debe ser posterior a hora_inicio")
        return v


class ReservaPresencialRequest(BaseModel):
    """HU-16 — Walk-in / presencial reservation created by admin."""

    cancha_id: uuid.UUID
    complejo_id: Optional[uuid.UUID] = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    nombre_cliente: Optional[str] = Field("Cliente Taquilla", max_length=255)
    cliente_nombre: Optional[str] = Field(None, max_length=255)
    cliente_email: Optional[str] = Field(None, max_length=255)
    telefono_cliente: Optional[str] = Field("3001234567", max_length=32)
    fecha: date
    hora_inicio: time
    hora_fin: Optional[time] = None
    monto: Decimal = Field(..., gt=0, decimal_places=2)
    admin_id: Optional[uuid.UUID] = None
    estado: Optional[EstadoReserva] = None
    pagado: Optional[bool] = None
    metodo_pago: Optional[str] = None

    @field_validator("hora_fin")
    @classmethod
    def hora_fin_after_hora_inicio(cls, v: Optional[time], info) -> Optional[time]:
        if v is None:
            return v
        hora_inicio = info.data.get("hora_inicio")
        if hora_inicio is not None and v <= hora_inicio:
            raise ValueError("hora_fin debe ser posterior a hora_inicio")
        return v


class CancelarReservaRequest(BaseModel):
    """HU-08 / HU-17 — Cancellation request (motivo is optional)."""

    motivo: Optional[str] = Field(None, max_length=500)


class ReprogramarReservaRequest(BaseModel):
    """HU-09 / HU-18 — Rescheduling request."""

    nueva_fecha: date
    nueva_hora_inicio: time
    nueva_hora_fin: time

    @field_validator("nueva_hora_fin")
    @classmethod
    def hora_fin_after_hora_inicio(cls, v: time, info) -> time:
        nueva_hora_inicio = info.data.get("nueva_hora_inicio")
        if nueva_hora_inicio is not None and v <= nueva_hora_inicio:
            raise ValueError("nueva_hora_fin debe ser posterior a nueva_hora_inicio")
        return v


class ReservaResponse(BaseModel):
    """Full representation of a Reserva returned to callers."""

    id: uuid.UUID
    codigo_uid: str
    cancha_id: uuid.UUID
    complejo_id: uuid.UUID
    usuario_id: Optional[uuid.UUID]
    nombre_cliente: Optional[str]
    cliente_nombre: Optional[str] = None
    usuario_nombre: Optional[str] = None
    cliente_email: Optional[str] = None
    telefono_cliente: Optional[str]
    fecha: date
    hora_inicio: time
    hora_fin: time
    estado: EstadoReserva
    motivo_cancelacion: Optional[str]
    admin_id: Optional[uuid.UUID]
    monto: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ErrorResponse(BaseModel):
    """Standard error envelope."""

    detail: str
    code: Optional[str] = None


__all__ = [
    "SolicitarReservaRequest",
    "ReservaPresencialRequest",
    "CancelarReservaRequest",
    "ReprogramarReservaRequest",
    "ReservaResponse",
    "ErrorResponse",
]
