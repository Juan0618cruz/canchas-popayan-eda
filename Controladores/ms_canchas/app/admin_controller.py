"""
Capa MVC: Controlador — AdminCanchasController (Gestión administrativa de complejos y canchas).

Responsable de la creación y edición de canchas, complejos deportivos, bloqueos por mantenimiento,
subida de imágenes y banners, y emisión de eventos de dominio a RabbitMQ.
"""
import logging
import os
import shutil
import uuid
from datetime import date, timedelta
from typing import Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.canchas_controller import (
    DEFAULT_FONDO_GENERAL,
    DEFAULT_FONDO_SLOT,
    build_virtual_slots,
    crear_mantenimiento,
    create_complejo,
    delete_cancha_record,
    eliminar_mantenimiento,
    listar_mantenimientos,
)
from app.models import AparienciaConfig, BloqueHorario, Cancha, Complejo
from app.rabbitmq import publish_event
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


class AdminCanchasController:
    """Controlador administrativo para canchas, complejos y configuración de apariencia."""

    @staticmethod
    async def listar_canchas_admin(
        db: AsyncSession,
        x_establecimiento_id: Optional[str] = None,
    ) -> list[CanchaResponse]:
        return await admin_list_canchas(db, x_establecimiento_id)

    @staticmethod
    async def crear_cancha(
        body: CanchaCreateRequest,
        db: AsyncSession,
        x_establecimiento_id: Optional[str] = None,
    ) -> CanchaResponse:
        return await admin_create_cancha(body, db, x_establecimiento_id)

    @staticmethod
    async def actualizar_cancha(
        cancha_id: uuid.UUID,
        body: CanchaUpdateRequest,
        db: AsyncSession,
        x_establecimiento_id: Optional[str] = None,
    ) -> CanchaResponse:
        return await admin_update_cancha(cancha_id, body, db, x_establecimiento_id)

    @staticmethod
    async def eliminar_cancha(
        cancha_id: uuid.UUID,
        db: AsyncSession,
        x_establecimiento_id: Optional[str] = None,
    ) -> None:
        await admin_delete_cancha(cancha_id, db, x_establecimiento_id)
from app.seed import _generate_slots

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".svg"}
DEFAULT_ESTABLECIMIENTO_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


def validate_establecimiento_id(x_establecimiento_id: str) -> str:
    """Validate X-Establecimiento-Id header as UUID or 'superadmin'."""
    if x_establecimiento_id != "superadmin":
        try:
            uuid.UUID(x_establecimiento_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Establecimiento-Id must be a valid UUID or 'superadmin'.",
            )
    return x_establecimiento_id


async def get_mis_canchas(
    complejo_id: Optional[uuid.UUID],
    db: AsyncSession,
) -> list[CanchaResponse]:
    """List courts for a given complejo or all registered courts."""
    if complejo_id:
        stmt = select(Cancha).where(Cancha.complejo_id == complejo_id).order_by(Cancha.nombre)
        res = await db.execute(stmt)
        return [CanchaResponse.model_validate(c) for c in res.scalars().all()]

    res_all = await db.execute(select(Cancha).order_by(Cancha.complejo_id, Cancha.nombre))
    return [CanchaResponse.model_validate(c) for c in res_all.scalars().all()]


async def admin_create_complejo(
    body: ComplejoCreateRequest,
    db: AsyncSession,
) -> ComplejoResponse:
    """Delegate complex creation to shared helper."""
    return await create_complejo(body, db)


async def update_complejo(
    complejo_id: uuid.UUID,
    body: ComplejoUpdateRequest,
    db: AsyncSession,
) -> ComplejoResponse:
    """Update mutable properties or banner image of a complex."""
    res = await db.execute(select(Complejo).where(Complejo.id == complejo_id))
    complejo = res.scalar_one_or_none()
    if not complejo:
        raise HTTPException(status_code=404, detail=f"Complejo {complejo_id} no encontrado.")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "imagen_url" and value == "":
            setattr(complejo, field, None)
        else:
            setattr(complejo, field, value)

    await db.commit()
    await db.refresh(complejo)
    return ComplejoResponse.model_validate(complejo)


