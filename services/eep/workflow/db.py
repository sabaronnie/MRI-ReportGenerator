"""SQLite store for workflow state — case assignment + report addenda.

Separate DB file (workflow.db, gitignored) keyed by case_id. Independent of the
in-memory case store so nothing in store.py / routers/cases.py changes.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
import uuid

_DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "data", "workflow.db")
DB_PATH = os.environ.get("WORKFLOW_DB_PATH", _DEFAULT_DB)

_lock = threading.Lock()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _lock, _connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS case_assignment (
                case_id TEXT PRIMARY KEY,
                assignee_id TEXT NOT NULL,
                assignee_name TEXT NOT NULL,
                claimed_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS case_addendum (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                author_id TEXT NOT NULL,
                author_name TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )


# ----------------------------------------------------------------- assignment ---

def get_assignment(case_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM case_assignment WHERE case_id = ?", (case_id,)
        ).fetchone()
    return dict(row) if row else None

def assignments_for(case_ids: list[str]) -> dict[str, dict]:
    """Bulk lookup keyed by case_id (for the worklist)."""
    if not case_ids:
        return {}
    placeholders = ",".join("?" for _ in case_ids)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM case_assignment WHERE case_id IN ({placeholders})", case_ids
        ).fetchall()
    return {r["case_id"]: dict(r) for r in rows}


def set_assignment(case_id: str, assignee_id: str, assignee_name: str) -> dict:
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO case_assignment (case_id, assignee_id, assignee_name, claimed_at) "
            "VALUES (?,?,?,?) "
            "ON CONFLICT(case_id) DO UPDATE SET assignee_id=excluded.assignee_id, "
            "assignee_name=excluded.assignee_name, claimed_at=excluded.claimed_at",
            (case_id, assignee_id, assignee_name, _now()),
        )
    return get_assignment(case_id)  # type: ignore[return-value]


def clear_assignment(case_id: str) -> None:
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM case_assignment WHERE case_id = ?", (case_id,))


# ------------------------------------------------------------------- addenda ---

def add_addendum(case_id: str, author_id: str, author_name: str, text: str) -> dict:
    aid = str(uuid.uuid4())
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO case_addendum (id, case_id, author_id, author_name, text, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (aid, case_id, author_id, author_name, text.strip(), _now()),
        )
    return list_addenda(case_id)[-1]


def list_addenda(case_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM case_addendum WHERE case_id = ? ORDER BY created_at", (case_id,)
        ).fetchall()
    return [dict(r) for r in rows]
