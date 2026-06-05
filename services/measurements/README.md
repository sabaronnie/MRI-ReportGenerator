# Measurements Service (IEP2)

Flask service running Phase 3 measurement components on a TotalSpineSeg `step2_output`. Each measurement is its own component module; the orchestrator runs them in dependency order, instruments every call with Prometheus, and returns a flat report.

## Components currently registered

| Component | Phase | Outputs |
|---|---|---|
| `cervical_body_morphometry` | 3A.1 + 3A.2 | `AP_width`, `H_anterior`, `H_middle`, `H_posterior`, `tilt_deg` per cervical vertebra |
| `spondylolisthesis` | 3A.3 | `spondy_slip_mm`, `spondy_pct_of_lower_AP` per adjacent vertebral pair |
| `c3c7_cobb_angle` | 4.1 | `Cobb_C3_C7` from reused `cervical_body_morphometry` AI/PI corners in the common PA-SI frame |
| `lordosis_classification` | 4.2 | Derived `lordotic` / `straightened / low lordosis` / `kyphotic` from `Cobb_C3_C7`, with supine-MRI caveat |
| `segmental_angles` | 4.3 | `segmental_angle` for `C3-C4` through `C6-C7` from reused inferior/superior endplate corners in the common PA-SI frame |
| `posterior_tangent_angle` | 4.4 | `posterior_tangent_C3_C7` from reused `PS/PI` posterior-wall corners, plus Cobb divergence metadata for cross-checking |
| `functional_canal_ap` | 3.1 | `dural_sac_AP_min` per cervical vertebra via SCT `sc_canal_t2` + `sct_process_segmentation` |
| `cord_ap` | 3.2 | `cord_AP` per cervical vertebra via SCT `seg_sc_contrast_agnostic`, aligned to `functional_canal_ap` focal slices |
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

The `POST /measure` body is the same zip the segmentation IEP returns: at minimum a `step2_output.nii.gz`. Components backed by SCT also require `step1_levels.nii.gz` and `input_iso.nii.gz`, which the segmentation IEP now bundles by default. Optional repeated form field `measurement=<name>` picks a subset of components.

```bash
curl -X POST -F "file=@segmentation.zip" http://localhost:8081/measure
# only AP-width / SI-height pipeline:
curl -X POST -F "file=@segmentation.zip" -F "measurement=cervical_body_morphometry" http://localhost:8081/measure
```

Response:

```json
{
  "manifest": {"seg_shape": [25, 60, 50], "voxel_spacing_mm": [1.0, 1.0, 1.0], "labels_present": [...]},
  "report": {
    "components": {"cervical_body_morphometry": {"status": "ok", "duration_s": 0.012, "metadata": {"levels": ["C3", ...]}}},
    "measurements": {
      "AP_width":     {"C3": 19.0, "C4": 19.5, ...},
      "H_anterior":   {"C3": 17.0, ...},
      "H_middle":     {"C3": 17.0, ...},
      "H_posterior":  {"C3": 17.0, ...},
      "tilt_deg":     {"C3": 0.0,  ...}
    },
    "flags": {
      "ap_width_outlier":  {"C3": false, ...},
      "wedge_fracture":    {"C3": false, ...},
      "biconcave_fracture":{"C3": false, ...}
    }
  }
}
```

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
