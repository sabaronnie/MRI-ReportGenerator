"""Phase 3A.5 - Disc AP width comparison + posterior bulge estimate."""

from __future__ import annotations

from typing import Any

import numpy as np

from ..context import ComponentResult, MeasurementContext, MeasurementError
from .cervical_body_morphometry import AP_AXIS, SI_AXIS
from .disc_si_height import (
    DISC_LABELS,
    DISC_TO_VERTS,
    extract_vertebral_body_slice,
    join_flags,
    measure_adjacent_body_slice,
)


NAME = "disc_ap_bulge"
DEPENDS_ON = ["disc_si_height"]

# Plausibility guards for the disc/VB AP ratio. On some scans the adjacent vertebral-body
# AP width is under-measured (the PCA mid-SI body method can read a clipped body ~10-11 mm
# instead of its true ~15-18 mm), which inflates the ratio to 1.4-1.8 and fakes a bulge.
# A cervical body floor and a ratio ceiling catch this so the disc is flagged, not trusted.
VB_AP_FLOOR_MM = 10.5          # no real cervical body AP is this small -> measurement failed
RATIO_IMPLAUSIBLE = 1.30       # disc/VB ratios above this are far likelier a VB mis-measure
                               # (a small-but-CONSISTENT body, ratio ~1.0, stays reliable)


def compute(ctx: MeasurementContext, prior_results: dict[str, Any]) -> ComponentResult:
    producer = prior_results.get("disc_si_height")
    if producer is None:
        raise MeasurementError("disc_ap_bulge requires `disc_si_height` in prior_results")

    seg = ctx.seg_data
    spacing_pa = float(ctx.voxel_spacing_mm[AP_AXIS])
    spacing_si = float(ctx.voxel_spacing_mm[SI_AXIS])

    rows: list[dict[str, Any]] = []
    measurements = {
        "disc_vb_ap_ratio": {},
        "posterior_bulge_mm": {},
        "vb_ap_width_ref": {},
    }
    flags = {
        "disc_bulge_present": {},
        "disc_ap_unreliable": {},
    }

    levels = producer.metadata.get("levels", [])
    for disc_name in levels:
        disc_label = DISC_LABELS[disc_name]
        slice_idx = int(producer.intermediate["slice_index"][disc_name])
        disc_ap_width = float(producer.measurements["disc_AP_width"][disc_name])
        disc_ap_bounds = tuple(producer.intermediate["ap_bounds_voxel"][disc_name])
        upper_vb, lower_vb = DISC_TO_VERTS[disc_name]

        upper = measure_adjacent_body_slice(seg, upper_vb, slice_idx, disc_ap_bounds, spacing_pa, spacing_si) if upper_vb else None
        lower = measure_adjacent_body_slice(seg, lower_vb, slice_idx, disc_ap_bounds, spacing_pa, spacing_si) if lower_vb else None
        vb_widths = [m.AP_width for m in (upper, lower) if m is not None]
        if not vb_widths:
            continue

        vb_ref = float(np.mean(vb_widths))
        ratio = disc_ap_width / vb_ref if vb_ref > 0 else float("nan")

        disc_mask_2d = seg[slice_idx, :, :] == disc_label
        upper_body = extract_vertebral_body_slice(seg, upper_vb, slice_idx, disc_ap_bounds, spacing_pa) if upper_vb else None
        lower_body = extract_vertebral_body_slice(seg, lower_vb, slice_idx, disc_ap_bounds, spacing_pa) if lower_vb else None
        posterior_bulge_mm, ref_line_length_mm = _posterior_bulge(
            disc_mask_2d, upper_body, lower_body, spacing_pa, spacing_si
        )

        row_flags = []
        prior_flag_string = producer.intermediate["flags"].get(disc_name, "")
        if prior_flag_string:
            row_flags.extend([x for x in prior_flag_string.split(";") if x])
        if upper is None:
            row_flags.append("upper_vb_missing")
        if lower is None:
            row_flags.append("lower_vb_missing")
        # Guard against an under-measured vertebral body faking a wide-disc ratio / bulge.
        vb_ap_implausible = vb_ref < VB_AP_FLOOR_MM or (np.isfinite(ratio) and ratio > RATIO_IMPLAUSIBLE)
        if vb_ap_implausible:
            row_flags.append("vb_ap_implausible")

        reliable = "yes" if producer.intermediate["reliable"].get(disc_name, True) and not any(
            x.endswith("_missing") for x in row_flags
        ) and not vb_ap_implausible else "no"

        rows.append(
            {
                "disc_label": disc_label,
                "disc_name": disc_name,
                "slice_index": slice_idx,
                "upper_vb": upper_vb,
                "lower_vb": lower_vb,
                "ap_width_mm": round(disc_ap_width, 3),
                "vb_ap_width_mm": round(vb_ref, 3),
                "disc_vb_ap_ratio": round(ratio, 3),
                "posterior_bulge_mm": round(posterior_bulge_mm, 3),
                "ref_line_length_mm": round(ref_line_length_mm, 3),
                "flags": join_flags(row_flags),
                "reliable": reliable,
            }
        )

        measurements["disc_vb_ap_ratio"][disc_name] = float(ratio)
        measurements["posterior_bulge_mm"][disc_name] = float(posterior_bulge_mm)
        measurements["vb_ap_width_ref"][disc_name] = float(vb_ref)
        flags["disc_bulge_present"][disc_name] = (
            not vb_ap_implausible and (posterior_bulge_mm >= 2.0 or ratio >= 1.10)
        )
        flags["disc_ap_unreliable"][disc_name] = reliable != "yes"

    if not rows:
        raise MeasurementError("disc_ap_bulge could not evaluate any discs")

    return ComponentResult(
        measurements=measurements,
        intermediate={},
        flags=flags,
        metadata={
            "levels": [row["disc_name"] for row in rows],
            "rows": rows,
            "method": "disc AP width versus adjacent vertebral AP width + posterior contour excursion",
        },
    )


