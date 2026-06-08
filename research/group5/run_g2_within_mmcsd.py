"""G2 WITHIN-MMCSD validation (49 symptomatic cases, same scanner -> confound-free).

The cross-dataset healthy-vs-unhealthy test is confounded (different scanners). The clean test
for the acquisition-sensitive disc metrics is WITHIN one dataset: per disc level, lesion vs
non-lesion (labels from high_pain_text.xlsx columns 2C2-3..2C7-T1, 1=lesion). Signal uses the
NATIVE tss/input grayscale (same grid as step2 -> no resample darkening). Bulge uses the fixed
endplate-corner reference. Reports Mann-Whitney p, Cohen's d, and AUC for every metric.
"""
import glob, os, sys
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

REPO = "/Users/andrew/Desktop/AUB/Spring 26/EECE 503n/Project/MRI-ReportGenerator"
sys.path.insert(0, REPO)
from services.measurements.context import load_context
from services.measurements.geometric import disc_si_height, disc_height_index, disc_ap_bulge
from services.measurements.signal import pfirrmann_grade

ROOT = "out_validation_g2"
SEG_COLS = {"2C2-3": "C2-C3", "2C3-4": "C3-C4", "2C4-5": "C4-C5",
            "2C5-6": "C5-C6", "2C6-7": "C6-C7", "2C7-T1": "C7-T1"}
LABELED = set(SEG_COLS.values())

xl = pd.read_excel("data/mmcsd/high_pain_text.xlsx", sheet_name="Sheet1").dropna(subset=["ID"])
xl["ID"] = xl["ID"].astype(int)


def lesion_levels(cid):
    n = int(cid.split("-")[-1]); row = xl[xl["ID"] == n]
    if row.empty:
        return None
    return {disc for col, disc in SEG_COLS.items() if col in row and int(row.iloc[0][col]) == 1}


# collect per-disc records (only the 6 labeled levels)
recs = []          # dict(level, lesion, ratio, grade, dhi, bulge, ap_ratio, width)
n_cases = 0
miss = []
for cd in sorted(glob.glob(f"{ROOT}/*")):
    if not os.path.isdir(cd):
        continue
    cid = os.path.basename(cd)
    step2 = glob.glob(f"{cd}/tss/step2_output/*.nii.gz")
    inp = glob.glob(f"{cd}/tss/input/*.nii.gz")
    les = lesion_levels(cid)
    if not step2 or not inp or les is None:
        miss.append(cid); continue
    try:
        ctx = load_context(step2[0], raw_path=inp[0])
        si = disc_si_height.compute(ctx); prior = {"disc_si_height": si}
        dhi = disc_height_index.compute(ctx, prior); prior["disc_height_index"] = dhi
        pf = pfirrmann_grade.compute(ctx, prior)
        bul = disc_ap_bulge.compute(ctx, prior)
    except Exception as e:
        miss.append(f"{cid}:{str(e)[:50]}"); continue
    n_cases += 1
    ncr = pf.measurements.get("nucleus_csf_ratio", {})
    grd = pf.measurements.get("pfirrmann_grade", {})
    dhiv = dhi.measurements.get("DHI", {})
    bmm = bul.measurements.get("posterior_bulge_mm", {})
    arat = bul.measurements.get("disc_vb_ap_ratio", {})
    dwid = si.measurements.get("disc_AP_width", {})
    for lvl in LABELED:
        if lvl not in ncr and lvl not in dhiv and lvl not in bmm:
            continue
        recs.append({
            "level": lvl, "lesion": int(lvl in les),
            "ratio": ncr.get(lvl, np.nan), "grade": grd.get(lvl, np.nan),
            "dhi": dhiv.get(lvl, np.nan), "bulge": bmm.get(lvl, np.nan),
            "ap_ratio": arat.get(lvl, np.nan), "width": dwid.get(lvl, np.nan),
        })

df = pd.DataFrame(recs)
print(f"cases used: {n_cases}/49 | discs (labeled levels): {len(df)} | "
      f"lesion {int(df.lesion.sum())} / non-lesion {int((1-df.lesion).sum())}")
if miss:
    print("skipped:", miss[:8], ("..." if len(miss) > 8 else ""))


