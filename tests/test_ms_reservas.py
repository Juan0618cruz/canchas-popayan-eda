"""
Suite de pruebas unitarias y de integración: Ciclo de Vida de Reservas
Microservicio cubierto: ms_reservas
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, time, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

_TESTS_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _TESTS_DIR.parent
for _p in (str(_ROOT_DIR), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FakeAsyncSession, activate_service, service_context

with service_context(
    "ms_reservas",
    [
        "app.database",
        "app.models",
        "app.reservas_controller",
        "app.main",
    ],
) as mods:
    res_db = mods["app.database"]
    res_models = mods["app.models"]
    res_ctrl = mods["app.reservas_controller"]
    res_app = mods["app.main"].app


@pytest.fixture
def fake_reservas_db(monkeypatch):
    activate_service("ms_reservas")
    session = FakeAsyncSession(initial_objects=[res_models.ContadorReservas(id=1, contador=0)])

    async def override_get_db():
        yield session

    monkeypatch.setattr(res_ctrl, "validate_no_maintenance", AsyncMock(return_value=None))
    sync_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(res_ctrl, "sync_canchas_reprogramacion", sync_mock)
    monkeypatch.setattr(
        res_ctrl,
        "fetch_usuario_info",
        AsyncMock(return_value=("CARLOS DAMIAN", "carlos.damian@popayan.co", "3112223344")),
    )

    res_app.dependency_overrides[res_db.get_db] = override_get_db
    yield session, sync_mock
    res_app.dependency_overrides.clear()


def test_crear_reserva_y_prevenir_doble_reserva_mismo_horario(fake_reservas_db):
    session, _ = fake_reservas_db
    client = TestClient(res_app)

    usuario_1 = str(uuid.uuid4())
    usuario_2 = str(uuid.uuid4())
    cancha_id = str(uuid.uuid4())
    complejo_id = str(uuid.uuid4())
    fecha_reserva = (date.today() + timedelta(days=3)).isoformat()

    payload = {
        "cancha_id": cancha_id,
        "complejo_id": complejo_id,
        "fecha": fecha_reserva,
        "hora_inicio": "18:00:00",
        "hora_fin": "19:00:00",
        "monto": 85000,
    }

    resp1 = client.post("/reservas", headers={"X-User-Id": usuario_1}, json=payload)
    assert resp1.status_code == 201
    reserva = resp1.json()
    assert reserva["codigo_uid"].startswith("RES-POP-")
    assert reserva["estado"] == "PENDIENTE_PAGO"

    # Verificar registro Outbox ReservaSolicitada
    outbox = session.all_of(res_models.OutboxEvent)
    assert any(ev.event_type == "ReservaSolicitada" for ev in outbox)

    # Segundo deportista intenta reservar la misma cancha, fecha y hora -> 409 Conflict
    resp2 = client.post("/reservas", headers={"X-User-Id": usuario_2}, json=payload)
    assert resp2.status_code == 409
    assert "ya está reservada" in resp2.json()["detail"].lower()


def test_reprogramar_reserva_libera_slot_anterior_y_ocupa_nuevo(fake_reservas_db):
    session, sync_mock = fake_reservas_db
    client = TestClient(res_app)

    usuario_id = str(uuid.uuid4())
    otro_usuario = str(uuid.uuid4())
    cancha_id = str(uuid.uuid4())
    complejo_id = str(uuid.uuid4())
    fecha_inicial = (date.today() + timedelta(days=4)).isoformat()
    fecha_nueva = (date.today() + timedelta(days=5)).isoformat()

    crear = client.post(
        "/reservas",
        headers={"X-User-Id": usuario_id},
        json={
            "cancha_id": cancha_id,
            "complejo_id": complejo_id,
            "fecha": fecha_inicial,
            "hora_inicio": "15:00:00",
            "hora_fin": "16:00:00",
            "monto": 90000,
        },
    )
    assert crear.status_code == 201
    reserva_id = crear.json()["id"]

    reprog = client.put(
        f"/reservas/{reserva_id}/reprogramar",
        headers={"X-User-Id": usuario_id},
        json={
            "nueva_fecha": fecha_nueva,
            "nueva_hora_inicio": "20:00:00",
            "nueva_hora_fin": "21:00:00",
        },
    )
    assert reprog.status_code == 200
    body = reprog.json()
    assert body["fecha"] == fecha_nueva
    assert body["hora_inicio"] == "20:00:00"
    assert body["hora_fin"] == "21:00:00"

    # Deben emitirse ReservaReprogramada, SlotLiberado y SlotOcupado + sincronizar con ms_canchas
    event_types = [ev.event_type for ev in session.all_of(res_models.OutboxEvent)]
    assert "ReservaReprogramada" in event_types
    assert "SlotLiberado" in event_types
    assert "SlotOcupado" in event_types
    sync_mock.assert_awaited_once()

    # La franja anterior (15:00 del día inicial) debe quedar libre para otro deportista
    nuevo_ocupante = client.post(
        "/reservas",
        headers={"X-User-Id": otro_usuario},
        json={
            "cancha_id": cancha_id,
            "complejo_id": complejo_id,
            "fecha": fecha_inicial,
            "hora_inicio": "15:00:00",
            "hora_fin": "16:00:00",
            "monto": 90000,
        },
    )
    assert nuevo_ocupante.status_code == 201


def test_cancelar_reserva_transiciona_a_cancelada_y_publica_evento(fake_reservas_db):
    session, _ = fake_reservas_db
    client = TestClient(res_app)

    usuario_id = str(uuid.uuid4())
    cancha_id = str(uuid.uuid4())
    complejo_id = str(uuid.uuid4())
    fecha_reserva = (date.today() + timedelta(days=6)).isoformat()

    crear = client.post(
        "/reservas",
        headers={"X-User-Id": usuario_id},
        json={
            "cancha_id": cancha_id,
            "complejo_id": complejo_id,
            "fecha": fecha_reserva,
            "hora_inicio": "19:00:00",
            "hora_fin": "20:00:00",
            "monto": 75000,
        },
    )
    assert crear.status_code == 201
    reserva_id = crear.json()["id"]

    cancel_resp = client.request(
        "DELETE",
        f"/reservas/{reserva_id}",
        headers={"X-User-Id": usuario_id},
        json={"motivo": "Lluvia fuerte en Popayán"},
    )
    assert cancel_resp.status_code == 200
    body = cancel_resp.json()
    assert body["estado"] == "CANCELADA"
    assert body["motivo_cancelacion"] == "Lluvia fuerte en Popayán"

    outbox_events = [ev.event_type for ev in session.all_of(res_models.OutboxEvent)]
    assert "ReservaCancelada" in outbox_events


def test_resolucion_nombre_real_cliente_en_creacion_y_taquilla(fake_reservas_db):
    session, _ = fake_reservas_db
    client = TestClient(res_app)

    usuario_id = str(uuid.uuid4())
    complejo_id = str(uuid.uuid4())
    cancha_id = str(uuid.uuid4())
    fecha_reserva = (date.today() + timedelta(days=7)).isoformat()

    # 1. Reserva online sin nombre explícito en body: resuelve via ms_usuarios
    crear = client.post(
        "/reservas",
        headers={"X-User-Id": usuario_id},
        json={
            "cancha_id": cancha_id,
            "complejo_id": complejo_id,
            "fecha": fecha_reserva,
            "hora_inicio": "17:00:00",
            "hora_fin": "18:00:00",
            "monto": 80000,
        },
    )
    assert crear.status_code == 201
    creada = crear.json()
    assert creada["nombre_cliente"] == "CARLOS DAMIAN"
    assert creada["cliente_nombre"] == "CARLOS DAMIAN"
    assert creada["usuario_nombre"] == "CARLOS DAMIAN"

    # 2. Simular reserva heredada en BD con nombre_cliente genérico "Usuario ..."
    legacy_id = uuid.uuid4()
    session.add(
        res_models.Reserva(
            id=legacy_id,
            codigo_uid="RES-POP-2026-9999",
            cancha_id=uuid.UUID(cancha_id),
            complejo_id=uuid.UUID(complejo_id),
            usuario_id=uuid.UUID(usuario_id),
            nombre_cliente="Usuario 1234abcd",
            telefono_cliente=None,
            fecha=date.today() + timedelta(days=7),
            hora_inicio=time(16, 0),
            hora_fin=time(17, 0),
            estado=res_models.EstadoReserva.CONFIRMADA,
            monto=80000,
        )
    )

    listado = client.get(
        "/reservas/admin/todas",
        headers={"X-Establecimiento-Id": complejo_id},
        params={"fecha": fecha_reserva},
    )
    assert listado.status_code == 200
    rows = listado.json()
    legacy_row = next(r for r in rows if r["id"] == str(legacy_id))
    assert legacy_row["nombre_cliente"] == "CARLOS DAMIAN"
    assert legacy_row["cliente_nombre"] == "CARLOS DAMIAN"
    assert legacy_row["usuario_nombre"] == "CARLOS DAMIAN"

