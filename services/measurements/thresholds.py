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
# See memory vb_hahp_norm_verified / vb_hahp_z_threshold; mirrors group5/flags_contract.py.
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
}


def classify(key: str, value: float) -> ThresholdEval:
    """Interpret a measurement value against the catalog.

    Returns a ThresholdEval with the standardized `status`, the per-measurement
    `severity` label, the boolean clinical `flag`, and the locked `citation` + caveat.
    Raises KeyError for an unknown key (the caller decides how to handle measurements
    not yet in the catalog).
    """
    spec = THRESHOLDS[key]
    value = float(value)
    if spec.bands:
        for band in spec.bands:
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
