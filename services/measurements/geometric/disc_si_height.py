"""Phase 3A.4 - Disc SI height with shared disc geometry helpers.

This reconstruction is based on the surviving plan docs and output artifacts
(`out_2_1_*`, `out_2_2_*`, `out_2_3_*`, `out_2_4_*`) after the untracked
working files were removed by `git clean -fd`.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..context import ComponentResult, MeasurementContext, MeasurementError
from .cervical_body_morphometry import (
    AP_AXIS,
    AP_WIDTH_TRIM_PCT,
    CANAL_LABELS,
    DISC_AP_MARGIN_MM,
    SAG_AXIS,
    SI_AXIS,
    _argbreak,
    _dist_mm,
    _largest_connected_component,
    _measure_body_slice,
)


NAME = "disc_si_height"
DEPENDS_ON: list[str] = []

DISC_LABELS = {
    "C2-C3": 63,
    "C3-C4": 64,
    "C4-C5": 65,
    "C5-C6": 66,
    "C6-C7": 67,
    "C7-T1": 71,
    "T1-T2": 72,
    "T2-T3": 73,
    "T3-T4": 74,
}

VERT_LABELS = {
    "C1": 11,
    "C2": 12,
    "C3": 13,
    "C4": 14,
    "C5": 15,
    "C6": 16,
    "C7": 17,
    "T1": 21,
    "T2": 22,
    "T3": 23,
    "T4": 24,
}

DISC_TO_VERTS = {
    "C2-C3": ("C2", "C3"),
    "C3-C4": ("C3", "C4"),
    "C4-C5": ("C4", "C5"),
    "C5-C6": ("C5", "C6"),
    "C6-C7": ("C6", "C7"),
    "C7-T1": ("C7", "T1"),
    "T1-T2": ("T1", "T2"),
    "T2-T3": ("T2", "T3"),
    "T3-T4": ("T3", "T4"),
}

CANAL_BAND_FRACTION = 0.70
EDGE_STRIP_FRACTION = 0.20
MID_AP_SLAB_MM = 1.5
MID_SI_SLAB_MM = 1.5
MIN_DISC_PIXELS_2D = 9
AP_WIDTH_PLAUSIBLE_MAX_MM = 25.0   # cervical disc AP above this is a measurement artifact


def compute(ctx: MeasurementContext, prior_results: dict[str, Any] | None = None) -> ComponentResult:
    seg = ctx.seg_data
    spacing_pa = float(ctx.voxel_spacing_mm[AP_AXIS])
    spacing_si = float(ctx.voxel_spacing_mm[SI_AXIS])

    canal_3d = np.isin(seg, CANAL_LABELS)
    canal_per_slice = canal_3d.sum(axis=(AP_AXIS, SI_AXIS))
    peak = int(canal_per_slice.max())
    if peak <= 0:
        raise MeasurementError("Canal labels absent from segmentation; cannot select midline disc slices")
    midline_band = canal_per_slice >= CANAL_BAND_FRACTION * peak

    rows: list[dict[str, Any]] = []
    for disc_name, disc_label in DISC_LABELS.items():
        if not (seg == disc_label).any():
            continue
        row = _measure_disc(seg, disc_name, disc_label, midline_band, spacing_pa, spacing_si)
        rows.append(row)

    if not rows:
        raise MeasurementError("No disc measurements could be produced from the segmentation")

    measurements = {
        "disc_H_anterior": {},
        "disc_H_middle": {},
        "disc_H_posterior": {},
        "disc_H_mean": {},
        "disc_H_center": {},
        "disc_AP_width": {},
    }
    intermediate: dict[str, Any] = {
        "slice_index": {},
        "corners_voxel": {},
        "ap_bounds_voxel": {},
        "si_bounds_voxel": {},
        "flags": {},
        "reliable": {},
        "disc_label": {},
    }
    flags = {
        "disc_measurement_unreliable": {},
        "disc_special_case_c2c3": {},
    }

    for row in rows:
        level = row["disc_name"]
        measurements["disc_H_anterior"][level] = row["h_anterior_mm"]
        measurements["disc_H_middle"][level] = row["h_middle_mm"]
        measurements["disc_H_posterior"][level] = row["h_posterior_mm"]
        measurements["disc_H_mean"][level] = row["h_mean_mm"]
        measurements["disc_H_center"][level] = row["h_center_mm"]
        measurements["disc_AP_width"][level] = row["ap_width_mm"]

        intermediate["slice_index"][level] = row["slice_index"]
        intermediate["corners_voxel"][level] = {
            "AS": tuple(row["AS_jk"]),
            "AI": tuple(row["AI_jk"]),
            "PS": tuple(row["PS_jk"]),
            "PI": tuple(row["PI_jk"]),
        }
        intermediate["ap_bounds_voxel"][level] = tuple(row["ap_bounds_voxel"])
        intermediate["si_bounds_voxel"][level] = tuple(row["si_bounds_voxel"])
        intermediate["flags"][level] = row["flags"]
        intermediate["reliable"][level] = row["reliable"] == "yes"
        intermediate["disc_label"][level] = row["disc_label"]

        flags["disc_measurement_unreliable"][level] = row["reliable"] != "yes"
        flags["disc_special_case_c2c3"][level] = "c2c3_dens" in row["flags"]

    return ComponentResult(
        measurements=measurements,
        intermediate=intermediate,
        flags=flags,
        metadata={
            "levels": [row["disc_name"] for row in rows],
            "rows": rows,
            "method": "per-disc midsagittal slice + PCA 4-corner / centerline geometry",
        },
    )


def _measure_disc(
    seg: np.ndarray,
    disc_name: str,
    disc_label: int,
    midline_band: np.ndarray,
    spacing_pa: float,
    spacing_si: float,
) -> dict[str, Any]:
    disc_3d = seg == disc_label
    slice_idx = select_midline_slice(disc_3d, midline_band)
    disc_2d = _largest_connected_component(disc_3d[slice_idx, :, :])
    measured = measure_disc_slice(disc_2d, slice_idx, spacing_pa, spacing_si)
    if measured is None:
        raise MeasurementError(f"{disc_name}: disc slice measurement failed")

    flags = []
    upper_vb, lower_vb = DISC_TO_VERTS[disc_name]
    if disc_name == "C2-C3":
        flags.append("c2c3_dens")
    if upper_vb and vertebra_touches_fov_edge(seg, upper_vb):
        flags.append("upper_vb_fov_edge")
    if lower_vb and vertebra_touches_fov_edge(seg, lower_vb):
        flags.append("lower_vb_fov_edge")
    # Plausibility guard: a cervical disc AP wider than this is a measurement artifact
    # (a tilted PCA axis or osteophyte spread), not real anatomy -> flag, don't trust it.
    if measured["ap_width_mm"] > AP_WIDTH_PLAUSIBLE_MAX_MM:
        flags.append("ap_width_implausible")

    reliable = "no" if flags else "yes"
    return {
        "disc_label": disc_label,
        "disc_name": disc_name,
        "slice_index": int(slice_idx),
        "AS_jk": list(measured["corners_voxel"]["AS"]),
        "AI_jk": list(measured["corners_voxel"]["AI"]),
        "PS_jk": list(measured["corners_voxel"]["PS"]),
        "PI_jk": list(measured["corners_voxel"]["PI"]),
        "h_anterior_mm": round(measured["h_anterior_mm"], 3),
        "h_middle_mm": round(measured["h_middle_mm"], 3),
        "h_posterior_mm": round(measured["h_posterior_mm"], 3),
        "h_mean_mm": round(measured["h_mean_mm"], 3),
        "h_center_mm": round(measured["h_center_mm"], 3),
        "ap_width_mm": round(measured["ap_width_mm"], 3),
        "ap_bounds_voxel": list(measured["ap_bounds_voxel"]),
        "si_bounds_voxel": list(measured["si_bounds_voxel"]),
        "flags": join_flags(flags),
        "reliable": reliable,
    }


def select_midline_slice(mask_3d: np.ndarray, midline_band: np.ndarray) -> int:
    areas = mask_3d.sum(axis=(AP_AXIS, SI_AXIS))
    masked = np.where(midline_band, areas, -1)
    if masked.max() > 0:
        return int(np.argmax(masked))
    return int(np.argmax(areas))


def measure_disc_slice(
    disc_mask_2d: np.ndarray,
    slice_idx: int,
    spacing_pa: float,
    spacing_si: float,
) -> dict[str, Any] | None:
    disc_mask_2d = _largest_connected_component(disc_mask_2d)
    if int(disc_mask_2d.sum()) < MIN_DISC_PIXELS_2D:
        return None

    coords_vox = np.argwhere(disc_mask_2d).astype(np.float64)  # (AP, SI)
    coords_mm = coords_vox * np.array([spacing_pa, spacing_si])
    center_mm = coords_mm.mean(axis=0)
    centered = coords_mm - center_mm

    cov = np.cov(centered.T)
    _, eigvecs = np.linalg.eigh(cov)
    e0, e1 = eigvecs[:, 0], eigvecs[:, 1]
    global_ap = np.array([1.0, 0.0])
    global_si = np.array([0.0, 1.0])

    if abs(np.dot(e0, global_ap)) >= abs(np.dot(e1, global_ap)):
        ap_axis = e0
        si_axis = e1
    else:
        ap_axis = e1
        si_axis = e0
    if ap_axis[0] < 0:
        ap_axis = -ap_axis
    if si_axis[1] < 0:
        si_axis = -si_axis

    ap_proj = centered @ ap_axis
    si_proj = centered @ si_axis
    ap_min, ap_max = float(ap_proj.min()), float(ap_proj.max())
    si_min, si_max = float(si_proj.min()), float(si_proj.max())
    ap_range = ap_max - ap_min
    si_range = si_max - si_min
    if ap_range <= 0 or si_range <= 0:
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
    ap_half_slab = max(MID_AP_SLAB_MM / 2.0, 0.08 * ap_range)
    in_mid_ap = np.abs(ap_proj - ap_mid) <= ap_half_slab
    if in_mid_ap.sum() < 3:
        in_mid_ap = np.abs(ap_proj - ap_mid) <= 2.0 * ap_half_slab
    if in_mid_ap.sum() < 3:
        return None
    M_sup = _argbreak(in_mid_ap, si_proj, "max", ap_proj, "max")
    M_inf = _argbreak(in_mid_ap, si_proj, "min", ap_proj, "max")

    si_mid = 0.5 * (si_min + si_max)
    si_half_slab = max(MID_SI_SLAB_MM / 2.0, 0.08 * si_range)
    in_mid_si = np.abs(si_proj - si_mid) <= si_half_slab
    if in_mid_si.sum() < 3:
        in_mid_si = np.abs(si_proj - si_mid) <= 2.0 * si_half_slab
    if in_mid_si.sum() < 3:
        return None
    A_mid = _argbreak(in_mid_si, ap_proj, "max", -np.abs(si_proj - si_mid), "max")
    P_mid = _argbreak(in_mid_si, ap_proj, "min", -np.abs(si_proj - si_mid), "max")

    proj_points = {
        "AS": (float(si_proj[AS]), float(ap_proj[AS])),
        "AI": (float(si_proj[AI]), float(ap_proj[AI])),
        "PS": (float(si_proj[PS]), float(ap_proj[PS])),
        "PI": (float(si_proj[PI]), float(ap_proj[PI])),
        "M_sup": (float(si_proj[M_sup]), float(ap_proj[M_sup])),
        "M_inf": (float(si_proj[M_inf]), float(ap_proj[M_inf])),
        "A_mid": (float(si_proj[A_mid]), float(ap_proj[A_mid])),
        "P_mid": (float(si_proj[P_mid]), float(ap_proj[P_mid])),
    }
    corners_voxel = {
        "AS": (int(coords_vox[AS, 0]), int(coords_vox[AS, 1])),
        "AI": (int(coords_vox[AI, 0]), int(coords_vox[AI, 1])),
        "PS": (int(coords_vox[PS, 0]), int(coords_vox[PS, 1])),
        "PI": (int(coords_vox[PI, 0]), int(coords_vox[PI, 1])),
    }

    ap_idx = coords_vox[:, 0]
    si_idx = coords_vox[:, 1]
    ap_center = 0.5 * (ap_idx.min() + ap_idx.max())
    center_band = np.abs(ap_idx - ap_center) <= 0.5
    if center_band.sum() < 2:
        center_band = np.abs(ap_idx - ap_center) <= 1.5
    if center_band.any():
        h_center_mm = (si_idx[center_band].max() - si_idx[center_band].min()) * spacing_si
    else:
        h_center_mm = _dist_mm(proj_points["M_sup"], proj_points["M_inf"])

    # Robust anterior/posterior heights: SI extent of the disc within an anterior or
    # posterior AP-column band (in the tilt-corrected PCA frame). This is bounded by the
    # disc's true SI extent in that column, so a ragged posterior margin voxel near the
    # canal cannot inflate it (single-corner _dist_mm produced 10-14 mm cervical discs and
    # a near-random anterior/posterior wedge). Falls back to the corner distance if a band
    # is too sparse.
    h_anterior_mm = _band_si_extent(
        ap_proj, si_proj, ap_max - AP_COLUMN_FRACTION * ap_range, ap_max,
        fallback=_dist_mm(proj_points["AS"], proj_points["AI"]),
    )
    h_posterior_mm = _band_si_extent(
        ap_proj, si_proj, ap_min, ap_min + AP_COLUMN_FRACTION * ap_range,
        fallback=_dist_mm(proj_points["PS"], proj_points["PI"]),
    )
    h_middle_mm = _dist_mm(proj_points["M_sup"], proj_points["M_inf"])

    # AP width at mid-height, trimmed to reject single-voxel anterior/posterior spikes.
    in_mid_si_local = np.abs(si_proj - si_mid) <= si_half_slab
    if in_mid_si_local.sum() >= 4:
        ap_in_mid = ap_proj[in_mid_si_local]
        ap_width_mm = float(np.percentile(ap_in_mid, 100 - AP_WIDTH_TRIM_PCT)
                            - np.percentile(ap_in_mid, AP_WIDTH_TRIM_PCT))
    else:
        ap_width_mm = abs(proj_points["A_mid"][1] - proj_points["P_mid"][1])

    return {
        "slice_index": int(slice_idx),
        "corners_voxel": corners_voxel,
        "h_anterior_mm": h_anterior_mm,
        "h_middle_mm": h_middle_mm,
        "h_posterior_mm": h_posterior_mm,
        "h_mean_mm": float(np.mean([h_anterior_mm, h_middle_mm, h_posterior_mm])),
        "h_center_mm": float(h_center_mm),
        "ap_width_mm": ap_width_mm,
        "ap_bounds_voxel": (int(ap_idx.min()), int(ap_idx.max())),
        "si_bounds_voxel": (int(si_idx.min()), int(si_idx.max())),
    }


# Anterior/posterior heights are sampled in the outer ~22% AP column at each margin.
# Narrow bands sit on the true anterior/posterior disc edges where the cervical lordotic
# wedge (anterior taller than posterior) is expressed; wider bands average toward the
# parallel-sided centre and wash the wedge out.
AP_COLUMN_FRACTION = 0.22


def _band_si_extent(ap_proj, si_proj, ap_lo: float, ap_hi: float, fallback: float) -> float:
    """SI extent (mm) of the disc within an AP-projection band [ap_lo, ap_hi]."""
    band = (ap_proj >= ap_lo) & (ap_proj <= ap_hi)
    if band.sum() < 2:
        return float(fallback)
    return float(si_proj[band].max() - si_proj[band].min())


def vertebra_touches_fov_edge(seg: np.ndarray, vert_name: str) -> bool:
    label = VERT_LABELS.get(vert_name)
    if label is None:
        return False
    mask = seg == label
    if not mask.any():
        return True
    si = np.where(mask)[SI_AXIS]
    return int(si.min()) == 0 or int(si.max()) == seg.shape[SI_AXIS] - 1


def extract_vertebral_body_slice(
    seg: np.ndarray,
    vert_name: str,
    slice_idx: int,
    disc_ap_bounds: tuple[int, int],
    spacing_pa: float,
) -> np.ndarray | None:
    label = VERT_LABELS.get(vert_name)
    if label is None or not (seg[slice_idx, :, :] == label).any():
        return None

    full = seg[slice_idx, :, :] == label
    margin_vox = int(np.ceil(DISC_AP_MARGIN_MM / spacing_pa))
    lo = max(0, int(disc_ap_bounds[0]) - margin_vox)
    hi = min(full.shape[0] - 1, int(disc_ap_bounds[1]) + margin_vox)

    trimmed = full.copy()
    trimmed[:lo, :] = False
    trimmed[hi + 1 :, :] = False
    if trimmed.any():
        return _largest_connected_component(trimmed)
    return _largest_connected_component(full)


def measure_adjacent_body_slice(
    seg: np.ndarray,
    vert_name: str,
    slice_idx: int,
    disc_ap_bounds: tuple[int, int],
    spacing_pa: float,
    spacing_si: float,
):
    mask = extract_vertebral_body_slice(seg, vert_name, slice_idx, disc_ap_bounds, spacing_pa)
    if mask is None or not mask.any():
        return None
    return _measure_body_slice(vert_name, mask, slice_idx, spacing_pa, spacing_si)


def join_flags(flags: list[str]) -> str:
    return ";".join(flag for flag in flags if flag)
