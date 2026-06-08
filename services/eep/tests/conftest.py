"""Shared test fixtures for the EEP.

The `client` fixture is **forward-compatible with the JWT auth** added on the full-stack branch:
- On this branch (no auth) there is no `/auth/login` route → the fixture returns a plain client.
- After the auth merge, `/cases*` requires a Bearer token → the fixture logs in with a seeded demo
  account and attaches the token, so these API tests keep passing without per-test changes.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from services.eep.app import app


def _auth_header_if_needed(client: TestClient) -> None:
    paths = {getattr(r, "path", None) for r in app.routes}
    if "/auth/login" not in paths:
        return  # auth not wired on this branch
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
