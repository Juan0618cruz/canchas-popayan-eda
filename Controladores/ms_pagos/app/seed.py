"""
ms_pagos/app/seed.py - Seed initial demonstration payments for November 2026.
Ensures that the admin sees payments, total revenue, and transactions in Caja y Pagos.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EstadoPago, MetodoPago, Pago

ADMIN_COMPLEJO_ID = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
ADMIN_USER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
DEPORTISTA_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


async def seed_pagos(session: AsyncSession) -> None:
    """Inserta pagos iniciales de demostración si la tabla está vacía."""
    res = await session.execute(select(func.count()).select_from(Pago))
    count = res.scalar_one()

    if count > 0:
        return

    pagos_demo = [
        Pago(
            id=uuid.UUID("44444444-1111-2222-3333-000000000001"),
            reserva_id=uuid.uuid4(),
            usuario_id=DEPORTISTA_USER_ID,
            admin_id=None,
            complejo_id=ADMIN_COMPLEJO_ID,
            monto=70000.0,
            metodo=MetodoPago.TARJETA,
            estado=EstadoPago.APROBADO,
            referencia_externa="TXN-BOP-2026-001",
            observaciones="Pago en línea reserva Fútbol 5",
            created_at=datetime(2026, 11, 5, 14, 30, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 11, 5, 14, 30, 0, tzinfo=timezone.utc),
        ),
        Pago(
            id=uuid.UUID("44444444-1111-2222-3333-000000000002"),
            reserva_id=uuid.uuid4(),
            usuario_id=DEPORTISTA_USER_ID,
            admin_id=None,
            complejo_id=ADMIN_COMPLEJO_ID,
            monto=90000.0,
            metodo=MetodoPago.BRE_B,
            estado=EstadoPago.APROBADO,
            referencia_externa="TXN-BOP-2026-002",
            observaciones="Pago Bre-B / Llave reserva Fútbol 7",
            created_at=datetime(2026, 11, 6, 18, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 11, 6, 18, 0, 0, tzinfo=timezone.utc),
        ),
        Pago(
            id=uuid.UUID("44444444-1111-2222-3333-000000000003"),
            reserva_id=uuid.uuid4(),
            usuario_id=None,
            admin_id=ADMIN_USER_ID,
            complejo_id=ADMIN_COMPLEJO_ID,
            monto=120000.0,
            metodo=MetodoPago.EFECTIVO,
            estado=EstadoPago.APROBADO,
            referencia_externa="TXN-BOP-2026-003",
            observaciones="Pago presencial en taquilla (Efectivo - Torneo)",
            created_at=datetime(2026, 11, 8, 20, 15, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 11, 8, 20, 15, 0, tzinfo=timezone.utc),
        ),
        Pago(
            id=uuid.UUID("44444444-1111-2222-3333-000000000004"),
            reserva_id=uuid.uuid4(),
            usuario_id=DEPORTISTA_USER_ID,
            admin_id=None,
            complejo_id=ADMIN_COMPLEJO_ID,
            monto=75000.0,
            metodo=MetodoPago.TARJETA,
            estado=EstadoPago.APROBADO,
            referencia_externa="TXN-BOP-2026-004",
            observaciones="Pago en línea tarjeta crédito",
            created_at=datetime(2026, 11, 9, 9, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 11, 9, 9, 0, 0, tzinfo=timezone.utc),
        ),
        Pago(
            id=uuid.UUID("44444444-1111-2222-3333-000000000005"),
            reserva_id=uuid.uuid4(),
            usuario_id=None,
            admin_id=ADMIN_USER_ID,
            complejo_id=ADMIN_COMPLEJO_ID,
            monto=80000.0,
            metodo=MetodoPago.TRANSFERENCIA,
            estado=EstadoPago.APROBADO,
            referencia_externa="TXN-BOP-2026-005",
            observaciones="Transferencia Bancolombia presencial taquilla",
            created_at=datetime(2026, 11, 9, 15, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 11, 9, 15, 0, 0, tzinfo=timezone.utc),
        ),
        Pago(
            id=uuid.UUID("44444444-1111-2222-3333-000000000006"),
            reserva_id=uuid.uuid4(),
            usuario_id=DEPORTISTA_USER_ID,
            admin_id=None,
            complejo_id=ADMIN_COMPLEJO_ID,
            monto=70000.0,
            metodo=MetodoPago.TARJETA,
            estado=EstadoPago.RECHAZADO,
            referencia_externa="TXN-BOP-2026-006",
            observaciones="Simulación de pago rechazado (Prueba Rollback Saga)",
            created_at=datetime(2026, 11, 7, 11, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 11, 7, 11, 0, 0, tzinfo=timezone.utc),
        ),
    ]

    session.add_all(pagos_demo)
    await session.commit()
    print("[seed] ✅ ms_pagos: 6 pagos de demostración iniciales registrados para noviembre de 2026.")
