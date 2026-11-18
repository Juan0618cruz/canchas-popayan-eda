"""
Capa MVC: Enrutador HTTP (Router) — Catálogo público de canchas y cálculo de disponibilidad.

Delega la lógica de cálculo de bloques horarios y consulta a CanchasController.
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import canchas_controller
from app.database import get_db
from app.models import TipoCancha
from app.schemas import (
    AparienciaConfigResponse,
    BloqueHorarioResponse,
    BloqueoMantenimientoCreate,
    BloqueoMantenimientoResponse,
    CanchaDisponibleResponse,
    CanchaResponse,
    ComplejoCanchasResponse,
    ComplejoCreateRequest,
    ComplejoResponse,
    SyncReprogramarSlotRequest,
)

router = APIRouter(tags=["canchas-publicas"])


@router.post(
    "/complejos",
    response_model=ComplejoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo complejo deportivo",
)
async def create_complejo_direct(
    body: ComplejoCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ComplejoResponse:
    return await canchas_controller.create_complejo(body, db)


@router.get(
    "/apariencia",
    response_model=AparienciaConfigResponse,
    summary="Obtener la configuración visual y fondos personalizados de la plataforma",
)
async def get_apariencia(
    db: AsyncSession = Depends(get_db),
) -> AparienciaConfigResponse:
    return await canchas_controller.get_apariencia(db)


@router.get(
    "/complejos",
    response_model=list[ComplejoCanchasResponse],
    summary="List all active complejos with their courts",
)
async def list_complejos(
    db: AsyncSession = Depends(get_db),
) -> list[ComplejoCanchasResponse]:
    return await canchas_controller.list_complejos(db)


@router.get(
    "/buscar",
    response_model=list[CanchaDisponibleResponse],
    summary="Search available courts by date and/or type",
)
async def buscar_canchas(
    fecha: date = Query(..., description="Date to search (YYYY-MM-DD)"),
    tipo: TipoCancha | None = Query(None, description="Court type filter"),
    db: AsyncSession = Depends(get_db),
) -> list[CanchaDisponibleResponse]:
    return await canchas_controller.buscar_canchas(fecha, tipo, db)


@router.get(
    "/complejos/{complejo_id}",
    response_model=ComplejoCanchasResponse,
    summary="Get a single complejo with its courts",
)
async def get_complejo(
    complejo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ComplejoCanchasResponse:
    return await canchas_controller.get_complejo(complejo_id, db)


@router.get(
    "",
    response_model=list[CanchaResponse],
    summary="List all courts directly",
)
@router.get(
    "/mis-canchas",
    response_model=list[CanchaResponse],
    summary="List courts alias",
)
async def list_canchas_direct(
    db: AsyncSession = Depends(get_db),
) -> list[CanchaResponse]:
    return await canchas_controller.list_canchas_direct(db)


@router.post(
    "/mantenimientos",
    response_model=BloqueoMantenimientoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Programar bloqueo de mantenimiento por rango horario",
)
async def crear_mantenimiento_direct(
    body: BloqueoMantenimientoCreate,
    db: AsyncSession = Depends(get_db),
) -> BloqueoMantenimientoResponse:
    return await canchas_controller.crear_mantenimiento(body, db)


@router.get(
    "/mantenimientos",
    response_model=list[BloqueoMantenimientoResponse],
    summary="Listar bloqueos de mantenimiento",
)
async def listar_mantenimientos_direct(
    cancha_id: Optional[uuid.UUID] = Query(None),
    fecha: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[BloqueoMantenimientoResponse]:
    return await canchas_controller.listar_mantenimientos(cancha_id, fecha, db)


@router.delete(
    "/mantenimientos/{mantenimiento_id}",
    status_code=status.HTTP_200_OK,
    summary="Eliminar o cancelar bloqueo de mantenimiento",
)
async def eliminar_mantenimiento_direct(
    mantenimiento_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    return await canchas_controller.eliminar_mantenimiento(mantenimiento_id, db)


@router.post(
    "/internal/reprogramar-slot",
    status_code=status.HTTP_200_OK,
    summary="Sincronización inmediata de franja al reprogramar reserva",
)
async def sync_reprogramar_slot_endpoint(
    body: SyncReprogramarSlotRequest,
    db: AsyncSession = Depends(get_db),
):
    return await canchas_controller.sync_reprogramar_slot(body, db)


@router.get(
    "/{cancha_id}/disponibilidad",
    response_model=list[BloqueHorarioResponse],
    summary="Get time slots for a court on a specific date",
)
async def get_disponibilidad(
    cancha_id: uuid.UUID,
    fecha: date = Query(..., description="Date to query (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
) -> list[BloqueHorarioResponse]:
    return await canchas_controller.get_disponibilidad(cancha_id, fecha, db)


@router.delete(
    "/{cancha_id}",
    status_code=status.HTTP_200_OK,
    summary="Eliminar cancha alias directo",
)
async def delete_cancha_direct(
    cancha_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await canchas_controller.delete_cancha_record(cancha_id, db)
    return {"message": "Cancha eliminada exitosamente", "id": str(cancha_id)}
