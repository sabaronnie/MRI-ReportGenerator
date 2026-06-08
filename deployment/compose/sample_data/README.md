# sample_data (mounted into the EEP at /data/samples)

Place here (gitignored):
- `sample_volume_T2.nii.gz` — base sagittal T2 (NiiVue background). Spine-Generic `sub-amu01`.
- `sample_mask_tss.nii.gz` — TotalSpineSeg `step2_output` (NiiVue overlay).
- `segmentation.zip` — a zip containing `step2_output.nii.gz` (enables real measurements-IEP calls on upload).

Source: Drive `validation_cohort/` (inputs/ + masks/.../tss/step2_output/). Same files the frontend uses under
`frontend/public/samples/`.
