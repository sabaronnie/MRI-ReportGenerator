"""Phase 3A.5 - Disc AP width comparison + posterior bulge estimate."""

from __future__ import annotations

from typing import Any

import numpy as np

from ..context import ComponentResult, MeasurementContext, MeasurementError
from .cervical_body_morphometry import AP_AXIS, SAG_AXIS, SI_AXIS
from .disc_si_height import DISC_LABELS, DISC_TO_VERTS, VERT_LABELS, join_flags, measure_adjacent_body_slice
from ._vertebral_geometry import endplate_lines


NAME = "disc_ap_bulge"
DEPENDS_ON = ["disc_si_height"]


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
        posterior_bulge_mm, ref_line_length_mm = _posterior_bulge(
            disc_mask_2d, upper, lower, spacing_pa, spacing_si,
            seg=seg, slice_idx=slice_idx, upper_vb=upper_vb, lower_vb=lower_vb,
        )

        row_flags = []
        prior_flag_string = producer.intermediate["flags"].get(disc_name, "")
        if prior_flag_string:
            row_flags.extend([x for x in prior_flag_string.split(";") if x])
        if upper is None:
            row_flags.append("upper_vb_missing")
        if lower is None:
            row_flags.append("lower_vb_missing")

        reliable = "yes" if producer.intermediate["reliable"].get(disc_name, True) and not any(
            x.endswith("_missing") for x in row_flags
        ) else "no"

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
        flags["disc_bulge_present"][disc_name] = posterior_bulge_mm >= 2.0 or ratio >= 1.10
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


def _endplate_posterior_corner(seg, slice_idx, vb_label, which, spacing_pa, spacing_si):
    """Posterior VB corner (ap_mm, si_mm) from the validated endplate-LINE fit, or None.

    `which` is 'PI' (upper VB, posterior-inferior) or 'PS' (lower VB, posterior-superior).
    Canonical RAS: the VB body slice is seg[slice_idx] with axes (AP, SI), anterior=HIGH ap.
    """
    # vb_label arrives as a level NAME ("C4") from DISC_TO_VERTS; resolve to its TSS integer.
    label = VERT_LABELS.get(vb_label) if isinstance(vb_label, str) else vb_label
    if label is None:
        return None
    body_2d = seg[slice_idx] == label
    if int(body_2d.sum()) < 20:
        return None
    el = endplate_lines(body_2d, ap_axis=0, si_axis=1, ap_spacing=spacing_pa,
                        si_spacing=spacing_si, anterior="high")
    return el["corners"][which] if el is not None else None


def _posterior_bulge(disc_mask_2d: np.ndarray, upper, lower, spacing_pa: float, spacing_si: float,
                     seg=None, slice_idx=None, upper_vb=None, lower_vb=None) -> tuple[float, float]:
    # Reference chord = the two adjacent posterior VB corners (upper posterior-inferior ->
    # lower posterior-superior). Source the corners from the endplate-LINE fit, which is
    # reliable on concave/sloped cervical endplates; corner-extrema mis-place the posterior
    # corner too far anterior and inflate the apparent bulge (healthy read 2.93mm / 60%
    # over-flag, BACKWARDS vs unhealthy -- the endplate chord drops healthy to ~0, flush; J21b).
    # Fall back to the corner-extrema corners when the endplate fit is unmeasurable.
    ap0 = si0 = ap1 = si1 = None
    if seg is not None and slice_idx is not None:
        pu = _endplate_posterior_corner(seg, slice_idx, upper_vb, "PI", spacing_pa, spacing_si)
        pl = _endplate_posterior_corner(seg, slice_idx, lower_vb, "PS", spacing_pa, spacing_si)
        if pu is not None and pl is not None:
            ap0, si0 = pu
            ap1, si1 = pl
    if ap0 is None:
        if upper is None or lower is None:
            return 0.0, float("nan")
        upper_pi = upper.corners_voxel["PI"]
        lower_ps = lower.corners_voxel["PS"]
        ap0 = float(upper_pi[1]) * spacing_pa
        si0 = float(upper_pi[2]) * spacing_si
        ap1 = float(lower_ps[1]) * spacing_pa
        si1 = float(lower_ps[2]) * spacing_si

    ref_len = float(np.hypot(ap1 - ap0, si1 - si0))
    if ref_len == 0.0:
        return 0.0, 0.0

    coords = np.argwhere(disc_mask_2d)
    if len(coords) == 0:
        return 0.0, ref_len

    posterior_excess = []
    for ap_idx, si_idx in coords:
        ap_mm = float(ap_idx) * spacing_pa
        si_mm = float(si_idx) * spacing_si
        if si1 == si0:
            ap_ref = 0.5 * (ap0 + ap1)
        else:
            t = (si_mm - si0) / (si1 - si0)
            t = float(np.clip(t, 0.0, 1.0))
            ap_ref = ap0 + t * (ap1 - ap0)
        posterior_excess.append(max(0.0, ap_ref - ap_mm))

    return float(max(posterior_excess, default=0.0)), ref_len
