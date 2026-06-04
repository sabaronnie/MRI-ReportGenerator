"""Colab cell 3/3 — run the measurement pipeline on the TotalSpineSeg output.

Prereq: cell 2 produced a segmentation under CASE_OUTPUT_DIR. This cell finds
that segmentation (via the manifest cell 2 wrote, or SEG_STEP2_PATH below),
loads it into a canonical isotropic context, and runs the measurement
components. The measurements are displayed inline in the cell — no file is written.

This is the same measurement code as the `services/measurements` IEP, inlined
for Colab so the notebook needs no repo imports.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
import matplotlib.pyplot as plt
from nibabel.affines import obliquity
from nibabel.processing import resample_from_to, resample_to_output
from scipy.ndimage import label as cc_label
from scipy.ndimage import zoom as ndi_zoom


# -------- Edit these before running --------
CASE_OUTPUT_DIR = Path("/content/drive/MyDrive/mri_report_generator_runs/case_001")
SEG_STEP2_PATH = None  # Optional override, e.g. "/content/.../tss_output/step2_output/scan.nii.gz"
RAW_MRI_PATH = None    # Optional raw MRI for signal-based components (unused by current components)
ENABLED_COMPONENTS = None  # Example: ["cervical_body_morphometry"]; None runs all
# ------------------------------------------


TARGET_ISO_MM = 1.0
ISO_TOL_MM = 0.05
OBLIQUE_DEG_TOL = 5.0
GRID_ALIGN_TOL = 0.02
# Acquisition slice thickness above which the 1 mm isotropic grid is interpolated
# through-plane, not real detail (typical sagittal cervical T2 is ~3-4 mm slices).
# Engineering quality-gate threshold, NOT a clinical cutoff.
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
# Sub-voxel boundary refinement: per-slice in-plane (AP/SI) upsample factor.
# Linear upsample + 0.5 re-threshold puts the edge at the half-level crossing
# (~marching-squares), cutting the ±1 voxel staircase to ~spacing/factor. Only
# the in-plane axes are refined, never the low-res slice axis. 1 disables it.
SUBVOXEL_FACTOR = 4
AP_WIDTH_LOW_MM = 12.0
AP_WIDTH_HIGH_MM = 22.0
TILT_DEG_MAX = 20.0
WEDGE_RATIO = 0.70
BICONCAVE_RATIO = 0.70
SAG_AXIS = 0
AP_AXIS = 1
SI_AXIS = 2
SPONDY_LEVEL_ORDER = ["C2", "C3", "C4", "C5", "C6", "C7", "T1"]
NEUTRAL_THRESHOLD_MM = 1.0
SPONDY_PRESENT_THRESHOLD_MM = 2.0
SUPINE_CAVEAT = (
    "Measured on supine MRI - functional radiographs may show greater slip "
    "(Lattig 2012; Segebarth 2015)."
)
LEVEL_COLORS = {
    "C3": "#ef4444",
    "C4": "#f97316",
    "C5": "#22c55e",
    "C6": "#3b82f6",
    "C7": "#8b5cf6",
}
SEG_OVERLAY_COLOR = np.array([1.0, 0.75, 0.2])


class MeasurementError(RuntimeError):
    """Raised when measurement inputs are unusable."""


@dataclass
class MeasurementContext:
    seg_path: Path | None
    seg_data: np.ndarray
    seg_affine: np.ndarray
    voxel_spacing_mm: tuple[float, float, float]
    raw_path: Path | None = None
    raw_data: np.ndarray | None = None
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


def _mount_drive_if_needed() -> None:
    if "google.colab" not in sys.modules:
        return
    from google.colab import drive  # type: ignore

    drive.mount("/content/drive", force_remount=False)


def _resolve_step2_path() -> Path:
    manifest = _read_manifest()
    if SEG_STEP2_PATH:
        step2_path = Path(SEG_STEP2_PATH)
        if not step2_path.exists():
            raise FileNotFoundError(f"SEG_STEP2_PATH does not exist: {step2_path}")
        return step2_path

    if manifest:
        step2_path = Path(manifest["step2_output"])
        if step2_path.exists():
            return step2_path

    candidate_dir = CASE_OUTPUT_DIR / "tss_output" / "step2_output"
    candidates = sorted(candidate_dir.glob("*.nii.gz"))
    if not candidates:
        raise FileNotFoundError(
            "Could not find a step2_output segmentation. Set SEG_STEP2_PATH explicitly "
            f"or make sure cell 2 created output under: {candidate_dir}"
        )
    return candidates[0]


def _read_source_spacing() -> list[float] | None:
    """Original MRI voxel spacing from the cell-2 manifest, if available.

    The step2 segmentation is already 1 mm isotropic, so this manifest is the
    only record of the true acquisition slice thickness. Returns None if the
    manifest is missing — load_context then falls back gracefully.
    """
    manifest = _read_manifest()
    return manifest.get("input_metadata", {}).get("voxel_spacing_mm") if manifest else None


def _read_manifest() -> dict[str, Any]:
    manifest_path = CASE_OUTPUT_DIR / "segmentation_run_manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text())
    except (ValueError, OSError):
        return {}


def _resolve_raw_mri_path() -> Path | None:
    if RAW_MRI_PATH:
        p = Path(RAW_MRI_PATH)
        return p if p.exists() else None

    manifest = _read_manifest()
    for key in ("iso_input", "prepared_nifti_path", "input_path"):
        candidate = manifest.get(key)
        if not candidate:
            continue
        p = Path(candidate)
        if p.exists() and p.suffix in {".nii", ".gz"}:
            return p
    return None


def _ensure_isotropic(seg_img: nib.Nifti1Image) -> tuple[nib.Nifti1Image, dict | None]:
    spacing = tuple(float(x) for x in seg_img.header.get_zooms()[:3])
    if all(abs(s - TARGET_ISO_MM) <= ISO_TOL_MM for s in spacing):
        return seg_img, None
    resampled = resample_to_output(seg_img, voxel_sizes=TARGET_ISO_MM, order=0)
    return resampled, {
        "from_spacing_mm": [round(s, 4) for s in spacing],
        "to_spacing_mm": [TARGET_ISO_MM] * 3,
    }


def _standardize_grid(
    img: nib.Nifti1Image,
    *,
    order: int,
) -> tuple[nib.Nifti1Image, dict | None]:
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


def _geometry_metrics(affine: np.ndarray) -> tuple[float, float]:
    linear = np.asarray(affine[:3, :3], dtype=np.float64)
    norms = np.linalg.norm(linear, axis=0)
    if np.any(norms <= 0) or not np.all(np.isfinite(norms)):
        return float("inf"), float("inf")

    unit = linear / norms
    alignment_error = float(np.max(np.abs(unit - np.eye(3))))
    max_oblique_deg = float(np.degrees(np.max(obliquity(affine))))
    return max_oblique_deg, alignment_error


def _coerce_spacing(spacing: Any) -> tuple[float, float, float] | None:
    """Validate an externally supplied voxel spacing; return None if unusable."""
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
    """Flag whether the 1 mm grid is real resolution or interpolated through-plane.

    source_spacing_mm   : original MRI voxel spacing (from the cell-2 manifest) —
                          the authoritative slice-thickness source.
    seg_file_spacing_mm : spacing of the segmentation file as received (already
                          ~1 mm after TotalSpineSeg --iso, so only a best-effort
                          fallback when the source spacing is unavailable).
    """
    if source_spacing_mm is not None:
        thickness = max(source_spacing_mm)
        basis = "source_mri"
    else:
        thickness = max(seg_file_spacing_mm)
        basis = "segmentation_file"
    return {
        "source_spacing_mm": [round(float(s), 4) for s in source_spacing_mm]
        if source_spacing_mm is not None
        else None,
        "segmentation_file_spacing_mm": [round(float(s), 4) for s in seg_file_spacing_mm],
        "measurement_grid_mm": [round(float(s), 4) for s in measurement_spacing_mm],
        "slice_thickness_mm": round(float(thickness), 4),
        "slice_thickness_basis": basis,
        "low_through_plane_resolution": bool(thickness > SLICE_THICKNESS_WARN_MM),
    }


def load_context(
    seg_path: Path | str,
    raw_path: Path | str | None = None,
    source_spacing_mm: Any = None,
) -> MeasurementContext:
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

    raw_data = None
    raw_path_resolved = None
    if raw_path is not None:
        raw_path_resolved = Path(raw_path).resolve()
        raw_img, _ = _standardize_grid(nib.load(str(raw_path_resolved)), order=1)
        raw_img = resample_from_to(raw_img, (seg_img.shape, seg_img.affine), order=1)
        raw_data = np.asarray(raw_img.dataobj).astype(np.float32)

    return MeasurementContext(
        seg_path=seg_path,
        seg_data=seg_data,
        seg_affine=seg_img.affine,
        voxel_spacing_mm=spacing,
        raw_path=raw_path_resolved,
        raw_data=raw_data,
        manifest={
            "seg_shape": list(seg_data.shape),
            "voxel_spacing_mm": list(spacing),
            "resolution_quality": _resolution_quality(
                source_spacing, seg_file_spacing_mm, spacing
            ),
            "geometry_standardized": geometry_record,
            "resampled_to_isotropic": resample_record,
            "labels_present": sorted(int(x) for x in np.unique(seg_data) if x != 0),
        },
    )


def run_all(ctx: MeasurementContext, enabled: list[str] | None = None) -> dict[str, Any]:
    available = {
        "cervical_body_morphometry": compute_cervical_body_morphometry,
        "spondylolisthesis": compute_spondylolisthesis,
    }
    ordered = ["cervical_body_morphometry", "spondylolisthesis"]
    selected = ordered if enabled is None else [name for name in ordered if name in enabled]

    report: dict[str, Any] = {"components": {}, "measurements": {}, "flags": {}}
    prior: dict[str, Any] = {}

    for name in selected:
        component = available[name]
        result = component(ctx, prior)
        for measurement_key, per_level in result.measurements.items():
            report["measurements"].setdefault(measurement_key, {}).update(per_level)
        for flag_key, per_level in result.flags.items():
            report["flags"].setdefault(flag_key, {}).update(per_level)
        report["components"][name] = {
            "status": "ok",
            "metadata": result.metadata,
            "intermediate": result.intermediate,
            "flags": result.flags,
        }
        prior[name] = result
    return report


def compute_cervical_body_morphometry(
    ctx: MeasurementContext,
    prior_results: dict[str, Any] | None = None,
) -> ComponentResult:
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
        row = _measure_level(seg, level, midline_band, spacing_pa, spacing_si)
        per_level_rows.append(row)

    if not per_level_rows:
        raise MeasurementError("No cervical vertebral body measurements could be produced")

    measurements = {
        "AP_width": {},
        "H_anterior": {},
        "H_middle": {},
        "H_posterior": {},
        "tilt_deg": {},
    }
    flags = {
        "ap_width_outlier": {},
        "tilt_outlier": {},
        "wedge_fracture": {},
        "biconcave_fracture": {},
    }
    intermediate: dict[str, Any] = {
        "corners_mm": {},
        "corners_voxel": {},
        "sagittal_slice": {},
        "ap_width_slice": {},
        "ap_width_si_mismatch_mm": {},
        "n_slices_used": {},
    }

    for row in per_level_rows:
        level = row["level"]
        measurements["AP_width"][level] = row["AP_width"]
        measurements["H_anterior"][level] = row["H_anterior"]
        measurements["H_middle"][level] = row["H_middle"]
        measurements["H_posterior"][level] = row["H_posterior"]
        measurements["tilt_deg"][level] = row["tilt_deg"]

        flags["ap_width_outlier"][level] = (
            row["AP_width"] < AP_WIDTH_LOW_MM or row["AP_width"] > AP_WIDTH_HIGH_MM
        )
        flags["tilt_outlier"][level] = row["tilt_deg"] > TILT_DEG_MAX
        flags["wedge_fracture"][level] = row["H_anterior"] < WEDGE_RATIO * row["H_posterior"]
        flags["biconcave_fracture"][level] = (
            row["H_middle"] < BICONCAVE_RATIO * max(row["H_anterior"], row["H_posterior"])
        )

        intermediate["corners_mm"][level] = row["corners_mm"]
        intermediate["corners_voxel"][level] = row["corners_voxel"]
        intermediate["sagittal_slice"][level] = row["slice_idx"]
        intermediate["ap_width_slice"][level] = row["ap_width_slice_idx"]
        intermediate["ap_width_si_mismatch_mm"][level] = row["ap_width_si_mismatch_mm"]
        intermediate["n_slices_used"][level] = row["n_slices_used"]

    return ComponentResult(
        measurements=measurements,
        intermediate=intermediate,
        flags=flags,
        metadata={
            "levels": [row["level"] for row in per_level_rows],
            "method": "disc-anchored body isolation + canal midline band + Genant heights + SHIP mid-body AP",
        },
    )


def _measure_level(
    seg: np.ndarray,
    level: str,
    midline_band: np.ndarray,
    spacing_pa: float,
    spacing_si: float,
) -> dict[str, Any]:
    body_3d = _isolate_body_3d(seg, level, spacing_pa)
    if body_3d is None:
        raise MeasurementError(f"{level}: body isolation failed")

    best_slice = _select_best_slice(body_3d, midline_band)
    if best_slice is None:
        raise MeasurementError(f"{level}: no valid slice in midline band")

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
        raise MeasurementError(f"{level}: measurement failed on best slice and neighbors")

    best_geom = next((m for m in per_slice if m.slice_idx == best_slice), per_slice[len(per_slice) // 2])
    best_ap = min(per_slice, key=lambda m: m.AP_si_mismatch)

    return {
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


def _largest_connected_component(mask: np.ndarray) -> np.ndarray:
    labeled, n = cc_label(mask)
    if n <= 1:
        return mask
    sizes = np.bincount(labeled.ravel())
    sizes[0] = 0
    return labeled == int(np.argmax(sizes))


def _refine_mask(
    mask_2d: np.ndarray,
    spacing_pa: float,
    spacing_si: float,
) -> tuple[np.ndarray, float, float, float]:
    """In-plane sub-voxel refinement: linear upsample + 0.5 re-threshold.

    Puts the body edge at the half-level crossing (~marching-squares) instead of
    on voxel centres. Returns the refined mask, its per-voxel mm spacing, and the
    scale (refined voxels per original voxel) for mapping landmarks back.
    """
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


def _measure_body_slice(
    level: str,
    body_mask_2d: np.ndarray,
    slice_idx: int,
    spacing_pa: float,
    spacing_si: float,
) -> SliceMeasurement | None:
    body_mask_2d = _largest_connected_component(body_mask_2d)
    if int(body_mask_2d.sum()) < MIN_BODY_PIXELS_2D:
        return None

    # Sub-voxel in-plane boundary refinement; min-pixel gate above stays on the
    # original mask so its meaning is unchanged.
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
    # Refined-grid indices -> original-voxel coordinates (cell-centre convention).
    # At scale==1 this is the identity, reproducing the original integer coords.
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


def compute_spondylolisthesis(
    ctx: MeasurementContext,
    prior_results: dict[str, Any],
) -> ComponentResult:
    producer = prior_results.get("cervical_body_morphometry")
    if producer is None:
        raise MeasurementError("spondylolisthesis requires cervical_body_morphometry first.")

    corners_voxel = producer.intermediate.get("corners_voxel", {})
    ap_widths = producer.measurements.get("AP_width", {})
    spacing_pa_mm = float(ctx.voxel_spacing_mm[1])

    present = [n for n in SPONDY_LEVEL_ORDER if corners_voxel.get(n)]
    pairs = list(zip(present[:-1], present[1:]))

    slips: dict[str, float] = {}
    pcts: dict[str, float] = {}
    grades: dict[str, str] = {}
    directions: dict[str, str] = {}
    report_lines: dict[str, str] = {}
    flags_present: dict[str, bool] = {}

    for upper, lower in pairs:
        pair_key = f"{upper}-{lower}"
        upper_pi = corners_voxel.get(upper, {}).get("PI")
        lower_ps = corners_voxel.get(lower, {}).get("PS")
        if upper_pi is None or lower_ps is None:
            continue

        slip_mm = float((upper_pi[1] - lower_ps[1]) * spacing_pa_mm)
        ap_w = float(ap_widths.get(lower, float("nan")))

        if not np.isfinite(ap_w) or ap_w <= 0:
            grade = "?"
            pct = float("nan")
            grade_text = f"grade unknown ({lower} AP_width unavailable)"
        else:
            pct = abs(slip_mm) / ap_w * 100.0
            grade = _meyerding_grade(pct)
            grade_text = f"Grade {grade}, {pct:.1f}% of {lower} AP_width"

        if abs(slip_mm) < NEUTRAL_THRESHOLD_MM:
            direction = "neutral"
        elif slip_mm > 0:
            direction = "anterolisthesis"
        else:
            direction = "retrolisthesis"

        slips[pair_key] = slip_mm
        pcts[pair_key] = pct
        grades[pair_key] = grade
        directions[pair_key] = direction
        flags_present[pair_key] = abs(slip_mm) >= SPONDY_PRESENT_THRESHOLD_MM
        report_lines[pair_key] = (
            f"{upper} on {lower}: {abs(slip_mm):.2f} mm {direction} "
            f"({grade_text}). {SUPINE_CAVEAT}"
        )

    return ComponentResult(
        measurements={
            "spondy_slip_mm": slips,
            "spondy_pct_of_lower_AP": pcts,
        },
        intermediate={},
        flags={"spondylolisthesis_present": flags_present},
        metadata={
            "spondy_meyerding_grade": grades,
            "spondy_direction": directions,
            "spondy_report_lines": report_lines,
            "spondy_caveat": SUPINE_CAVEAT,
            "pairs_evaluated": [f"{u}-{l}" for u, l in pairs],
        },
    )


def _meyerding_grade(pct: float) -> str:
    if pct < 25:
        return "I"
    if pct < 50:
        return "II"
    if pct < 75:
        return "III"
    if pct < 100:
        return "IV"
    return "V"


def _fmt(value: float | None, ndigits: int = 1) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "n/a"
    return f"{value:.{ndigits}f}"


def _print_text_table(title: str, columns: list[str], rows: list[dict]) -> None:
    print(f"\n=== {title} ===")
    if not rows:
        print("(none)")
        return
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in columns}
    print("  ".join(c.ljust(widths[c]) for c in columns))
    print("  ".join("-" * widths[c] for c in columns))
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(widths[c]) for c in columns))


def _show_table(title: str, columns: list[str], rows: list[dict]) -> None:
    """Render a table — pandas/HTML in a notebook, aligned text otherwise."""
    try:
        import pandas as pd
        from IPython.display import display
    except Exception:
        _print_text_table(title, columns, rows)
        return

    print(f"\n=== {title} ===")
    if not rows:
        print("(none)")
        return
    display(pd.DataFrame(rows, columns=columns))


def _display_report(report: dict, step2_path: Path, ctx: MeasurementContext) -> None:
    measurements = report.get("measurements", {})
    flags = report.get("flags", {})
    components = report.get("components", {})

    print("Measurements finished.")
    print(f"  segmentation : {step2_path}")
    print(f"  components   : {list(components.keys())}")
    print(f"  labels found : {ctx.manifest.get('labels_present')}")
    print(f"  voxel mm     : {ctx.manifest.get('voxel_spacing_mm')}")

    rq = ctx.manifest.get("resolution_quality", {})
    if rq:
        src = rq.get("source_spacing_mm")
        print(f"  source mm    : {src if src is not None else 'unknown (no cell-2 manifest)'}")
        print(
            f"  slice thick  : {rq.get('slice_thickness_mm')} mm "
            f"(basis: {rq.get('slice_thickness_basis')})"
        )
        if rq.get("low_through_plane_resolution"):
            print(
                "  *** LOW THROUGH-PLANE RESOLUTION: the 1 mm grid is interpolated, "
                "not real detail.\n"
                "      Slice-selection and AP/SI measurements are less reliable — "
                "treat this case as lower confidence."
            )

    # One row per cervical level: Genant heights + AP width + tilt + any flags.
    ap_width = measurements.get("AP_width", {})
    h_ant = measurements.get("H_anterior", {})
    h_mid = measurements.get("H_middle", {})
    h_post = measurements.get("H_posterior", {})
    tilt = measurements.get("tilt_deg", {})
    morph_flag_keys = ["ap_width_outlier", "tilt_outlier", "wedge_fracture", "biconcave_fracture"]
    morph_rows = []
    for level in LEVEL_LABELS:
        if level not in ap_width and level not in h_ant:
            continue
        flagged = [k for k in morph_flag_keys if flags.get(k, {}).get(level)]
        morph_rows.append({
            "level": level,
            "AP_width_mm": _fmt(ap_width.get(level)),
            "H_ant_mm": _fmt(h_ant.get(level)),
            "H_mid_mm": _fmt(h_mid.get(level)),
            "H_post_mm": _fmt(h_post.get(level)),
            "tilt_deg": _fmt(tilt.get(level)),
            "flags": ", ".join(flagged) if flagged else "-",
        })
    _show_table(
        "Cervical vertebral body morphometry (mm)",
        ["level", "AP_width_mm", "H_ant_mm", "H_mid_mm", "H_post_mm", "tilt_deg", "flags"],
        morph_rows,
    )

    # One row per adjacent level pair: slip, % of lower body, Meyerding grade.
    slip = measurements.get("spondy_slip_mm", {})
    pct = measurements.get("spondy_pct_of_lower_AP", {})
    meta = components.get("spondylolisthesis", {}).get("metadata", {})
    grades = meta.get("spondy_meyerding_grade", {})
    directions = meta.get("spondy_direction", {})
    present = flags.get("spondylolisthesis_present", {})
    spondy_rows = []
    for pair in slip:
        spondy_rows.append({
            "pair": pair,
            "slip_mm": _fmt(slip.get(pair), 2),
            "pct_of_lower_AP": _fmt(pct.get(pair)),
            "grade": grades.get(pair, "?"),
            "direction": directions.get(pair, "-"),
            "flagged": "YES" if present.get(pair) else "-",
        })
    _show_table(
        "Spondylolisthesis (adjacent levels)",
        ["pair", "slip_mm", "pct_of_lower_AP", "grade", "direction", "flagged"],
        spondy_rows,
    )

    report_lines = meta.get("spondy_report_lines", {})
    if report_lines:
        print("\nSpondylolisthesis notes (for physician review):")
        for line in report_lines.values():
            print(f"  - {line}")


def _draw_point(ax, point: tuple[float, float, float], color: str) -> None:
    _, ap, si = point
    ax.scatter(si, ap, s=24, c=color, edgecolors="black", linewidths=0.6, zorder=4)


def _draw_line(ax, p1: tuple[float, float, float], p2: tuple[float, float, float], color: str, lw: float = 2.0) -> None:
    _, ap1, si1 = p1
    _, ap2, si2 = p2
    ax.plot([si1, si2], [ap1, ap2], color=color, linewidth=lw, zorder=3)


def _show_geometric_overlays(report: dict, ctx: MeasurementContext) -> None:
    morph = report.get("components", {}).get("cervical_body_morphometry", {})
    intermediate = morph.get("intermediate", {})
    corners_by_level = intermediate.get("corners_voxel", {})
    slice_by_level = intermediate.get("sagittal_slice", {})
    if not corners_by_level or not slice_by_level:
        return

    base = ctx.raw_data if ctx.raw_data is not None else ctx.seg_data.astype(np.float32)
    seg = ctx.seg_data
    levels = [lvl for lvl in LEVEL_LABELS if lvl in corners_by_level and lvl in slice_by_level]
    if not levels:
        return

    fig, axes = plt.subplots(len(levels), 1, figsize=(8.5, 4.8 * len(levels)))
    if len(levels) == 1:
        axes = [axes]

    for ax, level in zip(axes, levels):
        slice_idx = int(slice_by_level[level])
        label_id = LEVEL_LABELS[level]
        body_mask = seg[slice_idx, :, :] == label_id
        seg_any = seg[slice_idx, :, :] > 0
        base_slice = base[slice_idx, :, :]

        ax.imshow(base_slice, cmap="gray", origin="lower")
        if np.any(seg_any):
            rgb = np.zeros((*seg_any.shape, 4), dtype=np.float32)
            rgb[..., :3] = SEG_OVERLAY_COLOR
            rgb[..., 3] = seg_any.astype(np.float32) * 0.10
            ax.imshow(rgb, origin="lower")
        if np.any(body_mask):
            body_rgba = np.zeros((*body_mask.shape, 4), dtype=np.float32)
            body_rgba[..., :3] = np.array([1.0, 0.2, 0.2])
            body_rgba[..., 3] = body_mask.astype(np.float32) * 0.26
            ax.imshow(body_rgba, origin="lower")

        color = LEVEL_COLORS.get(level, "#ffffff")
        corners = corners_by_level[level]
        for pair in (("AS", "AI"), ("PS", "PI"), ("M_sup", "M_inf"), ("P_mid", "A_mid")):
            if pair[0] in corners and pair[1] in corners:
                _draw_line(ax, corners[pair[0]], corners[pair[1]], color)
        for name in ("AS", "AI", "PS", "PI", "M_sup", "M_inf", "A_mid", "P_mid"):
            if name in corners:
                _draw_point(ax, corners[name], color)

        ax.set_title(f"{level} geometric overlay (sagittal slice {slice_idx})")
        ax.set_xlabel("SI axis (voxels)")
        ax.set_ylabel("AP axis (voxels)")

    plt.tight_layout()
    plt.show()

    spondy = report.get("components", {}).get("spondylolisthesis", {})
    spondy_meta = spondy.get("metadata", {})
    directions = spondy_meta.get("spondy_direction", {})
    slips = report.get("measurements", {}).get("spondy_slip_mm", {})
    if not slips:
        return

    present_pairs = []
    for pair in slips:
        upper, lower = pair.split("-")
        if upper in corners_by_level and lower in corners_by_level:
            present_pairs.append((pair, upper, lower))
    if not present_pairs:
        return

    fig, axes = plt.subplots(len(present_pairs), 1, figsize=(8.5, 4.8 * len(present_pairs)))
    if len(present_pairs) == 1:
        axes = [axes]

    for ax, (pair, upper, lower) in zip(axes, present_pairs):
        slice_idx = int(round((slice_by_level[upper] + slice_by_level[lower]) / 2.0))
        slice_idx = max(0, min(slice_idx, seg.shape[0] - 1))
        base_slice = base[slice_idx, :, :]
        seg_slice = np.isin(seg[slice_idx, :, :], [LEVEL_LABELS.get(upper, -1), LEVEL_LABELS.get(lower, -1)])

        ax.imshow(base_slice, cmap="gray", origin="lower")
        if np.any(seg_slice):
            rgba = np.zeros((*seg_slice.shape, 4), dtype=np.float32)
            rgba[..., :3] = np.array([0.3, 0.8, 1.0])
            rgba[..., 3] = seg_slice.astype(np.float32) * 0.22
            ax.imshow(rgba, origin="lower")

        upper_pi = corners_by_level[upper].get("PI")
        lower_ps = corners_by_level[lower].get("PS")
        if upper_pi is not None and lower_ps is not None:
            _draw_line(ax, upper_pi, lower_ps, "#f8fafc", lw=2.4)
            _draw_point(ax, upper_pi, LEVEL_COLORS.get(upper, "#ffffff"))
            _draw_point(ax, lower_ps, LEVEL_COLORS.get(lower, "#ffffff"))

        direction = directions.get(pair, "-")
        slip_mm = slips.get(pair, float("nan"))
        ax.set_title(f"{pair} slip overlay ({direction}, {_fmt(slip_mm, 2)} mm)")
        ax.set_xlabel("SI axis (voxels)")
        ax.set_ylabel("AP axis (voxels)")

    plt.tight_layout()
    plt.show()


def main() -> None:
    _mount_drive_if_needed()

    step2_path = _resolve_step2_path()
    raw_path = _resolve_raw_mri_path()
    source_spacing = _read_source_spacing()

    ctx = load_context(step2_path, raw_path=raw_path, source_spacing_mm=source_spacing)
    report = run_all(ctx, enabled=ENABLED_COMPONENTS)

    _display_report(report, step2_path, ctx)
    print("\nGeometric overlays:")
    _show_geometric_overlays(report, ctx)


main()
