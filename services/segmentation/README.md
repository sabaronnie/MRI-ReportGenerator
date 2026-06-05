# Segmentation Services

This folder now contains two segmentation-stage services:

- `services.segmentation.app` — input handling + TotalSpineSeg
- `services.segmentation.sct_app` — SCT canal + cord segmentation on top of the TotalSpineSeg zip

## Install

System binaries (not pip-installable):

- **dcm2niix** — DICOM → NIfTI converter. Install from <https://github.com/rordenlab/dcm2niix> (macOS: `brew install dcm2niix`).
- **CUDA-capable GPU** — TotalSpineSeg uses nnU-Net v2; CPU runs are very slow. T4 / 8 GB VRAM is enough.

Python dependencies:

```bash
pip install -r services/segmentation/requirements.txt
pip install pytest  # dev only, for running the test suite
```

The first TotalSpineSeg invocation downloads model weights (~hundreds of MB) into the user's nnU-Net data directory. Subsequent runs reuse them.

## Run TotalSpineSeg on one case (CLI)

```bash
# from the MRI-ReportGenerator/ directory
python -m services.segmentation.cli /path/to/scan.nii.gz /tmp/segwork
# or for a DICOM folder
python -m services.segmentation.cli /path/to/dicom_folder /tmp/segwork
```

Outputs land under `/tmp/segwork/tss_output/`:

- `step2_output/*.nii.gz` — final per-level segmentation (use this for measurements)
- `step1_levels/*.nii.gz` — single-voxel disc-level markers (feed to SCT for cord work)

## Run SCT segmentations on one case (CLI)

```bash
# input must already be 1 mm isotropic, e.g. the TotalSpineSeg input_iso output
python -m services.segmentation.sct_cli /path/to/input_iso.nii.gz /tmp/sctwork
```

Outputs land under `/tmp/sctwork/`:

- `canal/prediction.nii.gz` — SCT canal mask
- `spinalcord/prediction.nii.gz` — SCT cord mask

## Run as Flask services

```bash
flask --app services.segmentation.app run --host 0.0.0.0 --port 8080
flask --app services.segmentation.sct_app run --host 0.0.0.0 --port 8082
```

### Endpoints

- `GET /healthz` — liveness check.
- `POST /segment` — multipart upload, field `file` is either a `.nii`/`.nii.gz` or a `.zip` of a DICOM folder. Returns a `.zip` with `step2_output.nii.gz`, `step1_levels.nii.gz`, optionally `input_iso.nii.gz`, plus both `manifest.txt` and `segmentation_run_manifest.json`.
- `POST /segment-sct` — multipart upload of the zip returned by `/segment`. Returns a new zip containing the original TotalSpineSeg artifacts plus:
  - `sct_canal_seg.nii.gz`
  - `sct_spinalcord_seg.nii.gz`
  - `sct_segmentation_manifest.json`

Optional form field: `iso=false` to disable TotalSpineSeg's `--iso` 1mm-isotropic resampling.

```bash
curl -X POST -F "file=@scan.nii.gz" http://localhost:8080/segment -o out.zip
curl -X POST -F "file=@out.zip" http://localhost:8082/segment-sct -o out_sct.zip
```

## Tests

```bash
pytest services/segmentation/tests
```

The suite uses synthetic NIfTI (no patient data) and validates only the input-handling logic. End-to-end TotalSpineSeg verification must be done locally on a real case (CLAUDE.md medical-AI rule #5).

## License notes

- TotalSpineSeg — LGPLv3 (dynamic CLI invocation; do not statically embed)
- nnU-Net v2 — Apache 2.0
- dcm2niix — MIT
- nibabel — BSD
- Flask — BSD
