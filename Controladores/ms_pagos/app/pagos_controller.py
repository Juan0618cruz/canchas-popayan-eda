"""
Capa MVC: Controlador — PagosController (Lógica de pagos Wompi Colombia, webhooks y pagos presenciales).

Responsable del procesamiento de pagos en línea mediante la pasarela Wompi Colombia,
verificación criptográfica de firma de integridad, registro de pagos presenciales en taquilla,
y emisión de eventos de dominio Saga (PagoAprobado, PagoRechazado) hacia RabbitMQ.
"""

import hashlib
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, List, Optional

import httpx
from fastapi import HTTPException, status
from sqlalchemy import Date, and_, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import EstadoPago, MetodoPago, Pago
from app.rabbitmq import publish_event
from app.schemas import (
    ONLINE_METHODS,
    PagoPresencialRequest,
    PagoResponse,
    ProcesarPagoRequest,
    WompiConfigResponse,
    WompiPrepararRequest,
    WompiPrepararResponse,
    WompiWebhookRequest,
)

logger = logging.getLogger("ms_pagos.controller")


class PagosController:
    """Controlador central de transacciones financieras, pasarela Wompi y caja administrativa."""

    @staticmethod
    def obtener_config_wompi() -> WompiConfigResponse:
        return obtener_config_wompi()

    @staticmethod
    def preparar_checkout_wompi(body: WompiPrepararRequest) -> WompiPrepararResponse:
        return preparar_checkout_wompi(body)

    @staticmethod
    async def procesar_webhook_wompi(body: WompiWebhookRequest, db: AsyncSession) -> PagoResponse:
        return await procesar_webhook_wompi(body, db)

    @staticmethod
    async def procesar_pago_online(body: ProcesarPagoRequest, db: AsyncSession) -> PagoResponse:
        return await procesar_pago_online(body, db)

    @staticmethod
    async def registrar_pago_presencial(
        body: PagoPresencialRequest,
        db: AsyncSession,
        x_user_id: Optional[str] = None,
        x_establecimiento_id: Optional[str] = None,
    ) -> PagoResponse:
        return await registrar_pago_presencial(body, db, x_user_id, x_establecimiento_id)

    @staticmethod
    async def consultar_pagos_admin(
        db: AsyncSession,
        x_establecimiento_id: Optional[str] = None,
        fecha: Optional[date] = None,
        estado: Optional[EstadoPago] = None,
    ) -> List[PagoResponse]:
        return await consultar_pagos_admin(db, x_establecimiento_id, fecha, estado)

    @staticmethod
    async def consultar_pago_por_id(pago_id: uuid.UUID, db: AsyncSession) -> PagoResponse:
        return await consultar_pago_por_id(pago_id, db)

    @staticmethod
    async def consultar_pago_por_reserva(reserva_id: uuid.UUID, db: AsyncSession) -> PagoResponse:
        return await consultar_pago_por_reserva(reserva_id, db)

WOMPI_METHOD_MAP: dict[str, MetodoPago] = {
    "NEQUI": MetodoPago.WOMPI_NEQUI,
    "WOMPI_NEQUI": MetodoPago.WOMPI_NEQUI,
    "PSE": MetodoPago.WOMPI_PSE,
    "WOMPI_PSE": MetodoPago.WOMPI_PSE,
    "BANCOLOMBIA_TRANSFER": MetodoPago.WOMPI_BANCOLOMBIA,
    "BANCOLOMBIA_BUTTON": MetodoPago.WOMPI_BANCOLOMBIA,
    "BANCOLOMBIA": MetodoPago.WOMPI_BANCOLOMBIA,
    "WOMPI_BANCOLOMBIA": MetodoPago.WOMPI_BANCOLOMBIA,
    "CARD": MetodoPago.WOMPI_CARD,
    "WOMPI_CARD": MetodoPago.WOMPI_CARD,
    "TARJETA": MetodoPago.TARJETA,
    "BRE_B": MetodoPago.BRE_B,
}


def _generate_wompi_referencia() -> str:
    return f"WOMPI-POP-{uuid.uuid4().hex[:8].upper()}"


