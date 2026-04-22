# MRI-ReportGenerator

Cervical spine MRI analysis pipeline. Sagittal T2 MRI in, structured radiology-style report out.

**Course:** EECE503N / EECE798N — AI Engineering, AUB — Final Project (Spring 2026)
**Team:** Andrew Khoury · Roni (sabaronnie) · Hamad
**Status:** Research phase — master plan v1 under team review. No implementation yet.

---

## Where to start

If you're a teammate or Claude opening this repo for the first time, read in this order:

1. **[`CLAUDE.md`](./CLAUDE.md)** — rules, conventions, session protocol, hard rules
2. **[`SESSION_LOG.md`](./SESSION_LOG.md)** — what the last session did and what's pending
3. **[`plans/`](./plans/)** — open the most recently edited file; active work lives here
4. **[`cervical-spine-master-plan.md`](./cervical-spine-master-plan.md)** — top-level plan and scope index

---

## Pipeline overview

```
Input (DICOM/NIfTI) → Segmentation → Measurements → Interpretation → Report
     Phase 1            Phase 2        Phase 3         Phase 4      Phase 6
                        (TSS + SCT)    (3A/3B/3C)    (thresholds)    (PDF)
```

**Clinical Validation (Phase 5)** is a separate workstream, not a runtime stage.

## Architecture (per EECE503N rubric)

- **External Endpoint (EEP):** FastAPI orchestrator — public API, input validation, rate-limiting, response assembly
- **Internal Endpoint 1 (IEP1):** Segmentation service — TotalSpineSeg + Spinal Cord Toolbox wrappers
- **Internal Endpoint 2 (IEP2):** Measurements + Interpretation service — geometric, cord, and signal engines + threshold flagging
- **Deployment:** AWS, three Docker images, docker-compose + Kubernetes, Prometheus + Grafana

## Stack

- Python 3.10, FastAPI
- nnU-Net v2 via TotalSpineSeg
- Spinal Cord Toolbox (SCT) for cord morphometry
- MLflow for experiment tracking
- Docker + Docker Compose + Kubernetes
- AWS (provider chosen; exact services TBD — likely EKS or ECS)
- Prometheus + Grafana for observability

## Dataset

Duke University Cervical Spine MRI Segmentation Dataset (CSpineSeg) — Zhou et al. 2025, *Scientific Data* — via MIDRC.
- Used for: segmentation sanity check, demographic percentile curves, end-to-end plausibility runs
- **NOT used for:** clinical measurement validation (no radiologist ground truth in the dataset)
- Clinical validation path: AUBMC radiologist collaboration on a 20–30 case subset

## License

TBD — see open question in the master plan. Note: Duke CSpineSeg data is CC BY-NC-ND 4.0 (non-commercial, no derivatives), and our dependencies (TotalSpineSeg, SCT) are LGPLv3.

---

For anything deeper, go to `CLAUDE.md` and follow the read order.
