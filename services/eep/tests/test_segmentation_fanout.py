"""Unit tests for the segmentation parallel fan-out (config gating + mask merge)."""

from __future__ import annotations

import asyncio
import io
import zipfile

import httpx

from services.eep.clients import segmentation as seg


def _zip(name: str, data: bytes = b"x") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, data)
    return buf.getvalue()


def test_not_configured_by_default(monkeypatch):
    monkeypatch.setattr(seg.config, "SEG_TSS_URL", "")
    monkeypatch.setattr(seg.config, "SEG_SCT_URL", "")
    monkeypatch.setattr(seg.config, "SEG_SPINEPS_URL", "")
    assert seg.all_engines_configured() is False


def test_all_configured_true_when_all_set(monkeypatch):
    monkeypatch.setattr(seg.config, "SEG_TSS_URL", "http://tss:8083")
    monkeypatch.setattr(seg.config, "SEG_SCT_URL", "http://sct:8084")
    monkeypatch.setattr(seg.config, "SEG_SPINEPS_URL", "http://spineps:8085")
    assert seg.all_engines_configured() is True


def _multi_zip(*names: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in names:
            z.writestr(n, b"x")
    return buf.getvalue()


def _wire(monkeypatch):
    monkeypatch.setattr(seg.config, "SEG_TSS_URL", "http://tss")
    monkeypatch.setattr(seg.config, "SEG_SCT_URL", "http://sct")
    monkeypatch.setattr(seg.config, "SEG_SPINEPS_URL", "http://spineps")


def test_dag_merge_combines_engine_outputs(monkeypatch):
    """TSS ∥ SPINEPS on /segment, then SCT on /segment-sct (consuming the TSS zip); merge all masks."""
    _wire(monkeypatch)
    calls = []

    async def fake_post(client, base_url, path, data, send_name):
        calls.append((base_url, path))
        if base_url == "http://tss":
            return _multi_zip("step2_output.nii.gz", "input_iso.nii.gz")
        if base_url == "http://spineps":
            return _multi_zip("spineps_seg-vert_msk.nii.gz")
        if base_url == "http://sct":  # SCT re-includes the TSS artifacts + adds its masks
            return _multi_zip("step2_output.nii.gz", "input_iso.nii.gz", "sct_canal_seg.nii.gz")
        raise AssertionError(base_url)

    monkeypatch.setattr(seg, "_post", fake_post)
    merged = asyncio.run(seg.run_segmentation_async(b"scan", "study.nii.gz"))
    with zipfile.ZipFile(io.BytesIO(merged)) as z:
        names = set(z.namelist())
    assert {"step2_output.nii.gz", "input_iso.nii.gz", "sct_canal_seg.nii.gz", "spineps_seg-vert_msk.nii.gz"} == names
    # DAG: TSS + SPINEPS hit /segment; SCT hits /segment-sct (the staged dependency).
    paths = set(calls)
    assert ("http://tss", "/segment") in paths
    assert ("http://spineps", "/segment") in paths
    assert ("http://sct", "/segment-sct") in paths


def test_sct_failure_is_non_fatal(monkeypatch):
    """If SCT errors, the merge still carries the TSS (+ SPINEPS) masks."""
    _wire(monkeypatch)

    async def fake_post(client, base_url, path, data, send_name):
        if base_url == "http://sct":
            raise httpx.HTTPError("sct down")
        if base_url == "http://tss":
            return _multi_zip("step2_output.nii.gz")
        return _multi_zip("spineps_seg-vert_msk.nii.gz")

    monkeypatch.setattr(seg, "_post", fake_post)
    merged = asyncio.run(seg.run_segmentation_async(b"scan", "study.nii.gz"))
    with zipfile.ZipFile(io.BytesIO(merged)) as z:
        names = set(z.namelist())
    assert {"step2_output.nii.gz", "spineps_seg-vert_msk.nii.gz"} == names
