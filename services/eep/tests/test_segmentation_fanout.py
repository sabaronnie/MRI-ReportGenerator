"""Unit tests for the segmentation parallel fan-out (config gating + mask merge)."""

from __future__ import annotations

import asyncio
import io
import zipfile

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


def test_parallel_merge_combines_all_engine_outputs(monkeypatch):
    monkeypatch.setattr(seg.config, "SEG_TSS_URL", "http://tss")
    monkeypatch.setattr(seg.config, "SEG_SCT_URL", "http://sct")
    monkeypatch.setattr(seg.config, "SEG_SPINEPS_URL", "http://spineps")

    async def fake_segment_one(name, url, data, filename):
        outputs = {
            "totalspineseg": "step2_output.nii.gz",
            "sct": "sct_canal_seg.nii.gz",
            "spineps": "spineps_instances.nii.gz",
        }
        return name, _zip(outputs[name])

    monkeypatch.setattr(seg, "_segment_one", fake_segment_one)

    merged = asyncio.run(seg.run_segmentation_async(b"scan", "study.nii.gz"))
    with zipfile.ZipFile(io.BytesIO(merged)) as z:
        names = set(z.namelist())
    assert {"step2_output.nii.gz", "sct_canal_seg.nii.gz", "spineps_instances.nii.gz"} == names
