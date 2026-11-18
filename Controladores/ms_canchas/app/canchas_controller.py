"""
Capa MVC: Controlador — CanchasController (Consultas públicas y cálculo de disponibilidad).

Gestiona la consulta del catálogo de complejos deportivos, el cálculo en memoria y persistencia
de bloques horarios virtuales y la sincronización con RabbitMQ.
"""
import uuid
from datetime import date, datetime, time
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AparienciaConfig,
    BloqueHorario,
    BloqueoMantenimiento,
    Cancha,
    Complejo,
    EstadoBloque,
    TipoCancha,
)
from app.rabbitmq import sync_rescheduled_slot
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

DEFAULT_FONDO_GENERAL = "/assets/backgrounds/hero-stadium-bg.svg"
DEFAULT_FONDO_SLOT = "/assets/backgrounds/cancha-slot-bg.svg"


class CanchasController:
    """Controlador para la gestión y disponibilidad pública de canchas y complejos."""

    @staticmethod
    def construir_slots_virtuales(cancha: Cancha, fecha: date) -> list[BloqueHorarioResponse]:
        return build_virtual_slots(cancha, fecha)

    @staticmethod
    async def listar_complejos(db: AsyncSession) -> list[ComplejoCanchasResponse]:
        return await list_complejos(db)

    @staticmethod
    async def obtener_complejo(complejo_id: uuid.UUID, db: AsyncSession) -> ComplejoCanchasResponse:
        return await get_complejo(complejo_id, db)

    @staticmethod
    async def consultar_disponibilidad(
        cancha_id: uuid.UUID,
        fecha: date,
        db: AsyncSession,
    ) -> CanchaDisponibleResponse:
        return await get_disponibilidad_cancha(cancha_id, fecha, db)

    @staticmethod
    async def obtener_apariencia(db: AsyncSession) -> AparienciaConfigResponse:
        return await get_apariencia_config(db)


def build_virtual_slots(cancha: Cancha, fecha: date) -> list[BloqueHorarioResponse]:
    """Generate transient LIBRE 1-hour slots when no DB rows exist for a date."""
    slots: list[BloqueHorarioResponse] = []
    current_hour = cancha.hora_apertura.hour
    close_hour = cancha.hora_cierre.hour

    while current_hour < close_hour:
        slots.append(
            BloqueHorarioResponse(
                id=uuid.uuid4(),
                cancha_id=cancha.id,
                fecha=fecha,
                hora_inicio=time(current_hour, 0),
                hora_fin=time(current_hour + 1, 0),
                estado=EstadoBloque.LIBRE,
                reserva_id=None,
                updated_at=datetime.utcnow(),
            )
        )
        current_hour += 1

    return slots


async def create_complejo(
    body: ComplejoCreateRequest,
    db: AsyncSession,
) -> ComplejoResponse:
    """Create a new Complejo entity."""
    nuevo_complejo = Complejo(
        id=uuid.uuid4(),
        nombre=body.nombre.strip(),
        direccion=body.direccion.strip(),
        barrio=body.barrio.strip(),
        ciudad=body.ciudad or "Popayán",
        descripcion=body.descripcion,
        imagen_url=body.imagen_url,
        activo=body.activo,
    )
    db.add(nuevo_complejo)
    await db.commit()
    await db.refresh(nuevo_complejo)
    return ComplejoResponse.model_validate(nuevo_complejo)


async def get_apariencia(db: AsyncSession) -> AparienciaConfigResponse:
    """Fetch customizable platform background configuration."""
    res = await db.execute(select(AparienciaConfig).where(AparienciaConfig.id == 1))
    cfg = res.scalar_one_or_none()
    if not cfg:
        return AparienciaConfigResponse(
            fondo_general_url=DEFAULT_FONDO_GENERAL,
            fondo_slot_url=DEFAULT_FONDO_SLOT,
        )
    return AparienciaConfigResponse.model_validate(cfg)


