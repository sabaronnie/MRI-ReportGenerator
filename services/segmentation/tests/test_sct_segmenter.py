from __future__ import annotations

import subprocess
from pathlib import Path

from services.segmentation import sct_segmenter


def test_run_sct_deepseg_discovers_explicit_output(monkeypatch, tmp_path):
    monkeypatch.setattr(sct_segmenter.shutil, "which", lambda _: "/usr/local/bin/fake")

    def fake_run(cmd, capture_output, text):
        out_path = Path(cmd[cmd.index("-o") + 1])
        out_path.write_bytes(b"fake")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(sct_segmenter.subprocess, "run", fake_run)

    out = sct_segmenter.run_sct_deepseg("canal", tmp_path / "input.nii.gz", tmp_path / "work")
    assert out.name == "prediction.nii.gz"


def test_run_sct_segmentations_runs_both_tasks(monkeypatch, tmp_path):
    calls = []

    def fake_run(task, input_path, output_dir, keep_largest=True):
        calls.append(task)
        path = Path(output_dir) / "prediction.nii.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake")
        return path

    monkeypatch.setattr(sct_segmenter, "run_sct_deepseg", fake_run)

    result = sct_segmenter.run_sct_segmentations(tmp_path / "input_iso.nii.gz", tmp_path / "out")

    assert calls == ["canal", "spinalcord"]
    assert result.canal_seg.name == "prediction.nii.gz"
    assert result.cord_seg.name == "prediction.nii.gz"
