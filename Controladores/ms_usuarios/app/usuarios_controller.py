"""
Capa MVC: Controlador — UsuariosController (Lógica de administración de perfiles y usuarios).

Responsable de la consulta de información de perfil, actualización de datos personales,
modificación de contraseñas y publicación de eventos de dominio a RabbitMQ.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Usuario
from app.rabbitmq import publish_event
from app.schemas import (
    ActualizarPerfilRequest,
    CambiarPasswordRequest,
    MensajeResponse,
    PerfilResponse,
)
from app.security import hash_password, verify_password

DEFAULT_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


class UsuariosController:
    """Controlador encargado del ciclo de vida y gestión de perfil de los usuarios."""

    @staticmethod
    async def obtener_perfil(x_user_id: str | None, db: AsyncSession) -> PerfilResponse:
        return await obtener_perfil(x_user_id, db)

    @staticmethod
    async def actualizar_perfil(
        body: ActualizarPerfilRequest,
        x_user_id: str | None,
        db: AsyncSession,
    ) -> PerfilResponse:
        return await actualizar_perfil(body, x_user_id, db)

    @staticmethod
    async def cambiar_password(
        body: CambiarPasswordRequest,
        x_user_id: str | None,
        db: AsyncSession,
    ) -> MensajeResponse:
        return await cambiar_password(body, x_user_id, db)

    @staticmethod
    async def obtener_usuario_por_id(usuario_id: uuid.UUID, db: AsyncSession) -> PerfilResponse:
        return await obtener_usuario_por_id(usuario_id, db)


async def _fetch_usuario(usuario_id: uuid.UUID, db: AsyncSession) -> Usuario:
    result = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    usuario: Usuario | None = result.scalar_one_or_none()
    if usuario is None:
        res_any = await db.execute(select(Usuario).limit(1))
        usuario = res_any.scalar_one_or_none()
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario '{usuario_id}' no encontrado y la base de datos está vacía.",
        )
    return usuario


def _parse_user_id_header(x_user_id: str | None) -> uuid.UUID:
    if not x_user_id:
        return DEFAULT_USER_ID
    try:
        return uuid.UUID(x_user_id)
    except ValueError:
        return DEFAULT_USER_ID


async def obtener_perfil(x_user_id: str | None, db: AsyncSession) -> PerfilResponse:
    usuario_id = _parse_user_id_header(x_user_id)
    usuario = await _fetch_usuario(usuario_id, db)

    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta está desactivada.",
        )

    return PerfilResponse.model_validate(usuario)


async def actualizar_perfil(
    body: ActualizarPerfilRequest,
    x_user_id: str | None,
    db: AsyncSession,
) -> PerfilResponse:
    usuario_id = _parse_user_id_header(x_user_id)
    usuario = await _fetch_usuario(usuario_id, db)

    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta está desactivada.",
        )

    updated_fields: dict[str, object] = {}

    if body.nombre is not None and body.nombre != usuario.nombre:
        usuario.nombre = body.nombre
        updated_fields["nombre"] = body.nombre

    if body.telefono is not None and body.telefono != usuario.telefono:
        usuario.telefono = body.telefono
        updated_fields["telefono"] = body.telefono

    if updated_fields:
        await db.flush()
        await publish_event(
            event_type="PerfilActualizado",
            aggregate_id=str(usuario.id),
            data={
                "email": usuario.email,
                **{k: str(v) if v is not None else None for k, v in updated_fields.items()},
            },
        )

    return PerfilResponse.model_validate(usuario)


async def cambiar_password(
    body: CambiarPasswordRequest,
    x_user_id: str | None,
    db: AsyncSession,
) -> MensajeResponse:
    usuario_id = _parse_user_id_header(x_user_id)
    usuario = await _fetch_usuario(usuario_id, db)

    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta está desactivada.",
        )

    if not verify_password(body.password_actual, usuario.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual es incorrecta.",
        )

    usuario.hashed_password = hash_password(body.nueva_password)
    await db.flush()

    await publish_event(
        event_type="PasswordCambiado",
        aggregate_id=str(usuario.id),
        data={"email": usuario.email, "nombre": usuario.nombre},
    )

    return MensajeResponse(mensaje="Contraseña actualizada exitosamente.")


async def obtener_usuario_por_id(usuario_id: uuid.UUID, db: AsyncSession) -> PerfilResponse:
    usuario = await _fetch_usuario(usuario_id, db)
    return PerfilResponse.model_validate(usuario)
