# Measurements Service (IEP2)

Flask service running Phase 3 measurement components on a TotalSpineSeg `step2_output`. Each measurement is its own component module; the orchestrator runs them in dependency order, instruments every call with Prometheus, and returns a flat report.

Phase 4 / Group 6 assessement now lives in the sibling package [`services/assessement/`](../assessement/), which this service imports to attach assessed rows to the raw measurement output. Group 5 runtime code now lives under [`services/measurements/group5/`](./group5/) and is integrated into the measurements service rather than only existing as standalone sidecar code.

## Components currently registered

| Component | Phase | Outputs |
|---|---|---|
| `cervical_body_morphometry` | 3A.1 + 3A.2 | `AP_width`, `H_anterior`, `H_middle`, `H_posterior`, `tilt_deg` per cervical vertebra |
| `spondylolisthesis` | 3A.3 | `spondy_slip_mm`, `spondy_pct_of_lower_AP` per adjacent vertebral pair |
| `c3c7_cobb_angle` | 4.1 | `Cobb_C3_C7` from reused `cervical_body_morphometry` AI/PI corners in the common PA-SI frame |
| `lordosis_classification` | 4.2 | Derived `lordotic` / `straightened / low lordosis` / `kyphotic` from `Cobb_C3_C7`, with supine-MRI caveat |
| `segmental_angles` | 4.3 | `segmental_angle` for `C3-C4` through `C6-C7` from reused inferior/superior endplate corners in the common PA-SI frame |
| `posterior_tangent_angle` | 4.4 | `posterior_tangent_C3_C7` from reused `PS/PI` posterior-wall corners, plus Cobb divergence metadata for cross-checking |
| `group5_fracture_screen` | 5.2 | `vb_hahp_ratio` vertebral-body compression/deformity screen for C3-C7, plus a Group 5 findings contract in metadata |
| `functional_canal_ap` | 3.1 | `dural_sac_AP_min` per cervical vertebra via SCT `canal` + `sct_process_segmentation` |
| `cord_ap` | 3.2 | `cord_AP` per cervical vertebra via SCT `spinalcord`, aligned to `functional_canal_ap` focal slices |
| `sac` | 3.3 | `SAC` per cervical vertebra by same-slice subtraction of `dural_sac_AP_min - cord_AP` |

Each component file lives under [services/measurements/](.) and exports `NAME`, `DEPENDS_ON`, and `compute(ctx, prior)`. Add a new measurement by registering it in `orchestrator.COMPONENTS`.

## Install

```bash
pip install -r services/measurements/requirements.txt
pip install pytest      # dev only
```

## Run as a Flask service

```bash
PORT=8081 flask --app services.measurements.app run --host 0.0.0.0 --port 8081
```

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz` | Liveness probe (k8s `livenessProbe`) |
| GET | `/readyz`  | Readiness probe (k8s `readinessProbe`); confirms every registered component has a `compute` callable |
| GET | `/metrics` | Prometheus scrape endpoint |
| POST | `/measure` | Run measurement components on an uploaded segmentation zip |

The `POST /measure` body is the same zip the segmentation IEP returns: at minimum a `step2_output.nii.gz`. Components backed by SCT require `step1_levels.nii.gz` and either:

- `sct_canal_seg.nii.gz` / `sct_spinalcord_seg.nii.gz` from the new SCT segmentation service, or
- `input_iso.nii.gz` so the measurement service can fall back to running SCT itself.

Optional repeated form field `measurement=<name>` picks a subset of components.
Optional case/reporting fields such as `job_id`, `case_id`, `sex`, `age_years`,
`height_cm`, `report_language`, `include_appendix`, and repeated `disclaimer`
can be supplied so the response is immediately usable as the assessement-to-
reporting handoff contract.

```bash
curl -X POST -F "file=@segmentation.zip" http://localhost:8081/measure
# only AP-width / SI-height pipeline:
curl -X POST -F "file=@segmentation.zip" -F "measurement=cervical_body_morphometry" http://localhost:8081/measure
```

Response:

```json
{
  "contract_version": "1.0",
  "case": {
    "job_id": "scan_8f3a2c1d",
    "case_id": "scan_8f3a2c1d",
    "submitted_at": "2026-06-07T14:10:00Z",
    "patient_context": {"sex": "male", "age_years": 42, "height_cm": 178.0},
    "source_file": {"filename": "segmentation.zip"}
  },
  "manifest": {"seg_shape": [25, 60, 50], "voxel_spacing_mm": [1.0, 1.0, 1.0], "labels_present": [...]},
  "components": {"cervical_body_morphometry": {"status": "ok", "duration_s": 0.012, "metadata": {"levels": ["C3", "..."]}}},
  "measurements": {
    "AP_width": {"C3": 19.0, "C4": 19.5},
    "SAC": {"C5": 2.7}
  },
  "flags": {
    "ap_width_outlier": {"C3": false},
    "sac_high_risk": {"C5": true}
  },
  "assessements": {
    "measurements": [
      {
        "measurement": "SAC",
        "level": "C5",
        "value": 2.7,
        "unit": "mm",
        "status": "outside_reference",
        "severity": "high_risk",
        "flag": true,
        "demographics_used": {},
        "quality_flags": [],
        "caveat": "Derived metric; confirm with segmentation QC."
      }
    ],
    "syndromes": []
  },
  "report_context": {
    "modality": "cervical_sagittal_mri",
    "report_language": "en",
    "disclaimers": [
      "This is a research tool, not a medical device. Not for clinical diagnosis.",
      "Measurements acquired on supine MRI; functional radiographs may differ."
    ],
    "include_appendix": true
  }
}
```

`assessements.measurements` is the first Phase 4 scaffold: a standard per-measurement container that keeps the API stable while the full threshold engine is still being built. `assessements.syndromes` carries provisional advisory patterns such as the myelopathy combination rule. The current behavior is intentionally conservative:

- values with a non-quality pathology flag from their source component are marked `outside_reference`
- values without threshold logic yet are marked `review_only`
- citation provenance is intentionally not duplicated in every row; it belongs in the central threshold/rule catalog

## Prometheus metrics

| Metric | Type | Labels |
|---|---|---|
| `measurement_duration_seconds` | Histogram | `measurement` |
| `measurement_results_total` | Counter | `measurement`, `status` (`ok`/`error`) |
| `measurement_pathology_flags_total` | Counter | `measurement`, `flag` |

A Grafana dashboard reading these will give per-measurement latency, error rate, and pathology-flag rates without further app changes.

## Kubernetes layout (for later)

The service is K8s-ready as written:
- `/healthz` for `livenessProbe`
- `/readyz`  for `readinessProbe`
- `/metrics` for `ServiceMonitor` (Prometheus operator) or annotation-based scraping
- `PORT` env var (default 8081) — set via `containerPort`
- `MAX_UPLOAD_BYTES` env var (default 1 GiB)
- No on-disk state between requests — pod restarts are safe

A Dockerfile + Helm chart can be added once dependencies are pinned.

## Tests

```bash
pytest services/measurements/tests
```

The test suite uses synthetic 3D segmentations (no patient data) and verifies the joint AP-width / SI-height pipeline recovers known geometry.

End-to-end validation against the Phase 3A Duke-case run is the next-session task — run the segmentation IEP CLI, feed the resulting `step2_output.nii.gz` into `services.measurements.geometric.cervical_body_morphometry.compute()`, and compare to the Colab notebook numbers from 2026-04-28.
