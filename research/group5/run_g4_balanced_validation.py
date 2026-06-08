"""G4 FINAL validation (balanced): SPINEPS endplate-voxel C1 Cobb C3-C7.
Healthy = 12 original (out_sg_spineps) + 15 new (out_validation_g2_spineps_healthy) ~= 27.
Unhealthy = 41 (out_validation_g2_spineps). The healthy arm was the power bottleneck at n=11
(two-sided p=0.070, d=0.76); balancing it should cross p<0.05.
"""
import glob, os, sys
import numpy as np
import nibabel as nib
from scipy.stats import mannwhitneyu

REPO = "/Users/andrew/Desktop/AUB/Spring 26/EECE 503n/Project/MRI-ReportGenerator"
sys.path.insert(0, REPO)
from services.measurements.geometric._endplate_cobb import spineps_endplate_cobb_angle

HEALTHY_DIRS = ["out_sg_spineps", "out_validation_g2_spineps_healthy"]
UNHEALTHY_DIRS = ["out_validation_g2_spineps"]


def load_int(p):
    img = nib.load(p)
    return (np.rint(np.asarray(img.dataobj)).astype(int), tuple(nib.aff2axcodes(img.affine)),
            tuple(float(z) for z in img.header.get_zooms()[:3]))


def cobb_for(dirs, top=3, bottom=7):
    vals = {}
    for d in dirs:
        for f in sorted(glob.glob(f"{d}/*seg-vert_msk.nii.gz")):
            cid = os.path.basename(f).replace("_seg-vert_msk.nii.gz", "").replace("mod-", "").replace("_mod-T2w", "").replace("_T2w", "")
            seg, ax, zo = load_int(f)
            v = spineps_endplate_cobb_angle(seg, ax, zo, top, bottom)
            if v is not None and v == v:
                vals[cid] = float(v)
    return vals


def cohen_d(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    sp = np.sqrt(((len(a)-1)*a.var(ddof=1) + (len(b)-1)*b.var(ddof=1)) / (len(a)+len(b)-2))
    return (a.mean() - b.mean()) / sp if sp > 0 else 0.0


H = cobb_for(HEALTHY_DIRS)
U = cobb_for(UNHEALTHY_DIRS)
h = np.array(list(H.values())); u = np.array(list(U.values()))
print("=" * 70)
print(f"G4 C1 Cobb C3-C7  —  {h.size} healthy vs {u.size} unhealthy  (balanced)")
print("=" * 70)
print(f"  healthy  : median {np.median(h):6.1f}  mean {h.mean():6.1f} +/- {h.std(ddof=1):.1f} deg")
print(f"  unhealthy: median {np.median(u):6.1f}  mean {u.mean():6.1f} +/- {u.std(ddof=1):.1f} deg")
U_stat, p2 = mannwhitneyu(h, u, alternative="two-sided")
p1 = mannwhitneyu(h, u, alternative="greater").pvalue
auc = U_stat / (h.size * u.size)
d = cohen_d(h, u)
print(f"  Mann-Whitney  two-sided p = {p2:.5f}   one-sided p = {p1:.5f}")
print(f"  Cohen d = {d:.2f}   AUC = {auc:.2f}")
print(f"  VERDICT: {'SEPARATES — two-sided p<0.05 (VALIDATED)' if p2 < 0.05 else 'still borderline two-sided'}")
print(f"\n  healthy breakdown: {sum(1 for k in H if k.startswith('sub-'))} subjects")
