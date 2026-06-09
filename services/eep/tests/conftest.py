"""Shared test fixtures for the EEP.

Hermetic test env — temp DBs + a test JWT secret, set BEFORE the app imports (so neither the real
users.db nor workflow.db is touched by the suite, and auth has a valid secret at import time).

The `client` fixture logs in with the seeded demo account and attaches the Bearer token. It is a
no-op if `/auth/login` isn't wired, so the API tests pass with or without the auth layer.
"""

import os
import tempfile

_TMP = tempfile.mkdtemp()
os.environ.setdefault("USERS_DB_PATH", os.path.join(_TMP, "users.db"))
os.environ.setdefault("WORKFLOW_DB_PATH", os.path.join(_TMP, "workflow.db"))
os.environ.setdefault("JWT_SECRET", "test-secret-min-32-bytes-long-aaaaaaaa")
os.environ.setdefault("DEMO_PASSWORD", "demo12345")

import pytest  # noqa: E402  (env above must be set before the app imports)
from fastapi.testclient import TestClient  # noqa: E402

from services.eep.app import app  # noqa: E402


def _auth_header_if_needed(client: TestClient) -> None:
    paths = {getattr(r, "path", None) for r in app.routes}
    if "/auth/login" not in paths:
        return  # auth not wired
    email = os.environ.get("DEMO_EMAIL", "radiologist@demo")
    password = os.environ.get("DEMO_PASSWORD", "demo12345")
    resp = client.post("/auth/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        client.headers["Authorization"] = f"Bearer {resp.json()['token']}"


@pytest.fixture
def client() -> TestClient:
    c = TestClient(app)
    _auth_header_if_needed(c)
    return c
