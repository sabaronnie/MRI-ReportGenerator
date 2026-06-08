"""Central cited-threshold catalog (Phase 4 / Group 6 interpretation).

This is the single home for every measurement's normative range, severity bands,
flag threshold(s), citation, and modality caveat. Interpretation (interpretation.py)
calls `classify(key, value)` and attaches the result; provenance lives HERE, not
scattered per row (plans/phase-4-interpretation.md §4.1).

Policy (plans/phase-4-threshold-research-list.txt §7.3 — team decision):
  - `status` is standardized: within_reference / outside_reference / review_only /
    not_interpretable.
  - `severity` is per-measurement (different measurements need different vocabularies:
    binary, mild/moderate/severe, grade-based, or review-only). So each ThresholdSpec
    carries its own severity-band labels.

Medical-AI honesty rules (CLAUDE.md):
  - Cite every clinical number (PMID/DOI). Citation strings are the LOCKED strings from
    the verified-research memories (search agents hallucinated some author names on real
    PMIDs — do not re-derive; copy verbatim).
  - Where no cited threshold exists, the spec says so explicitly (citation=None, a
    `NOT FOUND / pending Phase-4` note) and `classify` returns review_only — we never
    invent a number.
  - Every band/flag is a finding "for physician review", never a diagnosis.
"""

from __future__ import annotations

from dataclasses import dataclass


# ---- status vocabulary (standardized; §7.3) --------------------------------------
STATUS_WITHIN = "within_reference"
STATUS_OUTSIDE = "outside_reference"
STATUS_REVIEW = "review_only"
STATUS_NOT_INTERPRETABLE = "not_interpretable"

# A band's `reference` says how the value compares to the normative reference; it maps
# to a status and drives the boolean clinical flag.
_REFERENCE_TO_STATUS = {
    "within": STATUS_WITHIN,
    "outside": STATUS_OUTSIDE,
    "review": STATUS_REVIEW,
}


@dataclass(frozen=True)
class Band:
    """One severity band in measurement units. [lo, hi): lo inclusive, hi exclusive;
    None means open (-inf / +inf). `label` is the per-measurement severity label;
    `reference` in {within, outside, review} drives status + the clinical flag."""

    label: str
    lo: float | None
    hi: float | None
    reference: str

    def contains(self, value: float) -> bool:
        return (self.lo is None or value >= self.lo) and (self.hi is None or value < self.hi)


@dataclass(frozen=True)
class ThresholdSpec:
    """Everything Group 6 needs to interpret one measurement output key."""

    key: str
    clinical_name: str
    unit: str
    tag: str                       # "raw" | "derived" | "quality"
    bands: tuple[Band, ...] | None  # None -> no cited threshold (review_only)
    citation: str | None
    modality_caveat: str | None
    demographic: str | None = None
    provenance_note: str | None = None
    unknown_status: str = STATUS_REVIEW   # status when bands is None or no band matches


@dataclass(frozen=True)
class ThresholdEval:
    """Result of interpreting one measurement value against the catalog."""

    measurement: str
    value: float
    unit: str
    status: str
    severity: str | None
    flag: bool
    citation: str | None
    caveat: str | None
    tag: str


# ---- the catalog -----------------------------------------------------------------
# Vertebral-body Ha/Hp compression screen (derived from H_anterior / H_posterior).
# This REPLACES the in-code 70%-wedge rule with our cohort-calibrated cervical screen:
# healthy Ha/Hp 0.94 ± 0.13 (Spine-Generic, n=60 C3-C7, 12 subjects, 3 vendors);
# flag at mean - 2*SD (~0.68), borderline at mean - 1*SD (~0.81). The medical Genant
# grade stays separate (it is the unchanged 20/25/40% standard, handled per vertebra).
# See memory vb_hahp_norm_verified / vb_hahp_z_threshold; mirrors
# services/measurements/group5/flags_contract.py.
_VB_HAHP_MEAN = 0.94
_VB_HAHP_SD = 0.13
_VB_HAHP_FLAG_CUT = round(_VB_HAHP_MEAN - 2 * _VB_HAHP_SD, 2)       # 0.68
_VB_HAHP_BORDERLINE_CUT = round(_VB_HAHP_MEAN - 1 * _VB_HAHP_SD, 2)  # 0.81

