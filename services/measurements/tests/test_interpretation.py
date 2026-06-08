"""Tests for the Phase 4 interpretation container + catalog-driven status/severity.

status/severity/flag for catalogued measurements (e.g. SAC) now come from thresholds.py;
measurements not in the catalog fall back to the prior flag-only heuristic. The container
fields and the status vocabulary are unchanged.
"""

from __future__ import annotations

from services.interpretation import (
    build_interpreted_measurements,
    detect_syndromes,
    interpret_group5_contract,
)


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
            "status": "review_only",
            "severity": "reduced_heuristic",
            "flag": False,
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


def test_interpret_group5_contract_maps_fracture_and_myelomalacia():
    # Group 6 consumes the Group-5 findings contract
    # (services/measurements/group5/flags_contract.py JSON shape) and
    # interprets the compression-screen ratio + the myelomalacia screen via the catalog.
    contract = {
        "levels": [
            {
                "level": "C5",
                "fracture": {"ratio": 0.60, "Ha_mm": 6.0, "Hp_mm": 10.0},
                "myelomalacia": {"assessed": True, "present": True},
            },
            {
                "level": "C6",
                "fracture": {"ratio": 0.94, "Ha_mm": 9.4, "Hp_mm": 10.0},
                "myelomalacia": {"assessed": False, "present": None},
            },
        ]
    }
    rows = interpret_group5_contract(contract)
    by = {(r["measurement"], r["level"]): r for r in rows}

    assert by[("vb_hahp_ratio", "C5")]["status"] == "outside_reference"
    assert by[("vb_hahp_ratio", "C5")]["severity"] == "compression_screen_positive"
    assert by[("vb_hahp_ratio", "C5")]["flag"] is True
    assert by[("myelomalacia", "C5")]["status"] == "outside_reference"
    assert by[("myelomalacia", "C5")]["flag"] is True

    assert by[("vb_hahp_ratio", "C6")]["status"] == "within_reference"
    assert ("myelomalacia", "C6") not in by   # not assessed -> no row (surfaced via not_assessed)


def test_detect_myelopathy_syndrome_when_all_criteria_present():
    # Provisional rule (plan §4.3): canal narrowing + SAC high-risk + cord signal anomaly at the
    # same level. Advisory only, never a diagnosis. Exact combination rule pending Phase-4.
    rows = [
        {"measurement": "dural_sac_AP_min", "level": "C5", "flag": True},
        {"measurement": "SAC", "level": "C5", "flag": True},
        {"measurement": "myelomalacia", "level": "C5", "flag": True},
    ]
    syndromes = detect_syndromes(rows)
    myelo = [s for s in syndromes if s["syndrome"] == "possible_myelopathy" and s["level"] == "C5"]
    assert len(myelo) == 1
    assert myelo[0]["status"] == "review_only"      # advisory, not a diagnosis
    assert myelo[0]["provisional"] is True
    assert "clinical correlation" in myelo[0]["advisory"].lower()


def test_no_myelopathy_syndrome_when_a_criterion_is_missing():
    rows = [
        {"measurement": "dural_sac_AP_min", "level": "C5", "flag": True},
        {"measurement": "SAC", "level": "C5", "flag": False},     # SAC not high-risk
        {"measurement": "myelomalacia", "level": "C5", "flag": True},
    ]
    syndromes = detect_syndromes(rows)
    assert not any(s["syndrome"] == "possible_myelopathy" for s in syndromes)
