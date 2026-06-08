"""G1 LOCAL validations (no new masks needed) — 12 healthy Spine-Generic, C3-C7.

Three deliverables, all on masks already on disk (out_sg/*_step2.nii.gz at 0.8mm and
*_4mm_step2.nii.gz at 4mm through-plane):

  A. TILT RECALIBRATION — the service flags vertebral tilt_deg > 20 deg as an outlier
     (cervical_body_morphometry.TILT_DEG_MAX). Tilt is the angle between the vertebra's
     own PCA superior-inferior axis and the global vertical (same definition as the
     service). We quantify the HEALTHY tilt distribution and propose a recalibrated cut
     (mean + ~2-3 SD / high percentile) so healthy necks stop tripping it.
  B. AP WIDTH + HEIGHT PRECISION — do healthy C3-C7 AP depth and Ha/Hp cluster tightly in
     a plausible mm range? Reports per-level mean/SD/CV; compares AP depth to the ~15-17mm
     cervical norm and Ha/Hp to the cohort 0.94 (vb_hahp_norm_verified).
  C. RESOLUTION ROBUSTNESS — each neck exists at 0.8mm and 4mm. Re-measure Ha/Hp, AP depth
     and Cobb C3-C7 at both and report agreement (mean abs diff) = a test-retest precision
     check that mm metrics survive coarse through-plane.

Reuses the VALIDATED geometry (vertebral_fracture endplate-line fit, cervical_alignment
canal-cut Cobb) — no reinvented math.
"""
import glob, json, os
import numpy as np
import nibabel as nib

from vertebral_fracture import (
    _endplate_fit, endplate_line_heights, extract_body_via_canal,
    extract_vertebral_body, vertebra_axes_from_orientation, mid_sagittal_index,
)
from cervical_alignment import cobb_angle

CERV = {13: "C3", 14: "C4", 15: "C5", 16: "C6", 17: "C7"}
CANAL = 2
SERVICE_TILT_MAX = 20.0  # current cervical_body_morphometry.TILT_DEG_MAX


def load_int(path):
    img = nib.load(path)
    return (np.rint(np.asarray(img.dataobj)).astype(int),
            nib.aff2axcodes(img.affine),
            tuple(float(z) for z in img.header.get_zooms()[:3]))


def vertebra_measures(vb_mask3d, axcodes, zooms):
    """tilt_deg + Ha/Hm/Hp + AP depth (mm) for one isolated vertebral-BODY 3D mask.

    Mirrors vertebral_fracture.measure_vertebra slicing, but also returns the PCA tilt
    (angle of the body SI axis from global vertical) and the PCA AP depth (rng)."""
    m = np.asarray(vb_mask3d, dtype=bool)
    ap, si, lr, anterior = vertebra_axes_from_orientation(axcodes)
    mid = mid_sagittal_index(m, lr)
    sl = [slice(None)] * m.ndim
    sl[lr] = mid
    slice2d = m[tuple(sl)]
    remaining = sorted(a for a in range(m.ndim) if a != lr)
    slice_ap, slice_si = remaining.index(ap), remaining.index(si)
    fit = _endplate_fit(slice2d, ap_axis=slice_ap, si_axis=slice_si,
                        ap_spacing=float(zooms[ap]), si_spacing=float(zooms[si]),
                        anterior=anterior, robust=False)
    if fit is None:
        return None
    u_si = fit["u_si"]                       # unit vector in (ap_mm, si_mm) image frame
    tilt = float(np.degrees(np.arccos(np.clip(abs(u_si[1]), 0.0, 1.0))))
    h = endplate_line_heights(slice2d, ap_axis=slice_ap, si_axis=slice_si,
                              ap_spacing=float(zooms[ap]), si_spacing=float(zooms[si]),
                              anterior=anterior)
    return {"tilt_deg": tilt, "Ha": h["Ha"], "Hm": h["Hm"], "Hp": h["Hp"],
            "ap_depth": float(fit["rng"])}


def measure_case(path):
    seg, ax, zo = load_int(path)
    canal = seg == CANAL
    per = {}
    for lbl, name in CERV.items():
        if not (seg == lbl).any():
            continue
        body = extract_body_via_canal(seg == lbl, canal, ax) if canal.any() else (seg == lbl)
        r = vertebra_measures(body, ax, zo)
        if r and r["Hp"] > 0:
            r["hahp"] = r["Ha"] / r["Hp"]
            per[name] = r
    try:
        cobb = cobb_angle(seg, ax, zo, 13, 17, canal_label=CANAL)
        cobb = float(cobb) if cobb is not None else np.nan
    except Exception:
        cobb = np.nan
    return per, cobb


def subj(path):
    return os.path.basename(path).split("_T2w")[0]


def stats(a):
    a = np.asarray([x for x in a if x == x], float)
    if a.size == 0:
        return {}
    return {"n": int(a.size), "mean": float(a.mean()), "sd": float(a.std(ddof=1)) if a.size > 1 else 0.0,
            "median": float(np.median(a)), "p95": float(np.percentile(a, 95)),
            "p99": float(np.percentile(a, 99)), "max": float(a.max()), "min": float(a.min())}


hi_cases = sorted(glob.glob("out_sg/*_T2w_step2.nii.gz"))
print(f"Healthy cases @0.8mm: {len(hi_cases)}")

res_hi, res_lo = {}, {}
for p in hi_cases:
    s = subj(p)
    res_hi[s] = measure_case(p)
    lo = p.replace("_step2.nii.gz", "_4mm_step2.nii.gz").replace("_T2w_4mm", "_T2w").replace("_T2w_step2", "_T2w_4mm_step2")
    lo = p.replace("_T2w_step2.nii.gz", "_T2w_4mm_step2.nii.gz")
    res_lo[s] = measure_case(lo) if os.path.exists(lo) else (None, np.nan)

