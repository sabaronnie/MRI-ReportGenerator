"""End-to-end test that calls the DEPLOYED system (rubric Q1).

Set EEP_BASE_URL to the deployed EEP load balancer, e.g.:
    EEP_BASE_URL=http://<eep-elb>.elb.amazonaws.com pytest tests/e2e -m e2e
Skipped when EEP_BASE_URL is unset so unit/CI runs stay hermetic.
"""

from __future__ import annotations

import io
import os

import httpx
import pytest

BASE = os.environ.get("EEP_BASE_URL", "").rstrip("/")

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not BASE, reason="set EEP_BASE_URL to run against the deployed system"),
]

TIMEOUT = 30.0


def test_deployed_health_and_readiness():
    assert httpx.get(f"{BASE}/healthz", timeout=TIMEOUT).status_code == 200
    ready = httpx.get(f"{BASE}/readyz", timeout=TIMEOUT).json()
    assert ready["status"] == "ready"
    # On the deployed stack both IEPs must be reachable (this is the GT3 orchestration check).
    assert ready["measurements_ready"] is True
    assert ready["reporting_ready"] is True


def test_deployed_lists_cases():
    cases = httpx.get(f"{BASE}/cases", timeout=TIMEOUT).json()
    ids = {c["case_id"] for c in cases}
    assert {"demo-healthy-0001", "demo-stenosis-0003", "demo-fracture-0002"} <= ids


def test_deployed_upload_then_report_roundtrip():
    # Upload (the EEP orchestrates the measurements IEP) ...
    up = httpx.post(
        f"{BASE}/cases",
        files={"file": ("e2e.nii.gz", io.BytesIO(b"\x1f\x8be2e"), "application/gzip")},
        timeout=60.0,
    )
    assert up.status_code in (200, 202)
    cid = up.json()["case_id"]
    # ... then render its report (the EEP orchestrates the reporting IEP).
    rep = httpx.get(f"{BASE}/cases/{cid}/report.html", timeout=TIMEOUT)
    assert rep.status_code == 200
    assert "Cervical Spine MRI Analysis Report" in rep.text


def test_deployed_metrics_exposed():
    body = httpx.get(f"{BASE}/metrics", timeout=TIMEOUT).text
    assert "eep_requests_total" in body
