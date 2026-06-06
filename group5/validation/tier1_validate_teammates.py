"""Tier-1 validation of the teammates' Groups 1-4 measurement code: run it on the 12 HEALTHY
Spine-Generic necks we already have, pool the distributions, and compare to published norms.
Read-only: imports and RUNS their code from the worktree, never edits it. Bypasses the
orchestrator (so no prometheus dep) by calling compute(ctx, prior) directly in dependency order.
"""
import glob
import os
import sys
from collections import defaultdict
import statistics

import numpy as np

WORKTREE = "/Users/andrew/Desktop/AUB/Spring 26/EECE 503n/Project/teammate-worktrees/mohammad/services"
sys.path.insert(0, WORKTREE)

from measurements.context import load_context
from measurements.geometric import (
    cervical_body_morphometry as morph,
    spondylolisthesis as spondy,
    disc_si_height as dheight,
    disc_height_index as dhi,
    disc_ap_bulge as bulge,
)
from measurements.signal import pfirrmann_grade as pfirr

# dependency-safe run order (morphometry -> spondy; disc_height -> dhi/bulge/pfirrmann)
ORDER = [morph, dheight, dhi, bulge, spondy, pfirr]

import sys as _s
STEP2 = sorted(glob.glob(_s.argv[1] if len(_s.argv)>1 else "/Users/andrew/dev/group5-proto/out_sg/*_T2w_step2.nii.gz"))
RAW = "/Users/andrew/dev/data-multi-subject/{sub}/anat/{sub}_T2w.nii.gz"

vals = defaultdict(list)            # (NAME, measurement_key) -> pooled values across levels x subjects
flag_raised = defaultdict(int)
flag_total = defaultdict(int)
n_ok = defaultdict(int)

for p in STEP2:
    sub = os.path.basename(p).split("_T2w")[0]
    raw = RAW.format(sub=sub)
    try:
        ctx = load_context(p, raw if os.path.exists(raw) else None)
    except Exception as e:
        print(f"  ctx FAIL {sub}: {e}")
        continue
    prior = {}
    for mod in ORDER:
        try:
            res = mod.compute(ctx, prior)
            prior[mod.NAME] = res
            n_ok[mod.NAME] += 1
            for mk, per in res.measurements.items():
                for lvl, v in per.items():
                    if v is not None and np.isfinite(v):
                        vals[(mod.NAME, mk)].append(float(v))
            for fk, per in res.flags.items():
                for lvl, raised in per.items():
                    flag_total[(mod.NAME, fk)] += 1
                    flag_raised[(mod.NAME, fk)] += int(bool(raised))
        except Exception as e:
            print(f"  {mod.NAME} FAIL {sub}: {type(e).__name__}: {e}")

print(f"\n=== ran on {len(STEP2)} healthy Spine-Generic necks; components OK per case: "
      + ", ".join(f"{m.NAME.split('_')[0]}={n_ok[m.NAME]}" for m in ORDER))

print("\n=== MEASUREMENTS (pooled across levels x subjects): mean ± SD [min, max] (n) ===")
for (name, mk), vv in sorted(vals.items()):
    mean = statistics.mean(vv); sd = statistics.pstdev(vv)
    print(f"  {name:26s} {mk:14s} {mean:6.2f} ± {sd:5.2f}  [{min(vv):5.1f}, {max(vv):5.1f}]  (n={len(vv)})")

print("\n=== FLAG RATES on HEALTHY (raised / total level-checks; on healthy these are false positives) ===")
for (name, fk), tot in sorted(flag_total.items()):
    r = flag_raised[(name, fk)]
    print(f"  {name:26s} {fk:22s} {r:3d}/{tot:3d} = {100*r/tot:4.0f}%")
