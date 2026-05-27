"""Experimental disc signal grading from raw T2 intensities."""

from __future__ import annotations

from typing import Any

import numpy as np

from ..context import ComponentResult, MeasurementContext, MeasurementError
from ..geometric.disc_si_height import DISC_LABELS, join_flags


NAME = "pfirrmann_grade"
DEPENDS_ON = ["disc_si_height", "disc_height_index"]

# Region-specific cut-points on `nucleus_norm` = (nucleus - dark)/(csf - dark),
# a scale/offset-robust hydration proxy in ~[0, 1] (brighter, wetter nucleus -> higher).
# Order: (grade_I_min, grade_II_min, grade_III_min, grade_IV_min); below grade_IV_min -> V.
#
# cervical: CALIBRATED to the Duke C-spine T2 intensity scale (10-scan cohort).
#   The grade ladder is recentered onto the observed nucleus_norm distribution so that
#   a well-hydrated young disc (scan 000001, nucleus_norm 0.35-0.63) reads grade I and
#   only genuinely dry discs (nucleus_norm < ~0.10) read IV. This shifts the *threshold
#   placement* to match the dataset's intensity range; it preserves the disc-to-disc
#   ordering and does not invent disc health. Still heuristic (no cervical ground truth).
# lumbar: GROUND-TRUTH calibrated against SPIDER radiologist Pfirrmann (see LAST_RUN.md).
NORM_CUTS = {
    "cervical": (0.30, 0.18, 0.095, 0.04),
    "lumbar": (0.454, 0.272, 0.150, 0.066),
}

# Optional auto-calibration override. colab/auto_calibrate.py writes refitted cut-points
# here when the Pfirrmann grade distribution drifts out of range on new data; if the file
# is absent or invalid the baked-in NORM_CUTS above are used. Loaded once at import (the
# calibrator re-runs measurement in a fresh process, so it always reads the latest file).
import json as _json  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

CALIBRATION_PATH = _Path(__file__).resolve().parents[1] / "calibration.json"


def _active_cuts() -> dict:
    cuts = {k: tuple(v) for k, v in NORM_CUTS.items()}
    try:
        if CALIBRATION_PATH.is_file():
            data = _json.loads(CALIBRATION_PATH.read_text())
            for region, c in data.get("pfirrmann_norm_cuts", {}).items():
                if isinstance(c, (list, tuple)) and len(c) == 4:
                    cuts[region] = tuple(float(x) for x in c)
    except Exception:  # noqa: BLE001 - never let a bad cal file break measurement
        pass
    return cuts


ACTIVE_CUTS = _active_cuts()


def _region_for(disc_name: str) -> str:
    """Map a disc level to the cut-point regime. Upper-thoracic discs in a C-spine
    FOV share the cervical T2 scale, so they use the cervical cuts."""
    if disc_name.startswith("L") or disc_name == "L5-S1":
        return "lumbar"
    return "cervical"


def compute(ctx: MeasurementContext, prior_results: dict[str, Any]) -> ComponentResult:
    if ctx.raw_data is None:
        raise MeasurementError("pfirrmann_grade requires raw MRI data in MeasurementContext.raw_data")

    disc_geom = prior_results.get("disc_si_height")
    if disc_geom is None:
        raise MeasurementError("pfirrmann_grade requires `disc_si_height` in prior_results")

    dhi_result = prior_results.get("disc_height_index")

    seg = ctx.seg_data
    raw = ctx.raw_data
    csf_mask = seg == 2
    if not csf_mask.any():
        raise MeasurementError("pfirrmann_grade requires spinal canal / CSF label 2 for normalization")

    csf_reference = float(np.percentile(raw[csf_mask], 95))
    dark_reference = float(np.percentile(raw[raw > 0], 5)) if np.any(raw > 0) else float(np.percentile(raw, 5))

    rows: list[dict[str, Any]] = []
    measurements = {
        "pfirrmann_grade": {},
        "nucleus_csf_ratio": {},
        "nucleus_norm": {},
        "heterogeneity": {},
        "na_contrast_norm": {},
    }
    flags = {
        "experimental_disc_signal_classifier": {},
        "pfirrmann_unreliable": {},
    }
    metadata = {
        "pfirrmann_label": {},
        "levels": [],
        "rows": rows,
        "experimental": True,
    }

    for disc_name in disc_geom.metadata.get("levels", []):
        disc_label = DISC_LABELS[disc_name]
        slice_idx = int(disc_geom.intermediate["slice_index"][disc_name])
        disc_mask_2d = seg[slice_idx, :, :] == disc_label
        raw_2d = raw[slice_idx, :, :]
        if not disc_mask_2d.any():
            continue

        features = _disc_signal_features(raw_2d, disc_mask_2d, csf_reference, dark_reference)
        height_ratio = float("nan")
        if dhi_result is not None and disc_name in dhi_result.measurements.get("DHI", {}):
            height_ratio = float(dhi_result.measurements["DHI"][disc_name])

        region = _region_for(disc_name)
        grade, label = _grade_disc(
            nucleus_norm=features["nucleus_norm"],
            na_contrast_norm=features["na_contrast_norm"],
            heterogeneity=features["heterogeneity"],
            height_ratio=height_ratio,
            region=region,
        )

        row_flags = []
        prior_flag_string = disc_geom.intermediate["flags"].get(disc_name, "")
        if prior_flag_string:
            row_flags.extend([x for x in prior_flag_string.split(";") if x])
        reliable = "yes" if disc_geom.intermediate["reliable"].get(disc_name, True) else "no"

        row = {
            "disc_label": disc_label,
            "disc_name": disc_name,
            "slice_index": slice_idx,
            "region": region,
            "intensity_mean": round(features["intensity_mean"], 2),
            "intensity_std": round(features["intensity_std"], 2),
            "nucleus_intensity": round(features["nucleus_intensity"], 2),
            "csf_reference": round(csf_reference, 2),
            "dark_reference": round(dark_reference, 2),
            "nucleus_csf_ratio": round(features["nucleus_csf_ratio"], 3),
            "nucleus_norm": round(features["nucleus_norm"], 3),
            "heterogeneity": round(features["heterogeneity"], 3),
            "na_contrast_norm": round(features["na_contrast_norm"], 3),
            "height_ratio": round(height_ratio, 3) if np.isfinite(height_ratio) else None,
            "pfirrmann_grade": grade,
            "pfirrmann_label": label,
            "experimental": "yes",
            "flags": join_flags(row_flags),
            "reliable": reliable,
        }
        rows.append(row)
        metadata["pfirrmann_label"][disc_name] = label
        metadata["levels"].append(disc_name)

        measurements["pfirrmann_grade"][disc_name] = float(grade)
        measurements["nucleus_csf_ratio"][disc_name] = float(features["nucleus_csf_ratio"])
        measurements["nucleus_norm"][disc_name] = float(features["nucleus_norm"])
        measurements["heterogeneity"][disc_name] = float(features["heterogeneity"])
        measurements["na_contrast_norm"][disc_name] = float(features["na_contrast_norm"])
        flags["experimental_disc_signal_classifier"][disc_name] = True
        flags["pfirrmann_unreliable"][disc_name] = reliable != "yes"

    if not rows:
        raise MeasurementError("pfirrmann_grade could not evaluate any discs")

    return ComponentResult(
        measurements=measurements,
        intermediate={},
        flags=flags,
        metadata=metadata,
    )