def _parse_date_only(val: Optional[str]) -> Optional[date]:
    if not val:
        return None
    val_str = str(val).strip()[:10]
    try:
        return datetime.strptime(val_str, "%Y-%m-%d").date()
    except Exception:
        return None


def _map_wompi_method(raw_method: Optional[str]) -> MetodoPago:
    normalized = str(raw_method or "WOMPI_CARD").strip().upper()
    return WOMPI_METHOD_MAP.get(normalized, MetodoPago.WOMPI_CARD)


def _resolve_nested_value(obj: Any, dotted_path: str) -> Any:
    """Resolve Wompi dotted property paths like 'transaction.id' against data."""
    current = obj
    for part in dotted_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _validate_wompi_webhook_signature(body: WompiWebhookRequest) -> None:
    """
    Validate Wompi webhook checksum when WOMPI_EVENTS_SECRET & signature are provided.
    Official Wompi spec: SHA256(concat(properties_values) + timestamp + events_secret).
    """
    secret = (settings.WOMPI_EVENTS_SECRET or "").strip()
    if not secret or not body.signature:
        return

    checksum = str(body.signature.get("checksum", "")).strip().lower()
    properties = body.signature.get("properties") or []
    ts = body.timestamp

    if not checksum or not properties or ts is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Firma de webhook Wompi incompleta.",
        )

    concat_values = ""
    for prop in properties:
        val = _resolve_nested_value(body.data or {}, str(prop))
        concat_values += "" if val is None else str(val)

    expected = hashlib.sha256(f"{concat_values}{ts}{secret}".encode("utf-8")).hexdigest().lower()
    if expected != checksum:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma SHA-256 de Wompi inválida.",
        )


async def _enrich_event_context(
    reserva_id: uuid.UUID,
    usuario_id: Optional[uuid.UUID],
    complejo_id: Optional[uuid.UUID],
    fallback_email: Optional[str] = None,
) -> dict[str, Any]:
    """
    Fetch user, reservation, and court/complex details over internal HTTP so
    PagoAprobado arrives with complete context for RabbitMQ consumers.
    """
    ctx: dict[str, Any] = {
        "email_usuario": fallback_email,
        "nombre_usuario": "Deportista",
    }

    async with httpx.AsyncClient(timeout=2.5) as client:
        # 1. Reservation details (includes cancha_id, codigo_uid, fecha, horas, usuario_id)
        try:
            res_r = await client.get(f"{settings.MS_RESERVAS_URL}/reservas/internal/{reserva_id}")
            if res_r.status_code == 200:
                rdata = res_r.json()
                ctx["codigo_uid"] = rdata.get("codigo_uid")
                ctx["cancha_id"] = rdata.get("cancha_id")
                ctx["complejo_id"] = rdata.get("complejo_id") or (str(complejo_id) if complejo_id else None)
                ctx["fecha"] = rdata.get("fecha")
                ctx["hora_inicio"] = rdata.get("hora_inicio")
                ctx["hora_fin"] = rdata.get("hora_fin")
                ctx["precio_total"] = rdata.get("monto")
                if not usuario_id and rdata.get("usuario_id"):
                    try:
                        usuario_id = uuid.UUID(str(rdata["usuario_id"]))
                    except ValueError:
                        pass
        except Exception as exc:
            logger.debug("Could not fetch reservation context %s: %s", reserva_id, exc)

        # 2. User email & name
        if usuario_id:
            ctx["usuario_id"] = str(usuario_id)
            try:
                user_r = await client.get(f"{settings.MS_USUARIOS_URL}/usuarios/{usuario_id}")
                if user_r.status_code == 200:
                    udata = user_r.json()
                    ctx["email_usuario"] = udata.get("email") or ctx.get("email_usuario")
                    ctx["nombre_usuario"] = udata.get("nombre") or ctx["nombre_usuario"]
            except Exception as exc:
                logger.debug("Could not fetch user context %s: %s", usuario_id, exc)

        # 3. Complex & court names
        target_complejo_id = ctx.get("complejo_id") or (str(complejo_id) if complejo_id else None)
        target_cancha_id = ctx.get("cancha_id")
        if target_complejo_id:
            try:
                comp_r = await client.get(f"{settings.MS_CANCHAS_URL}/canchas/complejos/{target_complejo_id}")
                if comp_r.status_code == 200:
                    cdata = comp_r.json()
                    ctx["nombre_complejo"] = cdata.get("nombre")
                    for cancha in cdata.get("canchas") or []:
                        if str(cancha.get("id")) == str(target_cancha_id):
                            ctx["nombre_cancha"] = cancha.get("nombre")
                            break
            except Exception as exc:
                logger.debug("Could not fetch complejo context %s: %s", target_complejo_id, exc)

    return ctx


