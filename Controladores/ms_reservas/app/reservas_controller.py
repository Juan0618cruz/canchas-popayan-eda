"""
Capa MVC: Controlador — ReservasController (Lógica de reservas de deportistas, concurrencia y eventos EDA).

Gestiona la creación de reservas con bloqueo pesimista/advisorio en PostgreSQL,
validación de horarios y conflictos de concurrencia, reprogramación, cancelación y
publicación transaccional con el patrón Transactional Outbox.
"""
import asyncio
import hashlib
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional, Sequence
from urllib.parse import unquote

import httpx
from fastapi import HTTPException, status
from sqlalchemy import and_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ContadorReservas, EstadoReserva, Reserva
from app.outbox import save_outbox_event
from app.schemas import (
    CancelarReservaRequest,
    ReprogramarReservaRequest,
    ReservaResponse,
    SolicitarReservaRequest,
)

COLOMBIA_OFFSET = timezone(timedelta(hours=-5))

ACTIVE_STATES = (
    EstadoReserva.PENDIENTE_PAGO,
    EstadoReserva.CONFIRMADA,
    EstadoReserva.CONFIRMADA_PRESENCIAL,
)

CANCELLABLE_STATES = (EstadoReserva.PENDIENTE_PAGO, EstadoReserva.CONFIRMADA)


class ReservasController:
    """Controlador especializado en la gestión de reservas para deportistas y usuarios web."""

    @staticmethod
    async def solicitar_reserva(
        body: SolicitarReservaRequest,
        session: AsyncSession,
        x_user_id: str,
        x_user_nombre: Optional[str] = None,
        x_user_email: Optional[str] = None,
    ) -> ReservaResponse:
        return await solicitar_reserva(
            body, session, x_user_id, x_user_nombre=x_user_nombre, x_user_email=x_user_email
        )

    @staticmethod
    async def mis_reservas(
        session: AsyncSession,
        x_user_id: str,
    ) -> List[ReservaResponse]:
        return await mis_reservas(session, x_user_id)

    @staticmethod
    async def cancelar_reserva(
        reserva_id: uuid.UUID,
        body: CancelarReservaRequest,
        session: AsyncSession,
        x_user_id: str,
    ) -> ReservaResponse:
        return await cancelar_reserva(reserva_id, body, session, x_user_id)

    @staticmethod
    async def reprogramar_reserva(
        reserva_id: uuid.UUID,
        body: ReprogramarReservaRequest,
        session: AsyncSession,
        x_user_id: str,
    ) -> ReservaResponse:
        return await reprogramar_reserva(reserva_id, body, session, x_user_id)


def _is_generic_nombre(nombre: Optional[str]) -> bool:
    if not nombre or not nombre.strip():
        return True
    cleaned = nombre.strip().lower()
    return cleaned == "usuario" or cleaned.startswith("usuario ")


async def acquire_slot_lock(
    session: AsyncSession,
    cancha_id: uuid.UUID,
    fecha: date,
    hora_inicio: time,
) -> None:
    """
    Acquire a PostgreSQL transaction-level advisory lock keyed on (cancha_id, fecha, hora_inicio)
    so simultaneous requests for the exact same slot serialize cleanly without race conditions.
    No-op for in-memory test sessions.
    """
    if not hasattr(session, "get_bind"):
        return
    raw_key = f"{cancha_id}:{fecha}:{hora_inicio.strftime('%H:%M')}".encode("utf-8")
    lock_id = int.from_bytes(hashlib.sha256(raw_key).digest()[:8], "big", signed=True)
    await session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_id})


async def fetch_usuario_info(
    usuario_id: uuid.UUID,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Fetch (nombre, email, telefono) for a user UUID from ms_usuarios."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.MS_USUARIOS_URL}/usuarios/{usuario_id}")
            if resp.status_code == 200:
                udata = resp.json()
                nombre = (udata.get("nombre") or "").strip() or None
                email = (udata.get("email") or "").strip() or None
                telefono = (udata.get("telefono") or "").strip() or None
                return nombre, email, telefono
    except Exception:
        pass
    return None, None, None


