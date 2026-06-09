"""Tests for the asynchronous real-segmentation upload path.

When all 3 segmentation engines are configured, an upload must return 202 'queued' immediately and
run segmentation -> measurements in a BACKGROUND task — never `asyncio.run()` inside the request's
already-running event loop, and never block the request for the minutes a CPU run takes. Real
failures must surface as a case-level error (not be silently masked by the stand-in fallback). The
stand-in fast path stays synchronous (covered in test_eep_api).
"""

from __future__ import annotations

import io
import zipfile

import pytest

from services.eep import config, store
from services.eep.clients import segmentation as seg
from services.eep.clients.measurements import MeasurementsClient

_ENGINE_OUTPUT = {
    "totalspineseg": "step2_output.nii.gz",
    "sct": "sct_canal_seg.nii.gz",
    "spineps": "spineps_instances.nii.gz",
}


def _zip(name: str, data: bytes = b"x") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, data)
    return buf.getvalue()


@pytest.fixture
def real_seg(monkeypatch):
    """All 3 engines wired + their network calls stubbed + a recognizable measurements core."""
    monkeypatch.setattr(config, "SEG_TSS_URL", "http://tss")
    monkeypatch.setattr(config, "SEG_SCT_URL", "http://sct")
    monkeypatch.setattr(config, "SEG_SPINEPS_URL", "http://spineps")
    monkeypatch.setattr(config, "MEASUREMENTS_URL", "http://measurements")

    async def fake_post(client, base_url, path, data, send_name):
        # Real DAG: TSS + SPINEPS on /segment; SCT on /segment-sct re-including the TSS artifact.
        if base_url == "http://tss":
            return _zip(_ENGINE_OUTPUT["totalspineseg"])
        if base_url == "http://spineps":
            return _zip(_ENGINE_OUTPUT["spineps"])
        if base_url == "http://sct":
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                z.writestr(_ENGINE_OUTPUT["totalspineseg"], b"x")
                z.writestr(_ENGINE_OUTPUT["sct"], b"x")
            return buf.getvalue()
        raise AssertionError(base_url)

    monkeypatch.setattr(seg, "_post", fake_post)

    def fake_measure(self, seg_zip, *, case_id, filename):
        # The worker must hand the merged zip to the measurements IEP (proves seg ran first).
        assert seg_zip.exists()
        with zipfile.ZipFile(seg_zip) as z:
            assert set(z.namelist()) == set(_ENGINE_OUTPUT.values())
        return {"measurements": {"sentinel": 42}, "flags": {"f": True}, "components": {}, "assessements": {}}

    monkeypatch.setattr(MeasurementsClient, "measure", fake_measure)


def test_real_seg_upload_queues_then_completes(client, real_seg):
    r = client.post("/cases", files={"file": ("study.nii.gz", b"rawscan", "application/gzip")})
    assert r.status_code == 202
    assert r.json()["status"] == "queued"
    cid = r.json()["case_id"]

    # The TestClient runs the background task to completion before returning the response.
    case = client.get(f"/cases/{cid}").json()
    assert case["case"]["status"] == "ready"
    assert case["measurements"] == {"sentinel": 42}
    assert case["job"]["stage"] == "ready"
    assert case["job"]["error"] is None


def test_real_seg_failure_marks_case_error(client, monkeypatch, real_seg):
    async def boom(client, base_url, path, data, send_name):
        raise RuntimeError("engine down")  # TSS fails -> the DAG raises -> case marked error

    monkeypatch.setattr(seg, "_post", boom)

    r = client.post("/cases", files={"file": ("study.nii.gz", b"rawscan", "application/gzip")})
    assert r.status_code == 202  # still accepted immediately — the failure is async
    cid = r.json()["case_id"]

    case = client.get(f"/cases/{cid}").json()
    assert case["case"]["status"] == "error"
    assert case["job"]["error"]


def test_non_simulated_case_stays_queued_without_worker():
    # Real-seg cases must NOT be driven by the simulated UX clock; status is worker-driven.
    res = store.create_case("scan.nii.gz", "tester", simulated=False)
    cid = res["case_id"]
    case = store.get_case(cid)
    assert case["case"]["status"] == "queued"
    assert case["job"]["stage"] == "queued"


def test_set_stage_and_update_core():
    res = store.create_case("scan.nii.gz", "tester", simulated=False)
    cid = res["case_id"]

    store.set_stage(cid, "segmenting", progress=0.2)
    assert store.get_job(cid)["stage"] == "segmenting"
    assert store.get_case(cid)["case"]["status"] == "processing"

    store.update_case_core(cid, {"measurements": {"m": 1}})
    store.set_stage(cid, "ready", progress=1.0)
    case = store.get_case(cid)
    assert case["case"]["status"] == "ready"
    assert case["measurements"] == {"m": 1}
    assert case["job"]["progress"] == 1.0


def test_set_stage_error_records_message():
    res = store.create_case("scan.nii.gz", "tester", simulated=False)
    cid = res["case_id"]
    store.set_stage(cid, "error", error="seg failed: totalspineseg")
    case = store.get_case(cid)
    assert case["case"]["status"] == "error"
    assert case["job"]["error"] == "seg failed: totalspineseg"
