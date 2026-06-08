"""G2 option A: does COMBINING the geometric disc metrics beat the best single one?

Honest evaluation:
- Features = the geometric metrics only (disc/VB AP ratio, DHI, disc AP width); signal + bulge are
  dead (J23) so excluded. Each is LEVEL-CENTERED (residual vs its level median) to remove the
  mid-cervical confound, exactly as in the stratified within-MMCSD test.
- The combined model is logistic regression evaluated with GROUP K-FOLD by CASE -> discs from the
  same patient never appear in both train and test, and the AUC is computed on OUT-OF-FOLD
  predictions, so the combo cannot inflate its score by fitting its own test data.
- KEEP the combo only if its CV-AUC meaningfully beats the best single metric (~0.62); else the
  single metric stands and we add no complexity.
"""
import glob, os, sys
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score

REPO = "/Users/andrew/Desktop/AUB/Spring 26/EECE 503n/Project/MRI-ReportGenerator"
sys.path.insert(0, REPO)
from services.measurements.context import load_context
from services.measurements.geometric import disc_si_height, disc_height_index, disc_ap_bulge

ROOT = "out_validation_g2"
SEG_COLS = {"2C2-3": "C2-C3", "2C3-4": "C3-C4", "2C4-5": "C4-C5",
            "2C5-6": "C5-C6", "2C6-7": "C6-C7", "2C7-T1": "C7-T1"}
LABELED = set(SEG_COLS.values())
xl = pd.read_excel("data/mmcsd/high_pain_text.xlsx", sheet_name="Sheet1").dropna(subset=["ID"])
xl["ID"] = xl["ID"].astype(int)


def lesion_levels(cid):
    n = int(cid.split("-")[-1]); row = xl[xl["ID"] == n]
    return None if row.empty else {d for c, d in SEG_COLS.items() if c in row and int(row.iloc[0][c]) == 1}


recs = []
for cd in sorted(glob.glob(f"{ROOT}/*")):
    if not os.path.isdir(cd):
        continue
    cid = os.path.basename(cd)
    step2 = glob.glob(f"{cd}/tss/step2_output/*.nii.gz"); inp = glob.glob(f"{cd}/tss/input/*.nii.gz")
    les = lesion_levels(cid)
    if not step2 or not inp or les is None:
        continue
    try:
        ctx = load_context(step2[0], raw_path=inp[0])
        si = disc_si_height.compute(ctx); prior = {"disc_si_height": si}
        dhi = disc_height_index.compute(ctx, prior); prior["disc_height_index"] = dhi
        bul = disc_ap_bulge.compute(ctx, prior)
    except Exception:
        continue
    dhiv = dhi.measurements.get("DHI", {}); arat = bul.measurements.get("disc_vb_ap_ratio", {})
    dwid = si.measurements.get("disc_AP_width", {})
    for lvl in LABELED:
        if lvl not in arat:
            continue
        recs.append({"case": cid, "level": lvl, "lesion": int(lvl in les),
                     "ap_ratio": arat.get(lvl, np.nan), "dhi": dhiv.get(lvl, np.nan),
                     "width": dwid.get(lvl, np.nan)})

df = pd.DataFrame(recs).dropna(subset=["ap_ratio", "dhi", "width"])
# level-center each feature, oriented so HIGHER = more lesion-like (dhi lower=worse -> negate)
for f in ["ap_ratio", "dhi", "width"]:
    df[f + "_c"] = df[f] - df.groupby("level")[f].transform("median")
df["dhi_c"] = -df["dhi_c"]
y = df["lesion"].values
groups = df["case"].values
print(f"{df['case'].nunique()} cases, {len(df)} discs, {int(y.sum())} lesion / {int((1-y).sum())} non-lesion\n")

# --- single-metric AUC (level-centered, no fitting -> no CV needed) ---
print("single metric (level-centered) AUC:")
singles = {}
for f in ["ap_ratio_c", "dhi_c", "width_c"]:
    a = roc_auc_score(y, df[f].values)
    singles[f] = a
    print(f"  {f:12s} {a:.3f}")
best_single = max(singles.values())

# --- combined logistic regression, CASE-grouped CV, out-of-fold AUC ---
X = StandardScaler().fit_transform(df[["ap_ratio_c", "dhi_c", "width_c"]].values)
oof = np.zeros(len(y))
gkf = GroupKFold(n_splits=5)
for tr, te in gkf.split(X, y, groups):
    m = LogisticRegression(max_iter=1000).fit(X[tr], y[tr])
    oof[te] = m.predict_proba(X[te])[:, 1]
combined_auc = roc_auc_score(y, oof)

print(f"\nbest single metric AUC : {best_single:.3f}")
print(f"combined CV AUC (oof)  : {combined_auc:.3f}")
delta = combined_auc - best_single
print(f"delta                  : {delta:+.3f}")
VERDICT = ("KEEP combined (beats single by a meaningful margin)" if delta >= 0.03
           else "NO GAIN -> keep the single disc/VB AP ratio; combined adds complexity without payoff")
print(f"\nVERDICT: {VERDICT}")
