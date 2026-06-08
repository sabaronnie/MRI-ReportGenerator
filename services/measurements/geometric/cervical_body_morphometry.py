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
from scipy.ndimage import zoom as ndi_zoom

from ..context import ComponentResult, MeasurementContext, MeasurementError
from ._vertebral_geometry import endplate_line_heights


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

# Sub-voxel boundary refinement: per-slice in-plane (AP/SI) upsample factor applied
# before locating landmarks. A linear upsample + 0.5 re-threshold places the body
# edge at the half-level crossing (~marching-squares) instead of on voxel centres,
# cutting the ±1 voxel quantisation on heights/widths/slip to ~spacing/factor.
# Only the in-plane axes are refined; the through-plane (slice) axis is left alone
# because it is the low-resolution direction (see context.resolution_quality).
# Set to 1 to disable and recover exact voxel-centre behaviour.
SUBVOXEL_FACTOR = 4

# Flags / soft sanity checks.
AP_WIDTH_LOW_MM = 12.0
AP_WIDTH_HIGH_MM = 22.0
# tilt_outlier is a SEGMENTATION/slice QUALITY flag (body PCA SI-axis vs global vertical),
# not a disease detector. The old 20 deg cut was a near-vertical (thoraco-lumbar) assumption:
# on the lordotic cervical spine, healthy mid/lower bodies are physiologically tilted ~28 deg
# from absolute vertical, so 20 deg flagged 88% of HEALTHY C3-C7 (Spine-Generic, n=60; J19).
# Recalibrated to the healthy distribution (median 27.9, mean 28.9 +/- 7.3, p99 42.5, max 43.5):
# 45 deg = mean + ~2.5SD -> 0% healthy false-flag with margin.
TILT_DEG_MAX = 45.0
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


def _refine_mask(
    mask_2d: np.ndarray,
    spacing_pa: float,
    spacing_si: float,
) -> tuple[np.ndarray, float, float, float]:
    """In-plane sub-voxel refinement of a 2D body mask.

    Linearly upsamples by SUBVOXEL_FACTOR in the cell (grid) convention and
    re-thresholds at 0.5, putting the boundary at the half-level crossing
    (equivalent to a marching-squares 0.5 contour along axis directions) rather
    than on voxel centres. Returns the refined mask, its per-voxel mm spacing,
    and the scale (refined voxels per original voxel) for converting landmark
    indices back to original-voxel coordinates.
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

    # Refine the in-plane boundary to sub-voxel before locating landmarks. The
    # min-pixel gate above runs on the original mask so its meaning is unchanged.
    refined, fine_pa, fine_si, scale = _refine_mask(body_mask_2d, spacing_pa, spacing_si)
    coords_vox = np.argwhere(refined).astype(np.float64)  # (N,2) -> (AP, SI) on refined grid
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
    # Map refined-grid indices back to original-voxel coordinates (cell-centre
    # convention). At scale==1 this is the identity, so factor=1 reproduces the
    # original integer voxel coordinates exactly (as floats).
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

    # Heights via the validated endplate-LINE fit, not corner extrema. Cervical endplates
    # are concave/sloped (Chen 2013), so single-corner AS/AI/PS/PI extrema misread the wall
    # heights -- on healthy necks they read anterior TALLER than posterior (Ha/Hp ~1.08) vs
    # the physiological ~0.94 (posterior > anterior wedge). The line fit (Wang 2023, ICC 0.97
    # vs 0.75) PCA-orients the body and reads the superior/inferior endplate gap at each wall
    # margin (J20). Runs on the sub-voxel-refined mask; falls back to corner heights if the
    # fit fails (degenerate/too-few-voxel slice). anterior = HIGH AP index in canonical RAS.
    el_h = endplate_line_heights(refined, ap_axis=0, si_axis=1, ap_spacing=fine_pa,
                                 si_spacing=fine_si, anterior="high")
    h_ant, h_mid, h_post = el_h["Ha"], el_h["Hm"], el_h["Hp"]
    if not (h_ant > 0 and h_post > 0):
        h_ant = _dist_mm(corners_mm["AS"], corners_mm["AI"])
        h_mid = _dist_mm(corners_mm["M_sup"], corners_mm["M_inf"])
        h_post = _dist_mm(corners_mm["PS"], corners_mm["PI"])

    return SliceMeasurement(
        level=level,
        slice_idx=int(slice_idx),
        AP_width=ap_only,
        H_anterior=h_ant,
        H_middle=h_mid,
        H_posterior=h_post,
        tilt_deg=tilt_deg,
        corners_mm=corners_mm,
        corners_voxel=corners_voxel,
        AP_only=ap_only,
        AP_si_mismatch=ap_si_mismatch,
    )
