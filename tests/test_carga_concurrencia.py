"""Suite de pruebas de carga, estres y concurrencia contra el API Gateway en vivo.

Ejecuta 3 escenarios contra GATEWAY_URL (por defecto http://localhost:8000):
1. Concurrencia extrema (Race Condition): 20 peticiones POST /reservas simultaneas
   para exactamente la misma cancha, fecha y hora -> 1 debe retornar 201 Created,
   19 deben retornar 409 Conflict y 0 errores 500.
2. Estres de lectura/navegacion (100 usuarios simultaneos): 100 peticiones concurrentes
   sobre /health, /canchas/complejos y /canchas/{id}/disponibilidad -> 100% 200 OK,
   midiendo latencia promedio, p95, maxima y RPS.
3. Rafaga paralela de 15 reservas + 15 pagos Wompi Sandbox (WOMPI_NEQUI / WOMPI_PSE),
   verificando integridad en RabbitMQ y salud de los microservicios.

Todas las reservas creadas durante la prueba se limpian al finalizar.
"""

from __future__ import annotations

import asyncio
import math
import os
import random
import time
import uuid
from datetime import date, timedelta
from pathlib import Path
import sys

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000").rstrip("/")


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, math.ceil((pct / 100.0) * len(ordered)) - 1))
    return ordered[idx]


def _print_metrics_block(title: str, lines: list[str]) -> None:
    print(f"\n=== {title} ===")
    for line in lines:
        print(f"  {line}")


async def _fetch_target_courts(client: httpx.AsyncClient) -> list[dict]:
    resp = await client.get(f"{GATEWAY_URL}/canchas/complejos")
    if resp.status_code != 200:
        pytest.fail(f"No se pudo consultar /canchas/complejos: {resp.status_code} {resp.text}")
    complejos = resp.json()
    courts: list[dict] = []
    for comp in complejos:
        comp_id = comp.get("id")
        for cancha in comp.get("canchas", []):
            if cancha.get("activo", True):
                courts.append(
                    {
                        "cancha_id": cancha["id"],
                        "complejo_id": comp_id,
                        "tarifa_por_hora": float(cancha.get("tarifa_por_hora", 80000)),
                    }
                )
    if not courts:
        pytest.skip("No hay canchas activas registradas en el sistema para ejecutar pruebas de carga.")
    return courts


async def _register_temp_user(client: httpx.AsyncClient, idx: int) -> dict:
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "nombre": f"LoadTest User {idx}-{suffix}",
        "email": f"loadtest_{idx}_{suffix}@canchaspopayan.test",
        "password": "LoadTest123!",
        "telefono": "3001234567",
        "rol": "DEPORTISTA",
    }
    resp = await client.post(f"{GATEWAY_URL}/auth/register", json=payload)
    if resp.status_code in (200, 201):
        data = resp.json()
        return {"id": data["id"], "nombre": data.get("nombre", payload["nombre"])}
    return {"id": str(uuid.uuid4()), "nombre": payload["nombre"]}


async def _cleanup_reservations(client: httpx.AsyncClient, reserva_ids: list[str]) -> None:
    if not reserva_ids:
        return
    tasks = [
        client.request(
            "DELETE",
            f"{GATEWAY_URL}/reservas/admin/{rid}",
            json={"motivo": "Limpieza automatica prueba de carga"},
        )
        for rid in reserva_ids
    ]
    await asyncio.gather(*tasks, return_exceptions=True)


async def _verify_gateway_up(client: httpx.AsyncClient) -> None:
    try:
        resp = await client.get(f"{GATEWAY_URL}/health")
        assert resp.status_code == 200, f"Gateway health fallo: {resp.status_code}"
    except httpx.ConnectError as exc:
        pytest.fail(
            f"No se pudo conectar al API Gateway en {GATEWAY_URL}. "
            f"Asegurate de que Docker Compose este activo. Error: {exc}"
        )


