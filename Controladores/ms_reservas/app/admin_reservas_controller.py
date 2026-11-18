"""
Capa MVC: Controlador — AdminReservasController (Gestión administrativa y taquilla presencial).

Controla la creación de reservas presenciales, cancelaciones y reprogramaciones efectuadas
por el administrador de establecimiento, y la consulta de la agenda completa por complejo.
"""
import uuid
from datetime import date, time
from typing import List, Optional

import httpx
from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.reservas_controller import (
    _check_slot_conflict,
    _get_next_codigo,
    acquire_slot_lock,
    emit_reprogramacion_events,
    enrich_reservas_responses,
    sync_canchas_reprogramacion,
    to_reserva_response,
    validate_no_maintenance,
    validate_slot_not_in_past,
)
from app.models import EstadoReserva, Reserva
from app.outbox import save_outbox_event
from app.schemas import (
    CancelarReservaRequest,
    ReprogramarReservaRequest,
    ReservaPresencialRequest,
    ReservaResponse,
)


class AdminReservasController:
    """Controlador de taquilla y operaciones de administración de reservas."""

    @staticmethod
    async def crear_reserva_presencial(
        body: ReservaPresencialRequest,
        session: AsyncSession,
        x_user_id: str,
        x_establecimiento_id: Optional[str] = None,
    ) -> ReservaResponse:
        return await crear_reserva_presencial(body, session, x_user_id, x_establecimiento_id)

    @staticmethod
    async def listar_reservas_admin(
        session: AsyncSession,
        x_establecimiento_id: Optional[str] = None,
        fecha: Optional[date] = None,
        cancha_id: Optional[uuid.UUID] = None,
        estado: Optional[str] = None,
    ) -> List[ReservaResponse]:
        return await listar_reservas_admin(session, x_establecimiento_id, fecha, cancha_id, estado)

    @staticmethod
    async def cancelar_reserva_admin(
        reserva_id: uuid.UUID,
        body: CancelarReservaRequest,
        session: AsyncSession,
        x_user_id: str,
        x_establecimiento_id: Optional[str] = None,
    ) -> ReservaResponse:
        return await cancelar_reserva_admin(reserva_id, body, session, x_user_id, x_establecimiento_id)

    @staticmethod
    async def reprogramar_reserva_admin(
        reserva_id: uuid.UUID,
        body: ReprogramarReservaRequest,
        session: AsyncSession,
        x_user_id: str,
        x_establecimiento_id: Optional[str] = None,
    ) -> ReservaResponse:
        return await reprogramar_reserva_admin(reserva_id, body, session, x_user_id, x_establecimiento_id)


