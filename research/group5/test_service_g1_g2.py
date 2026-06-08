"""Service-level test harness for the G1/G2 fixes — runs the ACTUAL repo service
modules over real healthy + unhealthy TSS masks (out_validation: 12 healthy sub-*,
10 unhealthy mmcsd-*). Prints the metrics each fix is supposed to move, so we can
keep-or-revert on evidence.

Usage: .venv/bin/python test_service_g1_g2.py
"""
import glob, os, sys
import numpy as np
import nibabel as nib

REPO = "/Users/andrew/Desktop/AUB/Spring 26/EECE 503n/Project/MRI-ReportGenerator"
sys.path.insert(0, REPO)
from services.measurements.context import load_context
from services.measurements.geometric import cervical_body_morphometry as morph

ROOT = "out_validation"


def cohort(cid):
    return "unhealthy" if cid.startswith("mmcsd") else "healthy"


def run():
    by = {"healthy": [], "unhealthy": []}
    for cd in sorted(glob.glob(f"{ROOT}/*")):
        if not os.path.isdir(cd):
            continue
        cid = os.path.basename(cd)
        step2 = glob.glob(f"{cd}/tss/step2_output/*.nii.gz")
        if not step2:
            continue
        try:
            ctx = load_context(step2[0])
            res = morph.compute(ctx)
        except Exception as e:
            print(f"  !! {cid}: {type(e).__name__}: {e}")
            continue
        tilt = res.measurements["tilt_deg"]
        ha = res.measurements["H_anterior"]
        hp = res.measurements["H_posterior"]
        apw = res.measurements["AP_width"]
        tflags = res.flags["tilt_outlier"]
        levels = list(tilt.keys())
        hahp = [ha[l] / hp[l] for l in levels if hp.get(l, 0) > 0]
        by[cohort(cid)].append({
            "cid": cid,
            "tilts": [tilt[l] for l in levels],
            "tilt_flagged": sum(1 for l in levels if tflags.get(l)),
            "n_levels": len(levels),
            "hahp": hahp,
            "apw": [apw[l] for l in levels if apw.get(l) == apw.get(l)],
        })
    return by


def summarize(by):
    for grp in ("healthy", "unhealthy"):
        cases = by[grp]
        tilts = [t for c in cases for t in c["tilts"]]
        flagged = sum(c["tilt_flagged"] for c in cases)
        nlev = sum(c["n_levels"] for c in cases)
        hahp = [r for c in cases for r in c["hahp"]]
        apw = [a for c in cases for a in c["apw"]]
        print(f"\n[{grp}] {len(cases)} cases, {nlev} levels")
        if tilts:
            print(f"  tilt: median {np.median(tilts):.1f}  mean {np.mean(tilts):.1f}+/-{np.std(tilts,ddof=1):.1f} deg")
        print(f"  tilt_outlier flags: {flagged}/{nlev} ({100*flagged/max(nlev,1):.0f}%)  [cut={morph.TILT_DEG_MAX:.0f} deg]")
        if hahp:
            print(f"  Ha/Hp: median {np.median(hahp):.2f}  mean {np.mean(hahp):.2f}+/-{np.std(hahp,ddof=1):.2f}")
        if apw:
            print(f"  AP_width: median {np.median(apw):.1f}  mean {np.mean(apw):.1f}+/-{np.std(apw,ddof=1):.1f} mm")
    # G1 expectation: healthy Ha/Hp ~0.90-0.95, NOT lower than unhealthy by a wide margin
    hh = [r for c in by["healthy"] for r in c["hahp"]]
    uu = [r for c in by["unhealthy"] for r in c["hahp"]]
    if hh and uu:
        print(f"\n  Ha/Hp healthy {np.median(hh):.2f} vs unhealthy {np.median(uu):.2f} "
              f"({'OK: healthy >= unhealthy' if np.median(hh) >= np.median(uu) - 0.02 else 'BACKWARDS: healthy < unhealthy'})")


if __name__ == "__main__":
    print("=" * 70)
    print(f"SERVICE G1 morphometry — TILT_DEG_MAX={morph.TILT_DEG_MAX}")
    print("=" * 70)
    summarize(run())
