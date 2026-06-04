"""Group 5 -> Group 6 output contract: emit the per-case findings JSON Group 6 consumes.

Group 5 produces signal/shape-based abnormal-finding SCREENS (not diagnoses). Group 6
(interpretation + report) needs those as a structured, self-describing document: per cervical
level a fracture/compression screen and an (optional) myelomalacia screen, each with a value,
a screen status, and a citable provenance, plus an explicit not-assessed list and honest
caveats. See plans/phase-4-interpretation.md (§4.2 per-level findings, §4.3 myelopathy
indicator consumes the per-level cord-signal flag).

This emitter is PURE (data in, dict out -> JSON-serialisable) and REUSES the validated
measurement logic (classify_genant + cervical_deformity_flag); it re-implements nothing.

STATUS: v0.1 PROPOSAL. The exact field set is partly a team decision (Group 6 + the AUBMC
measurement spec). Confirm with the team before freezing the schema.
"""
from vertebral_fracture import (
    COHORT_HAHP_MEAN,
    COHORT_HAHP_SD,
    cervical_deformity_flag,
    classify_genant,
)

SCHEMA_VERSION = "0.1"

# No-diagnosis wording (medical-AI rule: screens flag for review, never diagnose).
_FRACTURE_NOTE = ("vertebral-body compression/deformity screen — a flagged level is a finding "
                  "for physician review, not a diagnosis; clinical correlation required")
_MYELO_NOTE = ("cord T2-hyperintensity screen — a positive level is a finding for physician "
               "review, not a diagnosis; clinical correlation required")

_FRACTURE_CITATIONS = [
    "Tan 2004 (Eur Spine J, PMC3476578)",
    "Lee 2012 (PMC3393857)",
    "Kaur 2025 (J Human Anat)",
    "Chen 2013 (PLoS One, PMC3859485)",
    "Nell 2019 (PMC6764695)",
]

_NOT_ASSESSED = [
    "5.3 tumor/mass — no public labeled cervical-tumor MRI; not implemented",
    "5.4 post-surgical scar — requires gadolinium-enhanced sequences; out of scope",
]

_CAVEATS = [
    "Screens flag findings for physician review; no diagnosis is made.",
    "Fracture screen is a vertebral-body compression/deformity screen, NOT a general fracture "
    "detector — it has no power on non-compression fractures (odontoid/facet/posterior arch).",
    "Norm is triangulated: no like-for-like healthy MRI cervical Ha/Hp comparator exists "
    "(plausibility, not proof).",
    "Per-vertebra Ha/Hp SD is wide (~0.13) -> reliable at the group/screening level, coarse per body.",
    "C1/C2 are excluded (atlas/odontoid are structurally unique).",
]


def _screen_status(zscore, z):
    """flag (<= -z) / borderline (between -z and -1) / normal. Continuous z is kept too."""
    if zscore <= -z:
        return "flag"
    if zscore < -1.0:
        return "borderline"
    return "normal"


def _fracture_finding(heights, screen_z, mean, sd):
    Ha, Hm, Hp = float(heights["Ha"]), float(heights["Hm"]), float(heights["Hp"])
    ratio = Ha / Hp if Hp else float("nan")
    genant = classify_genant(heights)
    scr = cervical_deformity_flag(ratio, mean=mean, sd=sd, z=screen_z)
    return {
        "Ha_mm": round(Ha, 2),
        "Hm_mm": round(Hm, 2),
        "Hp_mm": round(Hp, 2),
        "ratio": round(float(ratio), 3),
        "genant_grade": int(genant["grade"]),     # medical Genant standard (separate from screen)
        "genant_type": genant["type"],
        "cervical_z": round(scr["zscore"], 2),     # data-driven cohort z (drives the screen)
        "screen": _screen_status(scr["zscore"], screen_z),
        "flagged": bool(scr["flagged"]),
        "note": _FRACTURE_NOTE,
    }


def _myelomalacia_finding(level, myelomalacia):
    """Optional 5.1 screen. myelomalacia=None -> not assessed; else dict {level: bool present}."""
    engine = "SCIseg (sct_deepseg lesion_sci_t2)"
    if myelomalacia is None or level not in myelomalacia:
        return {"assessed": False, "present": None, "engine": engine,
                "note": "not assessed in this run — " + _MYELO_NOTE}
    return {"assessed": True, "present": bool(myelomalacia[level]), "engine": engine,
            "note": _MYELO_NOTE}


def build_flags_contract(case_id, fracture_levels, myelomalacia=None, *,
                         modality="T2 sagittal MRI",
                         segmentation="TotalSpineSeg full (step2_output)",
                         screen_z=2.0, norm_mean=COHORT_HAHP_MEAN, norm_sd=COHORT_HAHP_SD,
                         schema_version=SCHEMA_VERSION):
    """Build the Group 5 -> Group 6 findings document.

    case_id          : opaque case identifier.
    fracture_levels  : list of (level_name, heights) where heights = {"Ha","Hm","Hp"} in mm
                       (as returned by vertebral_fracture.measure_vertebra).
    myelomalacia     : None (5.1 not run -> per level assessed=False) OR {level_name: present:bool}.
    screen_z         : cervical deformity-screen z policy (specificity knob; team/AUBMC decision).

    Returns a JSON-serialisable dict (plain str/int/float/bool/list/dict only).
    """
    levels = [{
        "level": name,
        "fracture": _fracture_finding(heights, screen_z, norm_mean, norm_sd),
        "myelomalacia": _myelomalacia_finding(name, myelomalacia),
    } for name, heights in fracture_levels]

    return {
        "schema_version": schema_version,
        "case_id": case_id,
        "modality": modality,
        "segmentation": segmentation,
        "group": "5 (signal/shape-based abnormal-finding screens)",
        "levels": levels,
        "not_assessed": list(_NOT_ASSESSED),
        "provenance": {
            "fracture_screen": {
                "norm": f"healthy Ha/Hp {norm_mean} +/- {norm_sd} "
                        "(Spine-Generic, n=60 C3-C7, 12 subjects, 3 vendors)",
                "rule": "flag when Ha/Hp < mean - z*sd",
                "z": float(screen_z),
                "threshold_ratio": round(float(norm_mean - screen_z * norm_sd), 3),
                "citations": list(_FRACTURE_CITATIONS),
            },
            "myelomalacia_screen": {
                "engine": "SCIseg (sct_deepseg lesion_sci_t2)",
                "citations": ["Naga Karthik 2024 (Radiology AI, PMC11065035)"],
            },
        },
        "caveats": list(_CAVEATS),
    }
