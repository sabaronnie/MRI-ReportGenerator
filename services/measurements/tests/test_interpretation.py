"""Tests for the Phase 4 interpretation container + catalog-driven status/severity.

status/severity/flag for catalogued measurements (e.g. SAC) now come from thresholds.py;
measurements not in the catalog fall back to the prior flag-only heuristic. The container
fields and the status vocabulary are unchanged.
"""

from __future__ import annotations

from services.measurements.interpretation import build_interpreted_measurements


def test_builds_simplified_interpretation_container():
    report = {
        "components": {
            "sac": {
                "status": "ok",
                "duration_s": 0.01,
                "metadata": {
                    "measurement_name": "SAC",
                    "sac_caveat": "Derived metric; confirm with segmentation QC.",
                },
            }
        },
        "measurements": {
            "SAC": {
                "C5": 2.7,
                "C6": 4.5,
            }
        },
        "flags": {
            "sac_high_risk": {
                "C5": True,
                "C6": False,
            },
            "sac_slice_misaligned": {
                "C5": True,
                "C6": False,
            },
        },
    }

    rows = build_interpreted_measurements(
        report,
        measurement_sources={"SAC": "sac"},
        flag_sources={
            "sac_high_risk": "sac",
            "sac_slice_misaligned": "sac",
        },
    )

    assert rows == [
        {
            "measurement": "SAC",
            "level": "C5",
            "value": 2.7,
            "unit": "mm",
            "status": "outside_reference",
            "severity": "high_risk",
            "flag": True,
            "demographics_used": {},
            "quality_flags": ["sac_slice_misaligned"],
            "caveat": "Derived metric; confirm with segmentation QC.",
        },
        {
            "measurement": "SAC",
            "level": "C6",
            "value": 4.5,
            "unit": "mm",
            "status": "within_reference",
            "severity": "normal",
            "flag": False,
            "demographics_used": {},
            "quality_flags": [],
            "caveat": "Derived metric; confirm with segmentation QC.",
        },
    ]


def test_quality_caution_flags_are_not_treated_as_pathology():
    # tilt_outlier / ap_width_outlier are geometry/segmentation CAUTION flags (owner-confirmed),
    # not stand-alone abnormalities. H_anterior is not catalogued, so the row falls back to the
    # flag heuristic; with only quality flags present it must NOT read as outside_reference.
    report = {
        "components": {"morph": {"metadata": {}}},
        "measurements": {"H_anterior": {"C5": 11.0}},
        "flags": {
            "tilt_outlier": {"C5": True},
            "ap_width_outlier": {"C5": True},
        },
    }
    rows = build_interpreted_measurements(
        report,
        measurement_sources={"H_anterior": "morph"},
        flag_sources={"tilt_outlier": "morph", "ap_width_outlier": "morph"},
    )
    row = rows[0]
    assert "tilt_outlier" in row["quality_flags"]
    assert "ap_width_outlier" in row["quality_flags"]
    assert row["status"] != "outside_reference"
    assert row["flag"] is False