_VB_HAHP_CITATION = (
    "Tan 2004 (Eur Spine J, PMC3476578); Lee 2012 (PMC3393857); Kaur 2025 (J Human Anat); "
    "Chen 2013 (PLoS One, PMC3859485); Nell 2019 (PMC6764695)"
)
_VB_HAHP_CAVEAT = (
    "Vertebral-body compression/deformity screen, NOT a general fracture detector "
    "(no power on non-compression fractures: odontoid/facet/posterior arch). Per-vertebra "
    "SD wide (~0.13) -> reliable at the group/screening level, coarse per body. Norm is "
    "triangulated (no like-for-like healthy cervical MRI Ha/Hp comparator) -> plausibility, "
    "not proof. Finding flagged for physician review; clinical correlation required."
)


# Spondylolisthesis slip (spondy_slip_mm). No supine-MRI presence threshold exists;
# >=2 mm is borrowed from upright radiographs -- conservative but under-sensitive on
# supine MRI. de Dios cervical-MRI MDC = 1.5 mm (the 1-2 mm band is within noise);
# White 3.5 mm = radiographic INSTABILITY, not presence. See memory
# cervical_spondylolisthesis_threshold_verified.
_SLIP_NEUTRAL_CUT = 1.0   # current code NEUTRAL_THRESHOLD_MM
_SLIP_PRESENT_CUT = 2.0   # current code SPONDY_PRESENT_THRESHOLD_MM
_SLIP_CITATION = (
    "Murakami 2020 (PMID 32591548); Murata 2019 (PMID 30899028); de Dios 2023 "
    "(cervical-MRI slip, MDC 1.5 mm); White 1975 (PMID 1132209, 3.5 mm = instability)"
)
_SLIP_CAVEAT = (
    "No supine-MRI presence threshold exists; >=2 mm is an upright-radiograph borrow -- "
    "conservative but UNDER-SENSITIVE supine (~38% of slips missed; Alvarez 2022, "
    "PMID 35276718). de Dios cervical-MRI MDC = 1.5 mm, so the 1-2 mm band is within "
    "measurement noise. White 3.5 mm = radiographic instability, not presence. Supine MRI "
    "under-measures functional slip. Finding for physician review; clinical correlation required."
)


# Disc bulge (posterior_bulge_mm). >1 mm = bulge, >1.35 mm = cord-compression risk
# (Nakashima, PMID 25584950, AUC 0.87 -- MODERATE confidence, PDF check pending). In-code
# >=2 mm is too lax (~70 yo mean). Reference line must be the tilted chord between adjacent
# posterior VB corners; our flat back-wall under-reports. memory disc_bulge_norm_verified.
_BULGE_PRESENT_CUT = 1.0
_BULGE_CORD_RISK_CUT = 1.35
_BULGE_CITATION = (
    "Nakashima 2015 (PMID 25584950, n=1211; >1 mm = bulge, >1.35 mm = cord-compression "
    "risk, AUC 0.87 -- MODERATE confidence, PDF confirmation pending); Matsumoto Grade "
    "0/1/2 (PMC3065617) = cervical-native ordinal"
)
_BULGE_CAVEAT = (
    "Reference line = TILTED CHORD between adjacent posterior VB corners; our current flat "
    "vertical back-wall UNDER-reports bulge on lordotic necks (confirmed bug, fix pending). "
    "In-code >=2 mm cutoff is too lax (~70 yo mean). Axial imaging defines true "
    "protrusion/herniation. Finding for physician review; clinical correlation required."
)

