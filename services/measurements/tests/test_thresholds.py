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

from services.interpretation import classify


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


# ---- Disc bulge / grade / height index -------------------------------------------
# Disc bulge: reference line is the TILTED CHORD between adjacent posterior VB corners;
# our flat back-wall under-reports on lordotic necks (confirmed bug). >1 mm = bulge,
# >1.35 mm = cord-compression risk (Nakashima, PMID 25584950, AUC 0.87 -- MODERATE conf).
# Disc grade: Miyazaki 2008 cervical grading (PMID 18525490), NOT lumbar Pfirrmann;
# ratio->grade cut-points have no kappa/AUC -> research-grade heuristic, review-only.
# DHI: in-code <0.30 is DEBUNKED; no validated absolute cervical DHI cut -> review-only gap.


def test_disc_bulge_below_one_mm_is_no_bulge():
    r = classify("posterior_bulge_mm", 0.5)
    assert r.status == "within_reference"
    assert r.severity == "no_bulge"
    assert r.flag is False


def test_disc_bulge_one_to_135_is_bulge_present():
    r = classify("posterior_bulge_mm", 1.2)
    assert r.status == "outside_reference"
    assert r.severity == "bulge_present"
    assert r.flag is True


def test_disc_bulge_above_135_is_cord_risk_with_tilted_chord_caveat():
    r = classify("posterior_bulge_mm", 1.5)
    assert r.status == "outside_reference"
    assert r.severity == "cord_risk"
    assert r.flag is True
    assert "Nakashima" in r.citation
    assert "tilted chord" in r.caveat.lower()


def test_pfirrmann_grade_is_research_grade_review_only():
    r = classify("pfirrmann_grade", 4)
    assert r.status == "review_only"
    assert r.severity == "grade_IV"
    assert r.flag is False
    assert "Miyazaki" in r.citation


def test_dhi_has_no_validated_cut_and_is_review_only():
    r = classify("DHI", 0.25)
    assert r.status == "review_only"
    assert r.severity is None
    assert r.flag is False
    assert "debunked" in (r.citation + " " + (r.caveat or "")).lower()


# ---- Canal / cord / stenosis -----------------------------------------------------
# dural_sac_AP_min: SOFT-TISSUE dural sac via SCT, NOT osseous canal -> do not conflate
# with bony CT/radiograph thresholds. Bands >13/10-13/<10 mm are a provisional clinical
# convention pending Phase-4 MRI confirmation. cord_AP: normative comparison delegated to
# SCT -normalize-hc (Valosek 2024); no fixed cut. SAC <3 mm = high risk (radiograph-origin,
# verify). Torg <0.8 = developmental stenosis (radiograph-origin).


def test_dural_sac_above_13_is_normal():
    r = classify("dural_sac_AP_min", 14.0)
    assert r.status == "within_reference"
    assert r.severity == "normal"
    assert r.flag is False


def test_dural_sac_10_to_13_is_borderline():
    r = classify("dural_sac_AP_min", 11.5)
    assert r.status == "within_reference"
    assert r.severity == "borderline"
    assert r.flag is False


def test_dural_sac_below_10_flags_with_soft_tissue_caveat():
    r = classify("dural_sac_AP_min", 8.0)
    assert r.status == "outside_reference"
    assert r.flag is True
    assert "soft-tissue" in r.caveat.lower()


def test_cord_ap_is_delegated_to_sct_normalize_hc():
    r = classify("cord_AP", 7.0)
    assert r.status == "review_only"
    assert r.severity is None
    assert r.flag is False
    assert "PAM50" in r.citation


def test_sac_below_3mm_is_high_risk():
    r = classify("SAC", 2.5)
    assert r.status == "outside_reference"
    assert r.severity == "high_risk"
    assert r.flag is True
    assert "radiograph" in r.caveat.lower()


def test_sac_at_or_above_3mm_is_normal():
    r = classify("SAC", 4.0)
    assert r.status == "within_reference"
    assert r.severity == "normal"
    assert r.flag is False


def test_torg_below_08_flags_developmental_stenosis():
    r = classify("Torg_Pavlov_ratio", 0.7)
    assert r.status == "outside_reference"
    assert r.severity == "developmental_stenosis_screen"
    assert r.flag is True
    assert "Torg" in r.citation


# ---- Alignment (Cobb / lordosis class; segmental + posterior-tangent gaps) --------
# Cobb is C3-C7 SUPINE -> apply supine offset; endpoint precision not yet at target ->
# alignment is a descriptive class for review, not hard-flagged. Segmental-angle and
# posterior-tangent have no validated cervical per-level norm -> review-only gaps.


def test_cobb_lordotic_is_within_reference():
    r = classify("Cobb_C3_C7", 15.0)
    assert r.status == "within_reference"
    assert r.severity == "lordotic"
    assert r.flag is False
    assert "NASSJ" in r.citation
    assert "supine" in r.caveat.lower()


def test_cobb_straightened_is_review_only():
    r = classify("Cobb_C3_C7", 5.0)
    assert r.status == "review_only"
    assert r.severity == "straightened"
    assert r.flag is False


def test_cobb_kyphotic_is_review_only_not_hard_flagged():
    r = classify("Cobb_C3_C7", -5.0)
    assert r.status == "review_only"
    assert r.severity == "kyphotic"
    assert r.flag is False


def test_segmental_angle_is_a_pending_gap():
    r = classify("segmental_angle", 3.0)
    assert r.status == "review_only"
    assert r.severity is None
    assert r.flag is False
    assert "pending" in r.caveat.lower()


def test_posterior_tangent_is_a_pending_gap():
    r = classify("posterior_tangent_C3_C7", 2.0)
    assert r.status == "review_only"
    assert r.flag is False


# ---- Quality / caution metrics (NOT clinical) ------------------------------------
# Owner (Ronnie) confirmed: ap_width_outlier + tilt_outlier are geometry/segmentation
# caution flags, never stand-alone abnormalities -> tag="quality", never a clinical flag.


def test_ap_width_within_sanity_window_is_within_reference():
    r = classify("AP_width", 18.0)
    assert r.status == "within_reference"
    assert r.severity == "within_sanity"
    assert r.flag is False
    assert r.tag == "quality"


def test_ap_width_outlier_is_caution_not_a_clinical_flag():
    r = classify("AP_width", 25.0)
    assert r.severity == "ap_width_outlier"
    assert r.status == "review_only"
    assert r.flag is False          # quality caution, NOT a clinical abnormality
    assert r.tag == "quality"


def test_tilt_deg_is_quality_caution_not_interpretable_clinically():
    r = classify("tilt_deg", 28.0)
    assert r.status == "not_interpretable"
    assert r.flag is False
    assert r.tag == "quality"
    assert "caution" in r.caveat.lower()


# ---- Signal: myelomalacia screen (Group 5.1, SCIseg) -----------------------------


def test_myelomalacia_present_flags_for_review():
    r = classify("myelomalacia", 1)
    assert r.status == "outside_reference"
    assert r.severity == "signal_anomaly_present"
    assert r.flag is True
    assert "SCIseg" in r.citation


def test_myelomalacia_absent_is_within_reference():
    r = classify("myelomalacia", 0)
    assert r.status == "within_reference"
    assert r.severity == "none"
    assert r.flag is False
