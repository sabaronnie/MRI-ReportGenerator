"""FastAPI auth guards (see docs/auth-design.md).

`get_current_user` decodes the Bearer JWT, then RE-LOADS the user from the DB and
checks `active` — so deactivating/deleting a user takes effect immediately and the
role is always read fresh (token role is advisory). `require_admin` builds on it.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from . import db
from .security import decode_token


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    payload = decode_token(authorization.split(" ", 1)[1].strip())
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="invalid or expired token")
    user = db.get_user(payload["sub"])
    if not user or not user["active"]:
        raise HTTPException(status_code=401, detail="user inactive or not found")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="admin only")
    return user
