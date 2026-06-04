"""Unit tests for the isolated SCT wrapper layer."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from services.measurements import sct


def test_run_deepseg_discovers_single_output(monkeypatch, tmp_path):
    monkeypatch.setattr(sct.shutil, "which", lambda _: "/usr/local/bin/fake")

    def fake_run(cmd, capture_output, text):
        out_dir = Path(cmd[cmd.index("-o") + 1]).parent
        (out_dir / "prediction_canal_seg.nii.gz").write_bytes(b"fake")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(sct.subprocess, "run", fake_run)

    out = sct.run_deepseg("sc_canal_t2", tmp_path / "input.nii.gz", tmp_path / "work")
    assert out.name == "prediction_canal_seg.nii.gz"


def test_run_process_segmentation_parses_csv(monkeypatch, tmp_path):
    monkeypatch.setattr(sct.shutil, "which", lambda _: "/usr/local/bin/fake")

    def fake_run(cmd, capture_output, text):
        csv_path = Path(cmd[cmd.index("-o") + 1])
        csv_path.write_text(
            "Slice (I->S),VertLevel,MEAN(diameter_AP),MEAN(area)\n"
            "12,5,8.25,71.0\n"
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(sct.subprocess, "run", fake_run)

    rows = sct.run_process_segmentation(
        tmp_path / "canal_seg.nii.gz",
        discfile=tmp_path / "levels.nii.gz",
        output_csv=tmp_path / "metrics.csv",
        perslice=True,
    )

    assert len(rows) == 1
    assert rows[0].slice_index == 12
    assert rows[0].vertebral_level == 5
    assert rows[0].metrics["diameter_AP"] == pytest.approx(8.25)
    assert rows[0].metrics["area"] == pytest.approx(71.0)
