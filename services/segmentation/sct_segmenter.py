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
    lesion_seg: Path | None = None   # SCIseg cord-lesion mask (Group 5.1); None if SCIseg unavailable/failed


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


def run_sct_sciseg(input_path: Path | str, output_dir: Path | str) -> Path | None:
    """Run SCIseg (intramedullary T2 cord-lesion / myelomalacia) for Group 5.1; return the lesion
    mask, or None if SCIseg is unavailable/fails (NON-FATAL -- 5.1 is a screen, must not block G3).

    SCT v7 form: `sct_deepseg lesion_sci_t2 -i <file>`; older v6.2-6.5 fallback:
    `sct_deepseg -task seg_sc_lesion_t2w_sci -i <file>`. SCIseg writes `<base>_sc_seg.nii.gz` +
    `<base>_lesion_seg.nii.gz` next to the input; we copy the input into an isolated dir and return
    the lesion mask from there. Lesions can be multiple, so `-largest` is NOT applied.
    """
    if shutil.which("sct_deepseg") is None:
        return None
    input_path = Path(input_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    local = output_dir / input_path.name
    if local.resolve() != input_path:
        shutil.copy(input_path, local)

    for cmd in (
        ["sct_deepseg", "lesion_sci_t2", "-i", str(local), "-r", "0"],                  # v7
        ["sct_deepseg", "-task", "seg_sc_lesion_t2w_sci", "-i", str(local), "-r", "0"],  # v6 fallback
    ):
        if subprocess.run(cmd, capture_output=True, text=True).returncode == 0:
            break
    else:
        return None  # both forms failed -> non-fatal

    lesions = sorted(p for p in output_dir.rglob("*.nii.gz") if "lesion" in p.name.lower())
    return lesions[0] if lesions else None


def run_sct_segmentations(
    input_path: Path | str,
    work_dir: Path | str,
) -> SCTSegmentationResult:
    """Run the SCT deepseg tasks: canal + cord (Group 3) and SCIseg cord-lesion (Group 5.1, non-fatal)."""
    input_path = Path(input_path).resolve()
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    canal_seg = run_sct_deepseg("canal", input_path, work_dir / "canal")
    cord_seg = run_sct_deepseg("spinalcord", input_path, work_dir / "spinalcord")
    lesion_seg = run_sct_sciseg(input_path, work_dir / "lesion")  # G5.1; None if unavailable
    return SCTSegmentationResult(
        output_dir=work_dir, canal_seg=canal_seg, cord_seg=cord_seg, lesion_seg=lesion_seg
    )


def _ensure_cli(binary: str) -> None:
    if shutil.which(binary) is None:
        raise SCTSegmentationError(
            f"{binary} not found on PATH. Install Spinal Cord Toolbox and ensure its "
            "commands are available in the runtime environment."
        )