async def _sync_reserva_estado(reserva_id: uuid.UUID, estado_pago: str) -> None:
    """Synchronously mark APPROVED reservation as CONFIRMADA in ms_reservas."""
    if estado_pago != "APPROVED":
        return
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            await client.post(
                f"{settings.MS_RESERVAS_URL}/reservas/internal/{reserva_id}/estado-pago",
                params={"estado": "APPROVED"},
            )
    except Exception as exc:
        logger.warning("Synchronous ms_reservas confirmation skipped (%s): %s", reserva_id, exc)


async def _emit_payment_outcome_event(
    pago: Pago,
    estado: EstadoPago,
    observaciones: Optional[str] = None,
    fallback_email: Optional[str] = None,
) -> None:
    """Publish PagoAprobado (with user + court details) or PagoRechazado to RabbitMQ."""
    if estado == EstadoPago.APROBADO:
        await _sync_reserva_estado(pago.reserva_id, "APPROVED")
        context = await _enrich_event_context(
            reserva_id=pago.reserva_id,
            usuario_id=pago.usuario_id,
            complejo_id=pago.complejo_id,
            fallback_email=fallback_email,
        )
        payload: dict[str, Any] = {
            **context,
            "pago_id": str(pago.id),
            "reserva_id": str(pago.reserva_id),
            "usuario_id": str(pago.usuario_id) if pago.usuario_id else context.get("usuario_id"),
            "complejo_id": str(pago.complejo_id),
            "monto": float(pago.monto),
            "precio_total": context.get("precio_total") or float(pago.monto),
            "metodo": pago.metodo.value,
            "metodo_pago": pago.metodo.value,
            "referencia_externa": pago.referencia_externa,
            "id_transaccion": pago.referencia_externa,
            "estado": "CONFIRMADA",
        }
        print(
            f"\n💰 [MS_PAGOS SAGA] Transacción de pago {pago.id} APROBADA (Reserva: {pago.reserva_id}, Monto: ${pago.monto:,.0f}).\n"
            f"📢 [MS_PAGOS SAGA] Publicando evento de dominio 'PagoAprobado' hacia RabbitMQ (exchange='canchas_events', routing_key='pago.aprobado')...",
            flush=True,
        )
        await publish_event(
            event_type="PagoAprobado",
            aggregate_id=str(pago.id),
            data=payload,
        )
        print(
            f"✅ [MS_PAGOS SAGA] Evento 'PagoAprobado' publicado exitosamente para Reserva {pago.reserva_id}\n",
            flush=True,
        )
    else:
        context = await _enrich_event_context(
            reserva_id=pago.reserva_id,
            usuario_id=pago.usuario_id,
            complejo_id=pago.complejo_id,
            fallback_email=fallback_email,
        )
        print(
            f"\n❌ [MS_PAGOS SAGA] Transacción de pago {pago.id} RECHAZADA (Reserva: {pago.reserva_id}). "
            f"Publicando evento 'PagoRechazado'...",
            flush=True,
        )
        await publish_event(
            event_type="PagoRechazado",
            aggregate_id=str(pago.id),
            data={
                **context,
                "pago_id": str(pago.id),
                "reserva_id": str(pago.reserva_id),
                "usuario_id": str(pago.usuario_id) if pago.usuario_id else context.get("usuario_id"),
                "metodo": pago.metodo.value,
                "metodo_pago": pago.metodo.value,
                "referencia_externa": pago.referencia_externa,
                "estado": "CANCELADA",
                "motivo": observaciones or "Pago rechazado por la pasarela Wompi",
                "razon_rechazo": observaciones or "Pago rechazado por la pasarela Wompi",
            },
        )
        print(
            f"⚠️ [MS_PAGOS SAGA] Evento 'PagoRechazado' publicado para Reserva {pago.reserva_id}\n",
            flush=True,
        )


