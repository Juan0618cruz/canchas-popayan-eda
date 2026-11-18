"""
ms_notificaciones — FastAPI application entry point (MVC).
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from app.rabbitmq_consumer import start_consumer
from app.routers.notificaciones import router as notificaciones_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("ms_notificaciones")

_consumer_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the RabbitMQ consumer background task on startup and cancel it on shutdown."""
    global _consumer_task  # noqa: PLW0603

    logger.info("Iniciando ms_notificaciones …")
    _consumer_task = asyncio.create_task(start_consumer(), name="rabbitmq_consumer")
    logger.info("Consumer RabbitMQ iniciado como tarea de fondo.")

    yield

    logger.info("Apagando ms_notificaciones …")
    if _consumer_task and not _consumer_task.done():
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
    logger.info("ms_notificaciones detenido.")


app = FastAPI(
    title="ms_notificaciones — Canchas Popayán",
    description=(
        "Microservicio de notificaciones. Consume eventos de RabbitMQ y simula "
        "el envío de correos electrónicos. Expone endpoints para inspeccionar "
        "el historial de correos despachados."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(notificaciones_router)


@app.get("/health", tags=["Salud"], summary="Health check")
async def health_check():
    """Retorna el estado de salud del servicio."""
    return {
        "status": "ok",
        "service": "ms_notificaciones",
        "version": "1.0.0",
    }
