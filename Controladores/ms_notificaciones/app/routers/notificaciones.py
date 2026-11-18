"""
Capa MVC: Enrutador HTTP (Router) — Auditoría de notificaciones y estadísticas de despacho.

Delega la agregación de métricas y la consulta de bitácora a NotificacionesController.
"""

from typing import Optional

from fastapi import APIRouter, Query

from app import notificaciones_controller

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])


@router.get(
    "/logs",
    summary="Listar correos despachados",
    response_description="Lista de correos simulados, del más reciente al más antiguo.",
)
async def list_notification_logs(
    event_type: Optional[str] = Query(
        default=None,
        description="Filtrar por tipo de evento (p. ej. PagoAprobado, ReservaSolicitada).",
    )
):
    return notificaciones_controller.listar_logs_notificaciones(event_type)


@router.get(
    "/logs/stats",
    summary="Estadísticas de correos por tipo de evento",
    response_description="Conteo de correos agrupado por eventType.",
)
async def notification_stats():
    return notificaciones_controller.obtener_estadisticas_notificaciones()