def obtener_config_wompi() -> WompiConfigResponse:
    """Expose public Wompi configuration to frontend checkout."""
    return WompiConfigResponse(
        public_key=settings.WOMPI_PUBLIC_KEY,
        sandbox=settings.WOMPI_SANDBOX,
    )


def preparar_checkout_wompi(body: WompiPrepararRequest) -> WompiPrepararResponse:
    """Generate unique WOMPI-POP-... reference and optional SHA-256 integrity signature."""
    referencia = (body.referencia_externa or "").strip() or _generate_wompi_referencia()
    amount_in_cents = int(round(body.monto * 100))
    currency = "COP"

    integrity_signature: Optional[str] = None
    integrity_secret = (settings.WOMPI_INTEGRITY_SECRET or "").strip()
    if integrity_secret:
        raw_str = f"{referencia}{amount_in_cents}{currency}{integrity_secret}"
        integrity_signature = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    return WompiPrepararResponse(
        referencia_externa=referencia,
        amount_in_cents=amount_in_cents,
        currency=currency,
        public_key=settings.WOMPI_PUBLIC_KEY,
        integrity_signature=integrity_signature,
        sandbox=settings.WOMPI_SANDBOX,
    )


async def procesar_pago(
    body: ProcesarPagoRequest,
    x_user_id: Optional[str],
    db: AsyncSession,
) -> PagoResponse:
    if body.metodo not in ONLINE_METHODS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Método de pago en línea no soportado: {body.metodo}",
        )

    usuario_uuid: Optional[uuid.UUID] = body.usuario_id
    if usuario_uuid is None and x_user_id:
        try:
            usuario_uuid = uuid.UUID(x_user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-User-Id header is not a valid UUID.",
            )

    referencia = (body.referencia_externa or "").strip() or _generate_wompi_referencia()
    estado = (
        EstadoPago.APROBADO
        if body.simular_resultado == "APROBADO"
        else EstadoPago.RECHAZADO
    )

    obs_parts = []
    if body.observaciones:
        obs_parts.append(body.observaciones)
    if body.datos_metodo:
        obs_parts.append(
            " | ".join(f"{k}: {v}" for k, v in body.datos_metodo.items() if v)
        )
    obs_text = " · ".join(obs_parts)[:512] if obs_parts else None

    pago = Pago(
        id=uuid.uuid4(),
        reserva_id=body.reserva_id,
        usuario_id=usuario_uuid,
        admin_id=None,
        complejo_id=body.complejo_id,
        monto=body.monto,
        metodo=body.metodo,
        estado=estado,
        referencia_externa=referencia,
        observaciones=obs_text,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(pago)
    await db.commit()
    await db.refresh(pago)

    fallback_email = (body.datos_metodo or {}).get("email_usuario")
    await _emit_payment_outcome_event(
        pago=pago,
        estado=estado,
        observaciones=obs_text,
        fallback_email=fallback_email,
    )

    return PagoResponse.model_validate(pago)


async def procesar_wompi_webhook(
    body: WompiWebhookRequest,
    x_user_id: Optional[str],
    db: AsyncSession,
) -> PagoResponse:
    """
    Process Wompi Colombia webhook callback or direct sandbox Wompi confirmation.
    Validates signature (if configured), records payment method (WOMPI_NEQUI,
    WOMPI_PSE, WOMPI_BANCOLOMBIA, WOMPI_CARD), updates reservation to CONFIRMADA
    when APPROVED, and publishes pago.aprobado / pago.rechazado on RabbitMQ.
    """
    _validate_wompi_webhook_signature(body)

    tx = (body.data or {}).get("transaction") if isinstance(body.data, dict) else None
    if not isinstance(tx, dict):
        tx = {}

    raw_status = str(tx.get("status") or body.status or "DECLINED").strip().upper()
    estado_pago = (
        EstadoPago.APROBADO if raw_status in ("APPROVED", "APROBADO") else EstadoPago.RECHAZADO
    )

    raw_method = (
        body.metodo_pago
        or tx.get("payment_method_type")
        or body.payment_method_type
        or "WOMPI_CARD"
    )
    metodo = _map_wompi_method(raw_method)

    referencia = str(
        tx.get("reference") or body.reference or _generate_wompi_referencia()
    ).strip()

    # Check if a payment with this reference already exists
    existing_pago = (
        await db.execute(select(Pago).where(Pago.referencia_externa == referencia))
    ).scalar_one_or_none()

    reserva_uuid: Optional[uuid.UUID] = body.reserva_id
    usuario_uuid: Optional[uuid.UUID] = body.usuario_id
    complejo_uuid: Optional[uuid.UUID] = body.complejo_id

    if existing_pago is not None:
        reserva_uuid = reserva_uuid or existing_pago.reserva_id
        usuario_uuid = usuario_uuid or existing_pago.usuario_id
        complejo_uuid = complejo_uuid or existing_pago.complejo_id

    if usuario_uuid is None and x_user_id:
        try:
            usuario_uuid = uuid.UUID(x_user_id)
        except ValueError:
            pass

    if reserva_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El webhook debe incluir reserva_id o una referencia existente.",
        )

    # Resolve monto and missing IDs from ms_reservas if needed
    amount_in_cents = tx.get("amount_in_cents") or body.amount_in_cents
    monto = (
        float(amount_in_cents) / 100.0
        if amount_in_cents
        else float(body.monto or (existing_pago.monto if existing_pago else 0))
    )

    if complejo_uuid is None or monto <= 0 or usuario_uuid is None:
        ctx = await _enrich_event_context(reserva_uuid, usuario_uuid, complejo_uuid)
        if complejo_uuid is None and ctx.get("complejo_id"):
            complejo_uuid = uuid.UUID(str(ctx["complejo_id"]))
        if usuario_uuid is None and ctx.get("usuario_id"):
            usuario_uuid = uuid.UUID(str(ctx["usuario_id"]))
        if monto <= 0 and ctx.get("precio_total"):
            monto = float(ctx["precio_total"])

    if complejo_uuid is None:
        complejo_uuid = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    if monto <= 0:
        monto = 1.0

    tx_id = tx.get("id") or body.transaction_id
    obs = body.observaciones or (
        f"Wompi Tx {tx_id} ({raw_status})" if tx_id else f"Wompi Webhook ({raw_status})"
    )

    if existing_pago is not None:
        existing_pago.metodo = metodo
        existing_pago.estado = estado_pago
        existing_pago.observaciones = obs[:512]
        existing_pago.updated_at = datetime.now(timezone.utc)
        pago = existing_pago
    else:
        pago = Pago(
            id=uuid.uuid4(),
            reserva_id=reserva_uuid,
            usuario_id=usuario_uuid,
            admin_id=None,
            complejo_id=complejo_uuid,
            monto=monto,
            metodo=metodo,
            estado=estado_pago,
            referencia_externa=referencia,
            observaciones=obs[:512],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(pago)

    await db.flush()

    customer_email = tx.get("customer_email") or body.customer_email
    await _emit_payment_outcome_event(
        pago=pago,
        estado=estado_pago,
        observaciones=obs,
        fallback_email=customer_email,
    )

    return PagoResponse.model_validate(pago)


async def obtener_mis_pagos(
    x_user_id: Optional[str],
    db: AsyncSession,
) -> List[PagoResponse]:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id header is required.",
        )

    try:
        user_uuid = uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-Id header is not a valid UUID.",
        )

    result = await db.execute(
        select(Pago)
        .where(Pago.usuario_id == user_uuid)
        .order_by(Pago.created_at.desc())
    )
    pagos = result.scalars().all()
    return [PagoResponse.model_validate(p) for p in pagos]


