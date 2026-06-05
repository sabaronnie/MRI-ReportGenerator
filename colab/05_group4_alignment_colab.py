"""Colab cells for Group 4 alignment testing on existing TotalSpineSeg output.

This notebook-style script assumes you already have a TotalSpineSeg
`step2_output.nii.gz` for the case. It reproduces the same corner-based logic
as the measurement service:
  4.1 C3-C7 Cobb angle
  4.2 Lordosis classification
  4.3 Segmental angles
  4.4 Posterior tangent angle

Unlike Group 3, no SCT dependency is needed here; we only reuse the vertebral
body corner pipeline on the TSS segmentation.
"""


# =============================================================================
# Colab cell 1/3 - install Python dependencies
# =============================================================================

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any


try:
    from google.colab import drive  # type: ignore
except ImportError:
    drive = None


# -------- Edit these before running --------
MOUNT_DRIVE = True
PIP_PACKAGES = [
    "nibabel>=5.0",
    "numpy>=1.24",
    "scipy>=1.10",
    "pandas>=2.0",
    "matplotlib>=3.8",
]
# ------------------------------------------


def _run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}")


if MOUNT_DRIVE and drive is not None:
    drive.mount("/content/drive", force_remount=False)

_run([sys.executable, "-m", "pip", "install", "-q", *PIP_PACKAGES])


# =============================================================================
# Colab cell 2/3 - configuration + helper functions
# =============================================================================

import nibabel as nib
import numpy as np
import pandas as pd
from nibabel.affines import obliquity
from nibabel.processing import resample_to_output
from scipy.ndimage import label as cc_label
from scipy.ndimage import zoom as ndi_zoom


# -------- Edit these before running --------
CASE_OUTPUT_DIR = Path("/content/drive/MyDrive/mri_report_generator_runs/case_001")
SEG_STEP2_PATH = None  # Optional override, e.g. "/content/.../step2_output.nii.gz"
# ------------------------------------------


TARGET_ISO_MM = 1.0
ISO_TOL_MM = 0.05
OBLIQUE_DEG_TOL = 5.0
GRID_ALIGN_TOL = 0.02
SLICE_THICKNESS_WARN_MM = 2.0

LEVEL_LABELS = {"C3": 13, "C4": 14, "C5": 15, "C6": 16, "C7": 17}
DISC_NEIGHBOURS = {
    "C3": (63, 64),
    "C4": (64, 65),
    "C5": (65, 66),
    "C6": (66, 67),
    "C7": (67, 71),
}
CANAL_LABELS = (1, 2)
DISC_AP_MARGIN_MM = 2.0
CANAL_BAND_FRACTION = 0.70
EDGE_STRIP_FRACTION = 0.15
MID_AP_SLAB_MM = 1.5
MID_SI_SLAB_MM = 1.5
MULTI_SLICE_OFFSETS = (-1, 0, 1)
MIN_BODY_PIXELS_2D = 25
SUBVOXEL_FACTOR = 4
SAG_AXIS = 0
AP_AXIS = 1
SI_AXIS = 2

KYPHOTIC_THRESHOLD_DEG = 0.0
LOW_LORDOSIS_THRESHOLD_DEG = 10.0
SUPINE_CAVEAT = (
    "Approximate classification only: derived from C3-C7 Cobb on supine MRI. "
    "Published normative thresholds are usually C2-C7 standing radiograph values "
    "and therefore read more lordotic than this pipeline."
)


class MeasurementError(RuntimeError):
    pass


@dataclass
class MeasurementContext:
    seg_path: Path | None
    seg_data: np.ndarray
    seg_affine: np.ndarray
    voxel_spacing_mm: tuple[float, float, float]
    manifest: dict = field(default_factory=dict)


@dataclass
class ComponentResult:
    measurements: dict[str, dict[str, float]]
    intermediate: dict[str, Any]
    flags: dict[str, dict[str, bool]]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SliceMeasurement:
    level: str
    slice_idx: int
    AP_width: float
    H_anterior: float
    H_middle: float
    H_posterior: float
    tilt_deg: float
    corners_mm: dict[str, tuple[float, float]]
    corners_voxel: dict[str, tuple[int, int, int]]
    AP_only: float
    AP_si_mismatch: float


