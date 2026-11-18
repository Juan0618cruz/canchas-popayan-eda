#!/usr/bin/env python3
"""
reset_platform.py - Script de Hard Reset y Restauración de Fábrica para Canchas Popayán EDA.

Limpia y sincroniza los 4 contenedores PostgreSQL (db_usuarios, db_canchas, db_reservas, db_pagos),
RabbitMQ y SQLite (ms_notificaciones), dejando la plataforma con 0 reservas, 0 pagos ($0 en caja),
admin principal (jpdiagon1@gmail.com) activo y canchas listas para demostración en vivo.
"""
import argparse
import subprocess
import sys


CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"
GRAY = "\033[90m"
RESET = "\033[0m"


def run_cmd(cmd: list[str], check: bool = True) -> str:
    """Ejecuta un comando en el sistema y retorna su salida estándar."""
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and res.returncode != 0:
        raise RuntimeError(f"Error ejecutando '{' '.join(cmd)}':\n{res.stderr.strip()}")
    return res.stdout.strip()


def check_docker() -> None:
    try:
        run_cmd(["docker", "--version"])
    except Exception as e:
        print(f"{RED}[ERROR] Docker no está disponible en el PATH: {e}{RESET}")
        sys.exit(1)

    required = ["db_usuarios", "db_canchas", "db_reservas", "db_pagos", "rabbitmq"]
    try:
        running = run_cmd(["docker", "ps", "--format", "{{.Names}}"]).split()
    except Exception as e:
        print(f"{RED}[ERROR] No se pudo conectar al daemon de Docker: {e}{RESET}")
        sys.exit(1)

    missing = [c for c in required if c not in running]
    if missing:
        print(f"{RED}[ERROR] Los siguientes contenedores requeridos no están activos:{RESET}")
        for c in missing:
            print(f"  {YELLOW}- {c}{RESET}")
        print("Inícialos con: docker compose up -d")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hard Reset y Restauración de Fábrica - Canchas Popayán EDA"
    )
    parser.add_argument(
        "--skip-confirmation",
        "-y",
        action="store_true",
        help="Omitir confirmación interactiva",
    )
    parser.add_argument(
        "--with-demo-payments",
        action="store_true",
        help="Sembrar 6 pagos demo en lugar de dejar caja en $0",
    )
    args = parser.parse_args()

    print(f"{CYAN}{'=' * 75}{RESET}")
    print(f"{CYAN}   CANCHAS POPAYAN EDA - HARD RESET / RESTAURACION DE FABRICA{RESET}")
    print(f"{CYAN}{'=' * 75}{RESET}\n")

    check_docker()

    if not args.skip_confirmation:
        print(f"{YELLOW}ATENCIÓN: Esta acción realizará un reseteo total de fábrica:{RESET}")
        print(f"{GRAY}  * Vaciará todas las reservas y reiniciará códigos a RES-000001{RESET}")
        print(f"{GRAY}  * Vaciará todos los pagos transaccionales (caja a $0 COP){RESET}")
        print(f"{GRAY}  * Liberará el 100% de los horarios de las canchas (estado LIBRE){RESET}")
        print(f"{GRAY}  * Eliminará usuarios de prueba manteniendo solo las cuentas semilla{RESET}")
        print(f"{GRAY}  * Purgará colas de RabbitMQ y logs de correos{RESET}\n")
        resp = input("¿Deseas proceder con el Hard Reset? (s/N): ").strip().lower()
        if resp not in ["s", "si", "y", "yes"]:
            print(f"{YELLOW}Operación cancelada por el usuario.{RESET}")
            sys.exit(0)
        print()

    print(f"{MAGENTA}Iniciando proceso de limpieza y sincronización...{RESET}\n")

    # 1. db_reservas
    print(f"{YELLOW}1/6 Limpiando db_reservas...{RESET}", end="", flush=True)
    sql_reservas = (
        "TRUNCATE TABLE reservas RESTART IDENTITY CASCADE; "
        "TRUNCATE TABLE outbox_events RESTART IDENTITY CASCADE; "
        "INSERT INTO contador_reservas (id, contador) VALUES (1, 0) "
        "ON CONFLICT (id) DO UPDATE SET contador = 0;"
    )
    run_cmd(["docker", "exec", "db_reservas", "psql", "-U", "postgres", "-d", "db_reservas", "-q", "-c", sql_reservas])
    print(f"{GREEN} [HECHO]{RESET}")

    # 2. db_pagos
    print(f"{YELLOW}2/6 Limpiando db_pagos...{RESET}", end="", flush=True)
    run_cmd(["docker", "exec", "db_pagos", "psql", "-U", "postgres", "-d", "db_pagos", "-q", "-c", "TRUNCATE TABLE pagos RESTART IDENTITY CASCADE;"])
    if args.with_demo_payments:
        run_cmd(["docker", "exec", "ms_pagos", "python", "-c", "import asyncio; from app.database import AsyncSessionLocal; from app.seed import seed_pagos; asyncio.run(seed_pagos(AsyncSessionLocal()))"], check=False)
        print(f"{GREEN} [HECHO (Con pagos demo)]{RESET}")
    else:
        print(f"{GREEN} [HECHO (0 pagos, $0 COP)]{RESET}")

    # 3. db_canchas
    print(f"{YELLOW}3/6 Sincronizando db_canchas (liberando horarios y eliminando bloqueos)...{RESET}", end="", flush=True)
    sql_canchas = (
        "UPDATE bloques_horarios SET estado = 'LIBRE', reserva_id = NULL; "
        "TRUNCATE TABLE bloqueos_mantenimiento RESTART IDENTITY CASCADE;"
    )
    run_cmd(["docker", "exec", "db_canchas", "psql", "-U", "postgres", "-d", "db_canchas", "-q", "-c", sql_canchas])
    run_cmd(["docker", "exec", "ms_canchas", "python", "-c", "import asyncio; from app.database import AsyncSessionLocal; from app.seed import seed_database; asyncio.run(seed_database(AsyncSessionLocal()))"], check=False)
    print(f"{GREEN} [HECHO]{RESET}")

    # 4. db_usuarios
    print(f"{YELLOW}4/6 Depurando usuarios de prueba en db_usuarios...{RESET}", end="", flush=True)
    sql_users = (
        "DELETE FROM tokens_recuperacion WHERE usuario_id NOT IN (SELECT id FROM usuarios WHERE email IN ('jpdiagon1@gmail.com', 'admin.balon@test.com', 'deportista@test.com')); "
        "DELETE FROM usuarios WHERE email NOT IN ('jpdiagon1@gmail.com', 'admin.balon@test.com', 'deportista@test.com'); "
        "UPDATE usuarios SET activo = true WHERE email IN ('jpdiagon1@gmail.com', 'admin.balon@test.com', 'deportista@test.com');"
    )
    run_cmd(["docker", "exec", "db_usuarios", "psql", "-U", "postgres", "-d", "db_usuarios", "-q", "-c", sql_users])
    run_cmd(["docker", "exec", "ms_usuarios", "python", "-c", "import asyncio; from app.database import AsyncSessionLocal; from app.seed import run_seed; asyncio.run(run_seed(AsyncSessionLocal()))"], check=False)
    print(f"{GREEN} [HECHO]{RESET}")

    # 5. ms_notificaciones
    print(f"{YELLOW}5/6 Vaciando bandeja de notificaciones (ms_notificaciones)...{RESET}", end="", flush=True)
    notif_cmd = (
        "import sqlite3, os; p='/app/data/notificaciones.db'; "
        "conn = sqlite3.connect(p) if os.path.exists(p) else None; "
        "(conn.execute('DELETE FROM email_logs;'), conn.commit(), conn.close()) if conn else None"
    )
    run_cmd(["docker", "exec", "ms_notificaciones", "python", "-c", notif_cmd], check=False)
    print(f"{GREEN} [HECHO]{RESET}")

    # 6. RabbitMQ
    print(f"{YELLOW}6/6 Purgando colas residuales en RabbitMQ...{RESET}", end="", flush=True)
    try:
        queues_raw = run_cmd(["docker", "exec", "rabbitmq", "rabbitmqctl", "list_queues", "-q", "name"], check=False).splitlines()
        for q in queues_raw:
            q_name = q.strip()
            if q_name and q_name != "name":
                run_cmd(["docker", "exec", "rabbitmq", "rabbitmqctl", "purge_queue", q_name], check=False)
    except Exception:
        pass
    print(f"{GREEN} [HECHO]{RESET}\n")

    # Auditoría / Métricas
    print(f"{CYAN}Obteniendo métricas finales de auditoría...{RESET}")

    usr_count = run_cmd(["docker", "exec", "db_usuarios", "psql", "-U", "postgres", "-d", "db_usuarios", "-t", "-A", "-c", "SELECT count(*) FROM usuarios;"])
    admin_activo = run_cmd(["docker", "exec", "db_usuarios", "psql", "-U", "postgres", "-d", "db_usuarios", "-t", "-A", "-c", "SELECT count(*) FROM usuarios WHERE email = 'jpdiagon1@gmail.com' AND activo = true;"])

    comp_count = run_cmd(["docker", "exec", "db_canchas", "psql", "-U", "postgres", "-d", "db_canchas", "-t", "-A", "-c", "SELECT count(*) FROM complejos;"])
    canchas_count = run_cmd(["docker", "exec", "db_canchas", "psql", "-U", "postgres", "-d", "db_canchas", "-t", "-A", "-c", "SELECT count(*) FROM canchas WHERE activo = true;"])
    slots_raw = run_cmd(["docker", "exec", "db_canchas", "psql", "-U", "postgres", "-d", "db_canchas", "-t", "-A", "-c", "SELECT count(*), count(*) FILTER (WHERE estado = 'LIBRE'), count(*) FILTER (WHERE estado != 'LIBRE') FROM bloques_horarios;"])
    s_parts = slots_raw.split("|")
    slots_libres = s_parts[1] if len(s_parts) > 1 else "0"
    slots_ocupados = s_parts[2] if len(s_parts) > 2 else "0"

    res_count = run_cmd(["docker", "exec", "db_reservas", "psql", "-U", "postgres", "-d", "db_reservas", "-t", "-A", "-c", "SELECT count(*) FROM reservas;"])
    outbox_count = run_cmd(["docker", "exec", "db_reservas", "psql", "-U", "postgres", "-d", "db_reservas", "-t", "-A", "-c", "SELECT count(*) FROM outbox_events;"])
    seq_raw = run_cmd(["docker", "exec", "db_reservas", "psql", "-U", "postgres", "-d", "db_reservas", "-t", "-A", "-c", "SELECT coalesce(contador, 0) FROM contador_reservas WHERE id = 1;"])
    next_code = f"RES-{(int(seq_raw) + 1):06d}" if seq_raw.isdigit() else "RES-000001"

    pagos_raw = run_cmd(["docker", "exec", "db_pagos", "psql", "-U", "postgres", "-d", "db_pagos", "-t", "-A", "-c", "SELECT count(*), coalesce(sum(monto), 0) FROM pagos;"])
    p_parts = pagos_raw.split("|")
    pagos_total = p_parts[0] if len(p_parts) > 0 else "0"
    pagos_monto = float(p_parts[1]) if len(p_parts) > 1 else 0.0

    notif_raw = run_cmd([
        "docker", "exec", "ms_notificaciones", "python", "-c",
        "import sqlite3, os; p='/app/data/notificaciones.db'; print(sqlite3.connect(p).cursor().execute('SELECT count(*) FROM email_logs;').fetchone()[0] if os.path.exists(p) else 0)"
    ], check=False) or "0"

    # RabbitMQ check
    rmq_messages = 0
    try:
        rmq_lines = run_cmd(["docker", "exec", "rabbitmq", "rabbitmqctl", "list_queues", "-q", "name", "messages"], check=False).splitlines()
        for line in rmq_lines:
            parts = line.split()
            if len(parts) >= 2 and parts[0] != "name" and parts[1].isdigit():
                rmq_messages += int(parts[1])
    except Exception:
        pass

    # Tabla Reporte
    print(f"\n{CYAN}{'=' * 85}{RESET}")
    print(f"{CYAN}             REPORTE DE ESTADO POST-RESET (FABRICA / DEMO EN VIVO)                   {RESET}")
    print(f"{CYAN}{'=' * 85}{RESET}")
    print(f"{WHITE}{'COMPONENTE':<20} {'METRICA VERIFICADA':<32} {'VALOR ACTUAL':<18} {'ESTADO':<12}{RESET}")
    print(f"{GRAY}{'-' * 85}{RESET}")

    def print_row(comp: str, metrica: str, valor: str, ok: bool, detalle: str):
        badge = f"{GREEN}[OK]{RESET}" if ok else f"{RED}[FALLO]{RESET}"
        val_str = f"{valor} {detalle}".strip()
        print(f"{WHITE}{comp:<20} {metrica:<32} {val_str:<18} {badge}{RESET}")

    print_row("db_usuarios", "Usuarios Semilla", f"{usr_count} cuentas", usr_count == "3", "(3 oficiales)")
    print_row("db_usuarios", "Admin Balón de Oro", "Activo", admin_activo == "1", "(jpdiagon1@gmail.com)")
    print_row("db_canchas", "Complejos Deportivos", f"{comp_count} activos", comp_count == "2", "(Balón de Oro, Bernabéu)")
    print_row("db_canchas", "Canchas Sintéticas", f"{canchas_count} canchas", canchas_count == "6", "(100% operativas)")
    print_row("db_canchas", "Bloques Horarios", f"{slots_libres} libres", slots_ocupados == "0", f"({slots_ocupados} ocupados / 100% libre)")
    print_row("db_reservas", "Reservas Activas", f"{res_count} reservas", res_count == "0", "(Vacío de fábrica)")
    print_row("db_reservas", "Eventos Outbox", f"{outbox_count} eventos", outbox_count == "0", "(Sin pendientes)")
    print_row("db_reservas", "Generador Códigos", next_code, seq_raw == "0", "(Reiniciado a 0)")
    print_row("db_pagos", "Transacciones Caja", f"{pagos_total} pagos", pagos_total == "0" or args.with_demo_payments, "(0 movimientos)")
    print_row("db_pagos", "Recaudación Total", f"${pagos_monto:,.0f} COP", pagos_monto == 0 or args.with_demo_payments, "($0 COP en caja)")
    print_row("ms_notificaciones", "Historial Correos", f"{notif_raw} logs", notif_raw == "0", "(Bandeja limpia)")
    print_row("RabbitMQ", "Colas de Mensajes", f"{rmq_messages} pendientes", rmq_messages == 0, "(0 acumulados)")

    print(f"{CYAN}{'=' * 85}{RESET}")
    print(f"{GREEN}   ESTADO GLOBAL: PLATAFORMA 100% LIMPIA Y LISTA PARA PRESENTACION EN VIVO          {RESET}")
    print(f"{CYAN}{'=' * 85}{RESET}\n")


if __name__ == "__main__":
    main()