async def generar_reporte_pagos(
    complejo_id: Optional[str],
    fecha_inicio: Optional[str],
    fecha_fin: Optional[str],
    estado: Optional[EstadoPago],
    x_establecimiento_id: Optional[str],
    db: AsyncSession,
) -> List[PagoResponse]:
    resolved_comp_uuid: Optional[uuid.UUID] = None
    candidate_comp = complejo_id or x_establecimiento_id
    if candidate_comp:
        try:
            resolved_comp_uuid = uuid.UUID(str(candidate_comp).strip())
        except Exception:
            pass

    filters = []
    if estado is not None:
        filters.append(Pago.estado == estado)

    d_inicio = _parse_date_only(fecha_inicio)
    d_fin = _parse_date_only(fecha_fin)
    if d_inicio:
        filters.append(cast(Pago.created_at, Date) >= d_inicio)
    if d_fin:
        filters.append(cast(Pago.created_at, Date) <= d_fin)

    if resolved_comp_uuid:
        query_comp = (
            select(Pago)
            .where(and_(Pago.complejo_id == resolved_comp_uuid, *filters))
            .order_by(Pago.created_at.desc())
        )
        res = await db.execute(query_comp)
        pagos = res.scalars().all()
        if pagos or filters:
            return [PagoResponse.model_validate(p) for p in pagos]

    query_general = select(Pago).order_by(Pago.created_at.desc())
    if filters:
        query_general = select(Pago).where(and_(*filters)).order_by(Pago.created_at.desc())
    res_gen = await db.execute(query_general)
    pagos_gen = res_gen.scalars().all()

    return [PagoResponse.model_validate(p) for p in pagos_gen]