def to_reserva_response(
    reserva: Reserva,
    cliente_email: Optional[str] = None,
) -> ReservaResponse:
    """Serialize Reserva ensuring nombre_cliente, cliente_nombre & usuario_nombre stay aligned."""
    resp = ReservaResponse.model_validate(reserva)
    display_name = (
        reserva.nombre_cliente.strip()
        if reserva.nombre_cliente and not _is_generic_nombre(reserva.nombre_cliente)
        else reserva.nombre_cliente
    )
    resp.cliente_nombre = display_name
    resp.usuario_nombre = display_name
    if cliente_email:
        resp.cliente_email = cliente_email
    return resp


async def enrich_reservas_responses(
    reservas: Sequence[Reserva],
    session: Optional[AsyncSession] = None,
) -> List[ReservaResponse]:
    """
    Resolve real client names via ms_usuarios for reservations missing `nombre_cliente`
    or carrying generic `'Usuario <uuid>'` placeholders, persisting fixes safely when possible.
    """
    unresolved_ids = {
        r.usuario_id
        for r in reservas
        if r.usuario_id is not None and _is_generic_nombre(r.nombre_cliente)
    }

    user_info_map: dict[uuid.UUID, tuple[Optional[str], Optional[str], Optional[str]]] = {}
    if unresolved_ids:
        uid_list = list(unresolved_ids)
        infos = await asyncio.gather(*(fetch_usuario_info(uid) for uid in uid_list))
        for uid, info in zip(uid_list, infos):
            user_info_map[uid] = info

    dirty = False
    responses: List[ReservaResponse] = []
    for r in reservas:
        resolved_email: Optional[str] = None
        if r.usuario_id and r.usuario_id in user_info_map:
            real_name, real_email, real_phone = user_info_map[r.usuario_id]
            resolved_email = real_email
            if real_name and _is_generic_nombre(r.nombre_cliente):
                r.nombre_cliente = real_name
                if not r.telefono_cliente and real_phone:
                    r.telefono_cliente = real_phone
                dirty = True

        responses.append(to_reserva_response(r, cliente_email=resolved_email))

    if dirty and session is not None:
        try:
            await session.commit()
        except Exception:
            try:
                await session.rollback()
            except Exception:
                pass

    return responses


async def _get_next_codigo(session: AsyncSession) -> str:
    result = await session.execute(
        select(ContadorReservas).where(ContadorReservas.id == 1).with_for_update()
    )
    contador_row: ContadorReservas | None = result.scalar_one_or_none()
    if contador_row is None:
        contador_row = ContadorReservas(id=1, contador=0)
        session.add(contador_row)

    contador_row.contador += 1
    year = datetime.now(COLOMBIA_OFFSET).year
    return f"RES-POP-{year}-{contador_row.contador:04d}"


async def _check_slot_conflict(
    session: AsyncSession,
    cancha_id: uuid.UUID,
    fecha: date,
    hora_inicio: time,
    exclude_reserva_id: uuid.UUID | None = None,
) -> bool:
    stmt = (
        select(Reserva)
        .where(
            and_(
                Reserva.cancha_id == cancha_id,
                Reserva.fecha == fecha,
                Reserva.hora_inicio == hora_inicio,
                Reserva.estado.in_(ACTIVE_STATES),
            )
        )
        .with_for_update(skip_locked=True)
    )
    if exclude_reserva_id is not None:
        stmt = stmt.where(Reserva.id != exclude_reserva_id)

    result = await session.execute(stmt)
    return result.scalars().first() is not None


def validate_slot_not_in_past(fecha: date, hora_inicio: time) -> None:
    """Valida que la fecha y hora de la reserva no pertenezcan al pasado (Colombia UTC-5)."""
    now_col = datetime.now(COLOMBIA_OFFSET)
    reserva_dt = datetime.combine(fecha, hora_inicio).replace(tzinfo=COLOMBIA_OFFSET)
    if reserva_dt < now_col:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pueden realizar reservas en horarios pasados.",
        )


