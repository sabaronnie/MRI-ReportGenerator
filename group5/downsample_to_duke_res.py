"""Resolution CONTROL for Group 5.2 healthy-norm validation.

Downsamples a high-res (0.8mm isotropic) Spine-Generic T2w to ~4mm-thick sagittal slices,
mimicking the Duke cervical-T2 acquisition (0.5x0.5x4mm). Run the SAME 5.2 pipeline on both
the native and the downsampled image:
  - if healthy Ha/Hp stays ~0.97 at 4mm  -> Duke's 0.85 is REAL degeneration
  - if healthy Ha/Hp sags toward ~0.85 at 4mm -> the 0.85 is a partial-volume/RESOLUTION artifact
This separates "real disease" from "thick-slice blur" — the conclusive control.

Wraps nibabel.processing.resample_to_output (library, not hand-rolled affine math). The L-R
axis (first RAS axis) is set thick; in-plane kept fine.

Usage: python downsample_to_duke_res.py <T2w.nii.gz> [more ...]   # writes <stem>_4mm.nii.gz
"""
import os
import sys

import nibabel as nib
import nibabel.processing as nproc


def downsample_lr(in_path, out_path, lr_mm=4.0, inplane_mm=0.8):
    """Resample to (L-R = lr_mm, in-plane = inplane_mm) in RAS; returns (shape, zooms)."""
    ds = nproc.resample_to_output(nib.load(in_path), (lr_mm, inplane_mm, inplane_mm), order=1)
    nib.save(ds, out_path)
    return ds.shape, tuple(round(float(z), 2) for z in ds.header.get_zooms())


def main():
    for inp in sys.argv[1:]:
        out = inp[:-7] + "_4mm.nii.gz" if inp.endswith(".nii.gz") else inp + "_4mm.nii.gz"
        shape, zooms = downsample_lr(inp, out)
        print(f"{os.path.basename(out)}  {shape}  {zooms}")


if __name__ == "__main__":
    main()
