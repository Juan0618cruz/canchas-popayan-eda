"""
Backward-compatible re-export shim for ms_notificaciones EmailLog store (MVC Model).
"""

from app.models import (
    EmailLog,
    email_inbox,
    ensure_seed_emails,
    get_all_emails,
    get_emails_by_event_type,
    get_stats,
    save_email,
)

__all__ = [
    "EmailLog",
    "email_inbox",
    "ensure_seed_emails",
    "save_email",
    "get_all_emails",
    "get_emails_by_event_type",
    "get_stats",
]
