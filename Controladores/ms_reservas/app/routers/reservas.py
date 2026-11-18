"""
Capa MVC: Enrutador HTTP (Router) — Endpoints de reservas para deportistas y usuarios web.

Delega la lógica transaccional, bloqueos y orquestación EDA a ReservasController.
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import reservas_controller
from app.database import get_db
from app.schemas import (
    CancelarReservaRequest,
    ReprogramarReservaRequest,
    ReservaResponse,
    SolicitarReservaRequest,
)

router = APIRouter(prefix="/reservas", tags=["reservas"])


@router.post(
    "",
    response_model=ReservaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="HU-06: Solicitar reserva online",
)
async def solicitar_reserva(
    body: SolicitarReservaRequest,
    session: AsyncSession = Depends(get_db),
    x_user_id: str = Header(default="11111111-1111-1111-1111-111111111111", alias="X-User-Id"),
    x_user_rol: str = Header(default="USUARIO", alias="X-User-Rol"),
    x_user_nombre: Optional[str] = Header(default=None, alias="X-User-Nombre"),
    x_user_email: Optional[str] = Header(default=None, alias="X-User-Email"),
) -> ReservaResponse:
    return await reservas_controller.solicitar_reserva(
        body, session, x_user_id, x_user_nombre=x_user_nombre, x_user_email=x_user_email
    )


@router.get(
    "/mis-reservas",
    response_model=List[ReservaResponse],
    summary="HU-07: Listar reservas propias",
)
async def mis_reservas(
    session: AsyncSession = Depends(get_db),
    x_user_id: str = Header(default="11111111-1111-1111-1111-111111111111", alias="X-User-Id"),
) -> List[ReservaResponse]:
    return await reservas_controller.listar_mis_reservas(session, x_user_id)


@router.get(
    "/internal/{reserva_id}",
    response_model=ReservaResponse,
    summary="Consulta interna de reserva por ID para otros microservicios",
)
async def get_reserva_interna(
    reserva_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ReservaResponse:
    return await reservas_controller.obtener_reserva_interna(reserva_id, session)


@router.post(
    "/internal/{reserva_id}/estado-pago",
    response_model=ReservaResponse,
    summary="Actualización síncrona de estado de reserva tras respuesta de pasarela",
)
async def sync_estado_pago_interno(
    reserva_id: uuid.UUID,
    estado: str = "APPROVED",
    session: AsyncSession = Depends(get_db),
) -> ReservaResponse:
    return await reservas_controller.actualizar_estado_pago_interno(reserva_id, estado, session)


@router.delete(
    "/{reserva_id}",
    response_model=ReservaResponse,
    summary="HU-08: Cancelar propia reserva",
)
async def cancelar_reserva(
    reserva_id: uuid.UUID,
    body: CancelarReservaRequest = None,
    session: AsyncSession = Depends(get_db),
    x_user_id: str = Header(default="11111111-1111-1111-1111-111111111111", alias="X-User-Id"),
) -> ReservaResponse:
    return await reservas_controller.cancelar_reserva(reserva_id, body, session, x_user_id)


@router.put(
    "/{reserva_id}/reprogramar",
    response_model=ReservaResponse,
    summary="HU-09: Reprogramar propia reserva",
)
async def reprogramar_reserva(
    reserva_id: uuid.UUID,
    body: ReprogramarReservaRequest,
    session: AsyncSession = Depends(get_db),
    x_user_id: str = Header(default="11111111-1111-1111-1111-111111111111", alias="X-User-Id"),
) -> ReservaResponse:
    return await reservas_controller.reprogramar_reserva(reserva_id, body, session, x_user_id)
