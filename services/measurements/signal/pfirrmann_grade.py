"""Experimental disc signal grading from raw T2 intensities."""

from __future__ import annotations

from typing import Any

import numpy as np

from ..context import ComponentResult, MeasurementContext, MeasurementError
from ..geometric.disc_si_height import DISC_LABELS, join_flags


NAME = "pfirrmann_grade"
DEPENDS_ON = ["disc_si_height", "disc_height_index"]


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

        grade, label = _grade_disc(
            nucleus_norm=features["nucleus_norm"],
            na_contrast_norm=features["na_contrast_norm"],
            heterogeneity=features["heterogeneity"],
            height_ratio=height_ratio,
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
            "region": "cervical",
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
) -> tuple[int, str]:
    if np.isfinite(height_ratio):
        if nucleus_norm >= 0.38 and na_contrast_norm >= 0.15 and heterogeneity <= 0.55 and height_ratio >= 0.18:
            return 1, "I (normal)"
        if nucleus_norm >= 0.25 and height_ratio >= 0.12:
            return 2, "II"
        if nucleus_norm >= 0.15 and height_ratio >= 0.08:
            return 3, "III"
        if height_ratio > 0.04:
            return 4, "IV"
        return 5, "V"

    if nucleus_norm >= 0.38 and na_contrast_norm >= 0.15 and heterogeneity <= 0.55:
        return 1, "I (normal)"
    if nucleus_norm >= 0.25:
        return 2, "II"
    if nucleus_norm >= 0.15:
        return 3, "III"
    return 4, "IV"