async def crear_reserva_presencial(
    body: ReservaPresencialRequest,
    session: AsyncSession,
    x_user_id: str,
) -> ReservaResponse:
    resolved_hora_fin = body.hora_fin or time(
        min(23, body.hora_inicio.hour + 1), body.hora_inicio.minute
    )
    resolved_complejo_id = body.complejo_id or uuid.UUID(
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    )
    try:
        resolved_admin_id = body.admin_id or (
            uuid.UUID(str(x_user_id))
            if x_user_id
            else uuid.UUID("33333333-3333-3333-3333-333333333333")
        )
    except Exception:
        resolved_admin_id = uuid.UUID("33333333-3333-3333-3333-333333333333")

    validate_slot_not_in_past(body.fecha, body.hora_inicio)
    await validate_no_maintenance(body.cancha_id, body.fecha, body.hora_inicio)

    try:
        async with session.begin():
            await acquire_slot_lock(session, body.cancha_id, body.fecha, body.hora_inicio)
            conflict = await _check_slot_conflict(
                session, body.cancha_id, body.fecha, body.hora_inicio
            )
            if conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Horario ya reservado: la cancha ya está reservada en ese horario.",
                )

            codigo_uid = await _get_next_codigo(session)

            resolved_nombre_cliente = (
                (body.cliente_nombre or "").strip()
                or (body.nombre_cliente or "").strip()
                or "Cliente Taquilla"
            )

            if body.estado:
                resolved_estado = body.estado
            elif body.pagado is False:
                resolved_estado = EstadoReserva.PENDIENTE_PAGO
            else:
                resolved_estado = EstadoReserva.CONFIRMADA

            reserva = Reserva(
                id=uuid.uuid4(),
                codigo_uid=codigo_uid,
                cancha_id=body.cancha_id,
                complejo_id=resolved_complejo_id,
                usuario_id=None,
                nombre_cliente=resolved_nombre_cliente,
                telefono_cliente=body.telefono_cliente or "3001234567",
                fecha=body.fecha,
                hora_inicio=body.hora_inicio,
                hora_fin=resolved_hora_fin,
                estado=resolved_estado,
                monto=body.monto,
                admin_id=resolved_admin_id,
            )
            session.add(reserva)
            await session.flush()

            await save_outbox_event(
                session=session,
                event_type="ReservaSolicitada",
                aggregate_id=str(reserva.id),
                data={
                    "reserva_id": str(reserva.id),
                    "codigo_uid": reserva.codigo_uid,
                    "cancha_id": str(reserva.cancha_id),
                    "complejo_id": str(reserva.complejo_id),
                    "usuario_id": None,
                    "nombre_cliente": reserva.nombre_cliente,
                    "telefono_cliente": reserva.telefono_cliente,
                    "fecha": str(reserva.fecha),
                    "hora_inicio": str(reserva.hora_inicio),
                    "hora_fin": str(reserva.hora_fin),
                    "monto": str(reserva.monto),
                    "tipo": "PRESENCIAL",
                    "admin_id": str(reserva.admin_id),
                    "estado": reserva.estado.value,
                },
            )

            if resolved_estado == EstadoReserva.CONFIRMADA:
                await save_outbox_event(
                    session=session,
                    event_type="ReservaConfirmada",
                    aggregate_id=str(reserva.id),
                    data={
                        "reserva_id": str(reserva.id),
                        "codigo_uid": reserva.codigo_uid,
                        "cancha_id": str(reserva.cancha_id),
                        "complejo_id": str(reserva.complejo_id),
                        "usuario_id": None,
                        "fecha": str(reserva.fecha),
                        "hora_inicio": str(reserva.hora_inicio),
                        "hora_fin": str(reserva.hora_fin),
                        "monto": str(reserva.monto),
                    },
                )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Horario ya reservado.",
        )

    if resolved_estado == EstadoReserva.CONFIRMADA:
        metodo_envio = (body.metodo_pago or "EFECTIVO").upper()
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.post(
                    "http://ms_pagos:8004/pagos/admin/presencial",
                    json={
                        "reserva_id": str(reserva.id),
                        "complejo_id": str(reserva.complejo_id),
                        "monto": float(reserva.monto),
                        "metodo": metodo_envio,
                        "fecha": str(reserva.fecha),
                        "observaciones": f"Pago presencial taquilla ({metodo_envio}) - {reserva.nombre_cliente}",
                    },
                    headers={"X-User-Id": str(resolved_admin_id)},
                )
        except Exception:
            pass

    await session.refresh(reserva)
    return to_reserva_response(reserva, cliente_email=body.cliente_email)


