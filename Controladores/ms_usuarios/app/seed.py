import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RolUsuario, Usuario
from app.security import hash_password

logger = logging.getLogger(__name__)

_DEPORTISTA_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
_ADMIN_BALON_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
_ADMIN_JP_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
_ESTABLECIMIENTO_BALON_DE_ORO_ID = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

_SEED_USERS: list[dict] = [
    {
        "id": _DEPORTISTA_ID,
        "nombre": "Carlos Muñoz",
        "email": "deportista@test.com",
        "password": "123456",
        "telefono": "3012345678",
        "rol": RolUsuario.USUARIO,
        "establecimiento_id": None,
        "activo": True,
    },
    {
        "id": _ADMIN_BALON_ID,
        "nombre": "Admin Balón de Oro",
        "email": "admin.balon@test.com",
        "password": "123456",
        "telefono": "3109876543",
        "rol": RolUsuario.ADMIN_ESTABLECIMIENTO,
        "establecimiento_id": _ESTABLECIMIENTO_BALON_DE_ORO_ID,
        "activo": True,
    },
    {
        "id": _ADMIN_JP_ID,
        "nombre": "Juan Pablo Admin",
        "email": "jpdiagon1@gmail.com",
        "password": "123456",
        "telefono": "3111234567",
        "rol": RolUsuario.ADMIN_ESTABLECIMIENTO,
        "establecimiento_id": _ESTABLECIMIENTO_BALON_DE_ORO_ID,
        "activo": True,
    },
]

async def run_seed(session: AsyncSession) -> None:
    logger.info("Running user seed verification …")
    now = datetime.now(timezone.utc)

    for user_data in _SEED_USERS:
        result = await session.execute(
            select(Usuario).where(Usuario.email == user_data["email"])
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            usuario = Usuario(
                id=user_data["id"],
                nombre=user_data["nombre"],
                email=user_data["email"],
                hashed_password=hash_password(user_data["password"]),
                telefono=user_data["telefono"],
                rol=user_data["rol"],
                establecimiento_id=user_data["establecimiento_id"],
                activo=True,
                created_at=now,
            )
            session.add(usuario)
            logger.info("  ↳ Created seed user: %s (%s)", usuario.email, usuario.rol.value)
        else:
            existing.activo = True
            existing.hashed_password = hash_password(user_data["password"])
            logger.info("  ↳ Updated seed user: %s (%s)", existing.email, existing.rol.value)

    await session.commit()
    logger.info("Seed verification complete.")
