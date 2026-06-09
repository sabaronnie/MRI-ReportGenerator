# MRI-ReportGenerator

Cervical spine MRI analysis pipeline — sagittal T2 MRI (DICOM/NIfTI) in, structured radiologist-style report out. The report carries vertebral/disc/canal/cord measurements, threshold-based assessment against cited norms, and anomaly flags **for physician review**.

**Course:** EECE503N / EECE798N — AI Engineering, AUB — Final Project (Spring 2026)

---

## How it works

```
Input (DICOM/NIfTI, sagittal T2)
  → Segmentation        TotalSpineSeg + Spinal Cord Toolbox + SPINEPS
  → Measurements        vertebra · disc · canal/cord · alignment · screens
  → Assessment          threshold catalog → status per finding
  → Report              clinical report, flagged for physician review
```

**Architecture (EECE503N rubric):**
- **EEP** — public gateway: input validation, rate-limiting, orchestrates all IEPs, assembles the response
- **IEP – Segmentation:** three engines behind HTTP (TotalSpineSeg, SCT, SPINEPS)
- **IEP – Measurements + Assessment:** geometric/cord/signal engines + cited-threshold assessment layer
- **IEP – Reporting:** turns the assessment handoff into an HTML/PDF clinical report
- **Deployment:** AWS EKS, Docker images, Kubernetes manifests, Prometheus + Grafana, MLflow

---

## Deliverables

### Paper

The compiled paper is at [`deliverables/paper/main.pdf`](deliverables/paper/main.pdf).

### Rubric deliverables

Four standalone rubric documents in [`deliverables/docs/`](deliverables/docs/), each self-contained and compilable independently:

| PDF | What it covers |
|-----|----------------|
| [`T1_ai_depth.pdf`](deliverables/docs/T1_ai_depth.pdf) | AI depth — models, training, integration |
| [`P2_baseline.pdf`](deliverables/docs/P2_baseline.pdf) | Baseline comparison |
| [`P4_publishability.pdf`](deliverables/docs/P4_publishability.pdf) | Publishability argument |
| [`C1_P3_novelty.pdf`](deliverables/docs/C1_P3_novelty.pdf) | Novelty & AI justification |

---

## Deployment & running the pipeline

Full step-by-step instructions — local Docker run and full AWS EKS deployment — are in the runbook:

**[`technical-documentation/RUNBOOK-deployment.md`](technical-documentation/RUNBOOK-deployment.md)**

Short version:
```bash
# Build the 3 segmentation model images
docker build -f deployment/docker/seg-tss.Dockerfile     -t mri-seg-tss:latest     .
docker build -f deployment/docker/seg-sct.Dockerfile     -t mri-seg-sct:latest     .
docker build -f deployment/docker/seg-spineps.Dockerfile -t mri-seg-spineps:latest .

# Start them
docker run -d --name seg-tss     -p 8083:8083 --shm-size=4g        mri-seg-tss:latest
docker run -d --name seg-sct     -p 8084:8084 --shm-size=2g        mri-seg-sct:latest
docker run -d --name seg-spineps -p 8085:8085 --shm-size=4g -m 40g mri-seg-spineps:latest

# Run one scan through the DAG
curl -sS -F "file=@scan.nii.gz;filename=input.nii.gz" http://localhost:8083/segment -o tss.zip &
curl -sS -F "file=@scan.nii.gz;filename=input.nii.gz" http://localhost:8085/segment -o spineps.zip &
wait
curl -sS -F "file=@tss.zip;filename=segmentation.zip" http://localhost:8084/segment-sct -o sct.zip
```

See the runbook for AWS deployment, GPU setup, and known gotchas.

---

## Validation status

| Group | Verdict |
|-------|---------|
| G3 canal / SAC / cord | ✅ strong (p=0.0001) |
| G2 disc | ⚠️ partial — disc/VB AP ratio AUC 0.62; signal & bulge are documented negatives |
| G4 alignment (Cobb) | ❌ not a discriminator (validated measurement, not a screen; d=0.28, p=0.32) |
| G1 Ha/Hp + G5.1 myelomalacia | ✅ healthy-validated screens (compression-fracture arm untested — no dataset) |
| G6 assessment | wired end-to-end |

Full results: [`docs/validation/results-final-2026-06-08.md`](docs/validation/results-final-2026-06-08.md)

---

## Tests

```bash
pytest services tests
```

---

## Medical-AI rules

1. **Cite every clinical claim.** If it can't be cited, it isn't claimed.
2. **Never diagnose.** Output wording: *"finding flagged for physician review"* / *"pattern consistent with possible X; clinical correlation required"* — never *"patient has X."*
3. **Separate training from evaluation data.** Segmenters are pretrained + frozen; the symptomatic cohort is a demonstration set, never trained on.
4. **No patient data in git** — NIfTI/DICOM are `.gitignore`d.
5. **No secrets in git** — `.env` / Secrets Manager / Actions secrets only.

---

## Licenses

| Component | License | Note |
|-----------|---------|------|
| TotalSpineSeg | LGPLv3 | dynamic CLI invocation |
| Spinal Cord Toolbox (incl. SCIseg) | LGPLv3 | dynamic CLI invocation |
| SPINEPS | Apache-2.0 | — |
| TPTBox / spinestats | Apache-2.0 | not AGPL, not a redistribution blocker |
| nnU-Net v2 | Apache-2.0 | via TotalSpineSeg |
| dcm2niix / nibabel / Flask | MIT / BSD / BSD | — |
| Duke CSpineSeg dataset | CC BY-NC-ND 4.0 | **non-commercial, no redistribution of derivatives** |
