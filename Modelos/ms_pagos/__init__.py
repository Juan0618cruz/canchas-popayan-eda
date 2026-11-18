"""
MVC Layer: Model (Modelo) — SQLAlchemy ORM models for ms_pagos.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MetodoPago(str, enum.Enum):
    """Supported payment methods (Wompi Colombia + presencial)."""
    WOMPI_NEQUI = "WOMPI_NEQUI"
    WOMPI_PSE = "WOMPI_PSE"
    WOMPI_BANCOLOMBIA = "WOMPI_BANCOLOMBIA"
    WOMPI_CARD = "WOMPI_CARD"
    TARJETA = "TARJETA"
    BRE_B = "BRE_B"
    EFECTIVO = "EFECTIVO"
    TRANSFERENCIA = "TRANSFERENCIA"


class EstadoPago(str, enum.Enum):
    """Lifecycle states of a payment record."""
    PENDIENTE = "PENDIENTE"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"


class Pago(Base):
    """Payment transaction record associated with a reservation."""

    __tablename__ = "pagos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    reserva_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    complejo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    monto: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    metodo: Mapped[MetodoPago] = mapped_column(
        Enum(MetodoPago, name="metodo_pago_enum", create_type=True),
        nullable=False,
    )
    estado: Mapped[EstadoPago] = mapped_column(
        Enum(EstadoPago, name="estado_pago_enum", create_type=True),
        nullable=False,
        default=EstadoPago.PENDIENTE,
    )
    referencia_externa: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    observaciones: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_pagos_complejo_created", "complejo_id", "created_at"),
        Index("ix_pagos_complejo_estado", "complejo_id", "estado"),
        Index("ix_pagos_usuario_created", "usuario_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Pago id={self.id} reserva={self.reserva_id} "
            f"monto={self.monto} estado={self.estado}>"
        )


__all__ = ["MetodoPago", "EstadoPago", "Pago"]
