"""Phase 3A.6 - Disc Height Index (derived)."""

from __future__ import annotations

from typing import Any

import numpy as np

from ..context import ComponentResult, MeasurementContext, MeasurementError
from .cervical_body_morphometry import AP_AXIS, SI_AXIS
from .disc_si_height import DISC_LABELS, DISC_TO_VERTS, join_flags, measure_adjacent_body_slice


NAME = "disc_height_index"
DEPENDS_ON = ["disc_si_height"]


def compute(ctx: MeasurementContext, prior_results: dict[str, Any]) -> ComponentResult:
    producer = prior_results.get("disc_si_height")
    if producer is None:
        raise MeasurementError("disc_height_index requires `disc_si_height` in prior_results")

    seg = ctx.seg_data
    spacing_pa = float(ctx.voxel_spacing_mm[AP_AXIS])
    spacing_si = float(ctx.voxel_spacing_mm[SI_AXIS])

    rows: list[dict[str, Any]] = []
    measurements = {
        "DHI": {},
        "DHI_anterior": {},
        "DHI_posterior": {},
    }
    flags = {
        "reduced_dhi": {},
        "disc_height_index_unreliable": {},
    }
    intermediate = {
        "h_upperVB_middle_mm": {},
        "h_lowerVB_middle_mm": {},
    }

    levels = producer.metadata.get("levels", [])
    for disc_name in levels:
        disc_label = DISC_LABELS[disc_name]
        slice_idx = int(producer.intermediate["slice_index"][disc_name])
        disc_ap_bounds = tuple(producer.intermediate["ap_bounds_voxel"][disc_name])
        upper_vb, lower_vb = DISC_TO_VERTS[disc_name]

        upper = measure_adjacent_body_slice(seg, upper_vb, slice_idx, disc_ap_bounds, spacing_pa, spacing_si) if upper_vb else None
        lower = measure_adjacent_body_slice(seg, lower_vb, slice_idx, disc_ap_bounds, spacing_pa, spacing_si) if lower_vb else None
        middle_heights = [m.H_middle for m in (upper, lower) if m is not None]
        if not middle_heights:
            continue

        denom = float(np.mean(middle_heights))
        h_ant = float(producer.measurements["disc_H_anterior"][disc_name])
        h_mid = float(producer.measurements["disc_H_middle"][disc_name])
        h_post = float(producer.measurements["disc_H_posterior"][disc_name])

        row_flags = []
        prior_flag_string = producer.intermediate["flags"].get(disc_name, "")
        if prior_flag_string:
            row_flags.extend([x for x in prior_flag_string.split(";") if x])
        if upper is None:
            row_flags.append("upper_vb_truncated")
        if lower is None:
            row_flags.append("lower_vb_truncated")

        reliable = "yes" if producer.intermediate["reliable"].get(disc_name, True) and len(middle_heights) == 2 else "no"
        rows.append(
            {
                "disc_label": disc_label,
                "disc_name": disc_name,
                "slice_index": slice_idx,
                "upper_vb": upper_vb,
                "lower_vb": lower_vb,
                "h_disc_anterior_mm": round(h_ant, 3),
                "h_disc_middle_mm": round(h_mid, 3),
                "h_disc_posterior_mm": round(h_post, 3),
                "h_upperVB_middle_mm": round(float(upper.H_middle) if upper is not None else float("nan"), 3),
                "h_lowerVB_middle_mm": round(float(lower.H_middle) if lower is not None else float("nan"), 3),
                "DHI": round(h_mid / denom, 4) if denom > 0 else None,
                "DHI_anterior": round(h_ant / denom, 4) if denom > 0 else None,
                "DHI_posterior": round(h_post / denom, 4) if denom > 0 else None,
                "flags": join_flags(row_flags),
                "reliable": reliable,
            }
        )

        measurements["DHI"][disc_name] = h_mid / denom
        measurements["DHI_anterior"][disc_name] = h_ant / denom
        measurements["DHI_posterior"][disc_name] = h_post / denom
        flags["disc_height_index_unreliable"][disc_name] = reliable != "yes"
        intermediate["h_upperVB_middle_mm"][disc_name] = float(upper.H_middle) if upper is not None else float("nan")
        intermediate["h_lowerVB_middle_mm"][disc_name] = float(lower.H_middle) if lower is not None else float("nan")

    if not rows:
        raise MeasurementError("disc_height_index could not evaluate any discs")

    # Reduced disc height = a RELATIVE >30% drop vs the patient's OWN cross-level median DHI
    # (Suzuki 2018). The absolute DHI<0.30 cut is debunked (uncited animal/lumbar borrow; research
    # handoff A.7 / disc_height_dhi_norms). Per-patient relative is ratio/scanner-robust and cut
    # healthy false-firing 77%->3% in validation (J17).
    dhi_vals = [v for v in measurements["DHI"].values() if v == v]
    ref_dhi = float(np.median(dhi_vals)) if dhi_vals else 0.0
    for disc_name, dhi in measurements["DHI"].items():
        flags["reduced_dhi"][disc_name] = bool(ref_dhi > 0 and dhi < 0.70 * ref_dhi)

    return ComponentResult(
        measurements=measurements,
        intermediate=intermediate,
        flags=flags,
        metadata={
            "levels": [row["disc_name"] for row in rows],
            "rows": rows,
            "method": "disc middle height divided by mean adjacent vertebral middle height",
        },
    )
