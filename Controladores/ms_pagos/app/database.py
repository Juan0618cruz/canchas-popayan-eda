"""
Motor asíncrono de SQLAlchemy y fábrica de sesiones para ms_pagos.
Utiliza el driver asyncpg para operaciones no bloqueantes contra PostgreSQL.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Motor asíncrono de base de datos
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Fábrica de sesiones asíncronas
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Clase base para todos los modelos ORM de SQLAlchemy."""
    pass


async def get_db() -> AsyncSession:
    """
    Dependencia de FastAPI que suministra una sesión asíncrona de base de datos.
    Cierra y gestiona automáticamente la transacción tras completar la solicitud.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_all_tables() -> None:
    """Create all database tables and ensure Wompi enum values exist."""
    async with engine.begin() as conn:
        from app.models import Base as ModelBase  # noqa: F401 – ensures models are imported
        await conn.run_sync(ModelBase.metadata.create_all)

    # PostgreSQL requires COMMIT / AUTOCOMMIT outside a transaction block for ALTER TYPE ADD VALUE
    async with engine.connect() as conn:
        autocommit_conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        for enum_val in ("WOMPI", "BRE_B", "EFECTIVO", "WOMPI_NEQUI", "WOMPI_PSE", "WOMPI_BANCOLOMBIA", "WOMPI_CARD"):
            await autocommit_conn.execute(
                text(f"ALTER TYPE metodo_pago_enum ADD VALUE IF NOT EXISTS '{enum_val}'")
            )