def read_manifest(case_dir: Path) -> dict[str, Any]:
    manifest_path = case_dir / "segmentation_run_manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text())
    except (ValueError, OSError):
        return {}


def resolve_step2_path(case_dir: Path) -> Path:
    if SEG_STEP2_PATH:
        step2_path = Path(SEG_STEP2_PATH)
        if not step2_path.exists():
            raise FileNotFoundError(f"SEG_STEP2_PATH does not exist: {step2_path}")
        return step2_path

    manifest = read_manifest(case_dir)
    candidate = manifest.get("step2_output")
    if candidate:
        step2_path = Path(candidate)
        if step2_path.exists():
            return step2_path

    candidate_dir = case_dir / "tss_output" / "step2_output"
    candidates = sorted(candidate_dir.glob("*.nii.gz"))
    if candidates:
        return candidates[0]

    found = sorted(case_dir.rglob("step2_output*.nii.gz"))
    if found:
        return found[0]
    raise FileNotFoundError("Could not resolve step2_output.nii.gz")


def _geometry_metrics(affine: np.ndarray) -> tuple[float, float]:
    linear = np.asarray(affine[:3, :3], dtype=np.float64)
    norms = np.linalg.norm(linear, axis=0)
    if np.any(norms <= 0) or not np.all(np.isfinite(norms)):
        return float("inf"), float("inf")
    unit = linear / norms
    alignment_error = float(np.max(np.abs(unit - np.eye(3))))
    max_oblique_deg = float(np.degrees(np.max(obliquity(affine))))
    return max_oblique_deg, alignment_error


def _standardize_grid(img: nib.Nifti1Image, *, order: int) -> tuple[nib.Nifti1Image, dict | None]:
    canonical = nib.as_closest_canonical(img)
    max_oblique_deg, max_alignment_error = _geometry_metrics(canonical.affine)
    if max_oblique_deg <= OBLIQUE_DEG_TOL and max_alignment_error <= GRID_ALIGN_TOL:
        return canonical, None

    spacing = tuple(float(x) for x in canonical.header.get_zooms()[:3])
    standardized = resample_to_output(canonical, voxel_sizes=spacing, order=order)
    standardized = nib.as_closest_canonical(standardized)
    return standardized, {
        "from_spacing_mm": [round(float(s), 4) for s in img.header.get_zooms()[:3]],
        "to_spacing_mm": [round(float(s), 4) for s in standardized.header.get_zooms()[:3]],
        "max_oblique_deg": round(max_oblique_deg, 3),
        "max_alignment_error": round(max_alignment_error, 5),
    }


def _ensure_isotropic(seg_img: nib.Nifti1Image) -> tuple[nib.Nifti1Image, dict | None]:
    spacing = tuple(float(x) for x in seg_img.header.get_zooms()[:3])
    if all(abs(s - TARGET_ISO_MM) <= ISO_TOL_MM for s in spacing):
        return seg_img, None
    resampled = resample_to_output(seg_img, voxel_sizes=TARGET_ISO_MM, order=0)
    return resampled, {
        "from_spacing_mm": [round(s, 4) for s in spacing],
        "to_spacing_mm": [TARGET_ISO_MM] * 3,
    }


def _coerce_spacing(spacing: Any) -> tuple[float, float, float] | None:
    if spacing is None:
        return None
    try:
        vals = tuple(float(x) for x in spacing)[:3]
    except (TypeError, ValueError):
        return None
    if len(vals) != 3 or any(s <= 0 or not np.isfinite(s) for s in vals):
        return None
    return vals


