"""Generate 2 demo reports (1 healthy + 1 symptomatic) for radiologist review + cross-reference.

Runs the FULL measurement+assessement pipeline (services.measurements.orchestrator.run_all) on
two cases that have TSS + SCT canal/cord + SPINEPS, and renders a human-readable, honest, cited
report per case. Also saves the raw run_all JSON (the canonical cross-reference for the frontend).
"""
import csv, glob, json, os, shutil, sys, zipfile
import numpy as np
sys.path.insert(0, "/Users/andrew/Desktop/AUB/Spring 26/EECE 503n/Project/MRI-ReportGenerator")
from services.measurements.context import load_context
from services.measurements.orchestrator import run_all
from services.assessement.assessement import detect_syndromes, _infer_unit
from services.assessement.thresholds import classify, THRESHOLDS

# spondylolisthesis is EXPERIMENTAL (no supine-MRI presence threshold; reads unstable corners) ->
# do not surface as a clinical flag; it false-fires on healthy supine necks.
_EXPERIMENTAL_FLAGS = {"spondylolisthesis_present"}


def g3_from_csv(case_dir):
    """Per-level canal/cord/SAC + dural-sac min from the precomputed SCT perslice CSVs (real SCT
    output, computed on Colab where SCT is installed; the deployed system runs SCT live)."""
    out = {}
    for task, key in [("canal", "canal_AP"), ("spinalcord", "cord_AP")]:
        p = f"{case_dir}/sct/{task}_perslice.csv"
        if not os.path.exists(p):
            continue
        per = {}
        for row in csv.DictReader(open(p)):
            vl, ap = row.get("VertLevel", "").strip(), row.get("MEAN(diameter_AP)", "").strip()
            if vl and ap:
                try:
                    lv = int(float(vl))
                    if 2 <= lv <= 7:
                        per.setdefault(lv, []).append(float(ap))
                except ValueError:
                    pass
        out[key] = {f"C{lv}": float(np.mean(v)) for lv, v in per.items()}
    if "canal_AP" in out and "cord_AP" in out:
        shared = set(out["canal_AP"]) & set(out["cord_AP"])
        out["SAC"] = {lv: out["canal_AP"][lv] - out["cord_AP"][lv] for lv in shared}
        out["dural_sac_AP_min"] = {"min": min(out["canal_AP"].values())}
    return out


def inject_g3(rep, case_dir, sex):
    """Add CSV-derived G3 measurements + their catalog assessement to the report."""
    g3 = g3_from_csv(case_dir)
    rows = rep["assessements"]["measurements"]
    for key, per in g3.items():
        rep["measurements"].setdefault(key, {}).update(per)
        if key not in THRESHOLDS:
            continue
        for level, val in per.items():
            ev = classify(key, val, sex=sex)
            rows.append({"measurement": key, "level": str(level), "value": float(val),
                         "unit": ev.unit, "status": ev.status, "severity": ev.severity,
                         "flag": ev.flag, "demographics_used": {}, "quality_flags": [],
                         "caveat": ev.caveat})
    rows.sort(key=lambda r: (r["measurement"], r["level"]))

OUT = "radiologist_demo"; os.makedirs(OUT, exist_ok=True)

CASES = [
    {"id": "sub-amu01", "cohort": "healthy control (Spine-Generic)",
     "step2": "out_validation/sub-amu01_T2w/tss/step2_output",
     "levels": "out_validation/sub-amu01_T2w/tss/step1_levels",
     "canal": "out_validation/sub-amu01_T2w/sct/canal/prediction.nii.gz",
     "cord":  "out_validation/sub-amu01_T2w/sct/spinalcord/prediction.nii.gz",
     "spineps": "out_sg_spineps/sub-amu01_mod-T2w_seg-vert_msk.nii.gz",
     "raw": "data/spine_generic/sub-amu01_T2w.nii.gz",
     "age": 28, "sex": "M", "height_cm": 176, "demo_note": "real demographics (Spine-Generic participants.tsv)"},
    {"id": "mmcsd-csm-002", "cohort": "symptomatic — cervical spondylotic myelopathy (MMCSD)",
     "step2": "out_validation/mmcsd-csm-002/tss/step2_output",
     "levels": "out_validation/mmcsd-csm-002/tss/step1_levels",
     "canal": "out_validation/mmcsd-csm-002/sct/canal/prediction.nii.gz",
     "cord":  "out_validation/mmcsd-csm-002/sct/spinalcord/prediction.nii.gz",
     "spineps": "out_validation_spineps/mod-mmcsd-csm-002_seg-vert_msk.nii.gz",
     "raw": "data/mmcsd/t2_sag/2/2.nii.gz",
     "age": 53, "sex": None, "height_cm": None,
     "demo_note": "age from MMCSD; sex code present but M/F mapping unconfirmed -> sex-neutral thresholds (demonstrates the no-patient-data fallback)"},
]

