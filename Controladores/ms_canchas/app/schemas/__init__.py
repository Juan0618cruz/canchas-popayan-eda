"""
app/schemas/__init__.py - Pydantic DTOs (View layer) for ms_canchas.
"""
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models import TipoCancha


# ---------------------------------------------------------------------------
# BloqueHorario
# ---------------------------------------------------------------------------
class BloqueHorarioResponse(BaseModel):
    """Public representation of a single time slot."""

    id: uuid.UUID
    cancha_id: uuid.UUID
    fecha: date
    hora_inicio: time
    hora_fin: time
    estado: str  # LIBRE, BLOQUEADO_TEMPORAL, OCUPADO, MANTENIMIENTO
    reserva_id: Optional[uuid.UUID] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class SyncReprogramarSlotRequest(BaseModel):
    """Internal DTO to synchronize old/new slots when a booking is rescheduled."""

    reserva_id: uuid.UUID
    cancha_id_anterior: uuid.UUID
    fecha_anterior: date
    hora_inicio_anterior: time
    cancha_id_nuevo: uuid.UUID
    fecha_nuevo: date
    hora_inicio_nuevo: time
    estado_bloque: str = "OCUPADO"


# ---------------------------------------------------------------------------
# Cancha
# ---------------------------------------------------------------------------
class CanchaBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)
    tipo: TipoCancha
    tarifa_por_hora: Decimal = Field(..., gt=0, decimal_places=2)
    descripcion: Optional[str] = Field(None, max_length=1000)
    imagen_url: Optional[str] = Field(None, max_length=500)
    activo: bool = True
    hora_apertura: time = time(8, 0)
    hora_cierre: time = time(22, 0)


class CanchaResponse(BaseModel):
    """Public representation of a court (no nested bloques for list views)."""

    id: uuid.UUID
    complejo_id: uuid.UUID
    nombre: str
    tipo: TipoCancha
    tarifa_por_hora: Decimal
    descripcion: Optional[str] = None
    imagen_url: Optional[str] = None
    activo: bool
    hora_apertura: time
    hora_cierre: time
    created_at: datetime

    model_config = {"from_attributes": True}


class CanchaConDisponibilidadResponse(CanchaResponse):
    """Court with its time slots for a specific date."""

    bloques: List[BloqueHorarioResponse] = []

    model_config = {"from_attributes": True}


class CanchaCreateRequest(BaseModel):
    """Admin: request to create a new court."""

    complejo_id: Optional[uuid.UUID] = None
    nombre: str = Field(..., min_length=1, max_length=200)
    tipo: TipoCancha = TipoCancha.FUTBOL_5
    tarifa_por_hora: Decimal = Field(..., gt=0, decimal_places=2)
    descripcion: Optional[str] = Field(None, max_length=1000)
    imagen_url: Optional[str] = Field(None, max_length=500)
    activo: bool = True
    hora_apertura: time = time(8, 0)
    hora_cierre: time = time(22, 0)


class CanchaUpdateRequest(BaseModel):
    """Admin: update mutable fields of a court."""

    complejo_id: Optional[uuid.UUID] = None
    nombre: Optional[str] = Field(None, min_length=1, max_length=200)
    tipo: Optional[TipoCancha] = None
    tarifa_por_hora: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    descripcion: Optional[str] = Field(None, max_length=1000)
    imagen_url: Optional[str] = Field(None, max_length=500)
    activo: Optional[bool] = None
    hora_apertura: Optional[time] = None
    hora_cierre: Optional[time] = None

    @field_validator("tarifa_por_hora")
    @classmethod
    def tarifa_must_be_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("tarifa_por_hora must be greater than 0")
        return v


# ---------------------------------------------------------------------------
# Complejo
# ---------------------------------------------------------------------------
class ComplejoBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)
    direccion: str = Field(..., min_length=1, max_length=300)
    barrio: str = Field(..., min_length=1, max_length=100)
    ciudad: str = Field("Popayán", min_length=1, max_length=100)
    descripcion: Optional[str] = Field(None, max_length=1000)
    imagen_url: Optional[str] = Field(None, max_length=500)
    activo: bool = True