# Disc signal grade (pfirrmann_grade). Cervical Miyazaki 2008 grading, NOT lumbar
# Pfirrmann; CSF-normalized ratio is cervical-validated, but the ratio->grade cut-points
# have no published kappa/AUC -> research-grade heuristic. memory cervical_disc_grading_verified.
_PFIRRMANN_CITATION = (
    "Miyazaki 2008 (PMID 18525490) cervical modified grading (NOT lumbar Pfirrmann); "
    "CSF-normalized ratio cervical-validated (Liu 2023 PMID 37156851, Watanabe 2025 "
    "PMID 39645168). DOI / Grade I-V table PDF check pending (human-gated)"
)
_PFIRRMANN_CAVEAT = (
    "Research-grade heuristic: the ratio->discrete-grade cut-points have NO published "
    "kappa/AUC for cervical and were hand-tuned to 10 Duke scans. The grade is surfaced "
    "for physician review, not a validated classification."
)
_PFIRRMANN_GRADE_LABELS = {1: "grade_I", 2: "grade_II", 3: "grade_III", 4: "grade_IV", 5: "grade_V"}

# Disc height index (DHI). The in-code DHI<0.30 is DEBUNKED (uncited, animal-lumbar
# borrow). No validated absolute cervical DHI cut-point exists; use a >30% inter-level
# drop (Suzuki 2018) or absolute disc height <3 mm (van Santbrink) instead -- both need
# cross-level context, handled in interpretation, not this single-value catalog.
# memory disc_height_dhi_norms.
_DHI_CITATION = (
    "DHI<0.30 DEBUNKED (uncited, animal-lumbar borrow). Reduced disc height = >30% drop "
    "vs adjacent (Suzuki 2018) or absolute <3 mm (van Santbrink 2026); closest cervical "
    "DHI formula = Machino 2021 (PMID 34098133, paywalled). No validated absolute cervical "
    "DHI cut-point -- pending Phase-4."
)
_DHI_CAVEAT = (
    "No validated absolute cervical DHI threshold; interpret via >30% inter-level drop or "
    "absolute disc height <3 mm instead. Review-only."
)


# Canal / cord / stenosis.
# dural_sac_AP_min: SOFT-TISSUE dural sac (SCT), not osseous canal. Bands are a provisional
# clinical convention pending Phase-4 MRI confirmation. memory groups_1_4_validation_datasets.
_DURAL_NORMAL_CUT = 13.0
_DURAL_STENOSIS_CUT = 10.0
_DURAL_CITATION = (
    "Nell 2019 (PMC6764695, C2-C7 healthy age/sex percentiles); stenosis bands >13/10-13/<10 mm "
    "are a clinical convention (Ulbrich 2014; Thelen 2019/SHIP) of OSSEOUS-canal / radiograph "
    "origin -- pending Phase-4 MRI soft-tissue confirmation"
)
_DURAL_CAVEAT = (
    "Measures SOFT-TISSUE dural-sac AP via SCT, NOT the osseous canal -- do not conflate with "
    "bony CT/radiograph canal thresholds. Value is a stable across-slice minimum, not a single "
    "manual caliper point. Bands provisional (pending Phase-4). Finding for physician review."
)
# cord_AP: normative comparison delegated to SCT -normalize-hc (Valosek 2024 / PAM50).
_CORD_AP_CITATION = (
    "Valosek 2024 PAM50 healthy-control database via SCT -normalize-hc (age/sex). No fixed mm "
    "cut hard-coded here"
)
_CORD_AP_CAVEAT = (
    "Cord AP normative comparison is delegated to SCT -normalize-hc (Valosek 2024); a reduced-vs-"
    "adjacent (>2 SD) rule for the myelopathy indicator is cross-level and handled in interpretation."
)
# SAC <3 mm = high compression risk (radiograph-origin, verify). Torg <0.8 developmental stenosis.
_SAC_CUT = 3.0
_SAC_CITATION = (
    "SAC <3 mm = high compression risk (plan-cited Fehlings 2015 / Nouri 2016) -- radiograph-origin, "
    "verify for MRI (pending Phase-4); Nell 2019 (PMC6764695) healthy percentiles"
)
_SAC_CAVEAT = (
    "SAC <3 mm high-risk cutoff is radiograph-origin; verify for MRI. Derived from same-slice "
    "subtraction -> reliability depends on slice alignment. Stronger as a risk flag than a full "
    "severity ladder. Finding for physician review."
)
_TORG_CUT = 0.8
_TORG_CITATION = (
    "Torg 1987 / Pavlov 1987: ratio <0.8 = developmental canal stenosis -- RADIOGRAPH origin; "
    "MRI thresholds may need adjustment (pending Phase-4)"
)
_TORG_CAVEAT = (
    "Torg-Pavlov ratio is radiograph-derived and has a known high false-positive rate in large "
    "vertebral bodies; MRI adaptation pending. Finding for physician review."
)


