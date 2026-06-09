# MRI-ReportGenerator

Cervical-spine MRI analysis pipeline: sagittal **T2 MRI (DICOM/NIfTI) in → structured,
radiologist-style report out**. The report carries vertebral / disc / canal / cord / alignment
measurements, threshold-based interpretation against cited norms, and anomaly flags **for physician
review**.

**Course:** EECE503N / EECE798N — AI Engineering, AUB — Final Project (Spring 2026)

---

## Pipeline

```
Input (DICOM/NIfTI, sagittal T2)
  → Segmentation        (TotalSpineSeg + Spinal Cord Toolbox + SPINEPS)
  → Measurements        (G1 vertebra · G2 disc · G3 canal/cord · G4 alignment · G5 screens)
  → Interpretation (G6) (cited threshold catalog → status per finding)
  → Report              (clinical report, "flagged for physician review")
```

## Architecture (EECE503N rubric)

- **EEP** — public orchestrator: input validation, rate-limiting, orchestrates the IEPs, assembles the response.
- **IEP — Segmentation:** three engines wrapped behind HTTP — TotalSpineSeg (vertebrae/discs/canal),
  Spinal Cord Toolbox (cord/canal + SCIseg lesion screen), SPINEPS (endplate voxels for the Cobb angle).
- **IEP — Measurements + Interpretation:** geometric / cord / signal engines + the cited-threshold
  interpretation layer (Group 6).
- **IEP — Reporting:** turns the interpretation handoff into a clinical report (HTML/PDF).
- **Deployment:** AWS, Docker images, docker-compose + Kubernetes, Prometheus + Grafana, MLflow.

## Where to start (read order)

1. **[`docs/pipeline-structure.md`](docs/pipeline-structure.md)** — full input→report map, per group.
2. **[`docs/validation/results-final-2026-06-08.md`](docs/validation/results-final-2026-06-08.md)** —
   final per-group verdicts (single source of truth) · **[`group-status`](docs/validation/group-status-2026-06-08.md)**.
3. **[`DEVELOPMENT_JOURNEY.md`](DEVELOPMENT_JOURNEY.md)** — the mistake→fix→validation narrative (J1–J26).
4. **[`overleaf/`](overleaf/)** — the paper + rubric deliverables (T1 AI-depth, P2 baseline, P4
   publishability, C1/P3 novelty); compile with `tectonic`.

## Validation status (final, reproduced from committed code)

No public dataset pairs cervical MRI with per-case expert measurements, so validation is
**threshold-crossing / distribution-separation**, never per-case sensitivity/specificity.

| Group | Verdict |
|---|---|
| G3 canal / SAC / cord | ✅ **strong** (p=0.0001) |
| G2 disc | ⚠️ **partial** — disc/VB AP ratio AUC 0.62; signal & bulge are documented negatives |
| G4 alignment (Cobb) | ❌ **not a discriminator** (validated *measurement*, not a screen; balanced d=0.28, p=0.32) |
| G1 Ha/Hp + G5.1 myelomalacia | ✅ healthy-validated **screens** (compression-fracture arm untested — no dataset) |
| G6 interpretation | 🟢 wired end-to-end |

## Medical-AI rules (hard, non-negotiable)

1. **Cite every clinical claim** — link the paper/guideline/normative study. If it can't be cited, it isn't claimed.
2. **Never diagnose.** Output wording is *"finding flagged for physician review"* / *"pattern consistent
   with possible X; clinical correlation required"* — never *"patient has X."*
3. **Separate training from evaluation data.** Segmenters are pretrained + frozen; the symptomatic cohort
   is a *demonstration* set, never trained on (no overfitting by construction).
4. **No patient data in git** — NIfTI/DICOM are `.gitignore`d; data lives locally or in cloud storage.
5. **No secrets in git** — `.env` / Secrets Manager / Actions secrets only.
6. **Prove on one case before scaling** to a corpus.

## Licenses (dependencies)

| Component | License | Note |
|---|---|---|
| TotalSpineSeg | LGPLv3 | dynamic CLI invocation |
| Spinal Cord Toolbox (incl. SCIseg) | LGPLv3 | dynamic CLI invocation |
| SPINEPS | Apache-2.0 | — |
| TPTBox (+ `spinestats`, pulled by SPINEPS) | Apache-2.0 | verified — not AGPL, not a redistribution blocker |
| nnU-Net v2 | Apache-2.0 | via TotalSpineSeg |
| dcm2niix / nibabel / Flask | MIT / BSD / BSD | — |
| Duke CSpineSeg dataset | CC BY-NC-ND 4.0 | **non-commercial, no redistribution of derivatives** |

## Datasets

- **Spine-Generic** — healthy multi-vendor cervical T2 (the healthy anchor for norms).
- **MMCSD** (Synapse `syn63903115`, Yu et al. 2025, *Sci Data*) — symptomatic CSM/CSR demonstration cohort.
- **Duke CSpineSeg** (Zhou et al. 2025, *Sci Data*) — distribution-only sanity checks (no per-case measurement GT).

## Tests

```bash
pytest services tests              # measurement / interpretation / reporting / web-layer suites
tectonic overleaf/paper/main.tex   # compile the paper (also each overleaf/deliverables/*.tex)
```
