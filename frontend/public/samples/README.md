# Mock viewer samples

The NiiVue viewer (mock mode) loads two files from this folder:

| file | what | source |
|---|---|---|
| `sample_volume_T2.nii.gz` | base sagittal T2 MRI (grayscale background) | Spine-Generic `sub-amu01` (open CC) — `validation_cohort/inputs/` on Drive |
| `sample_mask_tss.nii.gz` | TotalSpineSeg `step2_output` multi-label mask (colored overlay) | `validation_cohort/masks/sub-amu01_T2w/tss/step2_output/` on Drive |

Both are on the same grid (0.8 mm iso, identical affine) → they overlay directly in NiiVue.
The `.nii.gz` files are **gitignored** (loaded at runtime locally; the EEP serves them in `live` mode).

Label map (TSS): `11–17`=C1–C7, `21`=T1, `63–71`=disc levels (`71`=C7-T1); `2`=canal (per the
measurement code's convention — see `docs/contracts/segmentation-viewer-v0.1.md`).

To populate locally: download the two files from Drive into this folder with exactly the names above,
or run the app in `live` mode against the EEP.
