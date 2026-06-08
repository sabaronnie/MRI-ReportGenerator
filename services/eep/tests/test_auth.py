"""Auth tests — password hashing, JWT, login, role enforcement, revocation.

Uses a throwaway SQLite DB (env set before import) so it never touches the real
store. Run: pytest services/eep/tests/test_auth.py
"""

import os
import tempfile
import time

# Point the user store at a temp DB + set a test secret BEFORE importing the app.
_TMP_DB = os.path.join(tempfile.mkdtemp(), "users_test.db")
os.environ["USERS_DB_PATH"] = _TMP_DB
os.environ["JWT_SECRET"] = "test-secret"
os.environ["DEMO_PASSWORD"] = "demo12345"

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from services.eep.app import app  # noqa: E402
from services.eep.auth import security  # noqa: E402

client = TestClient(app)


# ----------------------------------------------------------------- security ---

def test_password_hash_roundtrip():
    h = security.hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"
    assert security.verify_password("correct horse battery staple", h)
    assert not security.verify_password("wrong", h)


def test_jwt_roundtrip_and_alg_pinning():
    tok = security.make_token("user-1", "admin")
    payload = security.decode_token(tok)
    assert payload and payload["sub"] == "user-1" and payload["role"] == "admin"
    # Tampered / wrong-secret token is rejected.
    assert security.decode_token(tok + "x") is None
    # alg:none must be rejected (alg-confusion guard).
    forged = jwt.encode({"sub": "x", "role": "admin"}, key="", algorithm="none")
    assert security.decode_token(forged) is None


def test_expired_token_rejected():
    secret = os.environ["JWT_SECRET"]
    expired = jwt.encode(
        {"sub": "u", "role": "viewer", "iat": int(time.time()) - 100, "exp": int(time.time()) - 10},
        secret, algorithm="HS256",
    )
    assert security.decode_token(expired) is None


# -------------------------------------------------------------------- login ---

def test_login_success_and_failure():
    ok = client.post("/auth/login", json={"email": "admin@demo", "password": "demo12345"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["token"] and body["user"]["role"] == "admin"
    assert "password_hash" not in body["user"]

    bad = client.post("/auth/login", json={"email": "admin@demo", "password": "nope"})
    assert bad.status_code == 401


def _token(email="admin@demo", password="demo12345"):
    return client.post("/auth/login", json={"email": email, "password": password}).json()["token"]


def test_me_requires_token():
    assert client.get("/auth/me").status_code == 401
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {_token()}"})
    assert r.status_code == 200 and r.json()["email"] == "admin@demo"


def test_cases_route_is_guarded():
    assert client.get("/cases").status_code == 401  # no token
    r = client.get("/cases", headers={"Authorization": f"Bearer {_token()}"})
    assert r.status_code == 200


def test_health_routes_stay_open():
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200


# ------------------------------------------------------------- admin: users ---

def test_non_admin_cannot_manage_users():
    rad = _token("radiologist@demo", "demo12345")
    assert client.get("/auth/users", headers={"Authorization": f"Bearer {rad}"}).status_code == 403


def test_admin_user_crud_and_new_user_can_login():
    admin = {"Authorization": f"Bearer {_token()}"}
    created = client.post(
        "/auth/users", headers=admin,
        json={"email": "new.doc@hospital.org", "name": "New Doc", "role": "radiologist",
              "password": "s3cretpw!"},
    )
    assert created.status_code == 201
    uid = created.json()["id"]

    # Duplicate email → 409
    dup = client.post(
        "/auth/users", headers=admin,
        json={"email": "new.doc@hospital.org", "name": "x", "role": "viewer", "password": "s3cretpw!"},
    )
    assert dup.status_code == 409

    # The new user can log in.
    assert client.post("/auth/login", json={"email": "new.doc@hospital.org", "password": "s3cretpw!"}).status_code == 200

    # Deactivate → their token stops working (DB-backed revocation).
    new_tok = client.post("/auth/login", json={"email": "new.doc@hospital.org", "password": "s3cretpw!"}).json()["token"]
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {new_tok}"}).status_code == 200
    client.patch(f"/auth/users/{uid}", headers=admin, json={"active": False})
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {new_tok}"}).status_code == 401

    # Delete works.
    assert client.delete(f"/auth/users/{uid}", headers=admin).status_code == 200


def test_cannot_remove_last_admin():
    admin = {"Authorization": f"Bearer {_token()}"}
    users = client.get("/auth/users", headers=admin).json()
    admin_id = next(u["id"] for u in users if u["role"] == "admin")
    # Only one admin seeded → demotion blocked.
    assert client.patch(f"/auth/users/{admin_id}", headers=admin, json={"role": "viewer"}).status_code == 409
    assert client.delete(f"/auth/users/{admin_id}", headers=admin).status_code == 409