# Global cervical Cobb (Cobb_C3_C7). Lordosis-positive; healthy ~10-35 deg (NASSJ 2025).
# Our code is C3-C7 inferior-inferior and SUPINE -> apply supine->standing offset; endpoint
# precision not yet at target (J8-J9) -> reported as a descriptive class for review, not
# hard-flagged. memory cervical_corner_endplate_method.
_COBB_LORDOTIC_CUT = 10.0
_COBB_STRAIGHT_CUT = 0.0
_COBB_CITATION = (
    "NASSJ 2025 (PMC12744292, asymptomatic C2-C7 ~18.7 deg, range ~10-35 deg); plan also "
    "cites Yukawa 2018 (~13.9 +/- 12.3 deg). Lordosis-positive."
)
_COBB_CAVEAT = (
    "Our Cobb is C3-C7 inferior-inferior and SUPINE (MRI reads ~5 deg less lordotic than "
    "standing radiographs) -> apply a supine->standing offset before comparing to standing "
    "norms; papers often report C2-C7. C6/C7 endpoint precision is not yet at target "
    "(SD ~16 deg; pending SPINEPS corpus + radiologist calibration) -> alignment is reported "
    "as a descriptive class for review, not hard-flagged."
)
# Per-level segmental angle + posterior tangent: no validated cervical per-level norm found.
_GAP_PENDING_CAVEAT = (
    "NOT FOUND: no validated per-level cervical normative range; pending Phase-4 research. "
    "Reported for physician review only."
)


# Quality / caution metrics (NOT clinical thresholds). Owner-confirmed (Ronnie): tilt_outlier +
# ap_width_outlier are geometry/segmentation caution flags, never stand-alone abnormalities.
# tilt 20 deg too aggressive (~28 deg common healthy). AP-width 12-22 mm is engineering sanity.
_AP_WIDTH_SANITY_LO = 12.0
_AP_WIDTH_SANITY_HI = 22.0
_AP_WIDTH_CITATION = (
    "Nell 2019 (PMC6764695) healthy per-level AP-width percentiles for clinical comparison; "
    "the in-code 12-22 mm is an ENGINEERING sanity window, not a clinical pathology threshold"
)
_AP_WIDTH_CAVEAT = (
    "AP-width outlier is a QUALITY/caution flag (segmentation sanity), NOT a clinical abnormality. "
    "Anterior osteophytes may inflate AP width; MRI-mask-based, not radiologist caliper. For "
    "clinical comparison use Nell 2019 age/sex percentiles."
)
_TILT_CAVEAT = (
    "Vertebral tilt is a QUALITY/geometry caution metric, NOT a clinical abnormality. The in-code "
    "20 deg threshold is too aggressive (~28 deg is common on healthy cervical masks; recalibrate) "
    "-- tilt_outlier is a segmentation/orientation caution, not pathology."
)
# Signal: myelomalacia screen (Group 5.1, SCIseg). Binary present/absent; non-diagnostic.
_MYELO_CITATION = (
    "SCIseg (sct_deepseg lesion_sci_t2); Naga Karthik 2024 (PMC11065035). Measured healthy "
    "specificity 10/11 (~91%)"
)
_MYELO_CAVEAT = (
    "Cord T2-hyperintensity SCREEN (SCIseg): a positive level is a finding for physician review "
    "(pattern consistent with possible myelopathy), NOT a diagnosis; clinical correlation required. "
    "Binary present/absent; sensitivity rests on SCIseg's publication."
)


