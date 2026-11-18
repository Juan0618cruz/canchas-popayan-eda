"""
MVC Layer: View / DTO Schemas (Vista) — Pydantic schemas for ms_pagos (incl. Wompi Colombia).
"""

import uuid
from datetime import date, datetime
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

from app.models import EstadoPago, MetodoPago

ONLINE_METHODS = (
    MetodoPago.WOMPI,
    MetodoPago.BRE_B,
    MetodoPago.WOMPI_NEQUI,
    MetodoPago.WOMPI_PSE,
    MetodoPago.WOMPI_BANCOLOMBIA,
    MetodoPago.WOMPI_CARD,
    MetodoPago.TARJETA,
)


class ProcesarPagoRequest(BaseModel):
    """HU-10 — Process an online payment through Wompi Colombia / Sandbox checkout."""

    reserva_id: uuid.UUID = Field(..., description="UUID of the reservation to pay for.")
    usuario_id: Optional[uuid.UUID] = Field(None, description="UUID of the user making the payment.")
    complejo_id: uuid.UUID = Field(..., description="UUID of the sports complex that owns the court.")
    monto: float = Field(..., gt=0, description="Amount in COP. Must be greater than 0.")
    metodo: MetodoPago = Field(
        ...,
        description=(
            "Online payment method: WOMPI or BRE_B."
        ),
    )
    simular_resultado: Literal["APROBADO", "RECHAZADO"] = Field(
        "APROBADO",
        description="Controls the sandbox gateway response.",
    )
    referencia_externa: Optional[str] = Field(
        None,
        max_length=64,
        description="Unique Wompi reference (WOMPI-POP-...). Generated if omitted.",
    )
    observaciones: Optional[str] = Field(None, max_length=512)
    datos_metodo: Optional[dict[str, Any]] = Field(
        None,
        description="Optional method metadata (e.g. phone for Nequi, bank for PSE).",
    )


class WompiPrepararRequest(BaseModel):
    """Prepares a unique Wompi reference and optional SHA-256 integrity signature."""

    reserva_id: uuid.UUID
    monto: float = Field(..., gt=0)
    referencia_externa: Optional[str] = Field(None, max_length=64)


class WompiPrepararResponse(BaseModel):
    """Parameters returned to the frontend for Wompi Widget / Sandbox Checkout."""

    referencia_externa: str
    amount_in_cents: int
    currency: str = "COP"
    public_key: str = ""
    integrity_signature: Optional[str] = None
    sandbox: bool = True


class WompiConfigResponse(BaseModel):
    public_key: str = ""
    sandbox: bool = True
    widget_script_url: str = "https://checkout.wompi.co/widget.js"


class WompiWebhookRequest(BaseModel):
    """
    Webhook payload from Wompi Colombia (or local Sandbox Checkout confirmation).
    Accepts both Wompi's official event envelope (event/data.transaction/signature)
    and simplified sandbox fields.
    """

    event: Optional[str] = "transaction.updated"
    data: Optional[dict[str, Any]] = None
    signature: Optional[dict[str, Any]] = None
    timestamp: Optional[int] = None
    sent_at: Optional[str] = None

    # Direct / sandbox convenience fields
    transaction_id: Optional[str] = None
    reference: Optional[str] = None
    status: Optional[str] = None
    payment_method_type: Optional[str] = None
    metodo_pago: Optional[str] = None
    amount_in_cents: Optional[int] = None
    monto: Optional[float] = None
    reserva_id: Optional[uuid.UUID] = None
    usuario_id: Optional[uuid.UUID] = None
    complejo_id: Optional[uuid.UUID] = None
    customer_email: Optional[str] = None
    observaciones: Optional[str] = None


class PagoPresencialRequest(BaseModel):
    """HU-20 — Register a presencial (in-person) payment collected at the complex."""

    reserva_id: uuid.UUID = Field(..., description="UUID of the reservation being paid.")
    complejo_id: Optional[uuid.UUID] = Field(None, description="UUID of the sports complex receiving the payment.")
    monto: float = Field(..., gt=0, description="Amount collected in COP.")
    metodo: Union[MetodoPago, str] = Field(
        default=MetodoPago.EFECTIVO,
        description="Presencial payment method: EFECTIVO, BRE_B, WOMPI.",
    )
    fecha: Optional[str] = Field(None, description="Optional date of the payment (YYYY-MM-DD).")
    observaciones: Optional[str] = Field(None, max_length=512, description="Optional admin notes.")


class PagoResponse(BaseModel):
    """Full representation of a Pago record returned to clients."""

    id: uuid.UUID
    reserva_id: uuid.UUID
    usuario_id: Optional[uuid.UUID]
    admin_id: Optional[uuid.UUID]
    complejo_id: uuid.UUID
    monto: float
    metodo: MetodoPago
    estado: EstadoPago
    referencia_externa: Optional[str]
    observaciones: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PagosFiltroRequest(BaseModel):
    """HU-19 — Query parameters for the admin payment reports endpoint."""

    complejo_id: Optional[uuid.UUID] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    estado: Optional[EstadoPago] = None

    @field_validator("fecha_fin")
    @classmethod
    def fecha_fin_no_antes_de_inicio(
        cls, fecha_fin: Optional[date], info
    ) -> Optional[date]:
        fecha_inicio = info.data.get("fecha_inicio")
        if fecha_inicio and fecha_fin and fecha_fin < fecha_inicio:
            raise ValueError("fecha_fin must not be earlier than fecha_inicio.")
        return fecha_fin


__all__ = [
    "ONLINE_METHODS",
    "ProcesarPagoRequest",
    "WompiPrepararRequest",
    "WompiPrepararResponse",
    "WompiConfigResponse",
    "WompiWebhookRequest",
    "PagoPresencialRequest",
    "PagoResponse",
    "PagosFiltroRequest",
]
