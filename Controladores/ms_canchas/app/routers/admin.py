"""
Capa MVC: Enrutador HTTP (Router) — Endpoints administrativos de canchas, complejos y apariencia.

Delega la gestión de recursos, validación y eventos a AdminCanchasController.
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Header, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import admin_controller
from app.database import get_db
from app.schemas import (
    AparienciaConfigResponse,
    AparienciaConfigUpdate,
    BloqueHorarioResponse,
    BloqueoMantenimientoCreate,
    BloqueoMantenimientoResponse,
    CanchaCreateRequest,
    CanchaResponse,
    CanchaUpdateRequest,
    ComplejoCreateRequest,
    ComplejoResponse,
    ComplejoUpdateRequest,
)

router = APIRouter(prefix="/admin", tags=["canchas-admin"])


async def get_establecimiento_id(
    x_establecimiento_id: str = Header(
        default=admin_controller.DEFAULT_ESTABLECIMIENTO_UUID,
        alias="X-Establecimiento-Id",
        description=(
            "UUID of the complejo the admin manages, or 'superadmin' for full access."
        ),
    ),
) -> str:
    """Validate and return the establecimiento id from the custom header."""
    return admin_controller.validate_establecimiento_id(x_establecimiento_id)


@router.get(
    "/mis-canchas",
    response_model=list[CanchaResponse],
    summary="Admin: listar canchas del complejo o todas las canchas",
)
@router.get(
    "/canchas",
    response_model=list[CanchaResponse],
    summary="Admin: listar todas las canchas directamente",
)
async def get_mis_canchas(
    complejo_id: Optional[uuid.UUID] = Query(None),
    establecimiento_id: str = Depends(get_establecimiento_id),
    db: AsyncSession = Depends(get_db),
) -> list[CanchaResponse]:
    return await admin_controller.get_mis_canchas(complejo_id, db)


@router.post(
    "/complejos",
    response_model=ComplejoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin: crear un nuevo complejo deportivo",
)
async def create_complejo(
    body: ComplejoCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ComplejoResponse:
    return await admin_controller.admin_create_complejo(body, db)


@router.put(
    "/complejos/{complejo_id}",
    response_model=ComplejoResponse,
    summary="Admin: actualizar datos o banner de un complejo deportivo",
)
async def update_complejo(
    complejo_id: uuid.UUID,
    body: ComplejoUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> ComplejoResponse:
    return await admin_controller.update_complejo(complejo_id, body, db)


@router.post(
    "/canchas",
    response_model=CanchaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin: crear una nueva cancha deportiva",
)
async def create_cancha(
    body: CanchaCreateRequest,
    establecimiento_id: str = Depends(get_establecimiento_id),
    db: AsyncSession = Depends(get_db),
) -> CanchaResponse:
    return await admin_controller.create_cancha(body, establecimiento_id, db)


@router.patch(
    "/canchas/{cancha_id}/estado",
    response_model=CanchaResponse,
    summary="Admin: alternar estado activo / mantenimiento de la cancha",
)
async def toggle_cancha_estado(
    cancha_id: uuid.UUID,
    activo: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> CanchaResponse:
    return await admin_controller.toggle_cancha_estado(cancha_id, activo, db)


@router.delete(
    "/canchas/{cancha_id}",
    status_code=status.HTTP_200_OK,
    summary="Admin: eliminar una cancha y sus bloques horarios asociados",
)
async def delete_cancha(
    cancha_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    return await admin_controller.delete_cancha(cancha_id, db)


@router.put(
    "/canchas/{cancha_id}",
    response_model=CanchaResponse,
    summary="Admin: update a court's details",
)
async def update_cancha(
    cancha_id: uuid.UUID,
    body: CanchaUpdateRequest,
    establecimiento_id: str = Depends(get_establecimiento_id),
    db: AsyncSession = Depends(get_db),
) -> CanchaResponse:
    return await admin_controller.update_cancha(cancha_id, body, db)


@router.get(
    "/complejos/{complejo_id}/disponibilidad",
    response_model=list[BloqueHorarioResponse],
    summary="Admin: view all time slots for a complejo on a date",
)
async def admin_get_disponibilidad(
    complejo_id: uuid.UUID,
    fecha: date = Query(..., description="Date to query (YYYY-MM-DD)"),
    establecimiento_id: str = Depends(get_establecimiento_id),
    db: AsyncSession = Depends(get_db),
) -> list[BloqueHorarioResponse]:
    return await admin_controller.admin_get_disponibilidad(complejo_id, fecha, establecimiento_id, db)


@router.post(
    "/mantenimientos",
    response_model=BloqueoMantenimientoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin: programar bloqueo de mantenimiento por rango horario",
)
async def admin_crear_mantenimiento(
    body: BloqueoMantenimientoCreate,
    db: AsyncSession = Depends(get_db),
) -> BloqueoMantenimientoResponse:
    return await admin_controller.admin_crear_mantenimiento(body, db)


@router.get(
    "/mantenimientos",
    response_model=list[BloqueoMantenimientoResponse],
    summary="Admin: listar bloqueos de mantenimiento",
)
async def admin_listar_mantenimientos(
    cancha_id: Optional[uuid.UUID] = Query(None),
    fecha: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[BloqueoMantenimientoResponse]:
    return await admin_controller.admin_listar_mantenimientos(cancha_id, fecha, db)


@router.delete(
    "/mantenimientos/{mantenimiento_id}",
    status_code=status.HTTP_200_OK,
    summary="Admin: eliminar o cancelar bloqueo de mantenimiento",
)
async def admin_eliminar_mantenimiento(
    mantenimiento_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    return await admin_controller.admin_eliminar_mantenimiento(mantenimiento_id, db)


@router.post(
    "/uploads/backgrounds",
    summary="Admin: subir imagen personalizada (JPG, PNG, WEBP, SVG) para fondos",
)
async def upload_background_image(
    file: UploadFile = File(...),
):
    return await admin_controller.upload_background_image(file)


@router.put(
    "/apariencia",
    response_model=AparienciaConfigResponse,
    summary="Admin: actualizar fondos visuales generales y de casillas",
)
async def update_apariencia(
    body: AparienciaConfigUpdate,
    db: AsyncSession = Depends(get_db),
) -> AparienciaConfigResponse:
    return await admin_controller.update_apariencia(body, db)


@router.post(
    "/apariencia/restaurar",
    response_model=AparienciaConfigResponse,
    summary="Admin: restaurar los diseños SVG de cancha por defecto",
)
async def restaurar_apariencia(
    restaurar_complejos_y_canchas: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> AparienciaConfigResponse:
    return await admin_controller.restaurar_apariencia(restaurar_complejos_y_canchas, db)