THRESHOLDS: dict[str, ThresholdSpec] = {
    "vb_hahp_ratio": ThresholdSpec(
        key="vb_hahp_ratio",
        clinical_name="vertebral-body anterior/posterior height ratio (Ha/Hp) compression screen",
        unit="ratio",
        tag="derived",
        bands=(
            Band("normal", _VB_HAHP_BORDERLINE_CUT, None, "within"),
            Band("borderline", _VB_HAHP_FLAG_CUT, _VB_HAHP_BORDERLINE_CUT, "within"),
            Band("compression_screen_positive", None, _VB_HAHP_FLAG_CUT, "outside"),
        ),
        citation=_VB_HAHP_CITATION,
        modality_caveat=_VB_HAHP_CAVEAT,
        provenance_note=(
            "Replaces the in-code 70% wedge rule; cohort z-screen at mean-2*SD. "
            "Genant 20/25/40% grade stays separate."
        ),
    ),
    "spondy_slip_mm": ThresholdSpec(
        key="spondy_slip_mm",
        clinical_name="vertebral slip magnitude (anterolisthesis / retrolisthesis)",
        unit="mm",
        tag="raw",
        bands=(
            Band("neutral", None, _SLIP_NEUTRAL_CUT, "within"),
            Band("borderline", _SLIP_NEUTRAL_CUT, _SLIP_PRESENT_CUT, "within"),
            Band("slip_present_screen", _SLIP_PRESENT_CUT, None, "outside"),
        ),
        citation=_SLIP_CITATION,
        modality_caveat=_SLIP_CAVEAT,
        provenance_note=(
            "Current code: neutral <1 mm, present >=2 mm. Our line-derived slip is still "
            "EXPERIMENTAL (SD ~2.9 mm on healthy) -> magnitude only, not screening-ready."
        ),
    ),
    "posterior_bulge_mm": ThresholdSpec(
        key="posterior_bulge_mm",
        clinical_name="posterior disc bulge excursion",
        unit="mm",
        tag="raw",
        bands=(
            Band("no_bulge", None, _BULGE_PRESENT_CUT, "within"),
            Band("bulge_present", _BULGE_PRESENT_CUT, _BULGE_CORD_RISK_CUT, "outside"),
            Band("cord_risk", _BULGE_CORD_RISK_CUT, None, "outside"),
        ),
        citation=_BULGE_CITATION,
        modality_caveat=_BULGE_CAVEAT,
        provenance_note="Replaces in-code >=2 mm / ratio>=1.10 flag; also needs the tilted-chord fix.",
    ),
    "pfirrmann_grade": ThresholdSpec(
        key="pfirrmann_grade",
        clinical_name="cervical disc signal grade (Miyazaki, modified Pfirrmann)",
        unit="grade",
        tag="derived",
        bands=tuple(
            Band(_PFIRRMANN_GRADE_LABELS[g], float(g), float(g) + 1, "review")
            for g in (1, 2, 3, 4, 5)
        ),
        citation=_PFIRRMANN_CITATION,
        modality_caveat=_PFIRRMANN_CAVEAT,
        provenance_note="Rename from lumbar 'pfirrmann' to cervical Miyazaki grading; keep CSF normalization.",
    ),
    "DHI": ThresholdSpec(
        key="DHI",
        clinical_name="disc height index",
        unit="ratio",
        tag="derived",
        bands=None,
        citation=_DHI_CITATION,
        modality_caveat=_DHI_CAVEAT,
        provenance_note="GAP: in-code DHI<0.30 debunked; no validated absolute cervical cut -> review-only.",
    ),
    "dural_sac_AP_min": ThresholdSpec(
        key="dural_sac_AP_min",
        clinical_name="functional canal / dural-sac AP minimum (SCT)",
        unit="mm",
        tag="raw",
        bands=(
            Band("normal", _DURAL_NORMAL_CUT, None, "within"),
            Band("borderline", _DURAL_STENOSIS_CUT, _DURAL_NORMAL_CUT, "within"),
            Band("stenosis_provisional", None, _DURAL_STENOSIS_CUT, "outside"),
        ),
        citation=_DURAL_CITATION,
        modality_caveat=_DURAL_CAVEAT,
        provenance_note="Soft-tissue dural sac; bands provisional pending Phase-4 MRI confirmation.",
    ),
    "cord_AP": ThresholdSpec(
        key="cord_AP",
        clinical_name="spinal cord AP diameter",
        unit="mm",
        tag="raw",
        bands=None,
        citation=_CORD_AP_CITATION,
        modality_caveat=_CORD_AP_CAVEAT,
        provenance_note="Normative comparison delegated to SCT -normalize-hc; no single-value cut.",
    ),
    "SAC": ThresholdSpec(
        key="SAC",
        clinical_name="space available for the cord (canal AP - cord AP)",
        unit="mm",
        tag="derived",
        bands=(
            Band("normal", _SAC_CUT, None, "within"),
            Band("high_risk", None, _SAC_CUT, "outside"),
        ),
        citation=_SAC_CITATION,
        modality_caveat=_SAC_CAVEAT,
        provenance_note="SAC<3 mm high-risk; radiograph-origin, verify (pending Phase-4).",
    ),
    "Torg_Pavlov_ratio": ThresholdSpec(
        key="Torg_Pavlov_ratio",
        clinical_name="Torg-Pavlov ratio (canal AP / vertebral-body AP)",
        unit="ratio",
        tag="derived",
        bands=(
            Band("normal", _TORG_CUT, None, "within"),
            Band("developmental_stenosis_screen", None, _TORG_CUT, "outside"),
        ),
        citation=_TORG_CITATION,
        modality_caveat=_TORG_CAVEAT,
        provenance_note="Planned; radiograph-origin <0.8; MRI adjustment pending Phase-4.",
    ),
    "Cobb_C3_C7": ThresholdSpec(
        key="Cobb_C3_C7",
        clinical_name="global cervical Cobb angle (C3-C7, lordosis-positive)",
        unit="deg",
        tag="derived",
        bands=(
            Band("lordotic", _COBB_LORDOTIC_CUT, None, "within"),
            Band("straightened", _COBB_STRAIGHT_CUT, _COBB_LORDOTIC_CUT, "review"),
            Band("kyphotic", None, _COBB_STRAIGHT_CUT, "review"),
        ),
        citation=_COBB_CITATION,
        modality_caveat=_COBB_CAVEAT,
        provenance_note=(
            "Sign fixed (was -21 deg kyphotic); magnitude/endpoints pending SPINEPS + radiologist "
            "GT. The label side = lordosis_classification."
        ),
    ),
    "segmental_angle": ThresholdSpec(
        key="segmental_angle",
        clinical_name="per-level segmental angle",
        unit="deg",
        tag="raw",
        bands=None,
        citation=None,
        modality_caveat=_GAP_PENDING_CAVEAT,
        provenance_note="GAP: no per-level cervical segmental-angle norm; focal-kyphosis cut pending Phase-4.",
    ),
    "posterior_tangent_C3_C7": ThresholdSpec(
        key="posterior_tangent_C3_C7",
        clinical_name="posterior tangent angle (C3-C7)",
        unit="deg",
        tag="derived",
        bands=None,
        citation=None,
        modality_caveat=_GAP_PENDING_CAVEAT,
        provenance_note="GAP: secondary cross-check metric; no normative range adopted (pending Phase-4).",
    ),
    "AP_width": ThresholdSpec(
        key="AP_width",
        clinical_name="vertebral-body AP width",
        unit="mm",
        tag="quality",
        bands=(
            Band("within_sanity", _AP_WIDTH_SANITY_LO, _AP_WIDTH_SANITY_HI, "within"),
            Band("ap_width_outlier", None, _AP_WIDTH_SANITY_LO, "review"),
            Band("ap_width_outlier", _AP_WIDTH_SANITY_HI, None, "review"),
        ),
        citation=_AP_WIDTH_CITATION,
        modality_caveat=_AP_WIDTH_CAVEAT,
        provenance_note="Sanity window only; clinical norm = Nell 2019 percentiles (cross-level/demographic).",
    ),
    "tilt_deg": ThresholdSpec(
        key="tilt_deg",
        clinical_name="vertebral-body tilt (vs global SI axis)",
        unit="deg",
        tag="quality",
        bands=None,
        citation=None,
        modality_caveat=_TILT_CAVEAT,
        unknown_status=STATUS_NOT_INTERPRETABLE,
        provenance_note="Quality caution; recalibrate the 20 deg threshold (too aggressive on cervical).",
    ),
    "myelomalacia": ThresholdSpec(
        key="myelomalacia",
        clinical_name="cord T2-hyperintensity screen (myelomalacia)",
        unit="present",
        tag="derived",
        bands=(
            Band("none", None, 0.5, "within"),
            Band("signal_anomaly_present", 0.5, None, "outside"),
        ),
        citation=_MYELO_CITATION,
        modality_caveat=_MYELO_CAVEAT,
        provenance_note="Group 5.1 binary screen; carried into Group 6 via the 5->6 flags contract.",
    ),
}


