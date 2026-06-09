# IEP Contracts + Infra Notes v0.1 (frontend handoff #4–#6)

> Supplements [`data-contract-v0.1.md`](data-contract-v0.1.md) for the EEP/infra track.
> 🟢 FROZEN / 🟡 LIKELY / ⚪ PROPOSED.

## #4 — Internal IEP contracts

### IEP-1 Segmentation (`services/segmentation`)
- **Input** 🟢: one sagittal-T2 cervical study as NIfTI `.nii.gz` or a zipped DICOM series.
  `input_handler` does fail-fast QC (orientation, dimensionality, degenerate intensity).
- **Output (TSS)** 🟢: `step2_output.nii.gz` (multi-label vertebra+disc+canal/cord), `step1_levels.nii.gz`
  (vertebral-level map), `input_iso.nii.gz` (1 mm-iso resampled MRI), + a manifest (voxel spacing, labels present).
- **Output (SCT, now a separate path)** 🟢: `sc_canal_t2` → binary canal mask; `spinalcord` → binary cord
  mask (`services/segmentation/sct_segmenter.py`, `sct_cli.py`, `sct_app.py`). SCT runs in its OWN
  environment (it + SPINEPS conflict with the TSS numpy stack → separate containers/sessions).
- **What changed in the 4ab7b8c refactor:** SCT segmentation was split out into `sct_*` modules; the TSS
  contract above is unchanged.

### IEP-2 Measurements (`services/measurements`)
- **Input** 🟢: a `MeasurementContext` built by `context.load_context(seg_path, raw_path=…,
  levels_path=…, sct_canal_seg_path=…, sct_cord_seg_path=…, source_spacing_mm=…)`. Only `seg_path`
  (TSS step2) is required; cord components need the SCT masks (or raw + SCT installed) + `step1_levels`.
- **Output** 🟢: the report object documented in the data contract —
  `{components, measurements, flags, interpretations}`. The `/measure` Flask endpoint takes a multipart
  upload of the segmentation zip and returns this JSON.
- **What changed in the refactor:** interpretation moved to `services/interpretation` (imported by the
  orchestrator); Group 5 integrated as the `group5_fracture_screen` component; `cord/` (G3) added;
  the G2 disc components exist but are **not yet registered** in the orchestrator `COMPONENTS`.
- **Stability** 🟡: G1/G4 numbers will change when the morphometry/slip endplate-line port lands (the
  *shape* is frozen; the *values* improve). The C1 SPINEPS Cobb is the production target once SPINEPS
  masks are plumbed through the context.

### Pipeline order (EEP orchestration)
`Segmentation (TSS [+ SCT]) → Measurements → Interpretation → Reporting`. Interpretation runs inside the
measurements service today (`run_all` appends `interpretations`); it may later be its own service call. 🟡

## #5 — Prometheus metrics (for Grafana)
Already emitted by `services/measurements/orchestrator.py` 🟢:
| metric | type | labels |
|---|---|---|
| `measurement_duration_seconds` | Histogram | `measurement` (component name) |
| `measurement_results_total` | Counter | `measurement`, `status` (`ok`/`error`) |
| `measurement_pathology_flags_total` | Counter | `measurement`, `flag` (flag_key) |

- Segmentation/EEP/reporting metrics ⚪ not yet defined — infra track to add (suggest
  `segmentation_duration_seconds`, `eep_request_duration_seconds`, request/error counters).
- Planned ML-signal metric ⚪: a per-case confidence/quality gauge (e.g. low-through-plane-resolution
  rate, component error rate) — TBD with the science track; the `resolution_quality` block in the
  measurement manifest is a natural source.

## #6 — Repo path map (post-4ab7b8c)
| area | path |
|---|---|
| Segmentation IEP (TSS + SCT) | `services/segmentation/` |
| Measurements IEP (G1/G4 geometric, G3 cord, G2 disc, G5) | `services/measurements/` |
| Interpretation / Group 6 | `services/interpretation/` |
| Reporting (builder + html/pdf renderers) | `services/reporting/` |
| EEP public API (scaffold) | `services/eep/` |
| Validation / research scripts | `research/group5/` |
| GPU notebooks | `colab/` (+ `colab/group5/`) |
| Deployment scaffolds | `deployment/{docker,compose,k8s}/` |
| Docs (this contract, architecture, rubric…) | `docs/` |
| Cross-service / E2E tests | `tests/{integration,e2e}/` |

**Frontend/EEP/infra homes** (your track to create): suggest `frontend/` (Next.js) at repo root and to
flesh out `services/eep/`; deployment under `deployment/`. Branch coordination 🟢: frontend track on
`feat/frontend/*` `feat/eep/*` `feat/deploy/*`; science track stays in `services/{measurements,
segmentation,interpretation}`, `research/`, `colab/`. Same discipline: granular commits, plain messages,
no signatures, `main` protected, stage by name.
