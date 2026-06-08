"""MASTER validation: all groups on 22 cohort necks (12 healthy + 10 MMCSD unhealthy).
Emits: per-case + cohort table, Mann-Whitney U separation p-values, JSON, and figures/ for the paper.
Reproduces G1 (Ha/Hp), G3 (canal/cord/SAC from SCT CSVs), G4 (canal-cut + SPINEPS C1), G2 (DHI/bulge).
"""
import csv, glob, json, os, re, sys
import numpy as np
import nibabel as nib
from scipy.stats import mannwhitneyu

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from vertebral_fracture import cervical_deformity_flag, extract_body_via_canal, measure_vertebra
from cervical_alignment import cobb_angle, spineps_endplate_cobb_angle

REPO = "/Users/andrew/Desktop/AUB/Spring 26/EECE 503n/Project/MRI-ReportGenerator"
sys.path.insert(0, REPO)
from services.measurements.context import load_context, MeasurementError
from services.measurements.geometric import disc_si_height, disc_height_index, disc_ap_bulge

ROOT = "out_validation"
SP_HEALTHY = "out_sg_spineps"
SP_UNHEALTHY = "out_validation_spineps"
CERV = {13: "C3", 14: "C4", 15: "C5", 16: "C6", 17: "C7"}
CANAL = 2
FIG = "figures"; os.makedirs(FIG, exist_ok=True)


def cohort(cid):
    return "unhealthy" if cid.startswith("mmcsd") else "healthy"


def subj_key(cid):
    return cid.replace("_T2w", "").replace("_mod-T2w", "").replace("mod-", "")


def load_int(path):
    img = nib.load(path)
    return np.rint(np.asarray(img.dataobj)).astype(int), nib.aff2axcodes(img.affine), tuple(float(z) for z in img.header.get_zooms()[:3])


# index SPINEPS seg-vert by subject key
spineps_idx = {}
for f in glob.glob(f"{SP_HEALTHY}/*seg-vert_msk.nii.gz") + glob.glob(f"{SP_UNHEALTHY}/*seg-vert_msk.nii.gz"):
    spineps_idx[subj_key(re.sub(r"_seg-vert_msk.*", "", os.path.basename(f)))] = f


def g3_from_csv(cd):
    out = {}
    for task, key in [("canal", "canal_AP"), ("spinalcord", "cord_AP")]:
        p = f"{cd}/sct/{task}_perslice.csv"
        if not os.path.exists(p):
            continue
        per = {}
        for row in csv.DictReader(open(p)):
            vl, ap = row.get("VertLevel", "").strip(), row.get("MEAN(diameter_AP)", "").strip()
            if vl and ap:
                try:
                    lv = int(float(vl))
                    if 3 <= lv <= 7:
                        per.setdefault(lv, []).append(float(ap))
                except ValueError:
                    pass
        out[key] = {lv: float(np.mean(v)) for lv, v in per.items()}
    out["SAC"] = {lv: out["canal_AP"][lv] - out["cord_AP"][lv]
                  for lv in set(out.get("canal_AP", {})) & set(out.get("cord_AP", {}))}
    return out