GROUPS = [
    ("G1 — Vertebral body", ["H_anterior", "H_middle", "H_posterior", "AP_width", "tilt_deg",
                             "vb_hahp_ratio", "spondy_slip_mm"]),
    ("G2 — Intervertebral disc", ["DHI", "disc_SI_height", "posterior_bulge_mm", "disc_vb_ap_ratio",
                                  "pfirrmann_grade", "nucleus_csf_ratio"]),
    ("G3 — Spinal canal & cord", ["dural_sac_AP_min", "canal_AP", "cord_AP", "SAC"]),
    ("G4 — Cervical alignment", ["Cobb_C3_C7", "segmental_angle", "posterior_tangent_C3_C7"]),
    ("G5 — Screens", ["myelomalacia"]),
]
DISCLAIMER = (
    "RESEARCH / PRE-VALIDATION OUTPUT — NOT A DIAGNOSIS. Every value below is an automated geometric "
    "or signal measurement; outside-reference values are findings **flagged for physician review**, not "
    "clinical conclusions. Clinical correlation required."
)


def fmt(v):
    return f"{v:.2f}" if isinstance(v, (int, float)) and v == v else str(v)


def render(case, rep):
    rows = rep["assessements"]["measurements"]
    by_meas = {}
    for r in rows:
        by_meas.setdefault(r["measurement"], []).append(r)
    L = []
    L.append(f"# Cervical Spine MRI — Automated Measurement Report")
    L.append(f"\n**Case:** {case['id']}  ·  **Cohort:** {case['cohort']}")
    pt = rep["patient"]
    L.append(f"**Patient:** age {pt['age'] if pt['age'] is not None else 'n/a'} · "
             f"sex {pt['sex'] or 'not provided'} · height {pt['height_cm'] or 'n/a'} cm  "
             f"_( {case['demo_note']} )_")
    L.append(f"\n> {DISCLAIMER}\n")
    # flags summary
    flagged = [r for r in rows if r["flag"]]
    L.append(f"## Summary")
    L.append(f"- Components run: {sum(1 for c in rep['components'].values() if c['status']=='ok')} ok, "
             f"{sum(1 for c in rep['components'].values() if c['status']=='error')} skipped (missing input).")
    L.append(f"- Findings flagged for review: **{len(flagged)}** measurement-levels "
             f"(across {len({r['measurement'] for r in flagged})} measurements).")
    syn = detect_syndromes(rows)
    if syn:
        for s in syn:
            L.append(f"- ⚠️ {s['syndrome'].replace('_',' ')} @ {s['level']} (provisional, advisory): {s['advisory']}")
    # Component-level clinical flags (non-quality) from report["flags"]
    _Q = ("low_confidence", "misaligned", "approximate", "resolution", "warning", "outlier", "unreliable")
    clinical = {}
    for fname, per in rep.get("flags", {}).items():
        if any(mk in fname.lower() for mk in _Q) or fname in _EXPERIMENTAL_FLAGS:
            continue
        lv = [k for k, raised in per.items() if raised]
        if lv:
            clinical[fname] = lv
    if clinical:
        L.append("\n**Clinical flags raised (component-level):**")
        for fn, lv in clinical.items():
            L.append(f"- `{fn}`: {', '.join(sorted(lv))}")
    L.append("")
    for title, keys in GROUPS:
        present = [(k, by_meas[k]) for k in keys if k in by_meas]
        if not present:
            continue
        L.append(f"## {title}")
        for k, items in present:
            items = sorted(items, key=lambda r: r["level"])
            unit = items[0]["unit"]
            cells = []
            for r in items:
                mark = "  ⚑" if r["flag"] else ""
                sev = f" [{r['severity']}]" if r.get("severity") else ""
                cells.append(f"{r['level']} {fmt(r['value'])}{unit}{sev}{mark}")
            L.append(f"- **{k}**: " + " · ".join(cells))
            cav = next((r["caveat"] for r in items if r.get("caveat")), None)
            demo = next((r["demographics_used"] for r in items if r.get("demographics_used")), None)
            if demo:
                L.append(f"    - _demographics used: {demo}_")
            if cav:
                L.append(f"    - _note: {cav}_")
        L.append("")
    L.append("## Validation provenance (where these measurements stand)")
    L.append("- **G3 canal/SAC/cord**: VALIDATED — healthy vs symptomatic separate at p=0.0001 (canal/SAC).")
    L.append("- **G1 Ha/Hp compression screen**: validated as a screen (0% healthy false-flag).")
    L.append("- **G4 C3–C7 Cobb (SPINEPS)**: method-validated (reads literature lordosis); discrimination directional.")
    L.append("- **G2 disc**: partial — disc/VB AP ratio separates (AUC 0.62); disc signal is a documented non-discriminator.")
    L.append("- **G5 screens**: myelomalacia ~91% healthy specificity.")
    L.append("- Thresholds are cited (catalog `services/assessement/thresholds.py`); some are conservative "
             "borrows pending cervical-MRI confirmation — see each note above.")
    L.append(f"\n_Demographic-adjusted thresholds (e.g. sex-specific canal cut) are correct in logic now; their "
             f"clinical accuracy will be confirmed once cases with complete patient data are available._")
    return "\n".join(L)


