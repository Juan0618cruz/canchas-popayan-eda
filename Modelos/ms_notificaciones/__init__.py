"""
MVC Layer: Model (Modelo) — SQLite-backed Email notification log model & store for ms_notificaciones.
"""

import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import settings

_DB_LOCK = threading.Lock()
_DB_INITIALIZED = False
email_inbox: list["EmailLog"] = []


def _resolve_db_path() -> Path:
    configured = Path(settings.NOTIF_DB_PATH)
    try:
        configured.parent.mkdir(parents=True, exist_ok=True)
        return configured
    except OSError:
        fallback = Path("/tmp/notificaciones.db")
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return fallback


_DB_PATH = _resolve_db_path()


@dataclass
class EmailLog:
    """Represents a single email notification record persisted in SQLite."""

    to_email: str
    to_name: str
    subject: str
    body: str
    event_type: str
    aggregate_id: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str = "ENVIADO_SIMULADO"
    error_detail: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialise the log entry to a plain dictionary."""
        return asdict(self)


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return

    with _DB_LOCK:
        if _DB_INITIALIZED:
            return
        with _get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS email_logs (
                    id TEXT PRIMARY KEY,
                    to_email TEXT NOT NULL,
                    to_name TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    aggregate_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_detail TEXT
                )
                """
            )
            conn.commit()
        _DB_INITIALIZED = True


def _row_to_email_log(row: sqlite3.Row) -> EmailLog:
    return EmailLog(
        id=row["id"],
        to_email=row["to_email"],
        to_name=row["to_name"],
        subject=row["subject"],
        body=row["body"],
        event_type=row["event_type"],
        aggregate_id=row["aggregate_id"],
        timestamp=row["timestamp"],
        status=row["status"],
        error_detail=row["error_detail"],
    )


def ensure_seed_emails() -> None:
    """Preload demo emails once if the database table is empty."""
    _init_db()
    with _DB_LOCK:
        with _get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM email_logs").fetchone()[0]
            if count > 0:
                return

    demo_events = [
        EmailLog(
            id=str(uuid.uuid4()),
            to_email="deportista@test.com",
            to_name="Carlos Gómez",
            subject="¡Pago Confirmado! Reserva RES-001",
            body="Reserva RES-001 confirmada vía Wompi · Nequi para Cancha Sintética El Golazo el 2026-11-09 a las 18:00. Monto: $70.000 COP.",
            event_type="PagoAprobado",
            aggregate_id=str(uuid.uuid4()),
            timestamp="2026-11-09T14:35:10Z",
            status="ENVIADO_SIMULADO",
            error_detail="Registro de demostración precargado.",
        ),
        EmailLog(
            id=str(uuid.uuid4()),
            to_email="deportista@test.com",
            to_name="Carlos Gómez",
            subject="Reserva Reprogramada - RES-002",
            body="Tu reserva RES-002 ha sido reprogramada satisfactoriamente para la fecha 2026-11-12 de 19:00 a 20:00.",
            event_type="ReservaReprogramada",
            aggregate_id=str(uuid.uuid4()),
            timestamp="2026-11-08T17:40:00Z",
            status="ENVIADO_SIMULADO",
            error_detail="Registro de demostración precargado.",
        ),
    ]
    for log in demo_events:
        save_email(log)


def save_email(email_log: EmailLog) -> None:
    """Persist an EmailLog row to SQLite DB."""
    _init_db()
    with _DB_LOCK:
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO email_logs
                (id, to_email, to_name, subject, body, event_type, aggregate_id, timestamp, status, error_detail)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    email_log.id,
                    email_log.to_email,
                    email_log.to_name,
                    email_log.subject,
                    email_log.body,
                    email_log.event_type,
                    email_log.aggregate_id,
                    email_log.timestamp,
                    email_log.status,
                    email_log.error_detail,
                ),
            )
            conn.commit()


def get_all_emails() -> list[EmailLog]:
    """Return all emails sorted by timestamp descending (newest first)."""
    ensure_seed_emails()
    with _DB_LOCK:
        with _get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM email_logs ORDER BY timestamp DESC"
            ).fetchall()
            return [_row_to_email_log(r) for r in rows]


def get_emails_by_event_type(event_type: str) -> list[EmailLog]:
    """Return all emails matching the given event_type, newest first."""
    ensure_seed_emails()
    with _DB_LOCK:
        with _get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM email_logs WHERE event_type = ? ORDER BY timestamp DESC",
                (event_type,),
            ).fetchall()
            return [_row_to_email_log(r) for r in rows]


def get_stats() -> dict[str, int]:
    """Return email notification counts grouped by event_type."""
    counts: dict[str, int] = {}
    for log in get_all_emails():
        counts[log.event_type] = counts.get(log.event_type, 0) + 1
    return counts


__all__ = [
    "EmailLog",
    "email_inbox",
    "save_email",
    "get_all_emails",
    "get_emails_by_event_type",
    "get_stats",
    "ensure_seed_emails",
]
