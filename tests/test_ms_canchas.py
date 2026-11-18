"""
Suite de pruebas unitarias y de integración: Complejos, Canchas y Mantenimiento
Microservicio cubierto: ms_canchas
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _TESTS_DIR.parent
for _p in (str(_ROOT_DIR), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FakeAsyncSession, activate_service, service_context

with service_context(
    "ms_canchas",
    [
        "app.database",
        "app.models",
        "app.admin_controller",
        "app.main",
    ],
) as mods:
    canchas_db = mods["app.database"]
    canchas_models = mods["app.models"]
    canchas_admin_ctrl = mods["app.admin_controller"]
    canchas_app = mods["app.main"].app


@pytest.fixture
def fake_canchas_db(monkeypatch):
    activate_service("ms_canchas")
    session = FakeAsyncSession()

    async def override_get_db():
        yield session

    published_events: list[dict] = []

    async def fake_publish_event(event_type: str, aggregate_id: str, data: dict, **_kwargs):
        published_events.append(
            {"event_type": event_type, "aggregate_id": aggregate_id, "data": data}
        )

    monkeypatch.setattr(canchas_admin_ctrl, "publish_event", fake_publish_event)
    canchas_app.dependency_overrides[canchas_db.get_db] = override_get_db
    yield session, published_events
    canchas_app.dependency_overrides.clear()


def test_creacion_complejo_y_cancha_siembra_bloques(fake_canchas_db):
    session, published_events = fake_canchas_db
    client = TestClient(canchas_app)

    comp_resp = client.post(
        "/canchas/complejos",
        json={
            "nombre": "Complejo La Estancia",
            "direccion": "Calle 5N # 8-20",
            "barrio": "La Estancia",
            "ciudad": "Popayán",
            "descripcion": "Canchas sintéticas FIFA Quality",
        },
    )
    assert comp_resp.status_code == 201
    complejo = comp_resp.json()
    complejo_id = complejo["id"]
    assert complejo["nombre"] == "Complejo La Estancia"

    cancha_resp = client.post(
        "/canchas/admin/canchas",
        headers={"X-Establecimiento-Id": complejo_id},
        json={
            "complejo_id": complejo_id,
            "nombre": "Cancha Sintética #1",
            "tipo": "FUTBOL_5",
            "tarifa_por_hora": 80000,
            "hora_apertura": "08:00:00",
            "hora_cierre": "14:00:00",
        },
    )
    assert cancha_resp.status_code == 201
    cancha = cancha_resp.json()
    assert cancha["complejo_id"] == complejo_id
    assert cancha["nombre"] == "Cancha Sintética #1"
    assert float(cancha["tarifa_por_hora"]) == 80000.0

    # Verificar que se sembraron bloques horarios (6 franjas x 30 días = 180) y evento CanchaCreada
    bloques = session.all_of(canchas_models.BloqueHorario)
    assert len(bloques) == 180
    assert any(ev["event_type"] == "CanchaCreada" for ev in published_events)

    listado = client.get("/canchas/complejos")
    assert listado.status_code == 200
    assert len(listado.json()) == 1
    assert len(listado.json()[0]["canchas"]) == 1


def test_bloqueo_mantenimiento_marca_franja_no_disponible(fake_canchas_db):
    client = TestClient(canchas_app)

    comp_resp = client.post(
        "/canchas/complejos",
        json={
            "nombre": "Arena Popayán",
            "direccion": "Cra 9 # 18-45",
            "barrio": "El Cadillal",
        },
    )
    complejo_id = comp_resp.json()["id"]

    cancha_resp = client.post(
        "/canchas/admin/canchas",
        headers={"X-Establecimiento-Id": complejo_id},
        json={
            "complejo_id": complejo_id,
            "nombre": "Cancha Sur F7",
            "tipo": "FUTBOL_7",
            "tarifa_por_hora": 110000,
            "hora_apertura": "08:00:00",
            "hora_cierre": "13:00:00",
        },
    )
    assert cancha_resp.status_code == 201
    cancha_id = cancha_resp.json()["id"]

    target_date = (date.today() + timedelta(days=2)).isoformat()

    # Programar mantenimiento de 10:00 a 12:00
    mant_resp = client.post(
        "/canchas/mantenimientos",
        json={
            "cancha_id": cancha_id,
            "fecha": target_date,
            "hora_inicio": "10:00:00",
            "hora_fin": "12:00:00",
            "motivo": "Cambio de caucho y cepillado",
        },
    )
    assert mant_resp.status_code == 201
    assert mant_resp.json()["motivo"] == "Cambio de caucho y cepillado"

    disp_resp = client.get(f"/canchas/{cancha_id}/disponibilidad", params={"fecha": target_date})
    assert disp_resp.status_code == 200
    slots_by_hour = {s["hora_inicio"][:5]: s["estado"] for s in disp_resp.json()}

    assert slots_by_hour["08:00"] == "LIBRE"
    assert slots_by_hour["09:00"] == "LIBRE"
    assert slots_by_hour["10:00"] == "MANTENIMIENTO"
    assert slots_by_hour["11:00"] == "MANTENIMIENTO"
    assert slots_by_hour["12:00"] == "LIBRE"
