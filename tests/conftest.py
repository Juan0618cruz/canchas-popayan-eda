"""
Shared pytest configuration, service isolation loader, and in-memory AsyncSession
test double for all Canchas Popayán EDA microservices.

Because every microservice defines its package under `app.*`, `load_service_modules`
isolates `sys.path` and `sys.modules["app*"]` per microservice and caches each
service's module tree so tests can run either together (`pytest tests/`) or one by one.
"""

from __future__ import annotations

import importlib
import operator
import os
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import pytest
from sqlalchemy.sql.dml import Delete
from sqlalchemy.sql.elements import (
    BinaryExpression,
    BindParameter,
    BooleanClauseList,
    False_,
    Null,
    True_,
    UnaryExpression,
)
from sqlalchemy.sql.selectable import Select

TESTS_DIR = Path(__file__).resolve().parent
ROOT_DIR = TESTS_DIR.parent

for _p in (str(ROOT_DIR), str(TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ALL_SERVICE_DIRS = [
    "api_gateway",
    "ms_usuarios",
    "ms_canchas",
    "ms_reservas",
    "ms_pagos",
    "ms_notificaciones",
]

# Ensure shared test JWT secret & safe local temp upload dir across services
os.environ.setdefault("JWT_SECRET", "canchas-popayan-test-jwt-secret-2026")
os.environ.setdefault("WOMPI_SANDBOX", "true")
os.environ.setdefault(
    "UPLOADS_DIR",
    str(Path(tempfile.gettempdir()) / "canchas_popayan_test_uploads"),
)

_SERVICE_MODULE_SNAPSHOTS: dict[str, dict[str, Any]] = {}


def _purge_app_modules() -> None:
    for key in list(sys.modules.keys()):
        if key == "app" or key.startswith("app."):
            del sys.modules[key]


def _set_service_sys_path(service_name: str) -> None:
    ctrl_path = ROOT_DIR / "Controladores" / service_name
    service_path = str(ctrl_path if ctrl_path.exists() else (ROOT_DIR / service_name))
    for s in ALL_SERVICE_DIRS:
        for parent in (ROOT_DIR / "Controladores", ROOT_DIR):
            candidate = str(parent / s)
            while candidate in sys.path:
                sys.path.remove(candidate)
    for _p in (str(TESTS_DIR), str(ROOT_DIR)):
        if _p not in sys.path:
            sys.path.insert(0, _p)
    sys.path.insert(0, service_path)


def activate_service(service_name: str) -> None:
    """Restore cached `app.*` modules and sys.path for the given microservice."""
    _set_service_sys_path(service_name)
    _purge_app_modules()
    snapshot = _SERVICE_MODULE_SNAPSHOTS.get(service_name)
    if snapshot:
        sys.modules.update(snapshot)


@contextmanager
def service_context(service_name: str, imports: Iterable[str]):
    """Import modules cleanly inside a dedicated `app.*` namespace per service."""
    _set_service_sys_path(service_name)
    _purge_app_modules()
    loaded: dict[str, Any] = {}
    try:
        for mod_name in imports:
            loaded[mod_name] = importlib.import_module(mod_name)
        _SERVICE_MODULE_SNAPSHOTS[service_name] = {
            k: v for k, v in sys.modules.items() if k == "app" or k.startswith("app.")
        }
        yield loaded
    finally:
        pass


# ---------------------------------------------------------------------------
# In-memory AsyncSession double for SQLAlchemy 2.0 ORM queries
# ---------------------------------------------------------------------------


class _FakeScalarResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return list(self._items)

    def first(self) -> Any:
        return self._items[0] if self._items else None

    def one_or_none(self) -> Any:
        if len(self._items) > 1:
            raise AssertionError(f"Expected <= 1 row, got {len(self._items)}")
        return self._items[0] if self._items else None


class _FakeResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def scalars(self) -> _FakeScalarResult:
        return _FakeScalarResult(self._items)

    def scalar_one_or_none(self) -> Any:
        return _FakeScalarResult(self._items).one_or_none()

    def first(self) -> Any:
        return self._items[0] if self._items else None

    def all(self) -> list[Any]:
        return list(self._items)


class _FakeTransaction:
    def __init__(self, session: "FakeAsyncSession") -> None:
        self._session = session

    async def __aenter__(self) -> "_FakeTransaction":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            await self._session.commit()
        else:
            await self._session.rollback()


def _extract_attr_name(expr: Any) -> str:
    if hasattr(expr, "key") and expr.key:
        return str(expr.key)
    if hasattr(expr, "name") and expr.name:
        return str(expr.name)
    raise ValueError(f"Cannot extract attribute name from {expr!r}")


def _extract_value(expr: Any) -> Any:
    if isinstance(expr, True_):
        return True
    if isinstance(expr, False_):
        return False
    if isinstance(expr, Null):
        return None
    if isinstance(expr, BindParameter):
        return expr.effective_value
    if hasattr(expr, "value"):
        return expr.value
    return expr


def _eval_criteria(row: Any, expr: Any) -> bool:
    if expr is None:
        return True

    if isinstance(expr, BooleanClauseList):
        if expr.operator == operator.and_:
            return all(_eval_criteria(row, c) for c in expr.clauses)
        if expr.operator == operator.or_:
            return any(_eval_criteria(row, c) for c in expr.clauses)

    if isinstance(expr, BinaryExpression):
        attr = _extract_attr_name(expr.left)
        lhs = getattr(row, attr, None)
        rhs = _extract_value(expr.right)
        op_name = getattr(expr.operator, "__name__", "")

        if op_name in ("eq", "is_"):
            return lhs == rhs
        if op_name in ("ne", "is_not"):
            return lhs != rhs
        if op_name == "in_op":
            return lhs in (rhs or [])
        if op_name in ("notin_op", "not_in_op"):
            return lhs not in (rhs or [])
        if op_name == "lt":
            return lhs is not None and lhs < rhs
        if op_name == "le":
            return lhs is not None and lhs <= rhs
        if op_name == "gt":
            return lhs is not None and lhs > rhs
        if op_name == "ge":
            return lhs is not None and lhs >= rhs

        try:
            return bool(expr.operator(lhs, rhs))
        except Exception:
            return False

    return True


def _apply_defaults(obj: Any) -> None:
    mapper = getattr(type(obj), "__mapper__", None)
    now = datetime.now(timezone.utc)
    if getattr(obj, "id", None) is None and hasattr(obj, "id"):
        col = mapper.columns.get("id") if mapper else None
        is_int = col is not None and "INT" in str(col.type).upper()
        obj.id = 1 if is_int else uuid.uuid4()

    for dt_field in ("created_at", "updated_at"):
        if hasattr(obj, dt_field) and getattr(obj, dt_field, None) is None:
            setattr(obj, dt_field, now)

    if hasattr(obj, "activo") and getattr(obj, "activo", None) is None:
        obj.activo = True

    if hasattr(obj, "published") and getattr(obj, "published", None) is None:
        obj.published = False


class FakeAsyncSession:
    """In-memory async SQLAlchemy-compatible session for FastAPI endpoint tests."""

    def __init__(self, initial_objects: Iterable[Any] = ()) -> None:
        self.store: dict[type, list[Any]] = {}
        self._pending: list[Any] = []
        for obj in initial_objects:
            self.add(obj)

    def all_of(self, model_cls: type) -> list[Any]:
        return list(self.store.get(model_cls, []))

    def add(self, obj: Any) -> None:
        _apply_defaults(obj)
        bucket = self.store.setdefault(type(obj), [])
        if obj not in bucket:
            bucket.append(obj)
        self._link_relationships(obj)

    def add_all(self, objs: Iterable[Any]) -> None:
        for obj in objs:
            self.add(obj)

    def _link_relationships(self, obj: Any) -> None:
        # Maintain bi-directional Cancha <-> Complejo references when both exist in store
        if hasattr(obj, "complejo_id") and hasattr(obj, "complejo"):
            for cls, rows in self.store.items():
                if cls.__name__ == "Complejo":
                    for comp in rows:
                        if comp.id == obj.complejo_id:
                            obj.complejo = comp
                            if hasattr(comp, "canchas") and obj not in comp.canchas:
                                comp.canchas.append(obj)

    async def delete(self, obj: Any) -> None:
        bucket = self.store.get(type(obj), [])
        if obj in bucket:
            bucket.remove(obj)

    async def flush(self) -> None:
        for rows in self.store.values():
            for row in rows:
                _apply_defaults(row)

    async def commit(self) -> None:
        await self.flush()

    async def rollback(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def refresh(self, obj: Any) -> None:
        _apply_defaults(obj)
        self._link_relationships(obj)

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction(self)

    async def execute(self, stmt: Any) -> _FakeResult:
        if isinstance(stmt, Delete):
            target_cls = stmt.table.entity_namespace if hasattr(stmt.table, "entity_namespace") else None
            # Find matching model bucket by __tablename__
            table_name = getattr(stmt.table, "name", None)
            for model_cls, rows in self.store.items():
                if getattr(model_cls, "__tablename__", None) == table_name or model_cls is target_cls:
                    kept = [
                        r for r in rows
                        if not all(_eval_criteria(r, c) for c in getattr(stmt, "_where_criteria", ()))
                    ]
                    self.store[model_cls] = kept
            return _FakeResult([])

        if isinstance(stmt, Select):
            entity = stmt.column_descriptions[0].get("entity")
            rows = list(self.store.get(entity, [])) if entity is not None else []
            for cond in getattr(stmt, "_where_criteria", ()):
                rows = [r for r in rows if _eval_criteria(r, cond)]

            for order_expr in reversed(getattr(stmt, "_order_by_clauses", ())):
                desc = False
                col = order_expr
                if isinstance(order_expr, UnaryExpression):
                    desc = getattr(order_expr.modifier, "__name__", "") == "desc_op"
                    col = order_expr.element
                try:
                    attr = _extract_attr_name(col)
                    rows.sort(
                        key=lambda r: (getattr(r, attr, None) is None, getattr(r, attr, None)),
                        reverse=desc,
                    )
                except Exception:
                    pass

            limit_val = getattr(stmt, "_limit_clause", None)
            if limit_val is not None:
                n = _extract_value(limit_val)
                if isinstance(n, int):
                    rows = rows[:n]

            return _FakeResult(rows)

        return _FakeResult([])