def _resolution_quality(
    source_spacing_mm: tuple[float, float, float] | None,
    seg_file_spacing_mm: tuple[float, float, float],
    measurement_spacing_mm: tuple[float, float, float],
) -> dict:
    if source_spacing_mm is not None:
        thickness = max(source_spacing_mm)
        basis = "source_mri"
    else:
        thickness = max(seg_file_spacing_mm)
        basis = "segmentation_file"
    return {
        "source_spacing_mm": [round(float(s), 4) for s in source_spacing_mm] if source_spacing_mm is not None else None,
        "segmentation_file_spacing_mm": [round(float(s), 4) for s in seg_file_spacing_mm],
        "measurement_grid_mm": [round(float(s), 4) for s in measurement_spacing_mm],
        "slice_thickness_mm": round(float(thickness), 4),
        "slice_thickness_basis": basis,
        "low_through_plane_resolution": bool(thickness > SLICE_THICKNESS_WARN_MM),
    }


def load_context(seg_path: Path | str, source_spacing_mm: Any = None) -> MeasurementContext:
    seg_path = Path(seg_path).resolve()
    source_spacing = _coerce_spacing(source_spacing_mm)

    raw_seg_img = nib.load(str(seg_path))
    seg_file_spacing_mm = tuple(float(x) for x in raw_seg_img.header.get_zooms()[:3])
    seg_img, geometry_record = _standardize_grid(raw_seg_img, order=0)

    spacing = tuple(float(x) for x in seg_img.header.get_zooms()[:3])
    if any(s <= 0 or not np.isfinite(s) for s in spacing):
        raise MeasurementError(f"{seg_path.name}: non-finite spacing {spacing}")

    seg_img, resample_record = _ensure_isotropic(seg_img)
    seg_data = np.asarray(seg_img.dataobj).astype(np.int32)
    spacing = tuple(float(x) for x in seg_img.header.get_zooms()[:3])

    return MeasurementContext(
        seg_path=seg_path,
        seg_data=seg_data,
        seg_affine=seg_img.affine,
        voxel_spacing_mm=spacing,
        manifest={
            "seg_shape": list(seg_data.shape),
            "voxel_spacing_mm": list(spacing),
            "resolution_quality": _resolution_quality(source_spacing, seg_file_spacing_mm, spacing),
            "geometry_standardized": geometry_record,
            "resampled_to_isotropic": resample_record,
            "labels_present": sorted(int(x) for x in np.unique(seg_data) if x != 0),
        },
    )


def _largest_connected_component(mask: np.ndarray) -> np.ndarray:
    labeled, n = cc_label(mask)
    if n <= 1:
        return mask
    sizes = np.bincount(labeled.ravel())
    sizes[0] = 0
    return labeled == int(np.argmax(sizes))


def _refine_mask(mask_2d: np.ndarray, spacing_pa: float, spacing_si: float) -> tuple[np.ndarray, float, float, float]:
    if SUBVOXEL_FACTOR <= 1:
        return mask_2d, spacing_pa, spacing_si, 1.0
    k = int(SUBVOXEL_FACTOR)
    fine = (
        ndi_zoom(
            mask_2d.astype(np.float32),
            k,
            order=1,
            grid_mode=True,
            mode="grid-constant",
            cval=0.0,
        )
        >= 0.5
    )
    fine = _largest_connected_component(fine)
    return fine, spacing_pa / k, spacing_si / k, float(k)


def _argbreak(mask: np.ndarray, values: np.ndarray, mode: str, tiebreak: np.ndarray, tb_mode: str) -> int:
    idx = np.where(mask)[0]
    sub = values[idx]
    target = sub.max() if mode == "max" else sub.min()
    candidates = idx[sub == target]
    tb = tiebreak[candidates]
    pick = candidates[np.argmax(tb) if tb_mode == "max" else np.argmin(tb)]
    return int(pick)