async def registrar_pago_presencial(
    body: PagoPresencialRequest,
    x_user_id: Optional[str],
    db: AsyncSession,
) -> PagoResponse:
    admin_uuid = uuid.UUID("33333333-3333-3333-3333-333333333333")
    if x_user_id:
        try:
            admin_uuid = uuid.UUID(x_user_id)
        except ValueError:
            pass

    complejo_uuid = body.complejo_id or uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

    pago_fecha = datetime.now(timezone.utc)
    if body.fecha:
        try:
            d_parts = str(body.fecha).strip()[:10].split("-")
            if len(d_parts) == 3:
                pago_fecha = datetime(
                    int(d_parts[0]), int(d_parts[1]), int(d_parts[2]),
                    12, 0, 0, tzinfo=timezone.utc
                )
        except Exception:
            pass

    raw_metodo = str(body.metodo.value if hasattr(body.metodo, "value") else body.metodo).upper().strip()
    if raw_metodo in ("NEQUI", "WOMPI_NEQUI"):
        resolved_metodo = MetodoPago.WOMPI_NEQUI
    elif raw_metodo in ("TARJETA", "CARD", "WOMPI_CARD"):
        resolved_metodo = MetodoPago.TARJETA
    elif raw_metodo == "TRANSFERENCIA":
        resolved_metodo = MetodoPago.TRANSFERENCIA
    else:
        resolved_metodo = MetodoPago.EFECTIVO

    pago = Pago(
        id=uuid.uuid4(),
        reserva_id=body.reserva_id,
        usuario_id=None,
        admin_id=admin_uuid,
        complejo_id=complejo_uuid,
        monto=body.monto,
        metodo=resolved_metodo,
        estado=EstadoPago.APROBADO,
        referencia_externa=f"PRE-{uuid.uuid4().hex[:6].upper()}",
        observaciones=body.observaciones or "Pago presencial registrado en taquilla",
        created_at=pago_fecha,
        updated_at=pago_fecha,
    )

    db.add(pago)
    await db.commit()
    await db.refresh(pago)

    try:
        await _sync_reserva_estado(pago.reserva_id, "APPROVED")
    except Exception as exc:
        logger.warning("No se pudo sincronizar reserva presencial de inmediato: %s", exc)

    try:
        await publish_event(
            event_type="PagoPresencialValidado",
            aggregate_id=str(pago.id),
            data={
                "pago_id": str(pago.id),
                "reserva_id": str(pago.reserva_id),
                "complejo_id": str(pago.complejo_id),
                "monto": float(pago.monto),
                "metodo": pago.metodo.value,
                "admin_id": str(admin_uuid),
            },
        )
    except Exception:
        pass

    return PagoResponse.model_validate(pago)


async def obtener_pago_por_reserva(
    reserva_id: uuid.UUID,
    db: AsyncSession,
) -> Optional[PagoResponse]:
    """Retrieve the most recent payment associated with a given reservation."""
    result = await db.execute(
        select(Pago).where(Pago.reserva_id == reserva_id).order_by(Pago.created_at.desc())
    )
    pago = result.scalars().first()
    if not pago:
        return None
    return PagoResponse.model_validate(pago)