async def list_complejos(db: AsyncSession) -> list[ComplejoCanchasResponse]:
    """List all active sports complexes with their courts."""
    result = await db.execute(
        select(Complejo)
        .where(Complejo.activo == True)  # noqa: E712
        .options(selectinload(Complejo.canchas))
        .order_by(Complejo.nombre)
    )
    complejos = result.scalars().all()
    return [ComplejoCanchasResponse.model_validate(c) for c in complejos]


async def buscar_canchas(
    fecha: date,
    tipo: Optional[TipoCancha],
    db: AsyncSession,
) -> list[CanchaDisponibleResponse]:
    """Search active courts with LIBRE slots for a given date and optional court type."""
    stmt = (
        select(Cancha)
        .join(Cancha.complejo)
        .where(
            and_(
                Cancha.activo == True,  # noqa: E712
                Complejo.activo == True,  # noqa: E712
            )
        )
        .options(selectinload(Cancha.complejo), selectinload(Cancha.bloques))
        .order_by(Cancha.tipo, Cancha.nombre)
    )

    if tipo is not None:
        stmt = stmt.where(Cancha.tipo == tipo)

    result = await db.execute(stmt)
    canchas = result.scalars().all()

    output: list[CanchaDisponibleResponse] = []
    for cancha in canchas:
        date_bloques = [b for b in cancha.bloques if b.fecha == fecha]

        if not date_bloques:
            date_bloques_resp = build_virtual_slots(cancha, fecha)
        else:
            date_bloques_resp = [
                BloqueHorarioResponse.model_validate(b) for b in date_bloques
            ]

        slots_libres = [
            b for b in date_bloques_resp if b.estado == EstadoBloque.LIBRE
        ]

        output.append(
            CanchaDisponibleResponse(
                id=cancha.id,
                complejo_id=cancha.complejo_id,
                complejo_nombre=cancha.complejo.nombre,
                complejo_direccion=cancha.complejo.direccion,
                nombre=cancha.nombre,
                tipo=cancha.tipo,
                tarifa_por_hora=cancha.tarifa_por_hora,
                hora_apertura=cancha.hora_apertura,
                hora_cierre=cancha.hora_cierre,
                slots_libres=slots_libres,
            )
        )

    return output


async def get_complejo(
    complejo_id: uuid.UUID,
    db: AsyncSession,
) -> ComplejoCanchasResponse:
    """Get a single active complejo with its courts."""
    result = await db.execute(
        select(Complejo)
        .where(
            and_(
                Complejo.id == complejo_id,
                Complejo.activo == True,  # noqa: E712
            )
        )
        .options(selectinload(Complejo.canchas))
    )
    complejo = result.scalar_one_or_none()
    if complejo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complejo {complejo_id} not found or inactive.",
        )

    return ComplejoCanchasResponse.model_validate(complejo)


async def get_disponibilidad(
    cancha_id: uuid.UUID,
    fecha: date,
    db: AsyncSession,
) -> list[BloqueHorarioResponse]:
    """Get time slots for a court on a specific date overlaying maintenance blocks."""
    result_cancha = await db.execute(select(Cancha).where(Cancha.id == cancha_id))
    cancha = result_cancha.scalar_one_or_none()
    if cancha is None:
        return []

    result_mantenimientos = await db.execute(
        select(BloqueoMantenimiento).where(
            and_(
                BloqueoMantenimiento.cancha_id == cancha_id,
                BloqueoMantenimiento.fecha == fecha,
                BloqueoMantenimiento.activo == True,  # noqa: E712
            )
        )
    )
    mantenimientos = result_mantenimientos.scalars().all()

    result_bloques = await db.execute(
        select(BloqueHorario)
        .where(
            and_(
                BloqueHorario.cancha_id == cancha_id,
                BloqueHorario.fecha == fecha,
            )
        )
        .order_by(BloqueHorario.hora_inicio)
    )
    bloques = result_bloques.scalars().all()

    if not bloques:
        slots = build_virtual_slots(cancha, fecha)
    else:
        slots = [BloqueHorarioResponse.model_validate(b) for b in bloques]

    for slot in slots:
        for m in mantenimientos:
            if slot.hora_inicio < m.hora_fin and slot.hora_fin > m.hora_inicio:
                slot.estado = "MANTENIMIENTO"
                break

    return slots


