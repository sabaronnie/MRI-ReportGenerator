"""G2 disc validation: run Mohammad's disc chain (services) on all 22 cohort masks.
Geometric disc measures need only the TSS seg (no raw): disc SI height, DHI, AP bulge.
Also dumps the DHI intermediates to chase Mohammad's denominator concern (healthy DHI ~0.26 vs his 0.49-0.57).
"""
import glob, os, sys
import numpy as np

REPO = "/Users/andrew/Desktop/AUB/Spring 26/EECE 503n/Project/MRI-ReportGenerator"
sys.path.insert(0, REPO)
from services.measurements.context import load_context, MeasurementError
from services.measurements.geometric import disc_si_height, disc_height_index, disc_ap_bulge

ROOT = "out_validation"


def cohort(cid):
    return "unhealthy" if cid.startswith("mmcsd") else "healthy"


def run_case(step2):
    ctx = load_context(step2)
    si = disc_si_height.compute(ctx)
    prior = {"disc_si_height": si}
    dhi = disc_height_index.compute(ctx, prior)
    bulge = disc_ap_bulge.compute(ctx, prior)
    return si, dhi, bulge


agg = {"healthy": {"dhi": [], "bulge": [], "reduced": 0, "ndisc": 0, "bulge_pos": 0},
       "unhealthy": {"dhi": [], "bulge": [], "reduced": 0, "ndisc": 0, "bulge_pos": 0}}

print("=" * 90)
print("G2 DISC — per case (DHI + AP bulge); intermediates for the first healthy case")
print("=" * 90)
shown_intermediate = False
for cd in sorted(glob.glob(f"{ROOT}/*")):
    if not os.path.isdir(cd):
        continue
    cid = os.path.basename(cd); grp = cohort(cid)
    f = glob.glob(f"{cd}/tss/step2_output/*.nii.gz")
    if not f:
        continue
    try:
        si, dhi, bulge = run_case(f[0])
    except MeasurementError as e:
        print(f"{cid:16s} [{grp}] ERROR: {e}"); continue
    dhis = dhi.measurements.get("DHI", {})
    reduced = dhi.flags.get("reduced_dhi", {})
    bulges = bulge.measurements.get("posterior_bulge_mm", bulge.measurements.get("disc_vb_ap_ratio", {}))
    dvals = [v for v in dhis.values() if v == v]
    bvals = [v for v in bulges.values() if v == v]
    agg[grp]["dhi"] += dvals
    agg[grp]["bulge"] += bvals
    agg[grp]["reduced"] += sum(1 for x in reduced.values() if x)
    agg[grp]["ndisc"] += len(dhis)
    bpos = bulge.flags.get("disc_bulge_present", {})
    agg[grp]["bulge_pos"] += sum(1 for x in bpos.values() if x)
    print(f"{cid:16s} [{grp:9s}] DHI med {np.median(dvals) if dvals else float('nan'):.2f} "
          f"reduced {sum(1 for x in reduced.values() if x)}/{len(dhis)} | "
          f"bulge med {np.median(bvals) if bvals else float('nan'):.2f}")
    if grp == "healthy" and not shown_intermediate:
        print("   -- DHI intermediates (chasing the denominator):")
        inter = dhi.intermediate
        for k in list(inter)[:1]:
            pass
        # dump per-level DHI + any VB-height intermediates exposed
        print("   DHI per level:", {k: round(v, 2) for k, v in dhis.items()})
        for ik, iv in dhi.intermediate.items():
            if isinstance(iv, dict):
                print(f"   intermediate[{ik}]:", {k: (round(v, 2) if isinstance(v, (int, float)) else v) for k, v in list(iv.items())[:6]})
        shown_intermediate = True

print("\n" + "=" * 90)
print("COHORT SUMMARY")
print("=" * 90)
for grp in ("healthy", "unhealthy"):
    a = agg[grp]
    dhi = np.array(a["dhi"]); bulge = np.array(a["bulge"])
    print(f"\n[{grp.upper()}]")
    if dhi.size:
        print(f"   DHI         median {np.median(dhi):.2f} mean {dhi.mean():.2f} range [{dhi.min():.2f},{dhi.max():.2f}]  | reduced_dhi (<0.30): {a['reduced']}/{a['ndisc']} ({100*a['reduced']/max(a['ndisc'],1):.0f}%)")
    if bulge.size:
        print(f"   bulge metric median {np.median(bulge):.2f} mean {bulge.mean():.2f} range [{bulge.min():.2f},{bulge.max():.2f}]  | bulge_present: {a['bulge_pos']}/{a['ndisc']}")
