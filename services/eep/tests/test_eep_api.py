"""Unit tests for the EEP public API (fixture mode — no real IEPs, fully self-contained).

Uses the auth-aware `client` fixture (services/eep/tests/conftest.py) so these pass both before and
after the JWT-auth merge.
"""

from __future__ import annotations

import io


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_readyz_shape(client):
    r = client.get("/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert "measurements_ready" in body and "reporting_ready" in body
    assert isinstance(body["cases"], int)


def test_metrics_exposes_prometheus(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "eep_requests_total" in r.text


def test_list_cases_returns_three_fixtures(client):
    r = client.get("/cases")
    assert r.status_code == 200
    cases = r.json()
    ids = {c["case_id"] for c in cases}
    assert {"demo-healthy-0001", "demo-stenosis-0003", "demo-fracture-0002"} <= ids
    assert len(cases) >= 3


def test_get_case_ok_and_404(client):
    assert client.get("/cases/demo-stenosis-0003").status_code == 200
    r = client.get("/cases/does-not-exist")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "not_found"


def test_upload_rejects_bad_type(client):
    r = client.post("/cases", files={"file": ("scan.txt", b"nope", "text/plain")})
    assert r.status_code == 415
    assert r.json()["detail"]["code"] == "unsupported_type"


def test_upload_accepts_nifti_and_returns_queued(client):
    r = client.post("/cases", files={"file": ("study.nii.gz", io.BytesIO(b"\x1f\x8bblob"), "application/gzip")})
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "queued"
    assert body["case_id"].startswith("upload-")


def test_signoff_marks_reviewed_and_signed(client):
    r = client.post("/cases/demo-healthy-0001/sign-off", json={"signed_by": "Dr. Test"})
    assert r.status_code == 200
    case = r.json()
    assert case["case"]["status"] == "reviewed"
    assert case["report"]["metadata"]["status"] == "signed"
    assert case["report"]["metadata"]["signed_by"] == "Dr. Test"


def test_signoff_404_for_unknown_case(client):
    assert client.post("/cases/nope/sign-off", json={"signed_by": "x"}).status_code == 404