async def validate_no_maintenance(
    cancha_id: uuid.UUID,
    fecha: date,
    hora_inicio: time,
) -> None:
    """Validate against ms_canchas (port 8002) that the slot is not under maintenance."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(
                f"http://ms_canchas:8002/canchas/{cancha_id}/disponibilidad",
                params={"fecha": str(fecha)},
            )
            if resp.status_code == 200:
                slots = resp.json()
                for s in slots:
                    if str(s.get("hora_inicio"))[:5] == str(hora_inicio)[:5]:
                        if s.get("estado") == "MANTENIMIENTO":
                            raise HTTPException(
                                status_code=status.HTTP_409_CONFLICT,
                                detail="La cancha se encuentra en mantenimiento en ese horario.",
                            )
    except HTTPException:
        raise
    except Exception:
        pass


async def emit_reprogramacion_events(
    session: AsyncSession,
    reserva: Reserva,
    fecha_anterior: date,
    hora_inicio_anterior: time,
    hora_fin_anterior: time,
    extra_data: dict | None = None,
) -> None:
    """Persist ReservaReprogramada, SlotLiberado, and SlotOcupado outbox events."""
    estado_reserva_str = (
        reserva.estado.value if hasattr(reserva.estado, "value") else str(reserva.estado)
    )
    estado_bloque = (
        "BLOQUEADO_TEMPORAL" if estado_reserva_str == "PENDIENTE_PAGO" else "OCUPADO"
    )

    reprogramada_data = {
        "reserva_id": str(reserva.id),
        "codigo_uid": reserva.codigo_uid,
        "cancha_id": str(reserva.cancha_id),
        "cancha_id_anterior": str(reserva.cancha_id),
        "cancha_id_nuevo": str(reserva.cancha_id),
        "complejo_id": str(reserva.complejo_id),
        "usuario_id": str(reserva.usuario_id) if reserva.usuario_id else None,
        "estado": estado_reserva_str,
        "fecha_anterior": str(fecha_anterior),
        "hora_inicio_anterior": str(hora_inicio_anterior),
        "hora_fin_anterior": str(hora_fin_anterior),
        "nueva_fecha": str(reserva.fecha),
        "nueva_hora_inicio": str(reserva.hora_inicio),
        "nueva_hora_fin": str(reserva.hora_fin),
        "fecha_nuevo": str(reserva.fecha),
        "hora_inicio_nuevo": str(reserva.hora_inicio),
        "hora_fin_nuevo": str(reserva.hora_fin),
    }
    if extra_data:
        reprogramada_data.update(extra_data)

    await save_outbox_event(
        session=session,
        event_type="ReservaReprogramada",
        aggregate_id=str(reserva.id),
        data=reprogramada_data,
    )
    await save_outbox_event(
        session=session,
        event_type="SlotLiberado",
        aggregate_id=str(reserva.id),
        data={
            "reserva_id": str(reserva.id),
            "cancha_id": str(reserva.cancha_id),
            "complejo_id": str(reserva.complejo_id),
            "fecha": str(fecha_anterior),
            "hora_inicio": str(hora_inicio_anterior),
            "hora_fin": str(hora_fin_anterior),
            "estado": "LIBRE",
            "motivo": "REPROGRAMACION",
        },
    )
    await save_outbox_event(
        session=session,
        event_type="SlotOcupado",
        aggregate_id=str(reserva.id),
        data={
            "reserva_id": str(reserva.id),
            "cancha_id": str(reserva.cancha_id),
            "complejo_id": str(reserva.complejo_id),
            "fecha": str(reserva.fecha),
            "hora_inicio": str(reserva.hora_inicio),
            "hora_fin": str(reserva.hora_fin),
            "estado": estado_bloque,
        },
    )


async def sync_canchas_reprogramacion(
    reserva: Reserva,
    fecha_anterior: date,
    hora_inicio_anterior: time,
) -> None:
    """Synchronously notify ms_canchas so the old slot frees and new slot locks immediately."""
    estado_reserva_str = (
        reserva.estado.value if hasattr(reserva.estado, "value") else str(reserva.estado)
    )
    estado_bloque = (
        "BLOQUEADO_TEMPORAL" if estado_reserva_str == "PENDIENTE_PAGO" else "OCUPADO"
    )
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(
                "http://ms_canchas:8002/canchas/internal/reprogramar-slot",
                json={
                    "reserva_id": str(reserva.id),
                    "cancha_id_anterior": str(reserva.cancha_id),
                    "fecha_anterior": str(fecha_anterior),
                    "hora_inicio_anterior": str(hora_inicio_anterior),
                    "cancha_id_nuevo": str(reserva.cancha_id),
                    "fecha_nuevo": str(reserva.fecha),
                    "hora_inicio_nuevo": str(reserva.hora_inicio),
                    "estado_bloque": estado_bloque,
                },
            )
    except Exception:
        pass


async def solicitar_reserva(
    body: SolicitarReservaRequest,
    session: AsyncSession,
    x_user_id: str,
    x_user_nombre: Optional[str] = None,
    x_user_email: Optional[str] = None,
) -> ReservaResponse:
    try:
        usuario_id = uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-Id header must be a valid UUID.",
        )

    validate_slot_not_in_past(body.fecha, body.hora_inicio)
    await validate_no_maintenance(body.cancha_id, body.fecha, body.hora_inicio)

    header_nombre = unquote(x_user_nombre).strip() if x_user_nombre else None
    header_email = unquote(x_user_email).strip() if x_user_email else None

    resolved_nombre = (
        (body.cliente_nombre or "").strip()
        or (body.nombre_cliente or "").strip()
        or (header_nombre or "")
    )
    resolved_email = (body.cliente_email or "").strip() or (header_email or "")
    resolved_phone = (body.telefono_cliente or "").strip() or None

    if _is_generic_nombre(resolved_nombre) or not resolved_email:
        fetched_nombre, fetched_email, fetched_phone = await fetch_usuario_info(usuario_id)
        if _is_generic_nombre(resolved_nombre) and fetched_nombre:
            resolved_nombre = fetched_nombre
        if not resolved_email and fetched_email:
            resolved_email = fetched_email
        if not resolved_phone and fetched_phone:
            resolved_phone = fetched_phone

    final_nombre = resolved_nombre or None

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

            reserva = Reserva(
                id=uuid.uuid4(),
                codigo_uid=codigo_uid,
                cancha_id=body.cancha_id,
                complejo_id=body.complejo_id,
                usuario_id=usuario_id,
                nombre_cliente=final_nombre,
                telefono_cliente=resolved_phone,
                fecha=body.fecha,
                hora_inicio=body.hora_inicio,
                hora_fin=body.hora_fin,
                estado=EstadoReserva.PENDIENTE_PAGO,
                monto=body.monto,
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
                    "usuario_id": str(reserva.usuario_id),
                    "nombre_usuario": final_nombre,
                    "nombre_cliente": final_nombre,
                    "cliente_nombre": final_nombre,
                    "email_usuario": resolved_email or None,
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

    await session.refresh(reserva)
    return to_reserva_response(reserva, cliente_email=resolved_email or None)


async def listar_mis_reservas(
    session: AsyncSession,
    x_user_id: str,
) -> List[ReservaResponse]:
    try:
        usuario_id = uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-Id header must be a valid UUID.",
        )

    result = await session.execute(
        select(Reserva)
        .where(Reserva.usuario_id == usuario_id)
        .order_by(Reserva.fecha.desc(), Reserva.hora_inicio.desc())
    )
    reservas = result.scalars().all()
    return await enrich_reservas_responses(reservas, session)


async def cancelar_reserva(
    reserva_id: uuid.UUID,
    body: Optional[CancelarReservaRequest],
    session: AsyncSession,
    x_user_id: str,
) -> ReservaResponse:
    try:
        usuario_id = uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-Id header must be a valid UUID.",
        )

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

        if reserva.usuario_id != usuario_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para cancelar esta reserva.",
            )

        if reserva.estado not in CANCELLABLE_STATES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"No se puede cancelar una reserva en estado '{reserva.estado}'.",
            )

        now_col = datetime.now(COLOMBIA_OFFSET)
        reserva_dt = datetime.combine(reserva.fecha, reserva.hora_inicio).replace(
            tzinfo=COLOMBIA_OFFSET
        )
        if (reserva_dt - now_col).total_seconds() < 7200:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Solo puedes cancelar con al menos 2 horas de anticipación "
                    "al inicio de la reserva."
                ),
            )

        reserva.estado = EstadoReserva.CANCELADA
        reserva.motivo_cancelacion = body.motivo

        await save_outbox_event(
            session=session,
            event_type="ReservaCancelada",
            aggregate_id=str(reserva.id),
            data={
                "reserva_id": str(reserva.id),
                "codigo_uid": reserva.codigo_uid,
                "cancha_id": str(reserva.cancha_id),
                "complejo_id": str(reserva.complejo_id),
                "usuario_id": str(reserva.usuario_id),
                "fecha": str(reserva.fecha),
                "hora_inicio": str(reserva.hora_inicio),
                "hora_fin": str(reserva.hora_fin),
                "motivo": body.motivo,
                "origen": "USUARIO",
            },
        )

    await session.refresh(reserva)
    return ReservaResponse.model_validate(reserva)


async def reprogramar_reserva(
    reserva_id: uuid.UUID,
    body: ReprogramarReservaRequest,
    session: AsyncSession,
    x_user_id: str,
) -> ReservaResponse:
    try:
        usuario_id = uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-Id header must be a valid UUID.",
        )

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

        if reserva.usuario_id != usuario_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para reprogramar esta reserva.",
            )

        validate_slot_not_in_past(body.nueva_fecha, body.nueva_hora_inicio)
        await validate_no_maintenance(
            reserva.cancha_id, body.nueva_fecha, body.nueva_hora_inicio
        )

        if reserva.estado not in CANCELLABLE_STATES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"No se puede reprogramar una reserva en estado '{reserva.estado}'.",
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

        fecha_anterior = reserva.fecha
        hora_inicio_anterior = reserva.hora_inicio
        hora_fin_anterior = reserva.hora_fin

        reserva.fecha = body.nueva_fecha
        reserva.hora_inicio = body.nueva_hora_inicio
        reserva.hora_fin = body.nueva_hora_fin

        await emit_reprogramacion_events(
            session=session,
            reserva=reserva,
            fecha_anterior=fecha_anterior,
            hora_inicio_anterior=hora_inicio_anterior,
            hora_fin_anterior=hora_fin_anterior,
        )

    await sync_canchas_reprogramacion(
        reserva=reserva,
        fecha_anterior=fecha_anterior,
        hora_inicio_anterior=hora_inicio_anterior,
    )

    await session.refresh(reserva)
    return ReservaResponse.model_validate(reserva)


async def obtener_reserva_interna(
    reserva_id: uuid.UUID,
    session: AsyncSession,
) -> ReservaResponse:
    """Internal read-only lookup for downstream services (ms_pagos, ms_notificaciones)."""
    result = await session.execute(select(Reserva).where(Reserva.id == reserva_id))
    reserva = result.scalar_one_or_none()
    if reserva is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reserva no encontrada.",
        )
    return ReservaResponse.model_validate(reserva)


async def actualizar_estado_pago_interno(
    reserva_id: uuid.UUID,
    estado_pago: str,
    session: AsyncSession,
) -> ReservaResponse:
    """Synchronously transition reservation state on Wompi/payment confirmation or decline."""
    async with session.begin():
        result = await session.execute(
            select(Reserva).where(Reserva.id == reserva_id).with_for_update()
        )
        reserva = result.scalar_one_or_none()
        if reserva is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reserva no encontrada.",
            )

        normalized = str(estado_pago).strip().upper()
        if normalized in ("APPROVED", "APROBADO", "CONFIRMADA"):
            if reserva.estado == EstadoReserva.PENDIENTE_PAGO:
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
                        "precio_total": str(reserva.monto),
                    },
                )
                print(
                    f"\n✅ [MS_RESERVAS SYNC] Reserva {reserva.codigo_uid} actualizada a CONFIRMADA. "
                    f"Evento 'ReservaConfirmada' agregado a Outbox.",
                    flush=True,
                )
        elif normalized in ("DECLINED", "RECHAZADO", "CANCELADA", "VOIDED", "ERROR"):
            if reserva.estado == EstadoReserva.PENDIENTE_PAGO:
                reserva.estado = EstadoReserva.CANCELADA
                reserva.motivo_cancelacion = "Pago rechazado por Wompi"

    await session.refresh(reserva)
    return ReservaResponse.model_validate(reserva)
