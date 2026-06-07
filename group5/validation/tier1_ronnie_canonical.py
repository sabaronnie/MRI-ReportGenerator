"""Tier-1 on Ronnie's CANONICAL Standarization-Ronnie code (G1 + G4) over the 12 healthy necks,
via his own orchestrator (run_all). G3 (canal/cord) needs SCT + input_iso + step1_levels -> Colab
only, so it errors gracefully here. Flags are split CLINICAL vs QUALITY per Ronnie's guidance +
the audits (tilt_outlier / *_approximate / *_unreliable / low_confidence / misaligned = quality)."""
import glob
import os
import sys
import statistics
from collections import defaultdict

import numpy as np

RONNIE = "/Users/andrew/Desktop/AUB/Spring 26/EECE 503n/Project/teammate-worktrees/ronnie"
sys.path.insert(0, RONNIE)

from services.measurements.context import load_context
from services.measurements.orchestrator import run_all

QUALITY_MARKERS = ("outlier", "approximate", "unreliable", "low_confidence",
                   "misaligned", "missing", "special_case")  # everything else clinical

def is_quality(flag_name):
    return any(m in flag_name for m in QUALITY_MARKERS)

vals = defaultdict(list)
clin = defaultdict(lambda: [0, 0])   # flag -> [raised, total]
qual = defaultdict(lambda: [0, 0])
comp_status = defaultdict(lambda: defaultdict(int))

for p in sorted(glob.glob("/Users/andrew/dev/group5-proto/out_sg/*_T2w_step2.nii.gz")):
    try:
        ctx = load_context(p)
        report = run_all(ctx)
    except Exception as e:
        print(f"  run FAIL {os.path.basename(p)}: {type(e).__name__}: {e}")
        continue
    for name, info in report.get("components", {}).items():
        comp_status[name][info.get("status", "?")] += 1
    for mk, per in report.get("measurements", {}).items():
        for lvl, v in per.items():
            if isinstance(v, (int, float)) and np.isfinite(v):
                vals[mk].append(float(v))
    for fk, per in report.get("flags", {}).items():
        tgt = qual if is_quality(fk) else clin
        for lvl, raised in per.items():
            tgt[fk][1] += 1
            tgt[fk][0] += int(bool(raised))

print("\n=== component status across 12 healthy necks (ok / error) ===")
for name, st in sorted(comp_status.items()):
    print(f"  {name:26s} " + " ".join(f"{k}={v}" for k, v in st.items()))

print("\n=== MEASUREMENTS (pooled): mean ± SD [min, max] (n) ===")
for mk, vv in sorted(vals.items()):
    print(f"  {mk:26s} {statistics.mean(vv):7.2f} ± {statistics.pstdev(vv):5.2f}  "
          f"[{min(vv):6.1f}, {max(vv):6.1f}]  (n={len(vv)})")

print("\n=== CLINICAL flags on HEALTHY (these SHOULD be ~0) ===")
for fk, (r, t) in sorted(clin.items()):
    print(f"  {fk:30s} {r:3d}/{t:3d} = {100*r/t:4.0f}%")
print("\n=== QUALITY/caution flags on HEALTHY (NOT clinical findings — measurement confidence) ===")
for fk, (r, t) in sorted(qual.items()):
    print(f"  {fk:30s} {r:3d}/{t:3d} = {100*r/t:4.0f}%")
