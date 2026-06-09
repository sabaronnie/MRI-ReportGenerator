"""SPINEPS CLI wrapper — per-vertebra instance + endplate-voxel masks for the Group 4 C1 Cobb.

SPINEPS predicts each vertebra's inferior-endplate sheet directly into the instance mask
(label = 100 + instance; C2=102 .. C7=107). The Group 4 C3--C7 Cobb fits its line to those
endplate voxels (services/measurements/geometric/_endplate_cobb.spineps_endplate_cobb_angle),
which beat TSS-corner and corpus methods on cervical necks (project J11--J12).

DEPLOYMENT NOTE: SPINEPS pins ``numpy==2.0.2``, incompatible with the TotalSpineSeg/nnU-Net stack,
so this MUST run as its own image/process. Invocation mirrors colab/group5/colab_spineps_spinegeneric
.ipynb and research/group5/run_spineps_alignment.py.
"""

from __future__ import annotations

import glob
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import nibabel as nib
import numpy as np


# Endplate-voxel labels SPINEPS writes into the (non-raw) instance mask: C2=102 .. C7=107.
ENDPLATE_LABELS = set(range(102, 108))


class SpinepsSegmentationError(RuntimeError):
    """Raised when SPINEPS fails or its instance mask lacks the endplate-voxel labels (102-107)."""


@dataclass
class SpinepsSegmentationResult:
    seg_vert: Path          # *_seg-vert_msk.nii.gz (instances + endplate sheets) -> the G4 Cobb input
    seg_spine: Path | None  # *_seg-spine_msk.nii.gz (semantic mask), if emitted
    endplate_labels_present: list[int]


def run_spineps(nifti_path: Path | str, work_dir: Path | str) -> SpinepsSegmentationResult:
    """Run SPINEPS on a sagittal T2 NIfTI; return the instance mask carrying endplate voxels."""
    if shutil.which("spineps") is None:
        raise SpinepsSegmentationError(
            "spineps CLI not found on PATH. Install in a numpy==2.0.2 environment: "
            "pip install spineps && pip install 'numpy==2.0.2'"
        )

    nifti_path = Path(nifti_path).resolve()
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    # SPINEPS writes its derivatives next to the input file -> run it in an isolated input dir.
    in_dir = work_dir / "spineps_in"
    in_dir.mkdir(parents=True, exist_ok=True)
    local = in_dir / nifti_path.name
    if local.resolve() != nifti_path:
        shutil.copy(nifti_path, local)

    cmd = [
        "spineps", "sample",
        "-ignore_bids_filter", "-ignore_inference_compatibility",
        "-i", str(local),
        "-model_semantic", "t2w",
        "-model_instance", "instance",
    ]
    # Device-agnostic: SPINEPS defaults to CUDA and hard-fails (.cuda()) on a CPU-only node, so pass
    # -cpu when no GPU is present. On a GPU node it runs on the GPU (far faster).
    try:
        import torch  # noqa: PLC0415 — optional; absence => assume CPU
        if not torch.cuda.is_available():
            cmd.append("-cpu")
    except Exception:  # noqa: BLE001
        cmd.append("-cpu")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SpinepsSegmentationError(
            f"SPINEPS failed (exit {result.returncode}):\nstderr: {result.stderr[-2000:]}"
        )

    # The NON-raw seg-vert mask carries the endplate sheets (the *-raw file only has labels 1-10).
    verts = [
        p for p in glob.glob(f"{in_dir}/**/*seg-vert_msk.nii.gz", recursive=True)
        if "-raw" not in Path(p).name
    ]
    if not verts:
        raise SpinepsSegmentationError(
            f"SPINEPS produced no seg-vert_msk.nii.gz under {in_dir}. "
            f"log tail: {(result.stderr or result.stdout)[-1000:]}"
        )
    seg_vert = Path(sorted(verts)[0])

    spines = glob.glob(f"{in_dir}/**/*seg-spine_msk.nii.gz", recursive=True)
    seg_spine = Path(sorted(spines)[0]) if spines else None

    present = set(int(x) for x in np.unique(nib.load(str(seg_vert)).get_fdata().astype(np.int32)) if x)
    endplate = sorted(present & ENDPLATE_LABELS)
    if not endplate:
        raise SpinepsSegmentationError(
            f"{seg_vert.name}: endplate labels 102-107 absent (got {sorted(present)}) "
            "-> mask is not usable for the Group 4 Cobb"
        )

    return SpinepsSegmentationResult(seg_vert=seg_vert, seg_spine=seg_spine, endplate_labels_present=endplate)
