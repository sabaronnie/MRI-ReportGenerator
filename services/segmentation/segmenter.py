"""Phase 2.1 — TotalSpineSeg CLI wrapper.

References: plans/phase-2-segmentation.md §2.1
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import nibabel as nib
import numpy as np


CERVICAL_VERTEBRA_LABELS = {11, 12, 13, 14, 15, 16, 17, 21}  # C1..C7, T1
CERVICAL_DISC_LABELS = {63, 64, 65, 66, 67, 71}              # C2/3..C7/T1
REQUIRED_VERTEBRAE = {12, 13, 14, 15, 16, 17}                # C2..C7


class SegmentationError(RuntimeError):
    """Raised when TotalSpineSeg fails or its output is missing required cervical labels."""


@dataclass
class SegmentationResult:
    output_dir: Path
    step2_output: Path
    step1_levels: Path
    iso_input: Path | None
    cervical_labels_present: list[int]


def run_totalspineseg(
    nifti_path: Path | str,
    work_dir: Path | str,
    *,
    iso: bool = True,
) -> SegmentationResult:
    """Run TotalSpineSeg on a sagittal T2 NIfTI; return paths to step2_output and step1_levels."""
    if shutil.which("totalspineseg") is None:
        raise SegmentationError(
            "totalspineseg CLI not found on PATH. "
            "Install with: pip install totalspineseg[nnunetv2]"
        )

    nifti_path = Path(nifti_path).resolve()
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    out_dir = work_dir / "tss_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    # input/output are positional in the upstream CLI; --iso enables 1mm-isotropic resampling.
    # --no-stalling uses the 'forkserver' multiprocessing start method to avoid the deadlock that
    # otherwise hangs export/preview in a container with a small /dev/shm (the pod also mounts a
    # larger /dev/shm). Without it, CPU runs stall indefinitely at "Generating preview images".
    cmd = ["totalspineseg", str(nifti_path), str(out_dir), "--no-stalling"]
    if iso:
        cmd.append("--iso")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SegmentationError(
            f"TotalSpineSeg failed (exit {result.returncode}):\n"
            f"stderr: {result.stderr[-2000:]}"
        )

    step2 = _expect_one_nifti(out_dir / "step2_output", "step2_output")
    levels = _expect_one_nifti(out_dir / "step1_levels", "step1_levels")
    iso_input = None
    if iso:
        iso_dir = out_dir / "input_iso"
        if iso_dir.is_dir():
            iso_files = sorted(iso_dir.glob("*.nii.gz"))
            iso_input = iso_files[0] if iso_files else None

    labels_present = _check_cervical_labels(step2)

    return SegmentationResult(
        output_dir=out_dir,
        step2_output=step2,
        step1_levels=levels,
        iso_input=iso_input,
        cervical_labels_present=sorted(labels_present),
    )


def _expect_one_nifti(folder: Path, label: str) -> Path:
    if not folder.is_dir():
        raise SegmentationError(f"TSS produced no {label} folder at {folder}")
    files = sorted(folder.glob("*.nii.gz"))
    if not files:
        raise SegmentationError(f"TSS produced no {label} NIfTI in {folder}")
    return files[0]


def _check_cervical_labels(seg_path: Path) -> set[int]:
    seg = nib.load(str(seg_path)).get_fdata().astype(np.int32)
    present = set(np.unique(seg).tolist()) - {0}
    missing = REQUIRED_VERTEBRAE - present
    if missing:
        raise SegmentationError(
            f"{seg_path.name}: required cervical vertebrae missing: "
            f"{sorted(missing)} (got labels {sorted(present)})"
        )
    return present & (CERVICAL_VERTEBRA_LABELS | CERVICAL_DISC_LABELS)