async def list_canchas_direct(db: AsyncSession) -> list[CanchaResponse]:
    """List all courts sorted by name."""
    result = await db.execute(select(Cancha).order_by(Cancha.nombre))
    canchas = result.scalars().all()
    return [CanchaResponse.model_validate(c) for c in canchas]


async def sync_reprogramar_slot(
    body: SyncReprogramarSlotRequest,
    db: AsyncSession,
) -> dict:
    """Synchronize freed and reserved slots synchronously on booking reschedule."""
    estado_bloque = (
        EstadoBloque.BLOQUEADO_TEMPORAL
        if str(body.estado_bloque).upper() == "BLOQUEADO_TEMPORAL"
        else EstadoBloque.OCUPADO
    )
    await sync_rescheduled_slot(
        session=db,
        reserva_id=body.reserva_id,
        cancha_id_ant=body.cancha_id_anterior,
        fecha_ant=body.fecha_anterior,
        hora_ant=body.hora_inicio_anterior,
        cancha_id_new=body.cancha_id_nuevo,
        fecha_new=body.fecha_nuevo,
        hora_new=body.hora_inicio_nuevo,
        estado_bloque=estado_bloque,
    )
    await db.commit()
    return {"ok": True}


async def delete_cancha_record(
    cancha_id: uuid.UUID,
    db: AsyncSession,
) -> Cancha:
    """Delete a court and its associated time slots; returns the deleted court before returning response."""
    result = await db.execute(select(Cancha).where(Cancha.id == cancha_id))
    cancha = result.scalar_one_or_none()
    if not cancha:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cancha {cancha_id} no encontrada.",
        )

    await db.execute(delete(BloqueHorario).where(BloqueHorario.cancha_id == cancha_id))
    await db.delete(cancha)
    await db.commit()
    return cancha


async def crear_mantenimiento(
    body: BloqueoMantenimientoCreate,
    db: AsyncSession,
) -> BloqueoMantenimientoResponse:
    """Create a scheduled maintenance block for a court."""
    cancha = (await db.execute(select(Cancha).where(Cancha.id == body.cancha_id))).scalar_one_or_none()
    if not cancha:
        raise HTTPException(status_code=404, detail="Cancha no encontrada.")

    mantenimiento = BloqueoMantenimiento(
        id=uuid.uuid4(),
        cancha_id=body.cancha_id,
        fecha=body.fecha,
        hora_inicio=body.hora_inicio,
        hora_fin=body.hora_fin,
        motivo=body.motivo or "Mantenimiento preventivo",
        activo=True,
    )
    db.add(mantenimiento)
    await db.commit()
    await db.refresh(mantenimiento)
    return BloqueoMantenimientoResponse.model_validate(mantenimiento)


async def listar_mantenimientos(
    cancha_id: Optional[uuid.UUID],
    fecha: Optional[date],
    db: AsyncSession,
) -> list[BloqueoMantenimientoResponse]:
    """List active maintenance blocks with optional court/date filtering."""
    filters = [BloqueoMantenimiento.activo == True]  # noqa: E712
    if cancha_id:
        filters.append(BloqueoMantenimiento.cancha_id == cancha_id)
    if fecha:
        filters.append(BloqueoMantenimiento.fecha == fecha)

    result = await db.execute(
        select(BloqueoMantenimiento)
        .where(and_(*filters))
        .order_by(BloqueoMantenimiento.fecha.desc(), BloqueoMantenimiento.hora_inicio.asc())
    )
    mantenimientos = result.scalars().all()
    return [BloqueoMantenimientoResponse.model_validate(m) for m in mantenimientos]


async def eliminar_mantenimiento(
    mantenimiento_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    """Delete a maintenance block by ID."""
    m = (
        await db.execute(
            select(BloqueoMantenimiento).where(BloqueoMantenimiento.id == mantenimiento_id)
        )
    ).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Mantenimiento no encontrado.")

    await db.delete(m)
    await db.commit()
    return {"message": "Mantenimiento eliminado exitosamente", "id": str(mantenimiento_id)}
