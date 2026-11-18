"""
app/main.py - FastAPI application entry point for ms_canchas.

Startup sequence:
  1. Create all DB tables (create_all)
  2. Run seed if DB is empty
  3. Launch RabbitMQ consumer as a background asyncio task

Routers:
  /canchas       → public query endpoints  (routers/canchas.py)
  /canchas/admin → admin command endpoints (routers/admin.py)
"""
import asyncio
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.database import engine, AsyncSessionLocal, Base
from app.rabbitmq import start_consumer
from app.routers import admin as admin_router
from app.routers import canchas as canchas_router
from app.schemas import HealthResponse
from app.seed import seed_database

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ms_canchas — Canchas Popayán",
    description=(
        "Microservice that manages sports complexes, courts, and time slot "
        "availability for the Canchas Popayán EDA platform."
    ),
    version="1.0.0",
    docs_url="/canchas/docs",
    openapi_url="/canchas/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS (allow all origins for internal / development use)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------
_consumer_task: asyncio.Task | None = None


@app.on_event("startup")
async def on_startup() -> None:
    global _consumer_task

    # 1. Create database tables and ensure image columns exist
    logger.info("[startup] Creating database tables…")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE complejos ADD COLUMN IF NOT EXISTS imagen_url VARCHAR(500);"))
        await conn.execute(text("ALTER TABLE canchas ADD COLUMN IF NOT EXISTS imagen_url VARCHAR(500);"))
    logger.info("[startup] Database tables ready.")

    # 2. Seed pilot data
    logger.info("[startup] Running database seed…")
    try:
        async with AsyncSessionLocal() as session:
            await seed_database(session)
    except Exception as exc:
        logger.warning("[startup] Seed database warning: %s", exc)

    # 3. Start RabbitMQ consumer
    logger.info("[startup] Starting RabbitMQ consumer…")
    _consumer_task = asyncio.create_task(start_consumer(), name="rabbitmq_consumer")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    global _consumer_task
    if _consumer_task and not _consumer_task.done():
        logger.info("[shutdown] Cancelling RabbitMQ consumer task…")
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
    logger.info("[shutdown] ms_canchas shut down cleanly.")


# ---------------------------------------------------------------------------
# Static uploads directory
# ---------------------------------------------------------------------------
UPLOADS_DIR = os.environ.get("UPLOADS_DIR", "/app/uploads")
BACKGROUNDS_DIR = os.path.join(UPLOADS_DIR, "backgrounds")
os.makedirs(BACKGROUNDS_DIR, exist_ok=True)
app.mount("/canchas/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
# Admin router is included FIRST so /canchas/admin/… routes take precedence
# over parameterised public routes like /canchas/{cancha_id}/…
app.include_router(admin_router.router, prefix="/canchas")
app.include_router(canchas_router.router, prefix="/canchas")


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Service health check",
)
async def health_check() -> HealthResponse:
    return HealthResponse(
        service=settings.SERVICE_NAME,
        status="ok",
        version=settings.SERVICE_VERSION,
    )
