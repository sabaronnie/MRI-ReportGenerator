"""Colab cell 2/3 — run TotalSpineSeg segmentation on one MRI scan.

Prereq: run cell 1 first (installs deps + caches weights on Drive), then
Runtime > Restart session.

This cell:
  1. Points TOTALSPINESEG_DATA at the same Drive cache cell 1 populated, so the
     weights are reused — no re-download.
  2. Prepares the input (NIfTI as-is, or converts a DICOM folder), standardises
     geometry to canonical RAS, and runs fail-fast QC.
  3. Runs `totalspineseg <input> <output> --iso`.
  4. Verifies the required cervical labels are present and writes a manifest that
     cell 3 reads.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import nibabel as nib
import numpy as np
from nibabel.affines import obliquity
from nibabel.processing import resample_from_to, resample_to_output
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap


# -------- Edit these before running --------
INPUT_SCAN_PATH = Path("/content/drive/MyDrive/503N_Proj/593973-000965_Study-MR-983_Series-3.nii.gz")  # .nii/.nii.gz OR a DICOM folder
CASE_ID = "case_001"
CASE_OUTPUT_DIR = Path(f"/content/drive/MyDrive/mri_report_generator_runs/{CASE_ID}")
USE_ISO_OUTPUT = True
# Must match cell 1's TOTALSPINESEG_DATA so the cached weights are reused.
TOTALSPINESEG_DATA = Path("/content/drive/MyDrive/mri_report_generator_cache/totalspineseg")
# ------------------------------------------


OBLIQUE_DEG_TOL = 5.0
GRID_ALIGN_TOL = 0.02
CERVICAL_VERTEBRA_LABELS = {11, 12, 13, 14, 15, 16, 17, 21}
CERVICAL_DISC_LABELS = {63, 64, 65, 66, 67, 71}
REQUIRED_VERTEBRAE = {12, 13, 14, 15, 16, 17}
LABEL_NAMES = {
    1: "Canal",
    2: "Cord",
    11: "C1",
    12: "C2",
    13: "C3",
    14: "C4",
    15: "C5",
    16: "C6",
    17: "C7",
    21: "T1",
    63: "C2-C3",
    64: "C3-C4",
    65: "C4-C5",
    66: "C5-C6",
    67: "C6-C7",
    71: "C7-T1",
}
PINNED_NNUNETV2 = "2.6.2"
PINNED_KORNIA = "0.7.2"
WEIGHT_DATASET_DIRS = (
    "Dataset101_TotalSpineSeg_step1",
    "Dataset102_TotalSpineSeg_step2",
)


class InputError(ValueError):
    """Raised when the input cannot be processed."""


class SegmentationError(RuntimeError):
    """Raised when TotalSpineSeg fails or required labels are missing."""


@dataclass
class InputMetadata:
    nifti_path: Path
    voxel_spacing_mm: tuple[float, float, float]
    shape: tuple[int, int, int]
    canonical_axes: str
    geometry_standardization: dict | None = None


@dataclass
class SegmentationResult:
    output_dir: Path
    step2_output: Path
    step1_levels: Path
    iso_input: Path | None
    cervical_labels_present: list[int]
    missing_required_vertebrae: list[int]


def _mount_drive_if_needed() -> None:
    if "google.colab" not in sys.modules:
        return
    from google.colab import drive  # type: ignore

    drive.mount("/content/drive", force_remount=False)


def _configure_env() -> None:
    # The ONLY env var TotalSpineSeg uses to locate weights. It derives the
    # nnUNet/results layout from this internally — do not set nnUNet_* by hand.
    TOTALSPINESEG_DATA.mkdir(parents=True, exist_ok=True)
    os.environ["TOTALSPINESEG_DATA"] = str(TOTALSPINESEG_DATA)
    print(f"TOTALSPINESEG_DATA={TOTALSPINESEG_DATA}")


def _check_weights_cached() -> None:
    present = TOTALSPINESEG_DATA.exists() and all(
        any(TOTALSPINESEG_DATA.rglob(name)) for name in WEIGHT_DATASET_DIRS
    )
    if present:
        print("Using cached TotalSpineSeg weights from Drive (no download needed).")
    else:
        print(
            "No cached weights found on Drive — TotalSpineSeg will download them "
            "on this run. Run cell 1 first to avoid this."
        )


def _preflight_totalspineseg_runtime() -> None:
    try:
        import importlib.metadata as md

        import kornia
        import torch
        from kornia.core import Tensor
    except Exception as e:
        raise SegmentationError(
            "Runtime is missing a compatible TotalSpineSeg dependency stack. "
            "Run cell 1 again, restart the runtime, then rerun this cell.\n"
            f"Preflight import error: {e}"
        ) from e

    torch_version = torch.__version__.split("+")[0]
    nnunetv2_version = md.version("nnunetv2")
    if kornia.__version__ != PINNED_KORNIA or nnunetv2_version != PINNED_NNUNETV2:
        raise SegmentationError(
            "Incompatible TotalSpineSeg dependency versions detected. "
            f"Expected kornia={PINNED_KORNIA}, nnunetv2={PINNED_NNUNETV2}; "
            f"got torch={torch_version}, kornia={kornia.__version__}, "
            f"nnunetv2={nnunetv2_version}. Rerun cell 1 and restart the runtime."
        )

    print(
        "Runtime preflight OK: "
        f"torch={torch_version}, kornia={kornia.__version__}, "
        f"nnunetv2={nnunetv2_version}, kornia.core.Tensor={Tensor}"
    )


def prepare_nifti(input_path: Path | str, work_dir: Path | str) -> InputMetadata:
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
    img, nifti_path, standardization = _standardize_geometry(img, nifti_path, work_dir)
    _validate_sagittal(img, nifti_path)
    return _qc_check(img, nifti_path, standardization)


def _is_nifti(p: Path) -> bool:
    name = p.name.lower()
    return name.endswith(".nii") or name.endswith(".nii.gz")


def _convert_dicom_with_dcm2niix(folder: Path, work_dir: Path) -> Path:
    if shutil.which("dcm2niix") is None:
        raise InputError("dcm2niix binary not found on PATH. Rerun cell 1.")

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
        f"Found: {[p.name for p in nifti_files]}"
    )


def _validate_sagittal(img: nib.Nifti1Image, nifti_path: Path) -> None:
    axcodes = nib.aff2axcodes(img.affine)
    shape = tuple(int(x) for x in img.shape[:3])
    if axcodes[0] not in ("L", "R") or shape[0] > min(shape[1], shape[2]):
        raise InputError(
            f"{nifti_path.name}: orientation {axcodes} with shape {shape} is not sagittal-dominant. "
            "Pipeline expects the left-right axis to be the slice stack."
        )


def _standardize_geometry(
    img: nib.Nifti1Image,
    nifti_path: Path,
    work_dir: Path,
) -> tuple[nib.Nifti1Image, Path, dict | None]:
    if img.ndim != 3:
        return img, nifti_path, None

    original_axes = "".join(nib.aff2axcodes(img.affine))
    canonical = nib.as_closest_canonical(img)
    canonical_axes = "".join(nib.aff2axcodes(canonical.affine))
    max_oblique_deg, max_alignment_error = _geometry_metrics(canonical.affine)
    needs_resample = max_oblique_deg > OBLIQUE_DEG_TOL or max_alignment_error > GRID_ALIGN_TOL
    axes_changed = canonical_axes != original_axes

    if not needs_resample and not axes_changed:
        return img, nifti_path, None

    if needs_resample:
        spacing = tuple(float(x) for x in canonical.header.get_zooms()[:3])
        standardized = resample_to_output(canonical, voxel_sizes=spacing, order=1)
        standardized = nib.as_closest_canonical(standardized)
        standardized_path = work_dir / "input_standardized.nii.gz"
    else:
        standardized = canonical
        standardized_path = work_dir / "input_canonical.nii.gz"

    nib.save(standardized, str(standardized_path))
    return standardized, standardized_path, {
        "original_axes": original_axes,
        "standardized_axes": "".join(nib.aff2axcodes(standardized.affine)),
        "from_spacing_mm": [round(float(s), 4) for s in img.header.get_zooms()[:3]],
        "to_spacing_mm": [round(float(s), 4) for s in standardized.header.get_zooms()[:3]],
        "max_oblique_deg": round(max_oblique_deg, 3) if needs_resample else 0.0,
        "max_alignment_error": round(max_alignment_error, 5) if needs_resample else 0.0,
        "canonicalized_only": not needs_resample,
    }


def _geometry_metrics(affine: np.ndarray) -> tuple[float, float]:
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
    if img.ndim != 3:
        raise InputError(f"{nifti_path.name}: expected 3D volume, got {img.ndim}D")

    shape = tuple(int(x) for x in img.shape[:3])
    if shape[0] < 10 or min(shape[1], shape[2]) < 128:
        raise InputError(
            f"{nifti_path.name}: dimensions {shape} too small "
            "(need >=10 sagittal slices, >=128x128 in-plane)"
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


def run_totalspineseg(
    nifti_path: Path | str,
    work_dir: Path | str,
    *,
    iso: bool = True,
) -> SegmentationResult:
    if shutil.which("totalspineseg") is None:
        raise SegmentationError(
            "totalspineseg CLI not found on PATH. Run cell 1 first, then restart."
        )

    nifti_path = Path(nifti_path).resolve()
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    out_dir = work_dir / "tss_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = ["totalspineseg", str(nifti_path), str(out_dir)]
    if iso:
        cmd.append("--iso")

    print("+", " ".join(cmd))
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

    labels_present, missing_required = _check_cervical_labels(step2)

    return SegmentationResult(
        output_dir=out_dir,
        step2_output=step2,
        step1_levels=levels,
        iso_input=iso_input,
        cervical_labels_present=sorted(labels_present),
        missing_required_vertebrae=sorted(missing_required),
    )


def _expect_one_nifti(folder: Path, label: str) -> Path:
    if not folder.is_dir():
        raise SegmentationError(f"TSS produced no {label} folder at {folder}")
    files = sorted(folder.glob("*.nii.gz"))
    if not files:
        raise SegmentationError(f"TSS produced no {label} NIfTI in {folder}")
    return files[0]


def _check_cervical_labels(seg_path: Path) -> tuple[set[int], set[int]]:
    seg = nib.load(str(seg_path)).get_fdata().astype(np.int32)
    present = set(np.unique(seg).tolist()) - {0}
    missing = REQUIRED_VERTEBRAE - present
    relevant = present & (CERVICAL_VERTEBRA_LABELS | CERVICAL_DISC_LABELS)
    return relevant, missing


def _render_segmentation_overlay(
    mri_path: Path,
    seg_path: Path,
) -> None:
    """Show one sagittal slice with cervical segmentation labels overlaid."""
    mri_img = nib.load(str(mri_path))
    seg_img = nib.load(str(seg_path))

    # TotalSpineSeg may output on an isotropic grid with a different sagittal
    # slice count from the input preview volume. Resample the MRI onto the
    # segmentation grid so the overlay is index-aligned.
    if mri_img.shape[:3] != seg_img.shape[:3] or not np.allclose(mri_img.affine, seg_img.affine):
        mri_img = resample_from_to(mri_img, (seg_img.shape, seg_img.affine), order=1)

    mri = mri_img.get_fdata().astype(np.float32)
    seg = seg_img.get_fdata().astype(np.int32)

    relevant_labels = sorted((CERVICAL_VERTEBRA_LABELS | CERVICAL_DISC_LABELS) & set(np.unique(seg)))
    if not relevant_labels:
        print("Overlay preview skipped: no cervical labels present in segmentation.")
        return

    relevant_mask = np.isin(seg, relevant_labels)
    per_slice = relevant_mask.sum(axis=(1, 2))
    slice_idx = int(np.argmax(per_slice))
    if per_slice[slice_idx] == 0:
        print("Overlay preview skipped: no cervical labels visible on any sagittal slice.")
        return

    mri_slice = np.rot90(mri[slice_idx, :, :])
    seg_slice = np.rot90(seg[slice_idx, :, :])
    palette = [
        "#ef4444", "#f97316", "#eab308", "#22c55e",
        "#14b8a6", "#3b82f6", "#8b5cf6", "#ec4899",
        "#84cc16", "#06b6d4", "#f59e0b", "#10b981",
    ]
    cmap = ListedColormap(palette[: len(relevant_labels)])
    remapped = np.zeros_like(seg_slice, dtype=np.int32)
    for idx, label in enumerate(relevant_labels):
        remapped[seg_slice == label] = idx
    remapped_masked = np.ma.masked_where(~np.isin(seg_slice, relevant_labels), remapped)

    plt.figure(figsize=(9, 9))
    plt.imshow(mri_slice, cmap="gray")
    plt.imshow(remapped_masked, cmap=cmap, alpha=0.35, interpolation="nearest")
    plt.title(f"TotalSpineSeg overlay on sagittal slice {slice_idx}")
    plt.axis("off")

    for label in relevant_labels:
        ys, xs = np.where(seg_slice == label)
        if ys.size == 0:
            continue
        y = float(np.median(ys))
        x = float(np.median(xs))
        plt.text(
            x + 4,
            y,
            LABEL_NAMES.get(label, str(label)),
            color="white",
            fontsize=10,
            weight="bold",
            bbox={"facecolor": "black", "alpha": 0.65, "pad": 1.5, "edgecolor": "none"},
        )

    plt.show()


def main() -> None:
    _mount_drive_if_needed()
    _configure_env()
    _check_weights_cached()
    _preflight_totalspineseg_runtime()

    CASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    metadata = prepare_nifti(INPUT_SCAN_PATH, CASE_OUTPUT_DIR)
    result = run_totalspineseg(
        metadata.nifti_path,
        CASE_OUTPUT_DIR,
        iso=USE_ISO_OUTPUT,
    )

    manifest = {
        "input_path": str(INPUT_SCAN_PATH),
        "prepared_nifti_path": str(metadata.nifti_path),
        "output_dir": str(result.output_dir),
        "step2_output": str(result.step2_output),
        "step1_levels": str(result.step1_levels),
        "iso_input": str(result.iso_input) if result.iso_input else None,
        "cervical_labels_present": result.cervical_labels_present,
        "missing_required_vertebrae": result.missing_required_vertebrae,
        "input_metadata": {
            "voxel_spacing_mm": list(metadata.voxel_spacing_mm),
            "shape": list(metadata.shape),
            "canonical_axes": metadata.canonical_axes,
            "geometry_standardization": metadata.geometry_standardization,
        },
    }

    manifest_path = CASE_OUTPUT_DIR / "segmentation_run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print("Segmentation finished.")
    print(f"  step2_output: {result.step2_output}")
    print(f"  step1_levels: {result.step1_levels}")
    if result.iso_input:
        print(f"  iso_input: {result.iso_input}")
    print(f"  manifest: {manifest_path}")
    print(f"  cervical labels present: {result.cervical_labels_present}")
    if result.missing_required_vertebrae:
        missing_names = [LABEL_NAMES.get(label, str(label)) for label in result.missing_required_vertebrae]
        print(
            "  WARNING: required cervical vertebrae missing: "
            f"{result.missing_required_vertebrae} ({missing_names})"
        )
        print("  Continuing anyway so you can review the overlay and manifest.")

    overlay_input = result.iso_input or metadata.nifti_path
    print("\nOverlay preview:")
    _render_segmentation_overlay(overlay_input, result.step2_output)

    print("\nNext: run cell 3 (03_run_measurements_colab.py).")


main()
