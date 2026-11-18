"""
Suite de pruebas unitarias y de integración: Eventos EDA y Notificaciones SMTP
Microservicio cubierto: ms_notificaciones
"""

from __future__ import annotations

import asyncio
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

from tests.conftest import activate_service, service_context

with service_context(
    "ms_notificaciones",
    [
        "app.config",
        "app.models",
        "app.smtp_service",
        "app.rabbitmq_consumer",
        "app.main",
    ],
) as mods:
    notif_config = mods["app.config"]
    notif_models = mods["app.models"]
    notif_smtp = mods["app.smtp_service"]
    notif_consumer = mods["app.rabbitmq_consumer"]
    notif_app = mods["app.main"].app


@pytest.fixture
def isolated_notif_db(tmp_path, monkeypatch):
    activate_service("ms_notificaciones")
    db_file = tmp_path / "test_notificaciones.db"
    monkeypatch.setattr(notif_config.settings, "NOTIF_DB_PATH", str(db_file))
    monkeypatch.setattr(notif_models, "_DB_PATH", db_file)
    monkeypatch.setattr(notif_models, "_DB_INITIALIZED", False)
    yield db_file


def test_consumo_evento_pago_aprobado_envia_smtp_html_y_persiste_log(
    isolated_notif_db, monkeypatch
):
    sent_messages: list[dict] = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=15):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ehlo(self):
            return None

        def starttls(self):
            return None

        def login(self, user, password):
            assert user == "jpdiagon1@gmail.com"
            assert password == "uinmqedieyqxswey"

        def sendmail(self, from_addr, to_addrs, msg_str):
            sent_messages.append({"from": from_addr, "to": to_addrs, "raw": msg_str})

    monkeypatch.setattr(notif_config.settings, "SMTP_USER", "jpdiagon1@gmail.com")
    monkeypatch.setattr(notif_config.settings, "SMTP_PASSWORD", "uinmqedieyqxswey")
    monkeypatch.setattr(notif_config.settings, "SMTP_FROM_EMAIL", "jpdiagon1@gmail.com")
    monkeypatch.setattr(notif_smtp.smtplib, "SMTP", FakeSMTP)

    async def fake_enrich(data: dict) -> dict:
        return dict(data)

    monkeypatch.setattr(notif_consumer, "_enrich_notification_data", fake_enrich)

    pago_id = str(uuid.uuid4())
    asyncio.run(
        notif_consumer._dispatch_and_deliver(
            event_type="PagoAprobado",
            aggregate_id=pago_id,
            data={
                "email_usuario": "deportista@popayan.co",
                "nombre_usuario": "Juan Camilo",
                "codigo_uid": "RES-POP-2026-0042",
                "nombre_complejo": "Complejo La Estancia",
                "nombre_cancha": "Cancha Sintética #1",
                "fecha": "2026-11-22",
                "hora_inicio": "19:00:00",
                "hora_fin": "20:00:00",
                "monto": 85000,
                "metodo_pago": "WOMPI_NEQUI",
                "referencia_externa": "WOMPI-POP-ABCD1234",
                "estado": "CONFIRMADA",
            },
        )
    )

    assert len(sent_messages) == 1
    assert sent_messages[0]["from"] == "jpdiagon1@gmail.com"
    assert sent_messages[0]["to"] == ["deportista@popayan.co"]

    client = TestClient(notif_app)
    logs_resp = client.get("/notificaciones/logs")
    assert logs_resp.status_code == 200
    payload = logs_resp.json()
    matching = [log for log in payload["correos"] if log["aggregate_id"] == pago_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "ENVIADO_SMTP"
    assert matching[0]["to_email"] == "deportista@popayan.co"
    assert "RES-POP-2026-0042" in matching[0]["body"]


def test_evento_sin_credenciales_smtp_no_falla_y_registra_estado(
    isolated_notif_db, monkeypatch
):
    monkeypatch.setattr(notif_config.settings, "SMTP_USER", "")
    monkeypatch.setattr(notif_config.settings, "SMTP_PASSWORD", "")

    async def fake_enrich(data: dict) -> dict:
        return dict(data)

    monkeypatch.setattr(notif_consumer, "_enrich_notification_data", fake_enrich)

    reserva_id = str(uuid.uuid4())
    asyncio.run(
        notif_consumer._dispatch_and_deliver(
            event_type="ReservaSolicitada",
            aggregate_id=reserva_id,
            data={
                "email_usuario": "maria@popayan.co",
                "nombre_usuario": "María Fernanda",
                "codigo_uid": "RES-POP-2026-0077",
                "nombre_complejo": "Arena Popayán",
                "nombre_cancha": "Cancha Norte F5",
                "fecha": "2026-11-25",
                "hora_inicio": "18:00:00",
                "hora_fin": "19:00:00",
                "monto": 70000,
            },
        )
    )

    client = TestClient(notif_app)
    logs_resp = client.get("/notificaciones/logs", params={"event_type": "ReservaSolicitada"})
    assert logs_resp.status_code == 200
    correos = logs_resp.json()["correos"]
    matching = [log for log in correos if log["aggregate_id"] == reserva_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "SIN_CREDENCIALES_SMTP"
    assert matching[0]["error_detail"]

    stats_resp = client.get("/notificaciones/logs/stats")
    assert stats_resp.status_code == 200
    stats_body = stats_resp.json()
    assert stats_body["por_evento"]["ReservaSolicitada"] >= 1
