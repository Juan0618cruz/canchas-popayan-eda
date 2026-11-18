"""
Suite de pruebas unitarias y de integración: Pasarela Wompi Colombia
Microservicio cubierto: ms_pagos
"""

from __future__ import annotations

import hashlib
import sys
import uuid
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
    "ms_pagos",
    [
        "app.config",
        "app.database",
        "app.models",
        "app.pagos_controller",
        "app.main",
    ],
) as mods:
    pagos_config = mods["app.config"]
    pagos_db = mods["app.database"]
    pagos_models = mods["app.models"]
    pagos_ctrl = mods["app.pagos_controller"]
    pagos_app = mods["app.main"].app


@pytest.fixture
def fake_pagos_db(monkeypatch):
    activate_service("ms_pagos")
    session = FakeAsyncSession()

    async def override_get_db():
        yield session

    published_events: list[dict] = []
    synced_reservas: list[tuple[uuid.UUID, str]] = []

    async def fake_publish_event(event_type: str, aggregate_id: str, data: dict, **_kwargs):
        published_events.append(
            {"event_type": event_type, "aggregate_id": aggregate_id, "data": data}
        )

    async def fake_sync_reserva(reserva_id: uuid.UUID, estado_pago: str):
        synced_reservas.append((reserva_id, estado_pago))

    async def fake_enrich(reserva_id, usuario_id, complejo_id, fallback_email=None):
        return {
            "codigo_uid": "RES-POP-2026-0001",
            "cancha_id": str(uuid.uuid4()),
            "complejo_id": str(complejo_id) if complejo_id else None,
            "fecha": "2026-11-20",
            "hora_inicio": "19:00:00",
            "hora_fin": "20:00:00",
            "precio_total": 85000.0,
            "email_usuario": fallback_email or "deportista@popayan.co",
            "nombre_usuario": "Camilo Torres",
            "nombre_complejo": "Complejo La Estancia",
            "nombre_cancha": "Cancha Sintética #1",
        }

    monkeypatch.setattr(pagos_ctrl, "publish_event", fake_publish_event)
    monkeypatch.setattr(pagos_ctrl, "_sync_reserva_estado", fake_sync_reserva)
    monkeypatch.setattr(pagos_ctrl, "_enrich_event_context", fake_enrich)

    pagos_app.dependency_overrides[pagos_db.get_db] = override_get_db
    yield session, published_events, synced_reservas
    pagos_app.dependency_overrides.clear()


def test_wompi_preparar_genera_referencia_y_firma_integridad(fake_pagos_db, monkeypatch):
    monkeypatch.setattr(pagos_config.settings, "WOMPI_INTEGRITY_SECRET", "test_integrity_secret")
    client = TestClient(pagos_app)

    resp = client.post(
        "/pagos/wompi/preparar",
        json={"reserva_id": str(uuid.uuid4()), "monto": 95000},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["referencia_externa"].startswith("WOMPI-POP-")
    assert body["amount_in_cents"] == 9500000
    assert body["currency"] == "COP"
    assert body["integrity_signature"]

    expected_sig = hashlib.sha256(
        f"{body['referencia_externa']}9500000COPtest_integrity_secret".encode("utf-8")
    ).hexdigest()
    assert body["integrity_signature"] == expected_sig


def test_procesar_pago_wompi_nequi_aprobado_y_publica_evento(fake_pagos_db):
    session, published_events, synced_reservas = fake_pagos_db
    client = TestClient(pagos_app)

    reserva_id = str(uuid.uuid4())
    usuario_id = str(uuid.uuid4())
    complejo_id = str(uuid.uuid4())

    resp = client.post(
        "/pagos/procesar",
        headers={"X-User-Id": usuario_id},
        json={
            "reserva_id": reserva_id,
            "complejo_id": complejo_id,
            "monto": 85000,
            "metodo": "WOMPI_NEQUI",
            "simular_resultado": "APROBADO",
            "datos_metodo": {"celular_nequi": "3124567890", "email_usuario": "laura@popayan.co"},
        },
    )
    assert resp.status_code == 200
    pago = resp.json()
    assert pago["metodo"] == "WOMPI_NEQUI"
    assert pago["estado"] == "APROBADO"
    assert pago["referencia_externa"].startswith("WOMPI-POP-")

    assert len(session.all_of(pagos_models.Pago)) == 1
    assert synced_reservas == [(uuid.UUID(reserva_id), "APPROVED")]
    assert len(published_events) == 1
    assert published_events[0]["event_type"] == "PagoAprobado"
    assert published_events[0]["data"]["metodo_pago"] == "WOMPI_NEQUI"
    assert published_events[0]["data"]["estado"] == "CONFIRMADA"


def test_wompi_webhook_pse_valida_firma_y_rechaza_firma_invalida(fake_pagos_db, monkeypatch):
    _, published_events, synced_reservas = fake_pagos_db
    monkeypatch.setattr(pagos_config.settings, "WOMPI_EVENTS_SECRET", "events_secret_test")
    client = TestClient(pagos_app)

    reserva_id = str(uuid.uuid4())
    tx_id = "120099-1700000001-9988"
    tx_status = "APPROVED"
    amount_in_cents = 11000000
    ts = 1731360000

    valid_checksum = hashlib.sha256(
        f"{tx_id}{tx_status}{amount_in_cents}{ts}events_secret_test".encode("utf-8")
    ).hexdigest()

    base_payload = {
        "event": "transaction.updated",
        "timestamp": ts,
        "reserva_id": reserva_id,
        "data": {
            "transaction": {
                "id": tx_id,
                "reference": "WOMPI-POP-PSE00123",
                "status": tx_status,
                "payment_method_type": "PSE",
                "amount_in_cents": amount_in_cents,
                "customer_email": "usuario.pse@popayan.co",
            }
        },
        "signature": {
            "properties": [
                "transaction.id",
                "transaction.status",
                "transaction.amount_in_cents",
            ],
            "checksum": valid_checksum,
        },
    }

    # 1. Firma válida -> 200 y método WOMPI_PSE
    ok_resp = client.post("/pagos/wompi/webhook", json=base_payload)
    assert ok_resp.status_code == 200
    body = ok_resp.json()
    assert body["metodo"] == "WOMPI_PSE"
    assert body["estado"] == "APROBADO"
    assert body["referencia_externa"] == "WOMPI-POP-PSE00123"
    assert synced_reservas[-1] == (uuid.UUID(reserva_id), "APPROVED")
    assert published_events[-1]["event_type"] == "PagoAprobado"

    # 2. Firma alterada -> 401 Unauthorized
    tampered = dict(base_payload)
    tampered["signature"] = {**base_payload["signature"], "checksum": "0" * 64}
    bad_resp = client.post("/pagos/wompi/webhook", json=tampered)
    assert bad_resp.status_code == 401