def test_concurrencia_extrema_20_peticiones_mismo_horario() -> None:
    """Test 1: 20 peticiones POST /reservas simultaneas sobre el mismo slot exacto."""

    async def _run() -> None:
        limits = httpx.Limits(max_connections=50, max_keepalive_connections=50)
        timeout = httpx.Timeout(30.0, connect=10.0)
        created_ids: list[str] = []
        async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
            await _verify_gateway_up(client)
            courts = await _fetch_target_courts(client)
            target = courts[0]

            # Fecha lejana aleatoria para evitar colision con reservas reales o corridas previas
            fecha_prueba = (date.today() + timedelta(days=random.randint(120, 900))).isoformat()
            hora_inicio = "21:00"
            hora_fin = "22:00"

            users = await asyncio.gather(*[_register_temp_user(client, i) for i in range(20)])
            barrier = asyncio.Event()

            async def _attempt(user: dict) -> tuple[int, float, str | None, str]:
                await barrier.wait()
                t0 = time.perf_counter()
                payload = {
                    "cancha_id": target["cancha_id"],
                    "complejo_id": target["complejo_id"],
                    "fecha": fecha_prueba,
                    "hora_inicio": hora_inicio,
                    "hora_fin": hora_fin,
                    "monto": target["tarifa_por_hora"],
                    "nombre_cliente": user["nombre"],
                    "cliente_nombre": user["nombre"],
                }
                resp = await client.post(
                    f"{GATEWAY_URL}/reservas",
                    json=payload,
                    headers={"X-User-Id": user["id"]},
                )
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                rid = None
                if resp.status_code == 201:
                    rid = resp.json().get("id")
                return resp.status_code, elapsed_ms, rid, resp.text[:160]

            try:
                tasks = [asyncio.create_task(_attempt(u)) for u in users]
                await asyncio.sleep(0.05)
                t_start = time.perf_counter()
                barrier.set()
                results = await asyncio.gather(*tasks)
                total_s = time.perf_counter() - t_start

                statuses = [r[0] for r in results]
                latencies = [r[1] for r in results]
                created_ids = [r[2] for r in results if r[2]]

                c_201 = statuses.count(201)
                c_409 = statuses.count(409)
                c_500 = sum(1 for s in statuses if s >= 500)
                otros = [r for r in results if r[0] not in (201, 409)]

                _print_metrics_block(
                    "TEST 1: CONCURRENCIA EXTREMA (20 POST /reservas MISMO SLOT)",
                    [
                        f"Cancha: {target['cancha_id']} | Fecha: {fecha_prueba} {hora_inicio}-{hora_fin}",
                        f"201 Created: {c_201} | 409 Conflict: {c_409} | 5xx Errors: {c_500}",
                        f"Tiempo total rafaga: {total_s * 1000:.1f} ms | "
                        f"Latencia promedio: {sum(latencies)/len(latencies):.1f} ms | "
                        f"p95: {_percentile(latencies, 95):.1f} ms | Max: {max(latencies):.1f} ms",
                    ],
                )

                assert c_500 == 0, f"Se detectaron errores 5xx: {otros}"
                assert c_201 == 1, f"Se esperaba exactamente 1 reserva creada (201), obtuvo {c_201}. Detalle: {otros}"
                assert c_409 == 19, f"Se esperaban exactamente 19 rechazos (409), obtuvo {c_409}. Detalle: {otros}"
            finally:
                await _cleanup_reservations(client, created_ids)

    asyncio.run(_run())


def test_carga_100_usuarios_simultaneos_lectura() -> None:
    """Test 2: 100 peticiones concurrentes de lectura y disponibilidad."""

    async def _run() -> None:
        limits = httpx.Limits(max_connections=120, max_keepalive_connections=100)
        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
            await _verify_gateway_up(client)
            courts = await _fetch_target_courts(client)
            cancha_id = courts[0]["cancha_id"]
            fecha = (date.today() + timedelta(days=7)).isoformat()

            endpoints = [
                f"{GATEWAY_URL}/canchas/complejos",
                f"{GATEWAY_URL}/canchas/{cancha_id}/disponibilidad?fecha={fecha}",
                f"{GATEWAY_URL}/health",
            ]
            urls = [endpoints[i % len(endpoints)] for i in range(100)]
            barrier = asyncio.Event()

            async def _hit(url: str) -> tuple[int, float]:
                await barrier.wait()
                t0 = time.perf_counter()
                resp = await client.get(url)
                return resp.status_code, (time.perf_counter() - t0) * 1000.0

            tasks = [asyncio.create_task(_hit(u)) for u in urls]
            await asyncio.sleep(0.05)
            t_start = time.perf_counter()
            barrier.set()
            results = await asyncio.gather(*tasks)
            total_s = max(time.perf_counter() - t_start, 1e-6)

            statuses = [r[0] for r in results]
            latencies = [r[1] for r in results]
            ok_count = statuses.count(200)
            rps = len(results) / total_s

            _print_metrics_block(
                "TEST 2: ESTRES LECTURA (100 USUARIOS SIMULTANEOS)",
                [
                    f"Respuestas 200 OK: {ok_count}/100 | Errores: {100 - ok_count}",
                    f"Throughput: {rps:.1f} req/s (RPS) | Tiempo total: {total_s:.2f} s",
                    f"Latencia promedio: {sum(latencies)/len(latencies):.1f} ms | "
                    f"p95: {_percentile(latencies, 95):.1f} ms | Max: {max(latencies):.1f} ms",
                ],
            )

            assert ok_count == 100, f"Fallaron peticiones de lectura: {[s for s in statuses if s != 200]}"

    asyncio.run(_run())


