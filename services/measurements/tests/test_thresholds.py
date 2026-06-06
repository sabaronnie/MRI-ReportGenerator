"""Tests for the central cited-threshold catalog (Phase 4 / Group 6).

The catalog (`thresholds.py`) is the single home for every measurement's normative
range, severity bands, flag thresholds, citation, and modality caveat — provenance
lives here, not scattered per interpretation row (plans/phase-4-interpretation.md §4.1).

These first tests cover the vertebral-body Ha/Hp compression screen, the one threshold
we validated ourselves (Spine-Generic healthy cohort Ha/Hp 0.94 ± 0.13, n=60 C3-C7;
flag at mean - 2*SD ~ 0.68; borderline at mean - 1*SD ~ 0.81). Citations are the locked
strings carried by group5/flags_contract.py (Tan 2004 / Lee 2012 / Kaur 2025 / Chen 2013
/ Nell 2019). See memory vb_hahp_norm_verified / vb_hahp_z_threshold.
"""

from __future__ import annotations

from services.measurements.thresholds import classify


def test_vb_hahp_normal_is_within_reference():
    r = classify("vb_hahp_ratio", 0.94)
    assert r.status == "within_reference"
    assert r.severity == "normal"
    assert r.flag is False
    assert "Tan 2004" in r.citation
    assert "compression" in r.caveat.lower()


def test_vb_hahp_borderline_is_within_reference_but_labelled():
    # mean - 1*SD = 0.81 down to mean - 2*SD = 0.68: low-normal, surfaced but not flagged
    r = classify("vb_hahp_ratio", 0.75)
    assert r.status == "within_reference"
    assert r.severity == "borderline"
    assert r.flag is False


def test_vb_hahp_below_minus_two_sd_flags_outside_reference():
    r = classify("vb_hahp_ratio", 0.60)
    assert r.status == "outside_reference"
    assert r.severity == "compression_screen_positive"
    assert r.flag is True


# ---- Spondylolisthesis slip (spondy_slip_mm) -------------------------------------
# No supine-MRI presence threshold exists; >=2 mm is an upright-radiograph borrow
# (conservative, but under-sensitive supine). de Dios cervical-MRI MDC = 1.5 mm, so the
# 1-2 mm band is within measurement noise. See memory
# cervical_spondylolisthesis_threshold_verified.


def test_slip_below_one_mm_is_neutral_within_reference():
    r = classify("spondy_slip_mm", 0.5)
    assert r.status == "within_reference"
    assert r.severity == "neutral"
    assert r.flag is False


def test_slip_one_to_two_mm_is_borderline_not_flagged():
    r = classify("spondy_slip_mm", 1.5)
    assert r.status == "within_reference"
    assert r.severity == "borderline"
    assert r.flag is False


def test_slip_at_or_above_two_mm_flags_with_supine_caveat():
    r = classify("spondy_slip_mm", 3.0)
    assert r.status == "outside_reference"
    assert r.severity == "slip_present_screen"
    assert r.flag is True
    assert "de Dios" in r.citation
    assert "supine" in r.caveat.lower()
