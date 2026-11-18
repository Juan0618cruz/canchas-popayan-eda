"""
Entry point for the ms_usuarios microservice.

Lifecycle
---------
startup  → create DB tables (create_all) + establish RabbitMQ connection
shutdown → close RabbitMQ connection gracefully

Routers
-------
/auth      – Registration, login, password recovery
/usuarios  – Profile management
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import create_tables, AsyncSessionLocal, get_db
from app.rabbitmq import close_rabbitmq, start_publisher
from app.routers.auth import router as auth_router, login as auth_login
from app.routers.usuarios import router as usuarios_router
from app.schemas import LoginRequest, LoginResponse
from app.seed import run_seed

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown tasks for the FastAPI application."""

    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("Starting %s v%s …", settings.APP_NAME, settings.APP_VERSION)

    # 1. Create database tables
    logger.info("Creating database tables (create_all) …")
    await create_tables()
    logger.info("Database tables ready.")

    # 2. Run seed data (creates test users if DB is empty)
    logger.info("Running seed data …")
    async with AsyncSessionLocal() as session:
        await run_seed(session)

    # 3. Connect to RabbitMQ
    logger.info("Connecting to RabbitMQ …")
    await start_publisher()

    logger.info("%s is ready to serve requests.", settings.APP_NAME)

    yield  # ── Application runs here ────────────────────────────────────────

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("Shutting down %s …", settings.APP_NAME)
    await close_rabbitmq()
    logger.info("Goodbye.")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ms_usuarios – Canchas Popayán",
    description=(
        "Microservicio de gestión de usuarios para la plataforma de reserva "
        "de canchas deportivas en Popayán, Colombia."
    ),
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS – restrict in production to specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router)
app.include_router(usuarios_router)


# ---------------------------------------------------------------------------
# Login aliases
# ---------------------------------------------------------------------------

@app.post("/login", response_model=LoginResponse, tags=["auth"])
@app.post("/usuarios/login", response_model=LoginResponse, tags=["auth"])
async def login_alias_endpoint(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Direct alias for /auth/login to support requests to /login and /usuarios/login."""
    return await auth_login(body, db)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    tags=["health"],
    summary="Health check",
    response_model=dict,
)
async def health() -> dict:
    """
    Returns a simple JSON payload confirming the service is alive.

    Used by Docker health checks, Kubernetes liveness probes, and load balancers.
    """
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
