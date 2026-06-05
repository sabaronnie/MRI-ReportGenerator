"""SCT segmentation wrapper for canal + spinal cord masks.

This module owns SCT *segmentation* only. Downstream morphometry remains in the
measurement service via `sct_process_segmentation`.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class SCTSegmentationError(RuntimeError):
    """Raised when SCT deepseg is unavailable or exits unsuccessfully."""


@dataclass
class SCTSegmentationResult:
    output_dir: Path
    canal_seg: Path
    cord_seg: Path


def run_sct_deepseg(
    task: str,
    input_path: Path | str,
    output_dir: Path | str,
    *,
    keep_largest: bool = True,
) -> Path:
    """Run SCT deepseg for one task and return the generated NIfTI path.

    Uses the SCT v7 CLI form: `sct_deepseg <task> -i ... -o ...`.
    """
    _ensure_cli("sct_deepseg")
    input_path = Path(input_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    out_path = output_dir / "prediction.nii.gz"
    cmd = [
        "sct_deepseg",
        task,
        "-i",
        str(input_path),
        "-o",
        str(out_path),
        "-r",
        "0",
    ]
    if keep_largest:
        cmd.extend(["-largest", "1"])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SCTSegmentationError(
            f"sct_deepseg {task} failed (exit {result.returncode}):\n"
            f"stderr: {result.stderr[-2000:]}"
        )

    if out_path.exists():
        return out_path

    nifti_files = sorted(output_dir.glob("*.nii.gz"))
    if len(nifti_files) == 1:
        return nifti_files[0]
    if not nifti_files:
        raise SCTSegmentationError(f"sct_deepseg {task} produced no NIfTI output in {output_dir}")
    raise SCTSegmentationError(
        f"sct_deepseg {task} produced multiple NIfTI outputs in {output_dir}: "
        f"{[p.name for p in nifti_files]}"
    )


def run_sct_segmentations(
    input_path: Path | str,
    work_dir: Path | str,
) -> SCTSegmentationResult:
    """Run the two SCT deepseg tasks needed by Group 3."""
    input_path = Path(input_path).resolve()
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    canal_seg = run_sct_deepseg("canal", input_path, work_dir / "canal")
    cord_seg = run_sct_deepseg("spinalcord", input_path, work_dir / "spinalcord")
    return SCTSegmentationResult(output_dir=work_dir, canal_seg=canal_seg, cord_seg=cord_seg)


def _ensure_cli(binary: str) -> None:
    if shutil.which(binary) is None:
        raise SCTSegmentationError(
            f"{binary} not found on PATH. Install Spinal Cord Toolbox and ensure its "
            "commands are available in the runtime environment."
        )