def _dist_mm(a: tuple[float, float], b: tuple[float, float]) -> float:
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def _isolate_body_3d(seg: np.ndarray, level: str, spacing_pa: float) -> np.ndarray | None:
    label = LEVEL_LABELS[level]
    vertebra = seg == label
    if not vertebra.any():
        return None
    disc_ids = [d for d in DISC_NEIGHBOURS[level] if d is not None]
    disc_mask = np.isin(seg, disc_ids)
    if not disc_mask.any():
        return None
    ap_idx = np.where(disc_mask)[AP_AXIS]
    ap_lo = int(ap_idx.min())
    ap_hi = int(ap_idx.max())
    margin_vox = int(np.ceil(DISC_AP_MARGIN_MM / spacing_pa))
    ap_lo = max(0, ap_lo - margin_vox)
    ap_hi = min(seg.shape[AP_AXIS] - 1, ap_hi + margin_vox)
    ap_filter = np.zeros(seg.shape[AP_AXIS], dtype=bool)
    ap_filter[ap_lo:ap_hi + 1] = True
    body_3d = vertebra & ap_filter[None, :, None]
    return body_3d if body_3d.any() else None


def _select_best_slice(body_3d: np.ndarray, midline_band: np.ndarray) -> int | None:
    body_per_slice = body_3d.sum(axis=(AP_AXIS, SI_AXIS))
    masked = np.where(midline_band, body_per_slice, -1)
    if masked.max() <= 0:
        return None
    return int(np.argmax(masked))


def _measure_body_slice(level: str, body_mask_2d: np.ndarray, slice_idx: int, spacing_pa: float, spacing_si: float) -> SliceMeasurement | None:
    body_mask_2d = _largest_connected_component(body_mask_2d)
    if int(body_mask_2d.sum()) < MIN_BODY_PIXELS_2D:
        return None

    refined, fine_pa, fine_si, scale = _refine_mask(body_mask_2d, spacing_pa, spacing_si)
    coords_vox = np.argwhere(refined).astype(np.float64)
    coords_mm = coords_vox * np.array([fine_pa, fine_si])

    center_mm = coords_mm.mean(axis=0)
    centered = coords_mm - center_mm
    cov = np.cov(centered.T)
    _, eigvecs = np.linalg.eigh(cov)
    e0, e1 = eigvecs[:, 0], eigvecs[:, 1]

    global_si = np.array([0.0, 1.0])
    if abs(np.dot(e1, global_si)) >= abs(np.dot(e0, global_si)):
        si_axis = e1
        ap_axis = e0
    else:
        si_axis = e0
        ap_axis = e1
    if si_axis[1] < 0:
        si_axis = -si_axis
    if ap_axis[0] < 0:
        ap_axis = -ap_axis

    si_proj = centered @ si_axis
    ap_proj = centered @ ap_axis
    si_min, si_max = float(si_proj.min()), float(si_proj.max())
    ap_min, ap_max = float(ap_proj.min()), float(ap_proj.max())
    si_range = si_max - si_min
    ap_range = ap_max - ap_min
    if si_range <= 0 or ap_range <= 0:
        return None

    top_strip = si_proj >= si_max - EDGE_STRIP_FRACTION * si_range
    bot_strip = si_proj <= si_min + EDGE_STRIP_FRACTION * si_range
    if not top_strip.any() or not bot_strip.any():
        return None

    AS = _argbreak(top_strip, ap_proj, "max", si_proj, "max")
    PS = _argbreak(top_strip, ap_proj, "min", si_proj, "max")
    AI = _argbreak(bot_strip, ap_proj, "max", si_proj, "min")
    PI = _argbreak(bot_strip, ap_proj, "min", si_proj, "min")

    ap_mid = 0.5 * (ap_min + ap_max)
    half_ap_slab = max(MID_AP_SLAB_MM / 2.0, 0.08 * ap_range)
    in_mid_ap_slab = np.abs(ap_proj - ap_mid) <= half_ap_slab
    if in_mid_ap_slab.sum() < 3:
        in_mid_ap_slab = np.abs(ap_proj - ap_mid) <= 2.0 * half_ap_slab
    if in_mid_ap_slab.sum() < 3:
        return None

    M_sup = _argbreak(in_mid_ap_slab, si_proj, "max", ap_proj, "max")
    M_inf = _argbreak(in_mid_ap_slab, si_proj, "min", ap_proj, "max")

    si_mid = 0.5 * (si_min + si_max)
    half_si_slab = max(MID_SI_SLAB_MM / 2.0, 0.08 * si_range)
    in_mid_si_slab = np.abs(si_proj - si_mid) <= half_si_slab
    if in_mid_si_slab.sum() < 3:
        in_mid_si_slab = np.abs(si_proj - si_mid) <= 2.0 * half_si_slab
    if in_mid_si_slab.sum() < 3:
        return None

    si_center_closeness = -np.abs(si_proj - si_mid)
    A_mid = _argbreak(in_mid_si_slab, ap_proj, "max", si_center_closeness, "max")
    P_mid = _argbreak(in_mid_si_slab, ap_proj, "min", si_center_closeness, "max")

    point_idx = {
        "AS": AS,
        "PS": PS,
        "AI": AI,
        "PI": PI,
        "M_sup": M_sup,
        "M_inf": M_inf,
        "A_mid": A_mid,
        "P_mid": P_mid,
    }
    corners_mm = {name: (float(si_proj[i]), float(ap_proj[i])) for name, i in point_idx.items()}
    corners_voxel = {
        name: (
            int(slice_idx),
            float((coords_vox[i, 0] + 0.5) / scale - 0.5),
            float((coords_vox[i, 1] + 0.5) / scale - 0.5),
        )
        for name, i in point_idx.items()
    }

    tilt_deg = float(np.degrees(np.arccos(np.clip(abs(np.dot(si_axis, global_si)), 0.0, 1.0))))
    ap_only = abs(corners_mm["A_mid"][1] - corners_mm["P_mid"][1])
    ap_si_mismatch = abs(corners_mm["A_mid"][0] - corners_mm["P_mid"][0])

    return SliceMeasurement(
        level=level,
        slice_idx=int(slice_idx),
        AP_width=ap_only,
        H_anterior=_dist_mm(corners_mm["AS"], corners_mm["AI"]),
        H_middle=_dist_mm(corners_mm["M_sup"], corners_mm["M_inf"]),
        H_posterior=_dist_mm(corners_mm["PS"], corners_mm["PI"]),
        tilt_deg=tilt_deg,
        corners_mm=corners_mm,
        corners_voxel=corners_voxel,
        AP_only=ap_only,
        AP_si_mismatch=ap_si_mismatch,
    )