rows = []
for cd in sorted(glob.glob(f"{ROOT}/*")):
    if not os.path.isdir(cd):
        continue
    cid = os.path.basename(cd); grp = cohort(cid)
    rec = {"case": cid, "cohort": grp}
    step2 = glob.glob(f"{cd}/tss/step2_output/*.nii.gz")
    if not step2:
        continue
    seg, ax, zo = load_int(step2[0])
    canal = seg == CANAL
    # G1 Ha/Hp
    hahp = []
    for lbl in CERV:
        if (seg == lbl).any():
            body = extract_body_via_canal(seg == lbl, canal, ax) if canal.any() else (seg == lbl)
            h = measure_vertebra(body, ax, zo, isolate_body=not canal.any())
            if h["Hp"] > 0:
                hahp.append(float(h["Ha"] / h["Hp"]))
    rec["hahp_min"] = min(hahp) if hahp else np.nan
    rec["hahp_flags"] = int(sum(cervical_deformity_flag(r)["flagged"] for r in hahp))
    # G4 canal-cut + C1
    try:
        c = cobb_angle(seg, ax, zo, 13, 17, canal_label=CANAL)
        rec["cobb_canalcut"] = float(c) if c is not None else np.nan
    except Exception:
        rec["cobb_canalcut"] = np.nan
    spv = spineps_idx.get(subj_key(cid))
    rec["cobb_c1"] = np.nan
    if spv:
        sseg, sax, szo = load_int(spv)
        v = spineps_endplate_cobb_angle(sseg, sax, szo, 3, 7)
        rec["cobb_c1"] = float(v) if v is not None and not np.isnan(v) else np.nan
    # G3
    g3 = g3_from_csv(cd)
    rec["canal_min"] = min(g3.get("canal_AP", {}).values(), default=np.nan)
    rec["cord_min"] = min(g3.get("cord_AP", {}).values(), default=np.nan)
    rec["sac_min"] = min(g3.get("SAC", {}).values(), default=np.nan)
    # G2 disc
    try:
        ctx = load_context(step2[0])
        si = disc_si_height.compute(ctx); prior = {"disc_si_height": si}
        dhi = disc_height_index.compute(ctx, prior).measurements.get("DHI", {})
        bul = disc_ap_bulge.compute(ctx, prior).measurements.get("posterior_bulge_mm", {})
        dvals = [v for v in dhi.values() if v == v]; bvals = [v for v in bul.values() if v == v]
        rec["dhi_med"] = float(np.median(dvals)) if dvals else np.nan
        rec["bulge_med"] = float(np.median(bvals)) if bvals else np.nan
    except Exception:
        rec["dhi_med"] = rec["bulge_med"] = np.nan
    rows.append(rec)

# ---- aggregate + stats ----
H = [r for r in rows if r["cohort"] == "healthy"]
U = [r for r in rows if r["cohort"] == "unhealthy"]


def col(group, k):
    return np.array([r[k] for r in group if r.get(k) == r.get(k)], float)


METRICS = [
    ("canal_min", "G3 canal AP min (mm)", "lower=worse"),
    ("sac_min", "G3 SAC min (mm)", "lower=worse"),
    ("cord_min", "G3 cord AP min (mm)", "lower=worse"),
    ("cobb_c1", "G4 Cobb C1 C3-C7 (deg)", "lower=less lordotic"),
    ("hahp_min", "G1 Ha/Hp min", "lower=worse"),
    ("dhi_med", "G2 DHI median", "lower=worse"),
    ("bulge_med", "G2 bulge median (mm)", "higher=worse"),
]

print("=" * 78)
print(f"MASTER VALIDATION — {len(H)} healthy vs {len(U)} unhealthy")
print("=" * 78)
summary = {}
for k, label, _ in METRICS:
    h, u = col(H, k), col(U, k)
    p = mannwhitneyu(h, u, alternative="two-sided").pvalue if h.size and u.size else np.nan
    summary[k] = {"healthy_median": float(np.median(h)) if h.size else None,
                  "unhealthy_median": float(np.median(u)) if u.size else None,
                  "healthy_n": int(h.size), "unhealthy_n": int(u.size), "mannwhitney_p": float(p)}
    print(f"{label:28s} H={np.median(h):6.2f} (n={h.size})  U={np.median(u):6.2f} (n={u.size})  p={p:.4f}")
    # figure
    fig, axp = plt.subplots(figsize=(4, 4))
    for i, (g, c) in enumerate([(h, "#2E86C1"), (u, "#E74C3C")]):
        x = np.random.default_rng(i).normal(i, 0.06, size=g.size)
        axp.scatter(x, g, c=c, alpha=0.75, s=36, edgecolor="k", linewidth=0.4)
        if g.size:
            axp.plot([i - 0.2, i + 0.2], [np.median(g)] * 2, c="k", lw=2)
    axp.set_xticks([0, 1]); axp.set_xticklabels([f"healthy\n(n={h.size})", f"unhealthy\n(n={u.size})"])
    axp.set_title(f"{label}\nMann-Whitney p={p:.3g}", fontsize=10)
    axp.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(f"{FIG}/{k}.png", dpi=130); plt.close(fig)

json.dump({"rows": rows, "summary": summary}, open("validation_master_results.json", "w"), indent=2, default=float)
print(f"\nfigures -> {FIG}/  | results -> validation_master_results.json")
print("\nG1 compression flags: H", sum(r['hahp_flags'] for r in H), "/", sum(1 for r in H for _ in [0]),
      "cases | U", sum(r['hahp_flags'] for r in U), "cases")
