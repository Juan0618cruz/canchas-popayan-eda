"""
MVC Layer: Model (Modelo) — SQLAlchemy ORM models for ms_reservas.
"""
import enum
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EstadoReserva(str, enum.Enum):
    PENDIENTE_PAGO = "PENDIENTE_PAGO"
    CONFIRMADA = "CONFIRMADA"
    CANCELADA = "CANCELADA"
    CANCELADA_ADMIN = "CANCELADA_ADMIN"
    CONFIRMADA_PRESENCIAL = "CONFIRMADA_PRESENCIAL"


class Reserva(Base):
    """Core reservation entity."""

    __tablename__ = "reservas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    codigo_uid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    cancha_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    complejo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    nombre_cliente: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefono_cliente: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fin: Mapped[time] = mapped_column(Time, nullable=False)
    estado: Mapped[EstadoReserva] = mapped_column(
        Enum(EstadoReserva, name="estado_reserva_enum"),
        nullable=False,
        default=EstadoReserva.PENDIENTE_PAGO,
    )
    motivo_cancelacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "uix_cancha_fecha_hora_activa",
            "cancha_id",
            "fecha",
            "hora_inicio",
            unique=True,
            postgresql_where=text(
                "estado NOT IN ('CANCELADA', 'CANCELADA_ADMIN')"
            ),
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Reserva {self.codigo_uid} cancha={self.cancha_id} "
            f"fecha={self.fecha} estado={self.estado}>"
        )


class OutboxEvent(Base):
    """Transactional Outbox table for reliable RabbitMQ event publishing."""

    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_outbox_published_created", "published", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OutboxEvent {self.event_type} agg={self.aggregate_id} published={self.published}>"


class ContadorReservas(Base):
    """Singleton counter used to generate sequential reservation codes."""

    __tablename__ = "contador_reservas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    contador: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ContadorReservas contador={self.contador}>"


__all__ = ["EstadoReserva", "Reserva", "OutboxEvent", "ContadorReservas"]