# Sex-specific dural-sac stenosis cut (Nell 2019 PMC6764695: M < 10 mm, F < 9 mm). Applied only
# when a patient sex is supplied; otherwise the sex-neutral 10 mm cut (spec.bands) is used.
_DURAL_STENOSIS_CUT_BY_SEX = {"M": 10.0, "F": 9.0}


def _norm_sex(sex: str | None) -> str | None:
    if not sex:
        return None
    s = str(sex).strip().lower()
    if s in ("m", "male"):
        return "M"
    if s in ("f", "female"):
        return "F"
    return None


def _bands_for(key: str, spec: "ThresholdSpec", sex: str | None) -> "tuple[Band, ...] | None":
    """The catalog bands, sex-adjusted where a cited sex-specific cut exists (dural sac)."""
    s = _norm_sex(sex)
    if key == "dural_sac_AP_min" and spec.bands and s in _DURAL_STENOSIS_CUT_BY_SEX:
        cut = _DURAL_STENOSIS_CUT_BY_SEX[s]
        return (
            Band("normal", _DURAL_NORMAL_CUT, None, "within"),
            Band("borderline", cut, _DURAL_NORMAL_CUT, "within"),
            Band("stenosis", None, cut, "outside"),
        )
    return spec.bands


def classify(key: str, value: float, sex: str | None = None) -> ThresholdEval:
    """Interpret a measurement value against the catalog.

    Returns a ThresholdEval with the standardized `status`, the per-measurement
    `severity` label, the boolean clinical `flag`, and the locked `citation` + caveat.
    `sex` ('M'/'F'/'male'/'female') applies the cited sex-specific cut where one exists
    (currently the dural-sac stenosis threshold, Nell 2019 M10/F9); ignored otherwise.
    Raises KeyError for an unknown key (the caller decides how to handle measurements
    not yet in the catalog).
    """
    spec = THRESHOLDS[key]
    value = float(value)
    bands = _bands_for(key, spec, sex)
    if bands:
        for band in bands:
            if band.contains(value):
                return ThresholdEval(
                    measurement=key,
                    value=value,
                    unit=spec.unit,
                    status=_REFERENCE_TO_STATUS[band.reference],
                    severity=band.label,
                    flag=(band.reference == "outside"),
                    citation=spec.citation,
                    caveat=spec.modality_caveat,
                    tag=spec.tag,
                )
    # No bands, or no band matched -> no cited threshold applies.
    return ThresholdEval(
        measurement=key,
        value=value,
        unit=spec.unit,
        status=spec.unknown_status,
        severity=None,
        flag=False,
        citation=spec.citation,
        caveat=spec.modality_caveat,
        tag=spec.tag,
    )
