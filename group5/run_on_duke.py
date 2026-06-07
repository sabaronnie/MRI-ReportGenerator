"""Run both detectors on the REAL Duke T2 + TotalSpineSeg-generated cord/canal masks.

Lightweight: numpy medians over a 512x512x14 volume — milliseconds, negligible RAM.
The heavy segmentation (TotalSpineSeg) already ran; this just consumes its output.
"""
import nibabel as nib
import numpy as np

from myelomalacia import detect_cord_signal_abnormality, detect_myelopathy_index

B = "/Users/andrew/dev/group5-proto"
img = nib.load(f"{B}/data/duke_000001_T2.nii.gz")
cord_img = nib.load(f"{B}/tss_output/step1_cord/duke_000001_T2.nii.gz")
canal_img = nib.load(f"{B}/tss_output/step1_canal/duke_000001_T2.nii.gz")

mri = img.get_fdata()
cord = (cord_img.get_fdata() > 0.5).astype(int)
canal = canal_img.get_fdata() > 0.5
csf = (canal & (cord == 0)).astype(int)   # CSF = canal minus the cord itself

print(f"T2 image : {img.shape}  axes={nib.aff2axcodes(img.affine)}")
print(f"cord mask: {cord_img.shape}  voxels={int(cord.sum())}  (aligned: {img.shape == cord_img.shape})")
print(f"canal    : voxels={int(canal.sum())}  ->  CSF(canal minus cord) voxels={int(csf.sum())}")


def si_axis(affine):
    for i, c in enumerate(nib.aff2axcodes(affine)):
        if c in ("S", "I"):
            return i
    raise ValueError("no S/I axis")


axis = si_axis(img.affine)

# Context: what does cord/CSF actually look like on this real T2, per level?
ratios = []
for L in range(mri.shape[axis]):
    sl = [slice(None)] * mri.ndim
    sl[axis] = L
    cm = cord[tuple(sl)].astype(bool)
    fm = csf[tuple(sl)].astype(bool)
    if cm.any() and fm.any():
        ratios.append(float(np.median(mri[tuple(sl)][cm]) / np.percentile(mri[tuple(sl)][fm], 75)))
ratios = np.array(ratios)

local = detect_cord_signal_abnormality(mri, cord, level_axis=axis, threshold_ratio=1.3)
weber = detect_myelopathy_index(mri, cord, csf, level_axis=axis, threshold=0.75)

print(f"\nlevel (S/I) axis = {axis}; {len(ratios)} levels contain both cord & CSF")
print(f"cord/CSF ratio on this scan: min={ratios.min():.2f}  median={np.median(ratios):.2f}  max={ratios.max():.2f}")
print(f"  (healthy T2 cord is darker than CSF, so ratios should sit well below 1)")
print(f"\ncord-vs-cord (local)   flags @1.3 : {len(local)}")
print(f"Weber cord-vs-CSF      flags @0.75: {len(weber)}")