class ComplejoCreateRequest(ComplejoBase):
    pass


class ComplejoUpdateRequest(BaseModel):
    nombre: Optional[str] = Field(None, min_length=1, max_length=200)
    direccion: Optional[str] = Field(None, min_length=1, max_length=300)
    barrio: Optional[str] = Field(None, min_length=1, max_length=100)
    ciudad: Optional[str] = Field(None, min_length=1, max_length=100)
    descripcion: Optional[str] = Field(None, max_length=1000)
    imagen_url: Optional[str] = Field(None, max_length=500)
    activo: Optional[bool] = None


class ComplejoResponse(BaseModel):
    """Complejo without courts — lightweight list view."""

    id: uuid.UUID
    nombre: str
    direccion: str
    barrio: str
    ciudad: str
    descripcion: Optional[str] = None
    imagen_url: Optional[str] = None
    activo: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ComplejoCanchasResponse(ComplejoResponse):
    """Complejo with its full list of courts."""

    canchas: List[CanchaResponse] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Búsqueda (search)
# ---------------------------------------------------------------------------
class CanchaDisponibleResponse(BaseModel):
    """
    Result item returned by GET /canchas/buscar.
    Shows a court with the LIBRE slots for the requested date.
    """

    id: uuid.UUID
    complejo_id: uuid.UUID
    complejo_nombre: str
    complejo_direccion: str
    nombre: str
    tipo: TipoCancha
    tarifa_por_hora: Decimal
    hora_apertura: time
    hora_cierre: time
    slots_libres: List[BloqueHorarioResponse] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Admin: mis-canchas
# ---------------------------------------------------------------------------
class MisCanchasResponse(BaseModel):
    """Admin response for courts belonging to their complex."""

    complejo: ComplejoResponse
    canchas: List[CanchaResponse] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    service: str
    status: str
    version: str


# ---------------------------------------------------------------------------
# Mantenimiento
# ---------------------------------------------------------------------------
class BloqueoMantenimientoCreate(BaseModel):
    cancha_id: uuid.UUID
    fecha: date
    hora_inicio: time
    hora_fin: time
    motivo: Optional[str] = "Mantenimiento preventivo"

    @field_validator("hora_fin")
    @classmethod
    def hora_fin_after_hora_inicio(cls, v: time, info) -> time:
        hora_inicio = info.data.get("hora_inicio")
        if hora_inicio is not None and v <= hora_inicio:
            raise ValueError("hora_fin debe ser posterior a hora_inicio")
        return v


class BloqueoMantenimientoResponse(BaseModel):
    id: uuid.UUID
    cancha_id: uuid.UUID
    fecha: date
    hora_inicio: time
    hora_fin: time
    motivo: Optional[str] = None
    activo: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Apariencia / Fondos
# ---------------------------------------------------------------------------
class AparienciaConfigResponse(BaseModel):
    fondo_general_url: Optional[str] = "/assets/backgrounds/hero-stadium-bg.svg"
    fondo_slot_url: Optional[str] = "/assets/backgrounds/cancha-slot-bg.svg"
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AparienciaConfigUpdate(BaseModel):
    fondo_general_url: Optional[str] = Field(None, max_length=500)
    fondo_slot_url: Optional[str] = Field(None, max_length=500)


__all__ = [
    "BloqueHorarioResponse",
    "SyncReprogramarSlotRequest",
    "CanchaBase",
    "CanchaResponse",
    "CanchaConDisponibilidadResponse",
    "CanchaCreateRequest",
    "CanchaUpdateRequest",
    "ComplejoBase",
    "ComplejoCreateRequest",
    "ComplejoUpdateRequest",
    "ComplejoResponse",
    "ComplejoCanchasResponse",
    "CanchaDisponibleResponse",
    "MisCanchasResponse",
    "HealthResponse",
    "BloqueoMantenimientoCreate",
    "BloqueoMantenimientoResponse",
    "AparienciaConfigResponse",
    "AparienciaConfigUpdate",
]
