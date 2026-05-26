"""Phase 1 — accept NIfTI or DICOM, produce a sagittal NIfTI ready for TotalSpineSeg.

References: plans/phase-1-input-handling.md
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import nibabel as nib
import numpy as np
from nibabel.affines import obliquity
from nibabel.processing import resample_to_output


class InputError(ValueError):
    """Raised when the input cannot be processed (bad format, wrong orientation, QC fail)."""


@dataclass
class InputMetadata:
    nifti_path: Path
    voxel_spacing_mm: tuple[float, float, float]
    shape: tuple[int, int, int]
    canonical_axes: str
    geometry_standardization: dict | None = None


OBLIQUE_DEG_TOL = 5.0
GRID_ALIGN_TOL = 0.02


def prepare_nifti(input_path: Path | str, work_dir: Path | str) -> InputMetadata:
    """Take a NIfTI file or DICOM folder, return validated NIfTI + metadata for downstream phases."""
    input_path = Path(input_path).resolve()
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise InputError(f"Input not found: {input_path}")

    if input_path.is_file() and _is_nifti(input_path):
        nifti_path = input_path
    elif input_path.is_dir():
        nifti_path = _convert_dicom_with_dcm2niix(input_path, work_dir)
    else:
        raise InputError(
            f"Input must be a .nii/.nii.gz file or a DICOM folder; got: {input_path}"
        )

    img = nib.load(str(nifti_path))
    _validate_sagittal(img, nifti_path)
    img, nifti_path, standardization = _standardize_geometry(img, nifti_path, work_dir)
    return _qc_check(img, nifti_path, standardization)


def _is_nifti(p: Path) -> bool:
    name = p.name.lower()
    return name.endswith(".nii") or name.endswith(".nii.gz")


def _convert_dicom_with_dcm2niix(folder: Path, work_dir: Path) -> Path:
    if shutil.which("dcm2niix") is None:
        raise InputError(
            "dcm2niix binary not found on PATH. "
            "Install from https://github.com/rordenlab/dcm2niix (macOS: `brew install dcm2niix`)."
        )
    out_dir = work_dir / "dcm2niix_out"
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = ["dcm2niix", "-z", "y", "-f", "scan_%d_%s", "-o", str(out_dir), str(folder)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise InputError(
            f"dcm2niix conversion failed (exit {result.returncode}):\n{result.stderr}"
        )

    nifti_files = sorted(out_dir.glob("*.nii.gz"))
    if not nifti_files:
        raise InputError(f"dcm2niix produced no NIfTI output in {out_dir}")
    if len(nifti_files) == 1:
        return nifti_files[0]

    # Multiple series in the folder — pick by Phase 1.2 heuristic (sag + T2, exclude T1/STIR).
    candidates = [
        p for p in nifti_files
        if "sag" in p.stem.lower()
        and "t2" in p.stem.lower()
        and "t1" not in p.stem.lower()
        and "stir" not in p.stem.lower()
    ]
    if len(candidates) == 1:
        return candidates[0]
    raise InputError(
        "Multiple series in DICOM folder; cannot auto-pick sagittal T2. "
        f"Found: {[p.name for p in nifti_files]}. "
        "Pre-filter the DICOM folder or pass the NIfTI directly."
    )


def _validate_sagittal(img: nib.Nifti1Image, nifti_path: Path) -> None:
    """Sagittal scans stack along the L-R axis. Reject anything else."""
    axcodes = nib.aff2axcodes(img.affine)
    if axcodes[0] not in ("L", "R"):
        raise InputError(
            f"{nifti_path.name}: orientation {axcodes} is not sagittal-dominant. "
            "Pipeline expects sagittal T2."
        )


def _standardize_geometry(
    img: nib.Nifti1Image,
    nifti_path: Path,
    work_dir: Path,
) -> tuple[nib.Nifti1Image, Path, dict | None]:
    """Resample oblique/sheared sagittal scans onto an orthogonal voxel grid."""
    if img.ndim != 3:
        return img, nifti_path, None

    canonical = nib.as_closest_canonical(img)
    max_oblique_deg, max_alignment_error = _geometry_metrics(canonical.affine)
    if max_oblique_deg <= OBLIQUE_DEG_TOL and max_alignment_error <= GRID_ALIGN_TOL:
        return img, nifti_path, None

    spacing = tuple(float(x) for x in canonical.header.get_zooms()[:3])
    standardized = resample_to_output(canonical, voxel_sizes=spacing, order=1)
    standardized = nib.as_closest_canonical(standardized)

    standardized_path = work_dir / "input_standardized.nii.gz"
    nib.save(standardized, str(standardized_path))
    return standardized, standardized_path, {
        "original_axes": "".join(nib.aff2axcodes(img.affine)),
        "standardized_axes": "".join(nib.aff2axcodes(standardized.affine)),
        "from_spacing_mm": [round(float(s), 4) for s in img.header.get_zooms()[:3]],
        "to_spacing_mm": [round(float(s), 4) for s in standardized.header.get_zooms()[:3]],
        "max_oblique_deg": round(max_oblique_deg, 3),
        "max_alignment_error": round(max_alignment_error, 5),
    }


def _geometry_metrics(affine: np.ndarray) -> tuple[float, float]:
    """Return obliquity and axis-alignment error for a candidate voxel grid."""
    linear = np.asarray(affine[:3, :3], dtype=np.float64)
    norms = np.linalg.norm(linear, axis=0)
    if np.any(norms <= 0) or not np.all(np.isfinite(norms)):
        return float("inf"), float("inf")

    unit = linear / norms
    alignment_error = float(np.max(np.abs(unit - np.eye(3))))
    max_oblique_deg = float(np.degrees(np.max(obliquity(affine))))
    return max_oblique_deg, alignment_error


def _qc_check(
    img: nib.Nifti1Image,
    nifti_path: Path,
    standardization: dict | None,
) -> InputMetadata:
    """Phase 1.4 fail-fast: dimensions, spacing, intensity range, NaN fraction."""
    if img.ndim != 3:
        raise InputError(f"{nifti_path.name}: expected 3D volume, got {img.ndim}D")

    shape = tuple(int(x) for x in img.shape[:3])
    if shape[0] < 10 or min(shape[1], shape[2]) < 128:
        raise InputError(
            f"{nifti_path.name}: dimensions {shape} too small "
            "(need ≥10 sagittal slices, ≥128×128 in-plane)"
        )

    spacing = tuple(float(x) for x in img.header.get_zooms()[:3])
    if any(s <= 0 or not np.isfinite(s) for s in spacing):
        raise InputError(f"{nifti_path.name}: non-finite/non-positive spacing {spacing}")

    data = img.get_fdata(caching="unchanged")
    nan_frac = float(np.isnan(data).sum()) / data.size
    if nan_frac > 0.20:
        raise InputError(f"{nifti_path.name}: {nan_frac:.0%} NaN voxels (>20% threshold)")

    finite = data[np.isfinite(data)]
    if finite.size == 0 or finite.min() == finite.max():
        raise InputError(f"{nifti_path.name}: degenerate intensity range")

    return InputMetadata(
        nifti_path=nifti_path,
        voxel_spacing_mm=spacing,
        shape=shape,
        canonical_axes="".join(nib.aff2axcodes(img.affine)),
        geometry_standardization=standardization,
    )