# Posterior-bulge estimator referenced to the adjacent vertebral posterior wall.
# A disc bulge is posterior protrusion of the disc margin beyond the posterior cortex of
# the neighbouring vertebral bodies. The earlier single-corner reference line failed
# because body isolation can pull ONE vertebral posterior corner ~12-20 mm anterior
# (over-clipping toward the canal), tilting the upper->lower chord ~80 deg off vertical
# and faking 10+ mm bulges. Empirically the disc posterior and the more-posterior
# vertebral wall agree within ~2 mm, so we:
#   1. take each vertebra's posterior edge as the MEDIAN over the band of rows nearest
#      the disc (robust to a single bad corner), and
#   2. use the MORE-POSTERIOR (smaller AP) of the two as a near-vertical wall, which
#      rejects whichever anchor was spuriously pulled anterior.
# Protrusion is then read per SI row and reduced with a high percentile.
BULGE_CONTOUR_PERCENTILE = 90
VB_ANCHOR_BAND_FRACTION = 0.35


def _vb_posterior_anchor(body_mask: np.ndarray, which: str) -> float | None:
    """Median posterior-edge AP (voxels) over the band of `body_mask` rows nearest the
    disc. `which` = 'inferior' for the upper vertebra, 'superior' for the lower."""
    if body_mask is None:
        return None
    coords = np.argwhere(body_mask)             # (ap_idx, si_idx)
    if len(coords) == 0:
        return None
    si = coords[:, 1]
    s_min, s_max = int(si.min()), int(si.max())
    span = max(1, s_max - s_min)
    if which == "inferior":
        sel = si <= s_min + VB_ANCHOR_BAND_FRACTION * span
    else:
        sel = si >= s_max - VB_ANCHOR_BAND_FRACTION * span
    band = coords[sel]
    if len(band) == 0:
        return None
    post_ap: dict[int, float] = {}
    for ap_i, si_i in band:
        s = int(si_i)
        if ap_i < post_ap.get(s, np.inf):       # posterior = smaller AP
            post_ap[s] = float(ap_i)
    return float(np.median(list(post_ap.values())))


def _posterior_bulge(disc_mask_2d: np.ndarray, upper_body, lower_body, spacing_pa: float, spacing_si: float) -> tuple[float, float]:
    a_up = _vb_posterior_anchor(upper_body, "inferior")
    a_lo = _vb_posterior_anchor(lower_body, "superior")
    if a_up is None or a_lo is None:
        return 0.0, float("nan")

    ref_ap = min(a_up, a_lo)                     # more-posterior wall = reliable anchor
    wall_offset_mm = abs(a_up - a_lo) * spacing_pa

    coords = np.argwhere(disc_mask_2d)
    if len(coords) == 0:
        return 0.0, wall_offset_mm
    post_ap: dict[int, float] = {}
    for ap_i, si_i in coords:
        s = int(si_i)
        if ap_i < post_ap.get(s, np.inf):
            post_ap[s] = float(ap_i)
    if not post_ap:
        return 0.0, wall_offset_mm

    # Protrusion = how far the disc posterior margin extends posterior to the wall.
    excursions = [max(0.0, (ref_ap - dpost) * spacing_pa) for dpost in post_ap.values()]
    bulge = float(np.percentile(excursions, BULGE_CONTOUR_PERCENTILE))
    return bulge, wall_offset_mm
