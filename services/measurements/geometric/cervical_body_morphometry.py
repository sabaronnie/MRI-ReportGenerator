"""Phase 3A.1 + 3A.2 — validated-style cervical vertebral body morphometry.

This component is the primary producer for cervical vertebral body measurements:
    AP_width, H_anterior, H_middle, H_posterior, tilt_deg

Method summary:
- canonical-RAS geometry from MeasurementContext
- 3D disc-anchored body isolation to exclude posterior elements
- canal-visible midline-band slice selection
- optional averaging across best slice ± 1
- Genant-style 3-point heights
- SHIP-style mid-body AP width

References:
- Genant HK et al. J Bone Miner Res. 1993. PMID: 8237484
- Nell C et al. PLoS One. 2019. doi:10.1371/journal.pone.0222682
- Huang J et al. Spine J. 2020. doi:10.1016/j.spinee.2019.11.010
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.ndimage import label as cc_label

from ..context import ComponentResult, MeasurementContext, MeasurementError


NAME = "cervical_body_morphometry"
DEPENDS_ON: list[str] = []

# TotalSpineSeg label map (cervical subset used in the project).
LEVEL_LABELS = {"C3": 13, "C4": 14, "C5": 15, "C6": 16, "C7": 17}
DISC_NEIGHBOURS = {
    "C3": (63, 64),
    "C4": (64, 65),
    "C5": (65, 66),
    "C6": (66, 67),
    "C7": (67, 71),
}
CANAL_LABELS = (1, 2)

# Hyper-parameters chosen to stay close to the validated-style Colab method.
DISC_AP_MARGIN_MM = 2.0
CANAL_BAND_FRACTION = 0.70
EDGE_STRIP_FRACTION = 0.15
MID_AP_SLAB_MM = 1.5
MID_SI_SLAB_MM = 1.5
MULTI_SLICE_OFFSETS = (-1, 0, 1)
MIN_BODY_PIXELS_2D = 25

# AP width is read as a trimmed extent (drop the outer AP_WIDTH_TRIM_PCT% of voxels at
# each end of the mid-SI band) instead of the single most anterior/posterior voxel. This
# rejects lone segmentation spikes that inflated AP width to anatomically impossible values
# (cervical bodies/discs reading 26-27 mm). Disc and vertebral-body AP use the SAME trim so
# their ratio stays method-consistent. The trim is mild (2.5%) so it removes spikes without
# systematically under-reading a clean rectangular body.
AP_WIDTH_TRIM_PCT = 2.5

# Flags / soft sanity checks.
AP_WIDTH_LOW_MM = 12.0
AP_WIDTH_HIGH_MM = 22.0
TILT_DEG_MAX = 20.0
WEDGE_RATIO = 0.70
BICONCAVE_RATIO = 0.70

# canonical-RAS axes from MeasurementContext.load_context()
SAG_AXIS = 0
AP_AXIS = 1
SI_AXIS = 2


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


def compute(ctx: MeasurementContext, prior_results: dict[str, Any] | None = None) -> ComponentResult:
    seg = ctx.seg_data
    spacing_pa = float(ctx.voxel_spacing_mm[AP_AXIS])
    spacing_si = float(ctx.voxel_spacing_mm[SI_AXIS])

    canal_3d = np.isin(seg, CANAL_LABELS)
    canal_per_slice = canal_3d.sum(axis=(AP_AXIS, SI_AXIS))
    canal_peak = int(canal_per_slice.max())
    if canal_peak == 0:
        raise MeasurementError("Canal labels (1/2) absent from segmentation — cannot select midline band")
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

        flags["ap_width_outlier"][level] = row["AP_width"] < AP_WIDTH_LOW_MM or row["AP_width"] > AP_WIDTH_HIGH_MM
        flags["tilt_outlier"][level] = row["tilt_deg"] > TILT_DEG_MAX
        flags["wedge_fracture"][level] = row["H_anterior"] < WEDGE_RATIO * row["H_posterior"]
        flags["biconcave_fracture"][level] = row["H_middle"] < BICONCAVE_RATIO * max(row["H_anterior"], row["H_posterior"])

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

    coords_vox = np.argwhere(body_mask_2d).astype(np.float64)  # (N,2) -> (AP, SI)
    coords_mm = coords_vox * np.array([spacing_pa, spacing_si])

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

    # Prefer points closest to the true SI center so off-center slices do not
    # inflate the measured AP span.
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
        name: (int(slice_idx), int(coords_vox[i, 0]), int(coords_vox[i, 1]))
        for name, i in point_idx.items()
    }

    tilt_deg = float(np.degrees(np.arccos(np.clip(abs(np.dot(si_axis, global_si)), 0.0, 1.0))))
    ap_in_mid = ap_proj[in_mid_si_slab]
    if ap_in_mid.size >= 4:
        ap_only = float(np.percentile(ap_in_mid, 100 - AP_WIDTH_TRIM_PCT)
                        - np.percentile(ap_in_mid, AP_WIDTH_TRIM_PCT))
    else:
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