async def create_cancha(
    body: CanchaCreateRequest,
    establecimiento_id: str,
    db: AsyncSession,
) -> CanchaResponse:
    """Create a court, seed 30 days of hourly slots, and publish CanchaCreada."""
    target_complejo_id = body.complejo_id
    if not target_complejo_id:
        try:
            target_complejo_id = uuid.UUID(establecimiento_id)
        except Exception:
            target_complejo_id = uuid.UUID(DEFAULT_ESTABLECIMIENTO_UUID)

    res_comp = await db.execute(select(Complejo).where(Complejo.id == target_complejo_id))
    if not res_comp.scalar_one_or_none():
        res_any = await db.execute(select(Complejo).limit(1))
        first_comp = res_any.scalar_one_or_none()
        if first_comp:
            target_complejo_id = first_comp.id
        else:
            comp_nuevo = Complejo(
                id=target_complejo_id,
                nombre="Complejo Deportivo Balón de Oro",
                direccion="Carrera 15 # 12-45, Barrio San José",
                barrio="San José",
                ciudad="Popayán",
                activo=True,
            )
            db.add(comp_nuevo)
            await db.flush()

    nueva_cancha = Cancha(
        id=uuid.uuid4(),
        complejo_id=target_complejo_id,
        nombre=body.nombre.strip(),
        tipo=body.tipo,
        tarifa_por_hora=body.tarifa_por_hora,
        descripcion=body.descripcion,
        imagen_url=body.imagen_url,
        activo=body.activo,
        hora_apertura=body.hora_apertura,
        hora_cierre=body.hora_cierre,
    )
    db.add(nueva_cancha)
    await db.flush()

    today = date.today()
    slots: list[BloqueHorario] = []
    for d in range(30):
        slots.extend(
            _generate_slots(
                cancha_id=nueva_cancha.id,
                fecha=today + timedelta(days=d),
                hora_apertura=nueva_cancha.hora_apertura,
                hora_cierre=nueva_cancha.hora_cierre,
            )
        )
    for i in range(0, len(slots), 500):
        db.add_all(slots[i : i + 500])
        await db.flush()

    await db.commit()
    await db.refresh(nueva_cancha)

    try:
        await publish_event(
            event_type="CanchaCreada",
            aggregate_id=str(nueva_cancha.id),
            data={
                "cancha_id": str(nueva_cancha.id),
                "complejo_id": str(nueva_cancha.complejo_id),
                "nombre": nueva_cancha.nombre,
                "tarifa_por_hora": float(nueva_cancha.tarifa_por_hora),
            },
            routing_key="cancha.creada",
        )
    except Exception:
        pass

    return CanchaResponse.model_validate(nueva_cancha)


async def toggle_cancha_estado(
    cancha_id: uuid.UUID,
    activo: Optional[bool],
    db: AsyncSession,
) -> CanchaResponse:
    """Toggle or set a court's active status and publish CanchaEstadoModificado."""
    result = await db.execute(select(Cancha).where(Cancha.id == cancha_id))
    cancha = result.scalar_one_or_none()
    if not cancha:
        raise HTTPException(status_code=404, detail=f"Cancha {cancha_id} no encontrada.")

    cancha.activo = activo if activo is not None else not cancha.activo
    await db.commit()
    await db.refresh(cancha)

    try:
        await publish_event(
            event_type="CanchaEstadoModificado",
            aggregate_id=str(cancha_id),
            data={"cancha_id": str(cancha_id), "activo": cancha.activo},
            routing_key="cancha.actualizada",
        )
    except Exception:
        pass

    return CanchaResponse.model_validate(cancha)


async def delete_cancha(
    cancha_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    """Delete a court and publish CanchaEliminada."""
    cancha = await delete_cancha_record(cancha_id, db)

    try:
        await publish_event(
            event_type="CanchaEliminada",
            aggregate_id=str(cancha_id),
            data={
                "cancha_id": str(cancha_id),
                "complejo_id": str(cancha.complejo_id),
                "nombre": cancha.nombre,
            },
            routing_key="cancha.eliminada",
        )
    except Exception:
        pass

    return {"message": "Cancha eliminada exitosamente", "id": str(cancha_id)}


async def update_cancha(
    cancha_id: uuid.UUID,
    body: CanchaUpdateRequest,
    db: AsyncSession,
) -> CanchaResponse:
    """Partially update court fields and publish CanchaActualizada."""
    result = await db.execute(
        select(Cancha)
        .where(Cancha.id == cancha_id)
        .options(selectinload(Cancha.complejo))
    )
    cancha = result.scalar_one_or_none()
    if cancha is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cancha {cancha_id} not found.",
        )

    update_data = body.model_dump(exclude_unset=True)
    if (
        "tarifa_por_hora" in update_data
        and update_data["tarifa_por_hora"] is not None
        and update_data["tarifa_por_hora"] <= 0
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="tarifa_por_hora must be greater than 0.",
        )

    for field, value in update_data.items():
        if field == "imagen_url" and value == "":
            setattr(cancha, field, None)
        elif value is not None or field == "imagen_url":
            setattr(cancha, field, value)

    await db.commit()
    await db.refresh(cancha)

    try:
        await publish_event(
            event_type="CanchaActualizada",
            aggregate_id=str(cancha_id),
            data={
                "cancha_id": str(cancha_id),
                "complejo_id": str(cancha.complejo_id),
                "cambios": update_data,
            },
            routing_key="cancha.actualizada",
        )
    except Exception as exc:
        logger.error("[admin] Failed to publish CanchaActualizada: %s", exc)

    return CanchaResponse.model_validate(cancha)


