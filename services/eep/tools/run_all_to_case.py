"""Map a measurement-pipeline ``run_all()`` output to the frontend case-envelope contract.

Implements the §3 mapping from the measurement-link handoff: the pipeline already emits
``measurements`` / ``flags`` / ``interpretations`` in the contract shape, so this is mostly a
passthrough plus deriving the case envelope, the report impression, and the triage badge.

CLI:  python -m services.eep.tools.run_all_to_case <run_all.json> <case_id> [source_filename]
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

BASE_DISCLAIMERS = [
    "Research-use structured interpretation - not a diagnosis. Clinical correlation required.",
]
# §4 wording, shown when patient sex is absent (sex-neutral thresholds in effect).
DEMOGRAPHIC_CAVEAT_NOSEX = (
    "Demographic-adjusted thresholds apply when age/sex are provided; with patient data "
    "absent, sex-neutral defaults are used. Clinical accuracy of demographic-adjusted "
    "findings will be confirmed once cases with complete patient data are available."
)


def to_case_envelope(
    run: dict,
    case_id: str,
    modality: str = "T2 sagittal MRI",
    source_filename: str | None = None,
    created_at: str | None = None,
) -> dict:
    patient = run.get("patient") or {}
    sex, age, height = patient.get("sex"), patient.get("age"), patient.get("height_cm")

    interp = dict(run.get("interpretations") or {})
    interp.setdefault("measurements", [])
    interp.setdefault("syndromes", [])
    rows = interp["measurements"]

    # triage_badge (§3): urgent if any non-quality outside_reference row; else none.
    outside = [
        r for r in rows
        if r.get("status") == "outside_reference" and r.get("flag") and not r.get("quality_flags")
    ]
    triage = "urgent" if outside else "none"

    # report.impression: one line per flagged (outside_reference) row, traceable to the key.
    impression = []
    for r in outside:
        disp = str(r.get("measurement") or "").replace("_", " ")
        val = r.get("value")
        vtxt = f"{round(val, 1)} {r.get('unit') or ''}".strip() if isinstance(val, (int, float)) else ""
        sev = str(r.get("severity") or "").replace("_", " ")
        line = f"{disp} at {r.get('level')} {vtxt} ({sev}) - finding flagged for physician review."
        impression.append({
            "text": " ".join(line.split()),
            "traceable_to": [r.get("measurement")],
            "status": "outside_reference",
        })
    if not impression:
        impression = [{
            "text": "No measurements exceeded reference thresholds; no findings flagged for physician review.",
            "traceable_to": [],
            "status": "within_reference",
        }]

    disclaimers = list(BASE_DISCLAIMERS)
    if not sex:
        disclaimers.append(DEMOGRAPHIC_CAVEAT_NOSEX)

    levels = sorted({
        r["level"] for r in rows
        if isinstance(r.get("level"), str) and r["level"].startswith("C") and "-" not in r["level"]
    })
    created_at = created_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "schema_version": 0.1,
        "case": {
            "case_id": case_id,
            "status": "ready",
            "modality": modality,
            "series_description": source_filename,
            "study_date": None,
            "uploader": "pipeline",
            "triage_badge": triage,
            "patient": {"sex": sex, "age": age},
            "patient_context": {"sex": sex, "age_years": age, "height_cm": height},
            "source_file": {"filename": source_filename},
            "created_at": created_at,
            "updated_at": created_at,
            "levels_measured": levels,
        },
        "job": {
            "stage": "ready",
            "stages": ["queued", "segmenting", "measuring", "interpreting", "ready"],
            "progress": 1.0,
            "error": None,
        },
        "measurements": run.get("measurements") or {},
        "flags": run.get("flags") or {},
        "components": run.get("components") or {},
        "interpretations": interp,
        "report_context": {
            "modality": "cervical_sagittal_mri",
            "report_language": "en",
            "disclaimers": disclaimers,
            "include_appendix": True,
        },
        "report": {"impression": impression, "findings_by_level": None, "disclaimers": disclaimers},
    }


if __name__ == "__main__":
    run = json.load(open(sys.argv[1]))
    cid = sys.argv[2]
    src = sys.argv[3] if len(sys.argv) > 3 else f"{cid}.nii.gz"
    json.dump(to_case_envelope(run, cid, source_filename=src), sys.stdout, indent=2)