def test_rafaga_15_reservas_y_pagos_wompi_paralelos() -> None:
    """Test 3: 15 reservas paralelas en slots distintos + 15 pagos Wompi Sandbox."""

    async def _run() -> None:
        limits = httpx.Limits(max_connections=60, max_keepalive_connections=50)
        timeout = httpx.Timeout(40.0, connect=10.0)
        created_ids: list[str] = []
        async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
            await _verify_gateway_up(client)
            courts = await _fetch_target_courts(client)
            users = await asyncio.gather(*[_register_temp_user(client, i + 100) for i in range(15)])

            base_date = date.today() + timedelta(days=random.randint(950, 1800))
            slots = []
            for idx in range(15):
                court = courts[idx % len(courts)]
                # Combinacion unica (cancha, dia, hora) para que las 15 sean validas sin colision
                day_offset = idx // 8
                hour = 8 + (idx % 8)
                slots.append(
                    {
                        "cancha_id": court["cancha_id"],
                        "complejo_id": court["complejo_id"],
                        "tarifa": court["tarifa_por_hora"],
                        "fecha": (base_date + timedelta(days=day_offset)).isoformat(),
                        "hora_inicio": f"{hour:02d}:00",
                        "hora_fin": f"{hour + 1:02d}:00",
                        "user": users[idx],
                        "metodo": "WOMPI_NEQUI" if idx % 2 == 0 else "WOMPI_PSE",
                    }
                )

            try:
                # Paso 1: 15 reservas simultaneas
                t_res_start = time.perf_counter()

                async def _book(item: dict) -> tuple[int, float, dict | None]:
                    t0 = time.perf_counter()
                    resp = await client.post(
                        f"{GATEWAY_URL}/reservas",
                        json={
                            "cancha_id": item["cancha_id"],
                            "complejo_id": item["complejo_id"],
                            "fecha": item["fecha"],
                            "hora_inicio": item["hora_inicio"],
                            "hora_fin": item["hora_fin"],
                            "monto": item["tarifa"],
                            "nombre_cliente": item["user"]["nombre"],
                            "cliente_nombre": item["user"]["nombre"],
                        },
                        headers={"X-User-Id": item["user"]["id"]},
                    )
                    ms = (time.perf_counter() - t0) * 1000.0
                    return resp.status_code, ms, resp.json() if resp.status_code == 201 else None

                res_results = await asyncio.gather(*[_book(s) for s in slots])
                res_total_s = time.perf_counter() - t_res_start
                res_latencies = [r[1] for r in res_results]
                created_items = []
                for idx, (status, _, body) in enumerate(res_results):
                    assert status == 201 and body is not None, f"Fallo reserva paralela #{idx}: status={status}"
                    created_ids.append(body["id"])
                    created_items.append((slots[idx], body["id"]))

                # Paso 2: 15 pagos Wompi Sandbox simultaneos
                t_pay_start = time.perf_counter()

                async def _pay(item: dict, reserva_id: str) -> tuple[int, float, str]:
                    t0 = time.perf_counter()
                    resp = await client.post(
                        f"{GATEWAY_URL}/pagos/procesar",
                        json={
                            "reserva_id": reserva_id,
                            "usuario_id": item["user"]["id"],
                            "complejo_id": item["complejo_id"],
                            "monto": item["tarifa"],
                            "metodo": item["metodo"],
                            "simular_resultado": "APROBADO",
                        },
                        headers={"X-User-Id": item["user"]["id"]},
                    )
                    ms = (time.perf_counter() - t0) * 1000.0
                    estado = resp.json().get("estado", "") if resp.status_code in (200, 201) else resp.text[:100]
                    return resp.status_code, ms, estado

                pay_results = await asyncio.gather(*[_pay(item, rid) for item, rid in created_items])
                pay_total_s = time.perf_counter() - t_pay_start
                pay_latencies = [r[1] for r in pay_results]
                approved = sum(1 for s, _, est in pay_results if s in (200, 201) and est == "APROBADO")

                # Paso 3: Verificar salud de servicios y RabbitMQ / notificaciones tras la rafaga
                health_resp = await client.get(f"{GATEWAY_URL}/health")
                notif_resp = await client.get(f"{GATEWAY_URL}/notificaciones/logs/stats")

                _print_metrics_block(
                    "TEST 3: RAFAGA 15 RESERVAS + 15 PAGOS WOMPI PARALELOS",
                    [
                        f"Reservas creadas (201): {len(created_items)}/15 en {res_total_s:.2f} s "
                        f"(prom {sum(res_latencies)/len(res_latencies):.1f} ms, p95 {_percentile(res_latencies, 95):.1f} ms)",
                        f"Pagos Wompi APROBADOS: {approved}/15 en {pay_total_s:.2f} s "
                        f"(prom {sum(pay_latencies)/len(pay_latencies):.1f} ms, p95 {_percentile(pay_latencies, 95):.1f} ms)",
                        f"Gateway /health: {health_resp.status_code} | Notificaciones /stats: {notif_resp.status_code}",
                    ],
                )

                assert approved == 15, f"Solo se aprobaron {approved}/15 pagos Wompi: {pay_results}"
                assert health_resp.status_code == 200, "Gateway degradado tras rafaga"
                assert notif_resp.status_code == 200, "ms_notificaciones no respondio tras rafaga RabbitMQ"
            finally:
                await _cleanup_reservations(client, created_ids)

    asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "-s"]))