async def admin_get_disponibilidad(
    complejo_id: uuid.UUID,
    fecha: date,
    establecimiento_id: str,
    db: AsyncSession,
) -> list[BloqueHorarioResponse]:
    """Return all hourly slots across active courts in a complejo for a given date."""
    if establecimiento_id != "superadmin" and str(complejo_id) != establecimiento_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorised to view this complejo's availability.",
        )

    complejo = (
        await db.execute(select(Complejo).where(Complejo.id == complejo_id))
    ).scalar_one_or_none()
    if complejo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complejo {complejo_id} not found.",
        )

    result_canchas = await db.execute(
        select(Cancha)
        .where(
            and_(
                Cancha.complejo_id == complejo_id,
                Cancha.activo == True,  # noqa: E712
            )
        )
        .order_by(Cancha.nombre)
    )
    canchas = result_canchas.scalars().all()

    all_slots: list[BloqueHorarioResponse] = []
    for cancha in canchas:
        result_bloques = await db.execute(
            select(BloqueHorario)
            .where(
                and_(
                    BloqueHorario.cancha_id == cancha.id,
                    BloqueHorario.fecha == fecha,
                )
            )
            .order_by(BloqueHorario.hora_inicio)
        )
        bloques = result_bloques.scalars().all()

        if not bloques:
            all_slots.extend(build_virtual_slots(cancha, fecha))
        else:
            all_slots.extend(
                [BloqueHorarioResponse.model_validate(b) for b in bloques]
            )

    return all_slots


async def admin_crear_mantenimiento(
    body: BloqueoMantenimientoCreate,
    db: AsyncSession,
) -> BloqueoMantenimientoResponse:
    """Create a maintenance block and publish MantenimientoProgramado."""
    resp = await crear_mantenimiento(body, db)
    try:
        await publish_event(
            event_type="MantenimientoProgramado",
            aggregate_id=str(resp.id),
            data={
                "mantenimiento_id": str(resp.id),
                "cancha_id": str(resp.cancha_id),
                "fecha": str(resp.fecha),
                "hora_inicio": str(resp.hora_inicio),
                "hora_fin": str(resp.hora_fin),
                "motivo": resp.motivo,
            },
            routing_key="cancha.mantenimiento",
        )
    except Exception:
        pass
    return resp


async def admin_listar_mantenimientos(
    cancha_id: Optional[uuid.UUID],
    fecha: Optional[date],
    db: AsyncSession,
) -> list[BloqueoMantenimientoResponse]:
    """Delegate listing maintenance blocks."""
    return await listar_mantenimientos(cancha_id, fecha, db)


async def admin_eliminar_mantenimiento(
    mantenimiento_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    """Delegate deleting maintenance block."""
    return await eliminar_mantenimiento(mantenimiento_id, db)


async def upload_background_image(file: UploadFile) -> dict:
    """Save an uploaded background image to the mounted uploads volume."""
    filename_orig = file.filename or "imagen.png"
    ext = os.path.splitext(filename_orig)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato no permitido ({ext}). Usa JPG, PNG, WEBP o SVG.",
        )

    uploads_dir = os.environ.get("UPLOADS_DIR", "/app/uploads")
    backgrounds_dir = os.path.join(uploads_dir, "backgrounds")
    os.makedirs(backgrounds_dir, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(backgrounds_dir, safe_name)

    with open(dest_path, "wb") as out_file:
        shutil.copyfileobj(file.file, out_file)

    return {
        "filename": safe_name,
        "url": f"/canchas/uploads/backgrounds/{safe_name}",
    }


async def _get_or_init_apariencia(db: AsyncSession) -> AparienciaConfig:
    res = await db.execute(select(AparienciaConfig).where(AparienciaConfig.id == 1))
    cfg = res.scalar_one_or_none()
    if not cfg:
        cfg = AparienciaConfig(
            id=1,
            fondo_general_url=DEFAULT_FONDO_GENERAL,
            fondo_slot_url=DEFAULT_FONDO_SLOT,
        )
        db.add(cfg)
    return cfg


async def update_apariencia(
    body: AparienciaConfigUpdate,
    db: AsyncSession,
) -> AparienciaConfigResponse:
    """Update customizable general and slot background URLs."""
    cfg = await _get_or_init_apariencia(db)
    update_data = body.model_dump(exclude_unset=True)
    if "fondo_general_url" in update_data:
        cfg.fondo_general_url = update_data["fondo_general_url"] or DEFAULT_FONDO_GENERAL
    if "fondo_slot_url" in update_data:
        cfg.fondo_slot_url = update_data["fondo_slot_url"] or DEFAULT_FONDO_SLOT

    await db.commit()
    await db.refresh(cfg)
    return AparienciaConfigResponse.model_validate(cfg)


async def restaurar_apariencia(
    restaurar_complejos_y_canchas: bool,
    db: AsyncSession,
) -> AparienciaConfigResponse:
    """Restore default SVG backgrounds and optionally clear custom entity images."""
    cfg = await _get_or_init_apariencia(db)
    cfg.fondo_general_url = DEFAULT_FONDO_GENERAL
    cfg.fondo_slot_url = DEFAULT_FONDO_SLOT

    if restaurar_complejos_y_canchas:
        complejos_res = await db.execute(select(Complejo))
        for comp in complejos_res.scalars().all():
            comp.imagen_url = None
        canchas_res = await db.execute(select(Cancha))
        for cancha in canchas_res.scalars().all():
            cancha.imagen_url = None

    await db.commit()
    await db.refresh(cfg)
    return AparienciaConfigResponse.model_validate(cfg)
