"""
ms_reservas — FastAPI application entry point.

Startup sequence
----------------
1. Create all DB tables (create_all via SQLAlchemy metadata).
2. Seed the ContadorReservas singleton row (id=1, contador=0) if absent.
3. Launch the Outbox Publisher background task (polls every 2 s).
4. Launch the RabbitMQ Saga Consumer background task.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from app.database import AsyncSessionLocal, engine, Base
from app.models import ContadorReservas
from app.outbox_publisher import run_outbox_publisher
from app.rabbitmq_consumer import run_consumer
from app.routers import reservas, admin_reservas

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Background tasks registry (kept alive for the lifetime of the process)
# ---------------------------------------------------------------------------
_background_tasks: list[asyncio.Task] = []


async def _create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uix_cancha_fecha_hora_activa "
                "ON reservas (cancha_id, fecha, hora_inicio) "
                "WHERE estado NOT IN ('CANCELADA', 'CANCELADA_ADMIN')"
            )
        )
    logger.info("DB tables and concurrency unique index verified / created.")


async def _seed_contador() -> None:
    """Ensure the ContadorReservas singleton row (id=1) exists."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ContadorReservas).where(ContadorReservas.id == 1)
        )
        if result.scalar_one_or_none() is None:
            session.add(ContadorReservas(id=1, contador=0))
            await session.commit()
            logger.info("ContadorReservas singleton created.")
        else:
            logger.info("ContadorReservas singleton already exists.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    await _create_tables()
    await _seed_contador()

    outbox_task = asyncio.create_task(run_outbox_publisher(), name="outbox_publisher")
    consumer_task = asyncio.create_task(run_consumer(), name="saga_consumer")
    _background_tasks.extend([outbox_task, consumer_task])
    logger.info("Background tasks started: outbox_publisher, saga_consumer")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    for task in _background_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    await engine.dispose()
    logger.info("ms_reservas shut down cleanly.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ms_reservas",
    description="Core Reservations Microservice — CQRS + Saga + Transactional Outbox",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reservas.router, tags=["Reservas"])
app.include_router(admin_reservas.router, tags=["Admin Reservas"])


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "ms_reservas"}
