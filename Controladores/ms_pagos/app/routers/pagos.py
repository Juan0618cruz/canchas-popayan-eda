"""
Capa MVC: Enrutador HTTP (Router) — Endpoints de procesamiento de pagos y pasarela Wompi Colombia.

Delega la validación criptográfica, el registro en base de datos y la emisión de eventos a PagosController.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import pagos_controller
from app.database import get_db
from app.models import EstadoPago
from app.schemas import (
    PagoPresencialRequest,
    PagoResponse,
    ProcesarPagoRequest,
    WompiConfigResponse,
    WompiPrepararRequest,
    WompiPrepararResponse,
    WompiWebhookRequest,
)

router = APIRouter(prefix="/pagos", tags=["Pagos"])


@router.get(
    "/wompi/config",
    response_model=WompiConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Configuración pública de la pasarela Wompi Colombia",
)
async def wompi_config() -> WompiConfigResponse:
    return pagos_controller.obtener_config_wompi()


@router.post(
    "/wompi/preparar",
    response_model=WompiPrepararResponse,
    status_code=status.HTTP_200_OK,
    summary="Generar referencia única WOMPI-POP-... y firma de integridad",
)
async def wompi_preparar(body: WompiPrepararRequest) -> WompiPrepararResponse:
    return pagos_controller.preparar_checkout_wompi(body)


@router.post(
    "/wompi/webhook",
    response_model=PagoResponse,
    status_code=status.HTTP_200_OK,
    summary="Webhook oficial Wompi Colombia / Confirmación Checkout",
)
async def wompi_webhook(
    body: WompiWebhookRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> PagoResponse:
    return await pagos_controller.procesar_wompi_webhook(body, x_user_id, db)


@router.post(
    "/procesar",
    response_model=PagoResponse,
    status_code=status.HTTP_200_OK,
    summary="HU-10: Procesar pago en línea (Wompi Sandbox / Checkout)",
)
async def procesar_pago(
    body: ProcesarPagoRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> PagoResponse:
    return await pagos_controller.procesar_pago(body, x_user_id, db)


@router.get(
    "/mis-pagos",
    response_model=List[PagoResponse],
    status_code=status.HTTP_200_OK,
    summary="Historial de pagos del usuario autenticado",
)
async def mis_pagos(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> List[PagoResponse]:
    return await pagos_controller.obtener_mis_pagos(x_user_id, db)


@router.get(
    "/admin/reportes",
    response_model=List[PagoResponse],
    status_code=status.HTTP_200_OK,
    summary="HU-19: Reporte de pagos para administradores de complejo",
)
@router.get(
    "",
    response_model=List[PagoResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar pagos",
)
@router.get(
    "/admin/todos",
    response_model=List[PagoResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar todos los pagos",
)
async def reporte_pagos(
    complejo_id: Optional[str] = Query(None),
    fecha_inicio: Optional[str] = Query(None),
    fecha_fin: Optional[str] = Query(None),
    estado: Optional[EstadoPago] = Query(None),
    x_establecimiento_id: Optional[str] = Header(None, alias="X-Establecimiento-Id"),
    db: AsyncSession = Depends(get_db),
) -> List[PagoResponse]:
    return await pagos_controller.generar_reporte_pagos(
        complejo_id=complejo_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        estado=estado,
        x_establecimiento_id=x_establecimiento_id,
        db=db,
    )


@router.post(
    "/admin/presencial",
    response_model=PagoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="HU-20: Registrar pago presencial",
)
@router.post(
    "/presencial",
    response_model=PagoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="HU-20: Registrar pago presencial (alias)",
)
async def registrar_pago_presencial(
    body: PagoPresencialRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> PagoResponse:
    return await pagos_controller.registrar_pago_presencial(body, x_user_id, db)


@router.get(
    "/reserva/{reserva_id}",
    response_model=Optional[PagoResponse],
    status_code=status.HTTP_200_OK,
    summary="Consultar pago asociado a una reserva",
)
async def obtener_pago_por_reserva(
    reserva_id: str,
    db: AsyncSession = Depends(get_db),
) -> Optional[PagoResponse]:
    import uuid
    try:
        reserva_uuid = uuid.UUID(str(reserva_id))
    except ValueError:
        return None
    return await pagos_controller.obtener_pago_por_reserva(reserva_uuid, db)
