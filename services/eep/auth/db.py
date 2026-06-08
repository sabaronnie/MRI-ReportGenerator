"""SQLite user store + first-boot seed (see docs/auth-design.md).

stdlib sqlite3, no DB server. The DB file is gitignored. Password hashes are
stored; plaintext never is. `verify_credentials` is the login entry point.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
import uuid

from .security import hash_password, verify_password

VALID_ROLES = ("admin", "radiologist", "technologist", "viewer")

_DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "data", "users.db")
DB_PATH = os.environ.get("USERS_DB_PATH", _DEFAULT_DB)

_lock = threading.Lock()


class EmailExistsError(Exception):
    """Raised when creating a user whose email is already taken."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _to_public(row: sqlite3.Row) -> dict:
    """User dict WITHOUT the password hash — safe to return to clients."""
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "role": row["role"],
        "active": bool(row["active"]),
        "created_at": row["created_at"],
    }


def init_db() -> None:
    with _lock, _connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )"""
        )
    seed_if_empty()


def get_user(user_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _to_public(row) if row else None


def get_by_email(email: str) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
        ).fetchone()


def list_users() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
    return [_to_public(r) for r in rows]


def create_user(email: str, name: str, role: str, password: str, active: bool = True) -> dict:
    if role not in VALID_ROLES:
        raise ValueError(f"invalid role: {role}")
    if len(password) < 8:
        raise ValueError("password too short (min 8)")
    uid = str(uuid.uuid4())
    try:
        with _lock, _connect() as conn:
            conn.execute(
                "INSERT INTO users (id,email,name,role,password_hash,active,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (uid, email.strip().lower(), name.strip(), role,
                 hash_password(password), 1 if active else 0, _now()),
            )
    except sqlite3.IntegrityError as exc:
        raise EmailExistsError(email) from exc
    return get_user(uid)  # type: ignore[return-value]


def update_user(user_id: str, *, role: str | None = None, active: bool | None = None) -> dict | None:
    sets, args = [], []
    if role is not None:
        if role not in VALID_ROLES:
            raise ValueError(f"invalid role: {role}")
        sets.append("role = ?")
        args.append(role)
    if active is not None:
        sets.append("active = ?")
        args.append(1 if active else 0)
    if not sets:
        return get_user(user_id)
    args.append(user_id)
    with _lock, _connect() as conn:
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", args)
    return get_user(user_id)


def set_password(user_id: str, password: str) -> bool:
    if len(password) < 8:
        raise ValueError("password too short (min 8)")
    with _lock, _connect() as conn:
        cur = conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(password), user_id),
        )
    return cur.rowcount > 0


def delete_user(user_id: str) -> bool:
    with _lock, _connect() as conn:
        cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return cur.rowcount > 0


def count_admins() -> int:
    with _connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'admin' AND active = 1"
        ).fetchone()[0]


def verify_credentials(email: str, password: str) -> dict | None:
    """Login: returns the public user on success, else None (and only for active users)."""
    row = get_by_email(email)
    if not row or not bool(row["active"]):
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return _to_public(row)


def seed_if_empty() -> None:
    """First boot: create the four demo accounts so the app is usable immediately.

    Dev passwords come from env (DEMO_PASSWORD; admin can be overridden via
    ADMIN_EMAIL/ADMIN_PASSWORD). These are DEV defaults — override in any real deploy.
    """
    with _connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if n:
        return
    demo_pw = os.environ.get("DEMO_PASSWORD", "demo12345")
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@demo")
    admin_pw = os.environ.get("ADMIN_PASSWORD", demo_pw)
    seed = [
        (admin_email, "Admin", "admin", admin_pw),
        ("radiologist@demo", "Dr. Rana Radiologist", "radiologist", demo_pw),
        ("tech@demo", "Tariq Technologist", "technologist", demo_pw),
        ("viewer@demo", "Nadia (referring)", "viewer", demo_pw),
    ]
    for email, name, role, pw in seed:
        try:
            create_user(email, name, role, pw)
        except EmailExistsError:
            pass
