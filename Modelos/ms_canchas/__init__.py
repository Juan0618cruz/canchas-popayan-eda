"""
app/models/__init__.py - SQLAlchemy ORM models (Model layer) for ms_canchas.

Models:
  - Complejo            : sports complex / facility
  - Cancha              : individual sports court inside a complex
  - BloqueHorario       : one-hour time slot on a specific date for a court
  - BloqueoMantenimiento: maintenance window blocking slots on a court/date
  - AparienciaConfig    : customizable platform background configuration
"""
import enum
import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class TipoCancha(str, enum.Enum):
    FUTBOL_5 = "FUTBOL_5"
    FUTBOL_7 = "FUTBOL_7"
    FUTBOL_8 = "FUTBOL_8"


class EstadoBloque(str, enum.Enum):
    LIBRE = "LIBRE"
    BLOQUEADO_TEMPORAL = "BLOQUEADO_TEMPORAL"
    OCUPADO = "OCUPADO"


# ---------------------------------------------------------------------------
# Complejo
# ---------------------------------------------------------------------------
class Complejo(Base):
    """Represents a sports complex (conjunto deportivo) in Popayán."""

    __tablename__ = "complejos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    direccion: Mapped[str] = mapped_column(String(300), nullable=False)
    barrio: Mapped[str] = mapped_column(String(100), nullable=False)
    ciudad: Mapped[str] = mapped_column(String(100), nullable=False, default="Popayán")
    descripcion: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    imagen_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    canchas: Mapped[list["Cancha"]] = relationship(
        "Cancha",
        back_populates="complejo",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Complejo id={self.id} nombre='{self.nombre}'>"


# ---------------------------------------------------------------------------
# Cancha
# ---------------------------------------------------------------------------
class Cancha(Base):
    """Represents a single sports court inside a Complejo."""

    __tablename__ = "canchas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    complejo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("complejos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[TipoCancha] = mapped_column(
        Enum(TipoCancha, name="tipo_cancha_enum"),
        nullable=False,
    )
    tarifa_por_hora: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    descripcion: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    imagen_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    hora_apertura: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        default=time(8, 0),
    )
    hora_cierre: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        default=time(22, 0),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    complejo: Mapped["Complejo"] = relationship("Complejo", back_populates="canchas")
    bloques: Mapped[list["BloqueHorario"]] = relationship(
        "BloqueHorario",
        back_populates="cancha",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    mantenimientos: Mapped[list["BloqueoMantenimiento"]] = relationship(
        "BloqueoMantenimiento",
        back_populates="cancha",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Cancha id={self.id} nombre='{self.nombre}' tipo={self.tipo}>"


# ---------------------------------------------------------------------------
# BloqueHorario
# ---------------------------------------------------------------------------
class BloqueHorario(Base):
    """
    Represents a 1-hour time slot for a court on a specific calendar date.

    - estado=LIBRE             : available for booking
    - estado=BLOQUEADO_TEMPORAL: reservation requested, payment pending
    - estado=OCUPADO           : payment confirmed, slot fully reserved
    """

    __tablename__ = "bloques_horarios"

    __table_args__ = (
        UniqueConstraint(
            "cancha_id",
            "fecha",
            "hora_inicio",
            name="uq_bloque_cancha_fecha_inicio",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    cancha_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canchas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fecha: Mapped[datetime] = mapped_column(Date, nullable=False, index=True)
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fin: Mapped[time] = mapped_column(Time, nullable=False)
    estado: Mapped[EstadoBloque] = mapped_column(
        Enum(EstadoBloque, name="estado_bloque_enum"),
        nullable=False,
        default=EstadoBloque.LIBRE,
    )
    reserva_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        default=None,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    cancha: Mapped["Cancha"] = relationship("Cancha", back_populates="bloques")

    def __repr__(self) -> str:
        return (
            f"<BloqueHorario cancha={self.cancha_id} fecha={self.fecha} "
            f"{self.hora_inicio}-{self.hora_fin} estado={self.estado}>"
        )


# ---------------------------------------------------------------------------
# BloqueoMantenimiento
# ---------------------------------------------------------------------------
class BloqueoMantenimiento(Base):
    """
    Represents a scheduled maintenance block for a court within a specific time window.
    Only the slots within [hora_inicio, hora_fin) are blocked, leaving the rest of the day free.
    """

    __tablename__ = "bloqueos_mantenimiento"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    cancha_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canchas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fin: Mapped[time] = mapped_column(Time, nullable=False)
    motivo: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        default="Mantenimiento preventivo",
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    cancha: Mapped["Cancha"] = relationship("Cancha", back_populates="mantenimientos")

    def __repr__(self) -> str:
        return (
            f"<BloqueoMantenimiento cancha={self.cancha_id} fecha={self.fecha} "
            f"{self.hora_inicio}-{self.hora_fin}>"
        )


# ---------------------------------------------------------------------------
# AparienciaConfig
# ---------------------------------------------------------------------------
class AparienciaConfig(Base):
    """Stores customizable theme backgrounds for the platform."""

    __tablename__ = "apariencia_config"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    fondo_general_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        default="/assets/backgrounds/hero-stadium-bg.svg",
    )
    fondo_slot_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        default="/assets/backgrounds/cancha-slot-bg.svg",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = [
    "TipoCancha",
    "EstadoBloque",
    "Complejo",
    "Cancha",
    "BloqueHorario",
    "BloqueoMantenimiento",
    "AparienciaConfig",
]
