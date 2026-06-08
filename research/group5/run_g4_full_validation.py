"""G4 FULL validation: SPINEPS endplate-voxel C1 Cobb, 12 healthy vs ~41 unhealthy MMCSD.

The C3-C7 Cobb was method-validated (healthy +15.2 = literature) but discrimination was underpowered
at n=10 (p=0.13, d=0.91). With ~41 unhealthy SPINEPS masks now segmented, re-test for separation.
Healthy seg-vert: out_sg_spineps/. Unhealthy seg-vert: out_validation_g2_spineps/.
"""
import glob, os, sys
import numpy as np
import nibabel as nib
from scipy.stats import mannwhitneyu

REPO = "/Users/andrew/Desktop/AUB/Spring 26/EECE 503n/Project/MRI-ReportGenerator"
sys.path.insert(0, REPO)
from services.measurements.geometric._endplate_cobb import spineps_endplate_cobb_angle


def load_int(path):
    img = nib.load(path)
    return (np.rint(np.asarray(img.dataobj)).astype(int),
            tuple(nib.aff2axcodes(img.affine)),
            tuple(float(z) for z in img.header.get_zooms()[:3]))


def cobb_for(folder, top=3, bottom=7):
    vals = {}
    for f in sorted(glob.glob(f"{folder}/*seg-vert_msk.nii.gz")):
        cid = os.path.basename(f).replace("_seg-vert_msk.nii.gz", "").replace("mod-", "")
        seg, ax, zo = load_int(f)
        v = spineps_endplate_cobb_angle(seg, ax, zo, top, bottom)
        if v is not None and v == v:
            vals[cid] = float(v)
    return vals


def cohen_d(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    sp = np.sqrt(((len(a)-1)*a.var(ddof=1) + (len(b)-1)*b.var(ddof=1)) / (len(a)+len(b)-2))
    return (a.mean() - b.mean()) / sp if sp > 0 else 0.0


for label, (top, bottom) in [("C3-C7 (validated span)", (3, 7)), ("C2-C7", (2, 7))]:
    H = cobb_for("out_sg_spineps", top, bottom)
    U = cobb_for("out_validation_g2_spineps", top, bottom)
    h = np.array(list(H.values())); u = np.array(list(U.values()))
    print("=" * 70)
    print(f"G4 SPINEPS C1 Cobb {label}: {h.size} healthy vs {u.size} unhealthy")
    print("=" * 70)
    if h.size and u.size:
        U_stat, p = mannwhitneyu(h, u, alternative="two-sided")
        auc = U_stat / (h.size * u.size)           # AUC for healthy > unhealthy (more lordotic)
        d = cohen_d(h, u)
        print(f"  healthy : median {np.median(h):6.1f}  mean {h.mean():6.1f} +/- {h.std(ddof=1):.1f} deg (n={h.size})")
        print(f"  unhealthy: median {np.median(u):6.1f}  mean {u.mean():6.1f} +/- {u.std(ddof=1):.1f} deg (n={u.size})")
        print(f"  Mann-Whitney p = {p:.5f}   Cohen d = {d:.2f}   AUC = {auc:.2f}")
        print(f"  VERDICT: {'SEPARATES (p<0.05)' if p < 0.05 else 'still not significant'}")
    print()