def cohen_d(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    na, nb = len(a), len(b)
    sp = np.sqrt(((na-1)*a.var(ddof=1) + (nb-1)*b.var(ddof=1)) / (na+nb-2))
    return (a.mean() - b.mean()) / sp if sp > 0 else 0.0


# metric, expected direction in lesion (lower/higher = worse)
METRICS = [
    ("ratio", "nucleus/CSF ratio", "lower"),
    ("grade", "Miyazaki grade", "higher"),
    ("dhi", "DHI", "lower"),
    ("bulge", "posterior bulge mm", "higher"),
    ("ap_ratio", "disc/VB AP ratio", "higher"),
    ("width", "disc AP width mm", "higher"),
]
print("\n=== WITHIN-MMCSD: lesion vs non-lesion discs ===")
print(f"{'metric':22s} {'lesion med':>11s} {'non-les med':>11s} {'d':>6s} {'AUC':>5s} {'p':>8s}  n(les/non)")
results = {}
for key, label, direction in METRICS:
    sub = df[["lesion", key]].dropna()
    L = sub[sub.lesion == 1][key].values
    N = sub[sub.lesion == 0][key].values
    if len(L) < 3 or len(N) < 3:
        continue
    U, p = mannwhitneyu(L, N, alternative="two-sided")
    auc = U / (len(L) * len(N))                 # AUC for "lesion > non-lesion"
    if direction == "lower":                    # report AUC as discrimination strength
        auc = 1 - auc
    d = cohen_d(L, N)
    results[key] = {"label": label, "lesion_median": float(np.median(L)), "nonlesion_median": float(np.median(N)),
                    "cohen_d": float(d), "auc": float(auc), "p": float(p), "n_lesion": len(L), "n_nonlesion": len(N)}
    print(f"{label:22s} {np.median(L):11.3f} {np.median(N):11.3f} {d:6.2f} {auc:5.2f} {p:8.4f}  {len(L)}/{len(N)}")

# ---- LEVEL-STRATIFIED (control the level confound: lesion discs cluster mid-cervical) ----
# Center each metric by its OWN level's median, then test lesion vs non-lesion on residuals.
# If a metric only separated because lesions sit at wide mid-cervical levels, the effect
# collapses here; if it survives, it is a genuine within-level lesion signal.
print("\n=== LEVEL-STRATIFIED (metric centered per level, removes level main-effect) ===")
print(f"{'metric':22s} {'d_resid':>7s} {'AUC':>5s} {'p':>8s}   per-level lesion-minus-nonlesion median")
strat = {}
for key, label, direction in METRICS:
    sub = df[["level", "lesion", key]].dropna().copy()
    if sub.empty:
        continue
    sub["resid"] = sub[key] - sub.groupby("level")[key].transform("median")
    L = sub[sub.lesion == 1]["resid"].values
    N = sub[sub.lesion == 0]["resid"].values
    if len(L) < 3 or len(N) < 3:
        continue
    U, p = mannwhitneyu(L, N, alternative="two-sided")
    auc = U / (len(L) * len(N))
    if direction == "lower":
        auc = 1 - auc
    d = cohen_d(L, N)
    # per-level raw lesion-minus-nonlesion median (sanity, only levels with both groups)
    per = []
    for lvl in ["C3-C4", "C4-C5", "C5-C6", "C6-C7"]:
        s = sub[sub.level == lvl]
        ll, nn = s[s.lesion == 1][key], s[s.lesion == 0][key]
        if len(ll) >= 2 and len(nn) >= 2:
            per.append(f"{lvl[-3:]}:{np.median(ll)-np.median(nn):+.2f}")
    strat[key] = {"d_resid": float(d), "auc_resid": float(auc), "p_resid": float(p)}
    print(f"{label:22s} {d:7.2f} {auc:5.2f} {p:8.4f}   {'  '.join(per)}")

import json
json.dump({"n_cases": n_cases, "n_discs": len(df), "results": results, "level_stratified": strat},
          open("g2_within_mmcsd_results.json", "w"), indent=2, default=float)
print("\nresults -> g2_within_mmcsd_results.json")
print("AUC = discrimination strength (0.5 = none). Stratified p<0.05 with consistent per-level signs = genuine.")
