"""Phase 3A.1 + 3A.2 — disc-anchored 6-point Genant pipeline.

Produces, per cervical vertebra, the four morphometric measurements:
    AP_width, H_anterior, H_middle, H_posterior  (mm)
plus the six PCA-projected corner pixels (intermediate state for downstream
components like 3A.3 spondylolisthesis, 3A.6 disc-height index, 3A.10 Cobb).

References: plans/phase-3a-geometric-measurements.md §3A.1 / §3A.2
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from ..context import ComponentResult, MeasurementContext, MeasurementError


NAME = "genant_6point"
DEPENDS_ON: list[str] = []

# TotalSpineSeg label map (cervical subset).
VERTEBRA_LABELS = {
    "C2": 12, "C3": 13, "C4": 14, "C5": 15, "C6": 16, "C7": 17,
}
# Adjacent disc above/below for each vertebra (None when out of cervical FOV).
DISC_NEIGHBOURS = {
    "C2": (None, 63),     # only C2-C3 disc below
    "C3": (63, 64),
    "C4": (64, 65),
    "C5": (65, 66),
    "C6": (66, 67),
    "C7": (67, 71),
}
CANAL_LABEL = 2

# Algorithm hyper-parameters (kept here so Phase 5 can sweep them later).
DISC_AP_MARGIN_MM = 2.0
CANAL_BAND_FRACTION = 0.70
EDGE_STRIP_FRACTION = 0.15
MIDLINE_SLAB_MM = 1.5

# Pathology flag thresholds (per Phase 3A plan).
AP_WIDTH_LOW_MM = 12.0
AP_WIDTH_HIGH_MM = 22.0
TILT_DEG_MAX = 20.0
WEDGE_RATIO = 0.70
BICONCAVE_RATIO = 0.70


@dataclass
class VertebraResult:
    level: str
    AP_width: float
    H_anterior: float
    H_middle: float
    H_posterior: float
    AP_superior: float
    AP_inferior: float
    tilt_deg: float
    sagittal_slice: int
    corners_mm: dict[str, tuple[float, float]]   # {AS, PS, AI, PI, M_sup, M_inf} → (SI, AP) mm
    corners_voxel: dict[str, tuple[int, int, int]]  # {…} → (LR, PA, IS) voxel index
    flags: dict[str, bool]


def compute(ctx: MeasurementContext, prior_results: dict[str, Any] | None = None) -> ComponentResult:
    """Run the joint 6-point Genant pipeline on every cervical vertebra present in ctx."""
    seg = ctx.seg_data
    spacing_pa = ctx.voxel_spacing_mm[1]
    spacing_is = ctx.voxel_spacing_mm[2]

    canal_3d = seg == CANAL_LABEL
    canal_per_slice = canal_3d.sum(axis=(1, 2))
    canal_peak = int(canal_per_slice.max())
    if canal_peak == 0:
        raise MeasurementError("Canal label (2) absent from segmentation — cannot pick midline band")
    midline_band = canal_per_slice >= CANAL_BAND_FRACTION * canal_peak

    per_vertebra: list[VertebraResult] = []
    for level, label in VERTEBRA_LABELS.items():
        if not (seg == label).any():
            continue
        try:
            per_vertebra.append(
                _run_one_vertebra(seg, level, label, midline_band, spacing_pa, spacing_is)
            )
        except MeasurementError as e:
            per_vertebra.append(_failed_result(level, str(e)))

    return _to_component_result(per_vertebra)


def _run_one_vertebra(
    seg: np.ndarray,
    level: str,
    label: int,
    midline_band: np.ndarray,
    spacing_pa: float,
    spacing_is: float,
) -> VertebraResult:
    body_3d = _isolate_body_3d(seg, label, level, spacing_pa)
    slice_idx = _select_slice(body_3d, midline_band)
    body_2d = body_3d[slice_idx]

    if body_2d.sum() < 25:
        raise MeasurementError(f"{level}: body 2D mask too small ({int(body_2d.sum())} pixels)")

    center_mm, si_axis, ap_axis = _pca_axes(body_2d, spacing_pa, spacing_is)
    si_proj, ap_proj, voxel_pa_is = _project(body_2d, center_mm, si_axis, ap_axis, spacing_pa, spacing_is)
    corner_idx = _extract_six_points(si_proj, ap_proj)

    corners_mm = {name: (float(si_proj[i]), float(ap_proj[i])) for name, i in corner_idx.items()}
    corners_voxel = {
        name: (int(slice_idx), int(voxel_pa_is[i, 0]), int(voxel_pa_is[i, 1]))
        for name, i in corner_idx.items()
    }

    AP_sup = _dist(corners_mm["AS"], corners_mm["PS"])
    AP_inf = _dist(corners_mm["AI"], corners_mm["PI"])
    AP_width = 0.5 * (AP_sup + AP_inf)
    H_anterior = _dist(corners_mm["AS"], corners_mm["AI"])
    H_middle = _dist(corners_mm["M_sup"], corners_mm["M_inf"])
    H_posterior = _dist(corners_mm["PS"], corners_mm["PI"])

    tilt = _tilt_degrees(si_axis)
    flags = {
        "ap_width_outlier": AP_width < AP_WIDTH_LOW_MM or AP_width > AP_WIDTH_HIGH_MM,
        "tilt_outlier": tilt > TILT_DEG_MAX,
        "wedge_fracture": H_anterior < WEDGE_RATIO * H_posterior,
        "biconcave_fracture": H_middle < BICONCAVE_RATIO * max(H_anterior, H_posterior),
    }

    return VertebraResult(
        level=level,
        AP_width=AP_width,
        H_anterior=H_anterior,
        H_middle=H_middle,
        H_posterior=H_posterior,
        AP_superior=AP_sup,
        AP_inferior=AP_inf,
        tilt_deg=tilt,
        sagittal_slice=int(slice_idx),
        corners_mm=corners_mm,
        corners_voxel=corners_voxel,
        flags=flags,
    )


def _isolate_body_3d(seg: np.ndarray, label: int, level: str, spacing_pa: float) -> np.ndarray:
    """Vertebra mask intersected with the AP-range of its adjacent discs (with a small margin)."""
    above_id, below_id = DISC_NEIGHBOURS[level]
    disc_ids = [d for d in (above_id, below_id) if d is not None]
    disc_mask = np.isin(seg, disc_ids)
    if not disc_mask.any():
        raise MeasurementError(f"{level}: adjacent discs {disc_ids} absent — cannot anchor body")

    pa_indices = np.where(disc_mask)[1]
    pa_lo = int(pa_indices.min())
    pa_hi = int(pa_indices.max())
    margin_vox = int(np.ceil(DISC_AP_MARGIN_MM / spacing_pa))
    pa_lo = max(0, pa_lo - margin_vox)
    pa_hi = min(seg.shape[1] - 1, pa_hi + margin_vox)

    vertebra_mask = seg == label
    pa_filter = np.zeros(seg.shape[1], dtype=bool)
    pa_filter[pa_lo:pa_hi + 1] = True
    return vertebra_mask & pa_filter[None, :, None]


def _select_slice(body_3d: np.ndarray, midline_band: np.ndarray) -> int:
    """Within the canal-defined midline band, pick the sagittal slice with the most body voxels."""
    body_per_slice = body_3d.sum(axis=(1, 2))
    masked = np.where(midline_band, body_per_slice, -1)
    if masked.max() <= 0:
        raise MeasurementError("no body voxels in canal-visible midline band")
    return int(np.argmax(masked))


def _pca_axes(
    body_2d: np.ndarray,
    spacing_pa: float,
    spacing_is: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """PCA in physical (mm) space. SI axis = eigenvector more aligned with global +IS."""
    coords_voxel = np.argwhere(body_2d)   # (N, 2) → (PA_idx, IS_idx)
    coords_mm = coords_voxel * np.array([spacing_pa, spacing_is])
    center_mm = coords_mm.mean(axis=0)
    centered = coords_mm - center_mm
    cov = (centered.T @ centered) / max(len(centered), 1)
    _, eigvecs = np.linalg.eigh(cov)
    e0, e1 = eigvecs[:, 0], eigvecs[:, 1]

    global_si = np.array([0.0, 1.0])  # +IS in (PA, IS) frame
    if abs(e1 @ global_si) >= abs(e0 @ global_si):
        si_axis, ap_axis = e1, e0
    else:
        si_axis, ap_axis = e0, e1
    if si_axis[1] < 0:
        si_axis = -si_axis
    if ap_axis[0] < 0:
        ap_axis = -ap_axis
    return center_mm, si_axis, ap_axis


def _project(
    body_2d: np.ndarray,
    center_mm: np.ndarray,
    si_axis: np.ndarray,
    ap_axis: np.ndarray,
    spacing_pa: float,
    spacing_is: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    coords_voxel = np.argwhere(body_2d)
    coords_mm = coords_voxel * np.array([spacing_pa, spacing_is])
    centered = coords_mm - center_mm
    si_proj = centered @ si_axis
    ap_proj = centered @ ap_axis
    return si_proj, ap_proj, coords_voxel


def _extract_six_points(si_proj: np.ndarray, ap_proj: np.ndarray) -> dict[str, int]:
    """Plan §3A.1 stage 4: edge-strip extrema with deterministic tie-breaks."""
    si_min, si_max = float(si_proj.min()), float(si_proj.max())
    si_range = si_max - si_min
    top_strip = si_proj >= si_max - EDGE_STRIP_FRACTION * si_range
    bot_strip = si_proj <= si_min + EDGE_STRIP_FRACTION * si_range
    if not top_strip.any() or not bot_strip.any():
        raise MeasurementError("edge strips empty — body too thin for 15%-fraction extraction")

    AS = _argbreak(top_strip, ap_proj, "max", si_proj, "max")  # anterior-superior
    PS = _argbreak(top_strip, ap_proj, "min", si_proj, "max")  # posterior-superior
    AI = _argbreak(bot_strip, ap_proj, "max", si_proj, "min")  # anterior-inferior
    PI = _argbreak(bot_strip, ap_proj, "min", si_proj, "min")  # posterior-inferior

    ap_mid = float(ap_proj.mean())
    slab_half = MIDLINE_SLAB_MM / 2.0
    in_slab = (ap_proj >= ap_mid - slab_half) & (ap_proj <= ap_mid + slab_half)
    if not in_slab.any():
        in_slab = (ap_proj >= ap_mid - 3.0) & (ap_proj <= ap_mid + 3.0)
    if not in_slab.any():
        raise MeasurementError("midline AP slab is empty")
    M_sup = _argbreak(in_slab, si_proj, "max", ap_proj, "max")
    M_inf = _argbreak(in_slab, si_proj, "min", ap_proj, "max")

    return {"AS": AS, "PS": PS, "AI": AI, "PI": PI, "M_sup": M_sup, "M_inf": M_inf}


def _argbreak(mask: np.ndarray, values: np.ndarray, mode: str, tiebreak: np.ndarray, tb_mode: str) -> int:
    """Argmax/argmin of `values` restricted to `mask`, with a deterministic tiebreak on `tiebreak`."""
    idx = np.where(mask)[0]
    sub = values[idx]
    target = sub.max() if mode == "max" else sub.min()
    candidates = idx[sub == target]
    tb_sub = tiebreak[candidates]
    pick = candidates[np.argmax(tb_sub) if tb_mode == "max" else np.argmin(tb_sub)]
    return int(pick)


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def _tilt_degrees(si_axis: np.ndarray) -> float:
    """Angle between PCA SI axis and global +IS, in degrees."""
    cos_theta = abs(float(si_axis @ np.array([0.0, 1.0])))
    cos_theta = max(0.0, min(1.0, cos_theta))
    return float(np.degrees(np.arccos(cos_theta)))


def _failed_result(level: str, reason: str) -> VertebraResult:
    nan = float("nan")
    return VertebraResult(
        level=level,
        AP_width=nan, H_anterior=nan, H_middle=nan, H_posterior=nan,
        AP_superior=nan, AP_inferior=nan, tilt_deg=nan,
        sagittal_slice=-1,
        corners_mm={},
        corners_voxel={},
        flags={"failed": True, "reason": reason},  # type: ignore[dict-item]
    )


def _to_component_result(per_vertebra: list[VertebraResult]) -> ComponentResult:
    measurements: dict[str, dict[str, float]] = {
        k: {} for k in ("AP_width", "H_anterior", "H_middle", "H_posterior",
                        "AP_superior", "AP_inferior", "tilt_deg")
    }
    flags: dict[str, dict[str, bool]] = {
        k: {} for k in ("ap_width_outlier", "tilt_outlier", "wedge_fracture", "biconcave_fracture")
    }
    intermediate: dict[str, Any] = {"corners_mm": {}, "corners_voxel": {}, "sagittal_slice": {}}

    for v in per_vertebra:
        for key in measurements:
            measurements[key][v.level] = getattr(v, key)
        for fkey in flags:
            if fkey in v.flags:
                flags[fkey][v.level] = bool(v.flags[fkey])
        intermediate["corners_mm"][v.level] = v.corners_mm
        intermediate["corners_voxel"][v.level] = v.corners_voxel
        intermediate["sagittal_slice"][v.level] = v.sagittal_slice

    return ComponentResult(
        measurements=measurements,
        intermediate=intermediate,
        flags=flags,
        metadata={"levels": [v.level for v in per_vertebra]},
    )
