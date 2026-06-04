"""Thin wrapper around Spinal Cord Toolbox CLIs used by measurement components.

Keeps subprocess construction / CSV parsing out of the component logic so the
measurement modules can focus on anatomy-specific decision rules.
"""

from __future__ import annotations

import csv
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class SCTError(RuntimeError):
    """Raised when an SCT command is unavailable or exits unsuccessfully."""


@dataclass(frozen=True)
class ShapeMetricRow:
    slice_index: int | None
    vertebral_level: int | None
    metrics: dict[str, float]
    raw: dict[str, str]


def run_deepseg(
    task: str,
    input_path: Path | str,
    output_dir: Path | str,
    *,
    keep_largest: bool = True,
) -> Path:
    """Run `sct_deepseg` for one task and return the generated NIfTI path.

    `task` follows the current SCT CLI syntax, e.g. `sc_canal_t2`.
    """
    _ensure_cli("sct_deepseg")
    input_path = Path(input_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    out_base = output_dir / "prediction"
    cmd = [
        "sct_deepseg",
        task,
        "-i",
        str(input_path),
        "-o",
        str(out_base),
        "-r",
        "0",
    ]
    if keep_largest:
        cmd.extend(["-largest", "1"])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SCTError(
            f"sct_deepseg {task} failed (exit {result.returncode}):\n"
            f"stderr: {result.stderr[-2000:]}"
        )

    nifti_files = sorted(output_dir.glob("*.nii.gz"))
    if not nifti_files:
        raise SCTError(f"sct_deepseg {task} produced no NIfTI output in {output_dir}")
    if len(nifti_files) == 1:
        return nifti_files[0]

    prefixed = [p for p in nifti_files if p.name.startswith(out_base.name)]
    if len(prefixed) == 1:
        return prefixed[0]
    raise SCTError(
        f"sct_deepseg {task} produced multiple NIfTI outputs in {output_dir}: "
        f"{[p.name for p in nifti_files]}"
    )


def run_process_segmentation(
    seg_path: Path | str,
    *,
    discfile: Path | str,
    output_csv: Path | str,
    vert: str = "2:7",
    perslice: bool = False,
    perlevel: bool = False,
    angle_corr: bool = True,
) -> list[ShapeMetricRow]:
    """Run `sct_process_segmentation` and parse its CSV output."""
    _ensure_cli("sct_process_segmentation")
    if perslice and perlevel:
        raise ValueError("Choose either perslice or perlevel, not both")

    seg_path = Path(seg_path).resolve()
    discfile = Path(discfile).resolve()
    output_csv = Path(output_csv).resolve()
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "sct_process_segmentation",
        "-i",
        str(seg_path),
        "-o",
        str(output_csv),
        "-vert",
        vert,
        "-discfile",
        str(discfile),
    ]
    if angle_corr:
        cmd.extend(["-angle-corr", "1"])
    if perslice:
        cmd.extend(["-perslice", "1"])
    if perlevel:
        cmd.extend(["-perlevel", "1"])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SCTError(
            f"sct_process_segmentation failed (exit {result.returncode}):\n"
            f"stderr: {result.stderr[-2000:]}"
        )
    if not output_csv.exists():
        raise SCTError(f"sct_process_segmentation produced no CSV output at {output_csv}")

    with output_csv.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise SCTError(f"sct_process_segmentation produced an empty CSV at {output_csv}")
    return [_parse_shape_metric_row(row) for row in rows]


def _ensure_cli(binary: str) -> None:
    if shutil.which(binary) is None:
        raise SCTError(
            f"{binary} not found on PATH. Install Spinal Cord Toolbox and ensure its "
            "commands are available in the runtime environment."
        )


def _parse_shape_metric_row(row: dict[str, str]) -> ShapeMetricRow:
    metrics: dict[str, float] = {}
    for key, value in row.items():
        if not key.startswith("MEAN(") or value in ("", None):
            continue
        try:
            metrics[key[5:-1]] = float(value)
        except ValueError:
            continue

    slice_index = _parse_optional_int(
        row.get("Slice (I->S)") or row.get("Slice") or row.get("SliceI->S")
    )
    vertebral_level = _parse_optional_int(
        row.get("VertLevel") or row.get("Vert Level") or row.get("Vertlevel")
    )
    return ShapeMetricRow(
        slice_index=slice_index,
        vertebral_level=vertebral_level,
        metrics=metrics,
        raw=row,
    )


def _parse_optional_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except ValueError:
        return None