def _disc_signal_features(
    raw_2d: np.ndarray,
    disc_mask_2d: np.ndarray,
    csf_reference: float,
    dark_reference: float,
) -> dict[str, float]:
    intens = raw_2d[disc_mask_2d].astype(np.float64)
    intensity_mean = float(np.mean(intens))
    intensity_std = float(np.std(intens))

    coords = np.argwhere(disc_mask_2d)
    ap = coords[:, 0].astype(np.float64)
    si = coords[:, 1].astype(np.float64)
    ap_mid = 0.5 * (ap.min() + ap.max())
    si_mid = 0.5 * (si.min() + si.max())
    ap_half = max(1.0, 0.25 * (ap.max() - ap.min()))
    si_half = max(1.0, 0.25 * (si.max() - si.min()))
    nucleus_sel = (np.abs(ap - ap_mid) <= ap_half) & (np.abs(si - si_mid) <= si_half)
    if nucleus_sel.sum() < 4:
        ap_half = max(1.0, 0.35 * (ap.max() - ap.min()))
        si_half = max(1.0, 0.35 * (si.max() - si.min()))
        nucleus_sel = (np.abs(ap - ap_mid) <= ap_half) & (np.abs(si - si_mid) <= si_half)

    nucleus_vals = raw_2d[coords[nucleus_sel, 0], coords[nucleus_sel, 1]].astype(np.float64)
    if len(nucleus_vals) == 0:
        nucleus_vals = intens
    bright_core = nucleus_vals[nucleus_vals >= np.percentile(nucleus_vals, 50)]
    nucleus_intensity = float(np.mean(bright_core if len(bright_core) else nucleus_vals))

    annulus_mask = ~nucleus_sel
    annulus_vals = raw_2d[coords[annulus_mask, 0], coords[annulus_mask, 1]].astype(np.float64)
    annulus_mean = float(np.mean(annulus_vals)) if len(annulus_vals) else intensity_mean

    denom = max(csf_reference - dark_reference, 1e-6)
    nucleus_csf_ratio = nucleus_intensity / max(csf_reference, 1e-6)
    nucleus_norm = (nucleus_intensity - dark_reference) / denom
    heterogeneity = intensity_std / max(intensity_mean, 1e-6)
    na_contrast_norm = max(0.0, nucleus_intensity - annulus_mean) / denom

    return {
        "intensity_mean": intensity_mean,
        "intensity_std": intensity_std,
        "nucleus_intensity": nucleus_intensity,
        "nucleus_csf_ratio": nucleus_csf_ratio,
        "nucleus_norm": nucleus_norm,
        "heterogeneity": heterogeneity,
        "na_contrast_norm": na_contrast_norm,
    }


def _grade_disc(
    nucleus_norm: float,
    na_contrast_norm: float,
    heterogeneity: float,
    height_ratio: float,
    region: str = "cervical",
) -> tuple[int, str]:
    """Ordinal Pfirrmann-style grade from the hydration signal, with a structural
    grade-V gate on disc-space collapse.

    The grade ladder is driven by `nucleus_norm` against region-calibrated cut-points
    (`NORM_CUTS`). Grade I additionally requires a clear nucleus-annulus contrast and
    low heterogeneity (homogeneous bright nucleus). Grade V is reserved for a collapsed
    disc space (low DHI) so that signal darkness alone caps at IV — see LAST_RUN.md.
    """
    c1, c2, c3, c4 = ACTIVE_CUTS.get(region, ACTIVE_CUTS["cervical"])

    # Structural collapse (very thin disc) -> V, regardless of signal.
    if np.isfinite(height_ratio) and height_ratio < 0.12:
        return 5, "V"

    if nucleus_norm >= c1 and na_contrast_norm >= 0.12 and heterogeneity <= 0.60:
        return 1, "I (normal)"
    if nucleus_norm >= c2:
        return 2, "II"
    if nucleus_norm >= c3:
        return 3, "III"
    if nucleus_norm >= c4:
        return 4, "IV"
    return 5, "V"
