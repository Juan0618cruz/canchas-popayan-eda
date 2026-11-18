"""
MVC Layer: View / DTO Schemas (Vista) — Pydantic schemas for ms_usuarios.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models import RolUsuario


class RegistroUsuarioRequest(BaseModel):
    """Body for registering a standard user."""

    nombre: str = Field(..., min_length=2, max_length=150, examples=["María García"])
    email: EmailStr = Field(..., examples=["maria@example.com"])
    password: str = Field(..., min_length=6, max_length=128, examples=["s3cr3t!"])
    telefono: Optional[str] = Field(None, max_length=20, examples=["+573001234567"])


class RegistroAdminRequest(BaseModel):
    """Body for registering an establishment administrator."""

    nombre: str = Field(..., min_length=2, max_length=150, examples=["Carlos López"])
    email: EmailStr = Field(..., examples=["carlos@cancha.com"])
    password: str = Field(..., min_length=6, max_length=128)
    telefono: Optional[str] = Field(None, max_length=20)
    establecimiento_nombre: str = Field(..., min_length=2, max_length=200, examples=["Canchas El Pital"])
    establecimiento_direccion: str = Field(..., min_length=5, max_length=300, examples=["Cra 5 #10-20, Popayán"])


class LoginRequest(BaseModel):
    """Credentials used to authenticate."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """Successful authentication response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    usuario_id: uuid.UUID
    nombre: str
    email: str
    rol: RolUsuario
    establecimiento_id: Optional[uuid.UUID] = None
    usuario: Optional[dict[str, Any]] = None


class SolicitudRecuperacionRequest(BaseModel):
    """Request to initiate password recovery."""

    email: EmailStr


class ConfirmarRecuperacionRequest(BaseModel):
    """Body to finalise a password reset using the one-time token."""

    token: str = Field(..., min_length=6, max_length=64, description="Código de 6 dígitos o token de recuperación")
    nueva_password: str = Field(..., min_length=6, max_length=128)

    @model_validator(mode="before")
    @classmethod
    def handle_password_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "new_password" in data and "nueva_password" not in data:
                data["nueva_password"] = data["new_password"]
        return data


class PerfilResponse(BaseModel):
    """Public profile information returned to the caller."""

    id: uuid.UUID
    nombre: str
    email: str
    telefono: Optional[str]
    rol: RolUsuario
    establecimiento_id: Optional[uuid.UUID]
    activo: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ActualizarPerfilRequest(BaseModel):
    """Fields that a user may update on their profile."""

    nombre: Optional[str] = Field(None, min_length=2, max_length=150)
    telefono: Optional[str] = Field(None, max_length=20)

    @field_validator("nombre", "telefono", mode="before")
    @classmethod
    def strip_whitespace(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class CambiarPasswordRequest(BaseModel):
    """Body for changing an authenticated user's password."""

    password_actual: str = Field(..., min_length=1)
    nueva_password: str = Field(..., min_length=6, max_length=128)


class MensajeResponse(BaseModel):
    """Generic status message."""

    mensaje: str


class ErrorResponse(BaseModel):
    """Standard error response body."""

    detail: str


__all__ = [
    "RegistroUsuarioRequest",
    "RegistroAdminRequest",
    "LoginRequest",
    "LoginResponse",
    "SolicitudRecuperacionRequest",
    "ConfirmarRecuperacionRequest",
    "PerfilResponse",
    "ActualizarPerfilRequest",
    "CambiarPasswordRequest",
    "MensajeResponse",
    "ErrorResponse",
]