async def cancelar_reserva_admin(
    reserva_id: uuid.UUID,
    body: Optional[CancelarReservaRequest],
    session: AsyncSession,
    x_user_id: str,
    x_establecimiento_id: Optional[str],
) -> ReservaResponse:
    if body is None:
        body = CancelarReservaRequest()

    async with session.begin():
        result = await session.execute(
            select(Reserva).where(Reserva.id == reserva_id).with_for_update()
        )
        reserva: Reserva | None = result.scalar_one_or_none()

        if reserva is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reserva no encontrada.",
            )

        if reserva.estado in (EstadoReserva.CANCELADA, EstadoReserva.CANCELADA_ADMIN):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"La reserva ya está cancelada (estado: '{reserva.estado}').",
            )

        if x_establecimiento_id:
            try:
                establecimiento_id = uuid.UUID(x_establecimiento_id)
                if reserva.complejo_id != establecimiento_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="No tienes permiso para cancelar reservas de otro complejo.",
                    )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="X-Establecimiento-Id must be a valid UUID.",
                )

        try:
            admin_id = uuid.UUID(x_user_id)
        except ValueError:
            admin_id = None

        reserva.estado = EstadoReserva.CANCELADA_ADMIN
        reserva.motivo_cancelacion = body.motivo
        reserva.admin_id = admin_id

        await save_outbox_event(
            session=session,
            event_type="ReservaCancelada",
            aggregate_id=str(reserva.id),
            data={
                "reserva_id": str(reserva.id),
                "codigo_uid": reserva.codigo_uid,
                "cancha_id": str(reserva.cancha_id),
                "complejo_id": str(reserva.complejo_id),
                "usuario_id": str(reserva.usuario_id) if reserva.usuario_id else None,
                "fecha": str(reserva.fecha),
                "hora_inicio": str(reserva.hora_inicio),
                "hora_fin": str(reserva.hora_fin),
                "motivo": body.motivo,
                "admin_id": str(admin_id) if admin_id else None,
                "origen": "ADMIN",
            },
        )

    await session.refresh(reserva)
    return to_reserva_response(reserva)


async def reprogramar_reserva_admin(
    reserva_id: uuid.UUID,
    body: ReprogramarReservaRequest,
    session: AsyncSession,
    x_user_id: str,
    x_establecimiento_id: Optional[str],
) -> ReservaResponse:
    async with session.begin():
        result = await session.execute(
            select(Reserva).where(Reserva.id == reserva_id).with_for_update()
        )
        reserva: Reserva | None = result.scalar_one_or_none()

        if reserva is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reserva no encontrada.",
            )

        if reserva.estado in (EstadoReserva.CANCELADA, EstadoReserva.CANCELADA_ADMIN):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"No se puede reprogramar una reserva en estado '{reserva.estado}'."
                ),
            )

        if x_establecimiento_id:
            try:
                establecimiento_id = uuid.UUID(x_establecimiento_id)
                if reserva.complejo_id != establecimiento_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="No tienes permiso para reprogramar reservas de otro complejo.",
                    )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="X-Establecimiento-Id must be a valid UUID.",
                )

        validate_slot_not_in_past(body.nueva_fecha, body.nueva_hora_inicio)
        await validate_no_maintenance(
            reserva.cancha_id, body.nueva_fecha, body.nueva_hora_inicio
        )

        conflict = await _check_slot_conflict(
            session,
            reserva.cancha_id,
            body.nueva_fecha,
            body.nueva_hora_inicio,
            exclude_reserva_id=reserva_id,
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La cancha ya está reservada en el nuevo horario solicitado.",
            )

        try:
            admin_id = uuid.UUID(x_user_id)
        except ValueError:
            admin_id = None

        fecha_anterior = reserva.fecha
        hora_inicio_anterior = reserva.hora_inicio
        hora_fin_anterior = reserva.hora_fin

        reserva.fecha = body.nueva_fecha
        reserva.hora_inicio = body.nueva_hora_inicio
        reserva.hora_fin = body.nueva_hora_fin
        reserva.admin_id = admin_id

        await emit_reprogramacion_events(
            session=session,
            reserva=reserva,
            fecha_anterior=fecha_anterior,
            hora_inicio_anterior=hora_inicio_anterior,
            hora_fin_anterior=hora_fin_anterior,
            extra_data={
                "admin_id": str(admin_id) if admin_id else None,
                "origen": "ADMIN",
            },
        )

    await sync_canchas_reprogramacion(
        reserva=reserva,
        fecha_anterior=fecha_anterior,
        hora_inicio_anterior=hora_inicio_anterior,
    )

    await session.refresh(reserva)
    return to_reserva_response(reserva)


