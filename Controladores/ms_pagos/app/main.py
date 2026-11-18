"""
ms_pagos — Payment Processing Microservice
Canchas Popayán EDA Platform

Responsibilities:
    - Online payment processing via simulated gateway (HU-10)
    - Admin payment reports (HU-19)
    - Presencial payment registration (HU-20)

Events published:
    - PagoAprobado          → pago.aprobado
    - PagoRechazado         → pago.rechazado
    - PagoPresencialValidado → pago.presencial.validado
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_all_tables, AsyncSessionLocal
from app.rabbitmq import close_rabbitmq, init_rabbitmq
from app.routers import pagos
from app.seed import seed_pagos

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("ms_pagos")

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ms_pagos — Canchas Popayán",
    description=(
        "Microservicio de procesamiento de pagos para la plataforma de reservas "
        "de canchas deportivas en Popayán, Colombia. "
        "Gestiona pagos en línea (pasarela simulada) y pagos presenciales."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS — permissive for development; tighten for production
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Startup / shutdown lifecycle
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def on_startup() -> None:
    """
    Executed once when the application starts.

    1. Creates all database tables (idempotent — safe to run repeatedly).
    2. Establishes the RabbitMQ connection and declares the exchange.
    """
    logger.info("ms_pagos starting up …")
    await create_all_tables()
    logger.info("Database tables verified / created.")
    # Seed demonstration payments
    try:
        async with AsyncSessionLocal() as session:
            await seed_pagos(session)
    except Exception as exc:
        logger.warning("ms_pagos seed warning: %s", exc)
    await init_rabbitmq()
    logger.info("ms_pagos is ready.")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """Gracefully release the RabbitMQ connection on shutdown."""
    logger.info("ms_pagos shutting down …")
    await close_rabbitmq()
    logger.info("ms_pagos stopped.")


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(pagos.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    description="Returns the operational status of the ms_pagos service.",
)
async def health() -> dict:
    """
    Lightweight liveness probe.

    Returns 200 OK with service metadata so load balancers and orchestrators
    can confirm the service is running.
    """
    return {
        "service": "ms_pagos",
        "status": "ok",
        "version": "1.0.0",
    }