# ---------- A. TILT ----------
tilts = [v["tilt_deg"] for per, _ in res_hi.values() for v in per.values()]
ts = stats(tilts)
n_over20 = sum(1 for t in tilts if t > SERVICE_TILT_MAX)
prop_p99 = float(np.ceil(ts["p99"]))
prop_mean3sd = ts["mean"] + 3 * ts["sd"]
print("\n=== A. TILT RECALIBRATION (healthy C3-C7, PCA SI-axis vs vertical) ===")
print(f"  n={ts['n']} vertebrae  median={ts['median']:.1f}  mean={ts['mean']:.1f} +/- {ts['sd']:.1f} deg")
print(f"  p95={ts['p95']:.1f}  p99={ts['p99']:.1f}  max={ts['max']:.1f}")
print(f"  healthy tripping current cut (>{SERVICE_TILT_MAX:.0f} deg): {n_over20}/{ts['n']} "
      f"({100*n_over20/ts['n']:.1f}%)")
print(f"  proposed cut: mean+3SD={prop_mean3sd:.1f} deg | ceil(p99)={prop_p99:.0f} deg")

# ---------- B. AP WIDTH + HEIGHT PRECISION ----------
print("\n=== B. AP DEPTH + HEIGHT PRECISION (healthy, per level) ===")
levelwise = {}
for name in CERV.values():
    ap = stats([per[name]["ap_depth"] for per, _ in res_hi.values() if name in per])
    hahp = stats([per[name]["hahp"] for per, _ in res_hi.values() if name in per])
    ha = stats([per[name]["Ha"] for per, _ in res_hi.values() if name in per])
    hp = stats([per[name]["Hp"] for per, _ in res_hi.values() if name in per])
    levelwise[name] = {"ap_depth": ap, "hahp": hahp, "Ha": ha, "Hp": hp}
    if ap:
        cv = 100 * ap["sd"] / ap["mean"]
        print(f"  {name}: AP depth {ap['mean']:5.1f}+/-{ap['sd']:.1f}mm (CV {cv:4.1f}%)  "
              f"Ha {ha['mean']:4.1f}  Hp {hp['mean']:4.1f}  Ha/Hp {hahp['mean']:.2f}+/-{hahp['sd']:.2f}")
all_ap = stats([per[n]["ap_depth"] for per, _ in res_hi.values() for n in per])
all_hahp = stats([per[n]["hahp"] for per, _ in res_hi.values() for n in per])
print(f"  ALL C3-C7: AP depth {all_ap['mean']:.1f}+/-{all_ap['sd']:.1f}mm (norm ~15-17mm AP); "
      f"Ha/Hp {all_hahp['mean']:.2f}+/-{all_hahp['sd']:.2f} (cohort 0.94+/-0.13)")

# ---------- C. RESOLUTION ROBUSTNESS ----------
print("\n=== C. RESOLUTION ROBUSTNESS (0.8mm vs 4mm through-plane) ===")
def paired(metric_fn):
    hi, lo = [], []
    for s in res_hi:
        if res_lo.get(s) is None:
            continue
        ph, _ = res_hi[s]; pl, _ = res_lo[s]
        for name in CERV.values():
            if name in ph and pl and name in pl:
                a, b = metric_fn(ph[name]), metric_fn(pl[name])
                if a == a and b == b:
                    hi.append(a); lo.append(b)
    return np.array(hi), np.array(lo)

for label, fn in [("Ha/Hp", lambda v: v["hahp"]), ("AP depth (mm)", lambda v: v["ap_depth"]),
                  ("tilt (deg)", lambda v: v["tilt_deg"])]:
    a, b = paired(fn)
    if a.size:
        mad = float(np.mean(np.abs(a - b)))
        bias = float(np.mean(b - a))
        print(f"  {label:16s} n={a.size}  mean|0.8-4mm|={mad:.3f}  bias(4mm-0.8mm)={bias:+.3f}")

# Cobb pairs (per case)
ch, cl = [], []
for s in res_hi:
    if res_lo.get(s) is None:
        continue
    a, b = res_hi[s][1], res_lo[s][1]
    if a == a and b == b:
        ch.append(a); cl.append(b)
ch, cl = np.array(ch), np.array(cl)
if ch.size:
    print(f"  Cobb C3-C7 (deg)  n={ch.size}  mean|0.8-4mm|={np.mean(np.abs(ch-cl)):.2f}  "
          f"bias={np.mean(cl-ch):+.2f}  | 0.8mm mean {ch.mean():.1f} vs 4mm mean {cl.mean():.1f}")

out = {
    "tilt": {**ts, "n_over_current_cut": n_over20, "current_cut": SERVICE_TILT_MAX,
             "proposed_mean_plus_3sd": prop_mean3sd, "proposed_ceil_p99": prop_p99},
    "ap_height_precision": {"per_level": levelwise, "all_ap_depth": all_ap, "all_hahp": all_hahp},
    "resolution": {"cobb_08mm_mean": float(ch.mean()) if ch.size else None,
                   "cobb_4mm_mean": float(cl.mean()) if cl.size else None,
                   "cobb_mad": float(np.mean(np.abs(ch-cl))) if ch.size else None},
}
json.dump(out, open("g1_local_validation_results.json", "w"), indent=2, default=float)
print("\nresults -> g1_local_validation_results.json")
