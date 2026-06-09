# Architecture

Cervical-spine MRI analysis pipeline: sagittal T2 MRI (DICOM/NIfTI) in → structured radiology-style
report out (vertebra / disc / canal / cord measurements + threshold interpretation + flags for
physician review). See `docs/deployment.md` for the deployed (AWS/EKS) topology.

## Service boundaries (rubric §4)
```
                 ┌──────────────┐         public boundary (FastAPI)
   client  ──▶   │     EEP      │   validation + limits + rate-limit + CORS + /metrics
                 │ services/eep │   orchestrates the IEPs
                 └──────┬───────┘
            ┌───────────┴────────────┐
            ▼                        ▼
   ┌──────────────┐         ┌──────────────┐
   │ measurements │         │  reporting   │     two independent IEPs
   │   (Flask)    │         │   (Flask)    │
   └──────────────┘         └──────────────┘
   geometric + cord(SCT) +   interpretation handoff
   group5 + interpretation   → clinical report (HTML)
```
- **EEP** (`services/eep/`) — public API + system boundary; orchestrates measurements (on upload) and
  reporting (on report request). Not a thin pass-through: validation, size/type limits, per-IP rate
  limit, fixture fallback, retries, Prometheus metrics.
- **IEP 1 — measurements** (`services/measurements/`) — geometric/cord/signal/Group-5 measurement logic;
  `services/interpretation/` (threshold catalog) runs in-process to produce the interpretation handoff.
- **IEP 2 — reporting** (`services/reporting/`) — consumes the interpretation handoff → clinical report.
- **segmentation** (`services/segmentation/`) — TotalSpineSeg/SCT wrappers; runs **upstream on GPU/Colab**
  (not a runtime in-cluster service); its mask is the input to measurements.

Each IEP exposes a clear input/output contract (`docs/contracts/`) and defined error/fallback behavior
(per-component `status`/`error`; the EEP falls back to a cloned-fixture core if an IEP is unreachable).

## Repo layout
- `services/{eep,measurements,interpretation,reporting,segmentation}/` — the services above
- `docs/contracts/` — frozen data/report/viewer contracts (the service boundary)
- `deployment/{docker,compose,k8s,aws,monitoring}/` — images, local stack, k8s, AWS deploy, observability
- `tests/{integration,e2e}/` + `services/*/tests/` — test suites (`docs/` ↔ rubric in `RUBRIC_TRACKER.md`)
- `mlops/` — validation/promotion pipeline (`docs/mlops.md`)
- `research/`, `colab/` — non-runtime validation scripts + GPU notebooks (kept out of the services)

## No LLM components (rubric §6)
This system uses **no LLM** anywhere in the request path. Segmentation is deep-learning
(TotalSpineSeg/SCT, pretrained), measurements are geometric/signal algorithms, and interpretation +
reporting are **rule-based** (a cited threshold table + deterministic templates). Therefore the §6
"prompt versioning / prompt-change evaluation" requirements are **not applicable** — there are no
prompts. Determinism is instead guaranteed by the golden regression test (`tests/integration/
test_golden_report.py`) and the MLOps validation gate (`mlops/validate.py`). See `docs/tradeoffs.md` §3
for why rule-based was chosen over an LLM report writer.
