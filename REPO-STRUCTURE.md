# REPO-STRUCTURE.md — MRI-ReportGenerator

> **Purpose of this file.** This is a complete, exact map of the repository's
> file/folder structure. Hand it to Claude (or any developer) and it can
> recreate the same skeleton. It documents *where things live and why*, not the
> internal logic of each module (that's in the code + `plans/`).
>
> **To replicate this structure with Claude, paste:**
> *"Create the following directory + file structure exactly as described in
> REPO-STRUCTURE.md. Create every folder and file shown in the tree, including
> empty `__init__.py` package markers. Use the file descriptions as the spec for
> each file's responsibility."*

---

## Directory tree (source files only)

Caches, virtualenvs, patient data, and model weights are intentionally excluded
(see [.gitignore](.gitignore) and the "Not in the tree" section below).

```
MRI-ReportGenerator/
├── README.md                          # Repo overview / quickstart / read-order (start here)
├── CODEOWNERS                         # GitHub per-path review ownership
├── DEVELOPMENT_JOURNEY.md             # Mistake→fix→validation narrative (J1–J26)
├── cervical-spine-master-plan.md      # Top-level plan + index; implementation-status table
│   # (CLAUDE.md / SESSION_LOG.md / handoffs/ are local-only Claude-workflow files, gitignored — not published)
├── .gitignore                         # Ignore rules (data, secrets, weights, caches)
│
├── plans/                             # Per-phase deep-dive research docs (one file per phase)
│   ├── phase-0-foundations.md         # Positioning, baselines, project foundations
│   ├── phase-1-input-handling.md      # Input: DICOM/NIfTI intake, orientation, spacing, QC
│   ├── phase-2-segmentation.md        # TotalSpineSeg + SCT, slice selection, seg QC
│   ├── phase-3a-geometric-measurements.md  # Vertebra/disc/canal geometry (AP, heights, Cobb…)
│   ├── phase-3b-cord-compression.md   # Cord measurements via SCT, SAC, compression
│   ├── phase-3c-signal-based.md       # Experimental T2-signal engine (myelomalacia / T2-MI)
│   ├── phase-4-assessement.md      # Threshold flagging, demographic percentiles
│   ├── phase-5-clinical-validation.md # Validation vs radiologist GT (ICC / Bland-Altman)
│   ├── phase-6-report-generation.md   # Structured PDF/DOCX report + figure overlays
│   └── phase-7-deferred.md            # Out-of-scope / deferred features (append-only)
│
├── services/                          # Deployable microservices: EEP + IEPs (one folder each)
│   │                                  #   EEP (Flask orchestrator) = NOT YET IMPLEMENTED
│   │
│   ├── segmentation/                  # IEP1 — Segmentation service (Phases 1 + 2)
│   │   ├── __init__.py
│   │   ├── input_handler.py           # Phase 1: NIfTI/DICOM intake, sagittal check, fail-fast QC
│   │   ├── segmenter.py               # Phase 2.1: TotalSpineSeg CLI wrapper (--iso default)
│   │   ├── app.py                     # Flask: GET /healthz, POST /segment
│   │   ├── cli.py                     # Single-case runner ("prove on one case before scaling")
│   │   ├── requirements.txt           # Service-pinned deps
│   │   ├── README.md                  # How to run this service
│   │   └── tests/
│   │       ├── __init__.py
│   │       └── test_input_handler.py  # Synthetic-NIfTI unit tests for Phase 1
│   │
│   └── measurements/                  # IEP2 — Measurements + Assessement service (Phase 3+4)
│       ├── __init__.py
│       ├── context.py                 # Per-case loader: canonical-RAS + 1mm-iso guard;
│       │                              #   defines MeasurementContext + ComponentResult dataclasses
│       ├── orchestrator.py            # Component registry, topo-sort on DEPENDS_ON, Prometheus
│       ├── app.py                     # Flask: /healthz, /readyz, /metrics, POST /measure
│       ├── requirements.txt           # Service-pinned deps (incl. scipy for resampling)
│       ├── README.md                  # How to run this service
│       ├── geometric/                 # Geometric measurement components (Phase 3A)
│       │   ├── __init__.py
│       │   ├── cervical_body_morphometry.py  # 3A.1 AP width + 3A.2 SI heights (producer)
│       │   ├── genant_6point.py       # 6-point Genant extraction pipeline (3A.1/3A.2 method)
│       │   └── spondylolisthesis.py   # 3A.3 slip + Meyerding grade (DEPENDS_ON morphometry)
│       └── tests/
│           ├── __init__.py
│           ├── test_cervical_body_morphometry.py
│           ├── test_genant_6point.py
│           ├── test_spondylolisthesis.py
│           └── test_context_isotropic.py     # Iso-guard tests for context.py
│
└── colab/                             # Exploratory Colab scripts (NOT part of the services)
    ├── cervical_body_measurements_validated.py        # Reference notebook used to validate 3A.1/3A.2
    └── cervical_body_measurements_single_midsagittal.py  # Exploratory shared-slice variant
```

---

## Structural conventions (the rules that make replication "exact")

These are the patterns to follow when adding anything new, so the structure stays
consistent:

### 1. Meta / governance files live at the repo root
`README.md`, `cervical-spine-master-plan.md`, `DEVELOPMENT_JOURNEY.md`, `CODEOWNERS`,
`.gitignore`. Nothing else belongs at the root. (Claude-workflow files — `CLAUDE.md`,
`SESSION_LOG.md`, `handoffs/` — are kept local-only and gitignored, not published.)

### 2. `plans/` holds one markdown file per pipeline phase
- Filename pattern: `phase-<N>[-<sublabel>]-<topic>.md`.
- Every plan file opens with the same header block:
  ```
  # Phase <N> — <Title>

  **Owner:** <name | TBD>
  **Reviewer:** <name | TBD>
  **Status:** <short status>
  **Last updated:** <date> by <name>
  ```
- Followed by a `## What a reviewer should check` section, the phase content,
  then `## Open questions specific to this phase` and `## Session notes`
  (append-only) at the bottom.

### 3. `services/` holds one folder per microservice (EEP + IEPs)
Each service is a **self-contained Python package** with this internal layout:
```
services/<service-name>/
├── __init__.py
├── app.py            # Flask entrypoint; at minimum GET /healthz + the service's POST endpoint
├── <domain modules>.py
├── requirements.txt  # service-pinned dependencies
├── README.md         # how to run this service
└── tests/
    ├── __init__.py
    └── test_<module>.py
```
- IEPs map 1:1 to a pipeline stage (segmentation → IEP1, measurements → IEP2).
- Three services → three Docker images → three owners (per the rubric's GT3).
- The **EEP** (public Flask orchestrator) follows the same package layout when
  added; it is not yet implemented.

### 4. Measurement components are pluggable, one file each
Inside `services/measurements/`, each measurement is its own module grouped by
engine subfolder:
- `geometric/` — Phase 3A (geometry on segmentation masks). **Exists.**
- `cord/` — Phase 3B (SCT cord/compression). *Add when 3B starts.*
- `signal/` — Phase 3C (T2 signal). *Add when 3C starts.*

Every component returns the shared `ComponentResult` shape and declares a
`DEPENDS_ON` list; the orchestrator topo-sorts and runs them. Add a new
measurement by dropping a module in the right engine folder + a matching test in
`tests/` — no orchestrator edits beyond registration.

### 5. `colab/` is exploratory only
Notebook-derived scripts used for prototyping / validation. **Not imported by
any service** and not part of the deployable pipeline. Production logic gets
ported into `services/`, not left here.

### 6. Tests mirror their package
A module `foo.py` in a service has `tests/test_foo.py` in that same service's
`tests/` folder. Run a service's suite with
`python -m pytest services/<service-name>/tests/ -q` from the repo root.

---

## Not in the tree (intentionally git-ignored)

These are expected to exist locally but must never be committed. Their absence
from the tree is correct — do **not** recreate or commit them:

| Excluded | Why |
|---|---|
| `venv/`, `.venv/`, `env/` | Local virtualenvs |
| `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/` | Tool caches |
| `*.nii`, `*.nii.gz`, `*.dcm`, `DICOM/`, `data/`, `duke_cspineseg/` | **Patient/medical data — never commit** |
| `.env`, `secrets/`, `*.key`, `*.pem`, `aws-credentials*` | **Secrets — never commit** |
| `*.pth`, `*.pt`, `*.onnx`, `weights/`, `totalspineseg/models/`, `nnUNet_*` | Model weights & nnU-Net dirs |
| `mlruns/`, `wandb/`, `outputs/`, `results/`, `logs/` | Experiment tracking & run outputs |
| `.vscode/`, `.idea/`, `.DS_Store` | IDE / OS cruft |
| `NOTES.local.md`, `scratch/`, `playground/` | Personal local-only scratch |

The full ignore list is in [.gitignore](.gitignore).

---

## Quick replication checklist (for Claude)

1. Create the root meta-files: `README.md`, `cervical-spine-master-plan.md`,
   `DEVELOPMENT_JOURNEY.md`, `CODEOWNERS`, `.gitignore`.
2. Create `plans/` with the 10 phase files, each using the standard header block.
3. Create `services/segmentation/` and `services/measurements/` using the
   self-contained service layout (incl. `__init__.py`, `app.py`,
   `requirements.txt`, `README.md`, `tests/`).
4. Under `services/measurements/`, create the `geometric/` component subfolder
   (add `cord/` and `signal/` only when those phases start).
5. Create `colab/` for exploratory scripts.
6. Do **not** create any of the git-ignored folders above.
