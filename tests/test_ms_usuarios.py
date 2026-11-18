"""
Suite de pruebas unitarias y de integración: Autenticación y Roles
Microservicios cubiertos: ms_usuarios + api_gateway
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

_TESTS_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _TESTS_DIR.parent
for _p in (str(_ROOT_DIR), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import httpx
import pytest
from fastapi.testclient import TestClient
from jose import jwt

from tests.conftest import FakeAsyncSession, activate_service, service_context

# Load ms_usuarios once under isolated `app.*` namespace
with service_context(
    "ms_usuarios",
    [
        "app.config",
        "app.database",
        "app.models",
        "app.schemas",
        "app.security",
        "app.auth_controller",
        "app.main",
    ],
) as mods:
    usr_config = mods["app.config"]
    usr_db = mods["app.database"]
    usr_models = mods["app.models"]
    usr_auth_ctrl = mods["app.auth_controller"]
    usr_app = mods["app.main"].app

# Load api_gateway once under isolated `app.*` namespace
with service_context(
    "api_gateway",
    [
        "app.config",
        "app.main",
    ],
) as gw_mods:
    gw_config = gw_mods["app.config"]
    gw_main = gw_mods["app.main"]
    gw_app = gw_main.app


@pytest.fixture
def fake_usuarios_db(monkeypatch):
    activate_service("ms_usuarios")
    session = FakeAsyncSession()

    async def override_get_db():
        yield session

    published_events: list[dict] = []

    async def fake_publish_event(event_type: str, aggregate_id: str, data: dict, **_kwargs):
        published_events.append(
            {"event_type": event_type, "aggregate_id": aggregate_id, "data": data}
        )

    monkeypatch.setattr(usr_auth_ctrl, "publish_event", fake_publish_event)
    usr_app.dependency_overrides[usr_db.get_db] = override_get_db
    yield session, published_events
    usr_app.dependency_overrides.clear()


def test_registro_deportista_crea_usuario_y_publica_evento(fake_usuarios_db):
    session, published_events = fake_usuarios_db
    client = TestClient(usr_app)

    resp = client.post(
        "/auth/register",
        json={
            "nombre": "Laura Gómez",
            "email": "laura.gomez@popayan.co",
            "password": "Password123!",
            "telefono": "+573101234567",
        },
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "laura.gomez@popayan.co"
    assert data["nombre"] == "Laura Gómez"
    assert data["rol"] == "USUARIO"
    assert data["activo"] is True
    assert uuid.UUID(data["id"])

    # Verificar persistencia en modelo Usuario y publicación EDA
    usuarios = session.all_of(usr_models.Usuario)
    assert len(usuarios) == 1
    assert usuarios[0].hashed_password != "Password123!"
    assert len(published_events) == 1
    assert published_events[0]["event_type"] == "UsuarioRegistrado"


def test_login_retorna_jwt_valido_con_claims_de_rol(fake_usuarios_db):
    client = TestClient(usr_app)

    reg = client.post(
        "/auth/register",
        json={
            "nombre": "Andrés Muñoz",
            "email": "andres.munoz@popayan.co",
            "password": "ClaveSegura99",
        },
    )
    assert reg.status_code == 201

    login_resp = client.post(
        "/auth/login",
        json={"email": "andres.munoz@popayan.co", "password": "ClaveSegura99"},
    )
    assert login_resp.status_code == 200
    body = login_resp.json()
    assert body["token_type"] == "bearer"
    assert body["rol"] == "USUARIO"
    assert body["access_token"]

    claims = jwt.decode(
        body["access_token"],
        usr_config.settings.JWT_SECRET,
        algorithms=[usr_config.settings.JWT_ALGORITHM],
    )
    assert claims["sub"] == body["usuario_id"]
    assert claims["email"] == "andres.munoz@popayan.co"
    assert claims["rol"] == "USUARIO"


def test_roles_admin_establecimiento_y_clasificacion_rutas_exclusivas(
    fake_usuarios_db, monkeypatch
):
    _, published_events = fake_usuarios_db
    usr_client = TestClient(usr_app)

    # 1. Registro de administrador de establecimiento en ms_usuarios
    admin_reg = usr_client.post(
        "/auth/register-admin",
        json={
            "nombre": "Juan Pablo Admin",
            "email": "admin.complejo@popayan.co",
            "password": "AdminPassword123!",
            "telefono": "+573009876543",
            "establecimiento_nombre": "Complejo Deportivo Balón de Oro",
            "establecimiento_direccion": "Cra 15 # 12-45, Popayán",
        },
    )
    assert admin_reg.status_code == 201
    admin_data = admin_reg.json()
    assert admin_data["rol"] == "ADMIN_ESTABLECIMIENTO"
    assert uuid.UUID(admin_data["establecimiento_id"])
    assert any(ev["event_type"] == "AdminEstablecimientoRegistrado" for ev in published_events)

    # 2. Clasificación de rutas exclusivas de ADMIN_ESTABLECIMIENTO en API Gateway
    activate_service("api_gateway")
    assert gw_main._requires_admin("POST", "/canchas/admin/complejos") is True
    assert gw_main._requires_admin("DELETE", "/canchas/admin/canchas/123") is True
    assert gw_main._requires_admin("POST", "/reservas/admin/presencial") is True
    assert gw_main._requires_admin("GET", "/pagos/admin/reportes") is True
    assert gw_main._requires_admin("GET", "/canchas/complejos") is False

    # 3. Propagación fiel de claims de rol desde Bearer JWT hacia los microservicios
    upstream_mock = AsyncMock()
    upstream_mock.request = AsyncMock(
        return_value=httpx.Response(status_code=200, json={"ok": True})
    )
    monkeypatch.setattr(gw_main, "_http_client", upstream_mock)
    gw_client = TestClient(gw_app)

    deportista_id = str(uuid.uuid4())
    deportista_token = jwt.encode(
        {"sub": deportista_id, "rol": "USUARIO", "email": "deportista@popayan.co"},
        gw_config.settings.jwt_secret,
        algorithm=gw_config.settings.jwt_algorithm,
    )
    resp_user = gw_client.get(
        "/reservas/mis-reservas",
        headers={"Authorization": f"Bearer {deportista_token}"},
    )
    assert resp_user.status_code == 200
    headers_user = upstream_mock.request.call_args.kwargs["headers"]
    assert headers_user["X-User-Id"] == deportista_id
    assert headers_user["X-User-Rol"] == "USUARIO"

    admin_token = jwt.encode(
        {
            "sub": admin_data["id"],
            "rol": "ADMIN_ESTABLECIMIENTO",
            "establecimiento_id": admin_data["establecimiento_id"],
            "email": "admin.complejo@popayan.co",
        },
        gw_config.settings.jwt_secret,
        algorithm=gw_config.settings.jwt_algorithm,
    )
    resp_admin = gw_client.get(
        "/pagos/admin/reportes",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_admin.status_code == 200
    headers_admin = upstream_mock.request.call_args.kwargs["headers"]
    assert headers_admin["X-User-Id"] == admin_data["id"]
    assert headers_admin["X-User-Rol"] == "ADMIN_ESTABLECIMIENTO"
    assert headers_admin["X-Establecimiento-Id"] == admin_data["establecimiento_id"]
