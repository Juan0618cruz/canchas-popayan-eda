"""
Capa MVC: Enrutador HTTP (Router) — Endpoints de autenticación para ms_usuarios.

Delega toda la lógica de negocio y publicación de eventos de dominio a AuthController.
"""

from typing import Any

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import auth_controller
from app.database import get_db
from app.schemas import (
    ConfirmarRecuperacionRequest,
    LoginResponse,
    MensajeResponse,
    PerfilResponse,
    RegistroAdminRequest,
    RegistroUsuarioRequest,
    SolicitudRecuperacionRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=PerfilResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un usuario estándar",
)
async def register_usuario(
    body: RegistroUsuarioRequest,
    db: AsyncSession = Depends(get_db),
) -> PerfilResponse:
    return await auth_controller.registrar_usuario(body, db)


@router.post(
    "/register-admin",
    response_model=PerfilResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un administrador de establecimiento",
)
async def register_admin(
    body: RegistroAdminRequest,
    db: AsyncSession = Depends(get_db),
) -> PerfilResponse:
    return await auth_controller.registrar_admin(body, db)


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Iniciar sesión",
)
async def login(
    body: Any = Body(default_factory=dict),
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    return await auth_controller.autenticar_usuario(body, db)


@router.post(
    "/forgot-password",
    response_model=MensajeResponse,
    status_code=status.HTTP_200_OK,
    summary="Solicitar restablecimiento de clave",
)
async def forgot_password(
    body: SolicitudRecuperacionRequest,
    db: AsyncSession = Depends(get_db),
) -> MensajeResponse:
    return await auth_controller.solicitar_recuperacion(body, db)


@router.post(
    "/reset-password",
    response_model=MensajeResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirmar restablecimiento de clave con token",
)
async def reset_password(
    body: ConfirmarRecuperacionRequest,
    db: AsyncSession = Depends(get_db),
) -> MensajeResponse:
    return await auth_controller.confirmar_recuperacion(body, db)
