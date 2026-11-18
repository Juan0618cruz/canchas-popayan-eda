"""
MVC Layer: Model (Modelo) — SQLAlchemy ORM models for ms_usuarios.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RolUsuario(str, enum.Enum):
    """Roles available within the platform."""
    USUARIO = "USUARIO"
    ADMIN_ESTABLECIMIENTO = "ADMIN_ESTABLECIMIENTO"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Usuario(Base):
    """Represents a registered user of the platform."""

    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rol: Mapped[RolUsuario] = mapped_column(
        Enum(RolUsuario, name="rol_usuario_enum"),
        nullable=False,
        default=RolUsuario.USUARIO,
    )
    # Linked to an establishment when rol == ADMIN_ESTABLECIMIENTO
    establecimiento_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now_utc,
    )

    # Relationship to recovery tokens
    tokens_recuperacion: Mapped[list["TokenRecuperacion"]] = relationship(
        "TokenRecuperacion",
        back_populates="usuario",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Usuario id={self.id} email={self.email} rol={self.rol}>"


class TokenRecuperacion(Base):
    """One-time password-reset token associated with a user."""

    __tablename__ = "tokens_recuperacion"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now_utc,
    )

    # Back-reference to the owner
    usuario: Mapped["Usuario"] = relationship(
        "Usuario",
        back_populates="tokens_recuperacion",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TokenRecuperacion id={self.id} usado={self.usado}>"


__all__ = ["RolUsuario", "Usuario", "TokenRecuperacion"]
