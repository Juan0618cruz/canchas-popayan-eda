"""
Capa MVC: Enrutador HTTP (Router) — Endpoints de administración de agenda y taquilla presencial.

Delega la validación de permisos de complejo y la orquestación a AdminReservasController.
"""
import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import admin_reservas_controller
from app.database import get_db
from app.models import EstadoReserva
from app.schemas import (
    CancelarReservaRequest,
    ReprogramarReservaRequest,
    ReservaPresencialRequest,
    ReservaResponse,
)

router = APIRouter(prefix="/reservas/admin", tags=["admin-reservas"])


@router.post(
    "/presencial",
    response_model=ReservaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="HU-16: Crear reserva presencial (admin)",
)
async def crear_reserva_presencial(
    body: ReservaPresencialRequest,
    session: AsyncSession = Depends(get_db),
    x_user_id: str = Header(default="22222222-2222-2222-2222-222222222222", alias="X-User-Id"),
    x_user_rol: str = Header(default="ADMIN", alias="X-User-Rol"),
) -> ReservaResponse:
    return await admin_reservas_controller.crear_reserva_presencial(body, session, x_user_id)


@router.delete(
    "/{reserva_id}",
    response_model=ReservaResponse,
    summary="HU-17: Cancelar reserva (admin)",
)
async def cancelar_reserva_admin(
    reserva_id: uuid.UUID,
    body: CancelarReservaRequest = None,
    session: AsyncSession = Depends(get_db),
    x_user_id: str = Header(default="22222222-2222-2222-2222-222222222222", alias="X-User-Id"),
    x_user_rol: str = Header(default="ADMIN", alias="X-User-Rol"),
    x_establecimiento_id: Optional[str] = Header(
        default=None, alias="X-Establecimiento-Id"
    ),
) -> ReservaResponse:
    return await admin_reservas_controller.cancelar_reserva_admin(
        reserva_id, body, session, x_user_id, x_establecimiento_id
    )


@router.put(
    "/{reserva_id}/reprogramar",
    response_model=ReservaResponse,
    summary="HU-18: Reprogramar reserva (admin)",
)
async def reprogramar_reserva_admin(
    reserva_id: uuid.UUID,
    body: ReprogramarReservaRequest,
    session: AsyncSession = Depends(get_db),
    x_user_id: str = Header(default="22222222-2222-2222-2222-222222222222", alias="X-User-Id"),
    x_user_rol: str = Header(default="ADMIN", alias="X-User-Rol"),
    x_establecimiento_id: Optional[str] = Header(
        default=None, alias="X-Establecimiento-Id"
    ),
) -> ReservaResponse:
    return await admin_reservas_controller.reprogramar_reserva_admin(
        reserva_id, body, session, x_user_id, x_establecimiento_id
    )


@router.get(
    "/por-slot",
    response_model=ReservaResponse,
    summary="Consultar reserva activa por cancha, fecha y hora (admin)",
)
async def obtener_reserva_por_slot(
    cancha_id: uuid.UUID = Query(...),
    fecha: date = Query(...),
    hora_inicio: str = Query(...),
    session: AsyncSession = Depends(get_db),
    x_user_id: str = Header(default="22222222-2222-2222-2222-222222222222", alias="X-User-Id"),
    x_user_rol: str = Header(default="ADMIN", alias="X-User-Rol"),
) -> ReservaResponse:
    from datetime import time as dt_time
    hora_parts = hora_inicio.strip().split(":")
    parsed_time = dt_time(int(hora_parts[0]), int(hora_parts[1]) if len(hora_parts) > 1 else 0)
    return await admin_reservas_controller.obtener_reserva_por_slot_admin(
        cancha_id, fecha, parsed_time, session
    )


@router.get(
    "/todas",
    response_model=List[ReservaResponse],
    summary="Listar todas las reservas del complejo (admin)",
)
async def listar_todas_reservas(
    session: AsyncSession = Depends(get_db),
    x_user_id: str = Header(default="22222222-2222-2222-2222-222222222222", alias="X-User-Id"),
    x_user_rol: str = Header(default="ADMIN", alias="X-User-Rol"),
    x_establecimiento_id: Optional[str] = Header(
        default=None, alias="X-Establecimiento-Id"
    ),
    estado: Optional[EstadoReserva] = Query(default=None, description="Filtrar por estado"),
    fecha: Optional[date] = Query(default=None, description="Filtrar por fecha (YYYY-MM-DD)"),
    cancha_id: Optional[uuid.UUID] = Query(default=None, description="Filtrar por cancha"),
) -> List[ReservaResponse]:
    return await admin_reservas_controller.listar_todas_reservas_admin(
        session, x_establecimiento_id, estado, fecha, cancha_id
    )


@router.get(
    "/{reserva_id}",
    response_model=ReservaResponse,
    summary="Consultar detalle de una reserva por ID (admin)",
)
async def obtener_reserva_por_id(
    reserva_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    x_user_id: str = Header(default="22222222-2222-2222-2222-222222222222", alias="X-User-Id"),
    x_user_rol: str = Header(default="ADMIN", alias="X-User-Rol"),
) -> ReservaResponse:
    return await admin_reservas_controller.obtener_reserva_por_id_admin(reserva_id, session)


@router.post(
    "/{reserva_id}/confirmar",
    response_model=ReservaResponse,
    summary="Confirmar estado de reserva tras pago presencial (admin)",
)
async def confirmar_reserva_admin(
    reserva_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    x_user_id: str = Header(default="22222222-2222-2222-2222-222222222222", alias="X-User-Id"),
    x_user_rol: str = Header(default="ADMIN", alias="X-User-Rol"),
) -> ReservaResponse:
    return await admin_reservas_controller.confirmar_reserva_admin(reserva_id, session)


@router.post(
    "/hard-reset",
    summary="Hard Reset: Vaciar reservas y reiniciar contador (admin)",
)
async def hard_reset_reservas_endpoint(
    session: AsyncSession = Depends(get_db),
    x_user_id: str = Header(default="22222222-2222-2222-2222-222222222222", alias="X-User-Id"),
    x_user_rol: str = Header(default="ADMIN", alias="X-User-Rol"),
):
    from sqlalchemy import text
    await session.execute(text("TRUNCATE TABLE reservas RESTART IDENTITY CASCADE;"))
    await session.execute(text("TRUNCATE TABLE outbox_events RESTART IDENTITY CASCADE;"))
    await session.execute(
        text(
            "INSERT INTO contador_reservas (id, contador) VALUES (1, 0) "
            "ON CONFLICT (id) DO UPDATE SET contador = 0;"
        )
    )
    await session.commit()
    return {
        "status": "success",
        "message": "ms_reservas reseteado de fábrica: reservas=0, outbox=0, contador=0",
        "proximo_codigo": "RES-000001",
    }