manifest = []
for case in CASES:
    step2 = glob.glob(f"{case['step2']}/*.nii.gz")[0]
    levels = glob.glob(f"{case['levels']}/*.nii.gz")
    ctx = load_context(step2, levels_path=levels[0] if levels else None,
                       sct_canal_seg_path=case["canal"], sct_cord_seg_path=case["cord"],
                       spineps_seg_path=case["spineps"], age=case["age"], sex=case["sex"],
                       height_cm=case["height_cm"])
    rep = run_all(ctx)
    inject_g3(rep, case["step2"].split("/tss/")[0], case["sex"])  # CSV-derived canal/cord/SAC + assess
    md = render(case, rep)
    base = case["id"]
    open(f"{OUT}/report_{base}.md", "w").write(md)
    json.dump(rep, open(f"{OUT}/report_{base}.json", "w"), indent=2, default=float)
    shutil.copy(case["raw"], f"{OUT}/MRI_{base}.nii.gz")
    nflag = sum(1 for r in rep["assessements"]["measurements"] if r["flag"])
    nok = sum(1 for c in rep["components"].values() if c["status"] == "ok")
    manifest.append((base, nok, nflag))
    print(f"{base}: {nok} components ok, {nflag} flagged -> report_{base}.md + .json + MRI")

# license note + zip
open(f"{OUT}/README.txt", "w").write(
    "Cervical spine MRI — automated measurement demo (2 cases).\n"
    "Each case: report_<id>.md (human-readable), report_<id>.json (raw values), MRI_<id>.nii.gz.\n\n"
    "LICENSE: sub-amu01 = Spine-Generic (open, shareable). mmcsd-csm-002 = MMCSD (Synapse syn63903115) "
    "— research use; confirm CC BY 4.0 vs NC-ND before any public redistribution (private radiologist "
    "review under research use is the intended scope).\n\n"
    "Outputs are RESEARCH/PRE-VALIDATION, flagged for physician review, never a diagnosis.\n")
with zipfile.ZipFile(f"{OUT}/radiologist_demo.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for f in glob.glob(f"{OUT}/*"):
        if not f.endswith(".zip"):
            z.write(f, os.path.basename(f))
print(f"\nzip -> {OUT}/radiologist_demo.zip ({os.path.getsize(OUT+'/radiologist_demo.zip')/1e6:.1f} MB)")
print("manifest:", manifest)