async def listar_todas_reservas_admin(
    session: AsyncSession,
    x_establecimiento_id: Optional[str],
    estado: Optional[EstadoReserva],
    fecha: Optional[date],
    cancha_id: Optional[uuid.UUID],
) -> List[ReservaResponse]:
    stmt = select(Reserva)
    filters = []

    if x_establecimiento_id:
        try:
            establecimiento_id = uuid.UUID(x_establecimiento_id)
            filters.append(Reserva.complejo_id == establecimiento_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Establecimiento-Id must be a valid UUID.",
            )

    if estado is not None:
        filters.append(Reserva.estado == estado)
    if fecha is not None:
        filters.append(Reserva.fecha == fecha)
    if cancha_id is not None:
        filters.append(Reserva.cancha_id == cancha_id)

    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(Reserva.fecha.desc(), Reserva.hora_inicio.asc())
    result = await session.execute(stmt)
    reservas = result.scalars().all()

    if not reservas and x_establecimiento_id:
        stmt_fb = select(Reserva)
        fb_filters = []
        if estado is not None:
            fb_filters.append(Reserva.estado == estado)
        if fecha is not None:
            fb_filters.append(Reserva.fecha == fecha)
        if cancha_id is not None:
            fb_filters.append(Reserva.cancha_id == cancha_id)
        if fb_filters:
            stmt_fb = stmt_fb.where(and_(*fb_filters))
        stmt_fb = stmt_fb.order_by(Reserva.fecha.desc(), Reserva.hora_inicio.asc())
        res_fb = await session.execute(stmt_fb)
        reservas = res_fb.scalars().all()

    return await enrich_reservas_responses(reservas, session)


async def obtener_reserva_por_id_admin(
    reserva_id: uuid.UUID,
    session: AsyncSession,
) -> ReservaResponse:
    """Retrieve full reservation details by ID for admin inspection."""
    res = await session.execute(select(Reserva).where(Reserva.id == reserva_id))
    reserva = res.scalar_one_or_none()
    if not reserva:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reserva no encontrada.",
        )
    responses = await enrich_reservas_responses([reserva], session)
    return responses[0]


async def obtener_reserva_por_slot_admin(
    cancha_id: uuid.UUID,
    fecha: date,
    hora_inicio: time,
    session: AsyncSession,
) -> ReservaResponse:
    """Retrieve active reservation matching court, date, and hour for admin drawer."""
    res = await session.execute(
        select(Reserva).where(
            and_(
                Reserva.cancha_id == cancha_id,
                Reserva.fecha == fecha,
                Reserva.hora_inicio == hora_inicio,
                Reserva.estado.not_in([EstadoReserva.CANCELADA, EstadoReserva.CANCELADA_ADMIN]),
            )
        )
    )
    reserva = res.scalar_one_or_none()
    if not reserva:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró reserva activa en ese horario.",
        )
    responses = await enrich_reservas_responses([reserva], session)
    return responses[0]


async def confirmar_reserva_admin(
    reserva_id: uuid.UUID,
    session: AsyncSession,
) -> ReservaResponse:
    """Admin action to confirm a pending reservation upon receiving payment."""
    async with session.begin():
        res = await session.execute(
            select(Reserva).where(Reserva.id == reserva_id).with_for_update()
        )
        reserva = res.scalar_one_or_none()
        if not reserva:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reserva no encontrada.",
            )
        if reserva.estado in (EstadoReserva.CANCELADA, EstadoReserva.CANCELADA_ADMIN):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede confirmar una reserva que ha sido cancelada.",
            )
        reserva.estado = EstadoReserva.CONFIRMADA
        await save_outbox_event(
            session=session,
            event_type="ReservaConfirmada",
            aggregate_id=str(reserva.id),
            data={
                "reserva_id": str(reserva.id),
                "codigo_uid": reserva.codigo_uid,
                "cancha_id": str(reserva.cancha_id),
                "complejo_id": str(reserva.complejo_id),
                "usuario_id": str(reserva.usuario_id) if reserva.usuario_id else None,
                "fecha": str(reserva.fecha),
                "hora_inicio": str(reserva.hora_inicio),
                "hora_fin": str(reserva.hora_fin),
                "monto": str(reserva.monto),
            },
        )
    responses = await enrich_reservas_responses([reserva], session)
    return responses[0]
