"""/auth API — login + current user + admin user management (see docs/auth-design.md)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import db
from .deps import get_current_user, require_admin
from .security import make_token

# Initialise the store (create table + seed demo accounts) on import.
db.init_db()

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


class CreateUserIn(BaseModel):
    email: str
    name: str
    role: str
    password: str = Field(min_length=8)
    active: bool = True


class UpdateUserIn(BaseModel):
    role: str | None = None
    active: bool | None = None


class PasswordIn(BaseModel):
    password: str = Field(min_length=8)


# ----------------------------------------------------------------- session ---

@router.post("/login")
def login(body: LoginIn):
    user = db.verify_credentials(body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="invalid credentials")
    return {"token": make_token(user["id"], user["role"]), "user": user}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/logout")
def logout(_: dict = Depends(get_current_user)):
    # Stateless JWT: the BFF clears the cookie. Endpoint exists for symmetry/audit.
    return {"ok": True}


# ----------------------------------------------------------- admin: users ----

@router.get("/users")
def list_users(_: dict = Depends(require_admin)):
    return db.list_users()


@router.post("/users", status_code=201)
def create_user(body: CreateUserIn, _: dict = Depends(require_admin)):
    try:
        return db.create_user(body.email, body.name, body.role, body.password, body.active)
    except db.EmailExistsError:
        raise HTTPException(status_code=409, detail="email already exists")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.patch("/users/{user_id}")
def update_user(user_id: str, body: UpdateUserIn, admin: dict = Depends(require_admin)):
    target = db.get_user(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    # Guard: don't let an admin demote/deactivate the last active admin (incl. self).
    removing_admin = (body.role is not None and body.role != "admin") or body.active is False
    if target["role"] == "admin" and removing_admin and db.count_admins() <= 1:
        raise HTTPException(status_code=409, detail="cannot remove the last active admin")
    try:
        return db.update_user(user_id, role=body.role, active=body.active)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/users/{user_id}/password")
def reset_password(user_id: str, body: PasswordIn, _: dict = Depends(require_admin)):
    try:
        if not db.set_password(user_id, body.password):
            raise HTTPException(status_code=404, detail="user not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"ok": True}


@router.delete("/users/{user_id}")
def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    target = db.get_user(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    if target["role"] == "admin" and db.count_admins() <= 1:
        raise HTTPException(status_code=409, detail="cannot delete the last active admin")
    db.delete_user(user_id)
    return {"ok": True}
