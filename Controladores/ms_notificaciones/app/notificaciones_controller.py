"""
Capa MVC: Controlador — NotificacionesController (Consulta de bitácora y estadísticas de correos despachados).

Responsable de la auditoría de notificaciones despachadas por eventos EDA, filtrado por eventType
y generación de métricas para sustentación técnica.
"""

from collections import Counter
from typing import Optional

from fastapi.responses import JSONResponse

from app.models import get_all_emails, get_emails_by_event_type


class NotificacionesController:
    """Controlador para el despacho y auditoría de eventos de notificación procesados."""

    @staticmethod
    async def despachar_correo(
        to_email: str,
        to_name: str,
        subject: str,
        plain_body: str,
        html_body: str,
    ) -> tuple[str, Optional[str]]:
        """
        Despacha un correo electrónico vía SMTP asíncrono haciendo uso del servicio SMTP.
        Retorna (status, error_detail).
        """
        from app.smtp_service import send_email_async
        return await send_email_async(
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            plain_body=plain_body,
            html_body=html_body,
        )

    @staticmethod
    def listar_logs_notificaciones(event_type: Optional[str] = None) -> JSONResponse:
        return listar_logs_notificaciones(event_type)

    @staticmethod
    def obtener_estadisticas_notificaciones() -> JSONResponse:
        return obtener_estadisticas_notificaciones()


def listar_logs_notificaciones(event_type: Optional[str] = None) -> JSONResponse:
    logs = get_emails_by_event_type(event_type) if event_type else get_all_emails()
    return JSONResponse(
        content={
            "total": len(logs),
            "filtro_event_type": event_type,
            "correos": [log.to_dict() for log in logs],
        }
    )


def obtener_estadisticas_notificaciones() -> JSONResponse:
    all_logs = get_all_emails()
    if not all_logs:
        return JSONResponse(
            content={
                "total_correos": 0,
                "por_evento": {},
                "mensaje": "No se han procesado notificaciones aún.",
            }
        )

    counter: Counter = Counter(log.event_type for log in all_logs)
    return JSONResponse(
        content={
            "total_correos": len(all_logs),
            "por_evento": dict(counter.most_common()),
        }
    )