def compute_cervical_body_morphometry(ctx: MeasurementContext) -> ComponentResult:
    seg = ctx.seg_data
    spacing_pa = float(ctx.voxel_spacing_mm[AP_AXIS])
    spacing_si = float(ctx.voxel_spacing_mm[SI_AXIS])

    canal_3d = np.isin(seg, CANAL_LABELS)
    canal_per_slice = canal_3d.sum(axis=(AP_AXIS, SI_AXIS))
    canal_peak = int(canal_per_slice.max())
    if canal_peak == 0:
        raise MeasurementError("Canal labels (1/2) absent from segmentation.")
    midline_band = canal_per_slice >= CANAL_BAND_FRACTION * canal_peak

    per_level_rows: list[dict[str, Any]] = []
    for level in LEVEL_LABELS:
        if not (seg == LEVEL_LABELS[level]).any():
            continue
        body_3d = _isolate_body_3d(seg, level, spacing_pa)
        if body_3d is None:
            continue
        best_slice = _select_best_slice(body_3d, midline_band)
        if best_slice is None:
            continue

        per_slice: list[SliceMeasurement] = []
        for off in MULTI_SLICE_OFFSETS:
            slice_idx = best_slice + off
            if not (0 <= slice_idx < seg.shape[SAG_AXIS]):
                continue
            body_2d = body_3d[slice_idx, :, :]
            measured = _measure_body_slice(level, body_2d, slice_idx, spacing_pa, spacing_si)
            if measured is not None:
                per_slice.append(measured)
        if not per_slice:
            continue

        best_geom = next((m for m in per_slice if m.slice_idx == best_slice), per_slice[len(per_slice) // 2])
        best_ap = min(per_slice, key=lambda m: m.AP_si_mismatch)
        per_level_rows.append(
            {
                "level": level,
                "slice_idx": int(best_geom.slice_idx),
                "AP_width": float(best_ap.AP_width),
                "H_anterior": float(np.mean([m.H_anterior for m in per_slice])),
                "H_middle": float(np.mean([m.H_middle for m in per_slice])),
                "H_posterior": float(np.mean([m.H_posterior for m in per_slice])),
                "tilt_deg": float(np.mean([m.tilt_deg for m in per_slice])),
                "n_slices_used": len(per_slice),
                "corners_mm": best_ap.corners_mm,
                "corners_voxel": best_ap.corners_voxel,
                "ap_width_slice_idx": int(best_ap.slice_idx),
                "ap_width_si_mismatch_mm": float(best_ap.AP_si_mismatch),
            }
        )

    if not per_level_rows:
        raise MeasurementError("No cervical body morphometry rows were produced.")

    measurements = {"AP_width": {}, "H_anterior": {}, "H_middle": {}, "H_posterior": {}, "tilt_deg": {}}
    intermediate = {
        "corners_mm": {},
        "corners_voxel": {},
        "sagittal_slice": {},
        "ap_width_slice": {},
        "ap_width_si_mismatch_mm": {},
        "n_slices_used": {},
    }
    for row in per_level_rows:
        level = row["level"]
        for key in measurements:
            measurements[key][level] = row[key]
        intermediate["corners_mm"][level] = row["corners_mm"]
        intermediate["corners_voxel"][level] = row["corners_voxel"]
        intermediate["sagittal_slice"][level] = row["slice_idx"]
        intermediate["ap_width_slice"][level] = row["ap_width_slice_idx"]
        intermediate["ap_width_si_mismatch_mm"][level] = row["ap_width_si_mismatch_mm"]
        intermediate["n_slices_used"][level] = row["n_slices_used"]

    return ComponentResult(
        measurements=measurements,
        intermediate=intermediate,
        flags={},
        metadata={"levels": [row["level"] for row in per_level_rows]},
    )


def _require_corners(corners_voxel: dict[str, Any], level: str, required: tuple[str, ...]) -> dict[str, tuple[float, float, float]]:
    level_corners = corners_voxel.get(level)
    if not level_corners:
        raise MeasurementError(f"Required corners missing for {level}")
    missing = [name for name in required if level_corners.get(name) is None]
    if missing:
        raise MeasurementError(f"Missing corners for {level}: {missing}")
    return level_corners


def _line_angle_deg(a: tuple[float, float, float], b: tuple[float, float, float], spacing_pa_mm: float, spacing_si_mm: float) -> float:
    dpa = (b[1] - a[1]) * spacing_pa_mm
    dsi = (b[2] - a[2]) * spacing_si_mm
    return float(np.degrees(np.arctan2(dsi, dpa)))


def _normalize_deg(angle_deg: float) -> float:
    normalized = (angle_deg + 180.0) % 360.0 - 180.0
    return 180.0 if normalized == -180.0 else normalized


def compute_group4(ctx: MeasurementContext, morphometry: ComponentResult) -> dict[str, Any]:
    corners_voxel = morphometry.intermediate["corners_voxel"]
    spacing_pa_mm = float(ctx.voxel_spacing_mm[AP_AXIS])
    spacing_si_mm = float(ctx.voxel_spacing_mm[SI_AXIS])

    c3 = _require_corners(corners_voxel, "C3", ("AI", "PI", "PS"))
    c7 = _require_corners(corners_voxel, "C7", ("AI", "PI", "PS"))

    c3_inf = _line_angle_deg(c3["AI"], c3["PI"], spacing_pa_mm, spacing_si_mm)
    c7_inf = _line_angle_deg(c7["AI"], c7["PI"], spacing_pa_mm, spacing_si_mm)
    cobb_c3c7 = _normalize_deg(c3_inf - c7_inf)

    if cobb_c3c7 < KYPHOTIC_THRESHOLD_DEG:
        lordosis_class = "kyphotic"
        class_approximate = False
    elif cobb_c3c7 < LOW_LORDOSIS_THRESHOLD_DEG:
        lordosis_class = "straightened / low lordosis"
        class_approximate = True
    else:
        lordosis_class = "lordotic"
        class_approximate = True

    segmental_angles: dict[str, float] = {}
    for upper_level, lower_level in [("C3", "C4"), ("C4", "C5"), ("C5", "C6"), ("C6", "C7")]:
        try:
            upper = _require_corners(corners_voxel, upper_level, ("AI", "PI"))
            lower = _require_corners(corners_voxel, lower_level, ("AS", "PS"))
        except MeasurementError:
            continue
        upper_angle = _line_angle_deg(upper["AI"], upper["PI"], spacing_pa_mm, spacing_si_mm)
        lower_angle = _line_angle_deg(lower["AS"], lower["PS"], spacing_pa_mm, spacing_si_mm)
        segmental_angles[f"{upper_level}-{lower_level}"] = round(_normalize_deg(upper_angle - lower_angle), 3)

    c3_post = _line_angle_deg(c3["PS"], c3["PI"], spacing_pa_mm, spacing_si_mm)
    c7_post = _line_angle_deg(c7["PS"], c7["PI"], spacing_pa_mm, spacing_si_mm)
    posterior_tangent = _normalize_deg(c3_post - c7_post)
    divergence = abs(cobb_c3c7 - posterior_tangent)

    return {
        "Cobb_C3_C7_deg": round(cobb_c3c7, 3),
        "lordosis_classification": lordosis_class,
        "lordosis_classification_approximate": class_approximate,
        "classification_caveat": SUPINE_CAVEAT,
        "segmental_angles_deg": segmental_angles,
        "posterior_tangent_C3_C7_deg": round(posterior_tangent, 3),
        "cobb_vs_posterior_tangent_divergence_deg": round(divergence, 3),
        "sign_convention": "lordosis_positive_kyphosis_negative",
    }


# =============================================================================
# Colab cell 3/3 - run Group 4 alignment metrics
# =============================================================================

CASE_OUTPUT_DIR = CASE_OUTPUT_DIR.resolve()
CASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
step2_path = resolve_step2_path(CASE_OUTPUT_DIR)
manifest = read_manifest(CASE_OUTPUT_DIR)
source_spacing = manifest.get("input_metadata", {}).get("voxel_spacing_mm")

print("Resolved input:")
print("  SEG_STEP2_PATH:", step2_path)

ctx = load_context(step2_path, source_spacing_mm=source_spacing)
morphometry = compute_cervical_body_morphometry(ctx)
alignment = compute_group4(ctx, morphometry)

summary_rows = [
    {"metric": "Cobb_C3_C7_deg", "value": alignment["Cobb_C3_C7_deg"]},
    {"metric": "lordosis_classification", "value": alignment["lordosis_classification"]},
    {"metric": "lordosis_classification_approximate", "value": alignment["lordosis_classification_approximate"]},
    {"metric": "posterior_tangent_C3_C7_deg", "value": alignment["posterior_tangent_C3_C7_deg"]},
    {"metric": "cobb_vs_posterior_tangent_divergence_deg", "value": alignment["cobb_vs_posterior_tangent_divergence_deg"]},
]
summary_df = pd.DataFrame(summary_rows)

segmental_df = pd.DataFrame(
    [{"segment": key, "angle_deg": value} for key, value in alignment["segmental_angles_deg"].items()]
)

print("\nGroup 4 summary:")
display(summary_df if "display" in globals() else summary_df)

print("\nSegmental angles:")
display(segmental_df if "display" in globals() else segmental_df)

out_json = CASE_OUTPUT_DIR / "group4_alignment_results.json"
out_json.write_text(json.dumps(alignment, indent=2))
print("\nSaved summary JSON to:", out_json)
print("Classification caveat:", alignment["classification_caveat"])
