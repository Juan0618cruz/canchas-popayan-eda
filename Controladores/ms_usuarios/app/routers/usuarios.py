"""
Capa MVC: Enrutador HTTP (Router) — Endpoints de perfil de usuario para ms_usuarios.

Delega la lógica de gestión de cuentas y persistencia a UsuariosController.
"""

import uuid

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import auth_controller, usuarios_controller
from app.database import get_db
from app.schemas import (
    ActualizarPerfilRequest,
    CambiarPasswordRequest,
    LoginRequest,
    LoginResponse,
    MensajeResponse,
    PerfilResponse,
)

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Alias de inicio de sesión (/usuarios/login)",
)
async def usuarios_login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    return await auth_controller.autenticar_usuario(body, db)


@router.get(
    "/perfil",
    response_model=PerfilResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener perfil del usuario autenticado",
)
async def get_perfil(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> PerfilResponse:
    return await usuarios_controller.obtener_perfil(x_user_id, db)


@router.put(
    "/perfil",
    response_model=PerfilResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar perfil del usuario autenticado",
)
async def actualizar_perfil(
    body: ActualizarPerfilRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> PerfilResponse:
    return await usuarios_controller.actualizar_perfil(body, x_user_id, db)


@router.put(
    "/perfil/password",
    response_model=MensajeResponse,
    status_code=status.HTTP_200_OK,
    summary="Cambiar contraseña del usuario autenticado",
)
async def cambiar_password(
    body: CambiarPasswordRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> MensajeResponse:
    return await usuarios_controller.cambiar_password(body, x_user_id, db)


@router.get(
    "/{usuario_id}",
    response_model=PerfilResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener información de un usuario por ID (uso interno)",
)
async def get_usuario_by_id(
    usuario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PerfilResponse:
    return await usuarios_controller.obtener_usuario_por_id(usuario_id, db)
