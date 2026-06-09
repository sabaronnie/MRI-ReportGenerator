═══════════════════════════════════════════════════════════════════════════════════════════════════
HANDOFF — Ronnie: final FRONTEND linking so the professor can run the whole pipeline · 2026-06-09
From: Andrew (deployment/infra chat). AWS is now TORN DOWN — the professor runs everything on HIS OWN
machine, locally. So "link it well" = the local full-stack must work end-to-end with one command.
═══════════════════════════════════════════════════════════════════════════════════════════════════

## 0) THE GOAL
Professor uploads an MRI in the web UI → it runs the REAL 3-engine DAG → measurements → report, all on
his laptop (Docker). The frontend already supports this (`NEXT_PUBLIC_API_MODE=live`); the gaps are (a)
the local compose doesn't include the 3 segmentation engines yet, and (b) verify the live API client
matches the REAL EEP contract + handles the long async job.

## 1) WHAT'S ALREADY DONE (don't redo)
- **Frontend has a live mode**: `NEXT_PUBLIC_API_MODE=live` → talks to `NEXT_PUBLIC_EEP_URL`
  (`frontend/Dockerfile` build-args; the API client reads both).
- **Compose** `deployment/compose/docker-compose.yml` already wires `frontend (3000, live → http://localhost:8080)
  → eep (8080) → measurements (8081)`, and EEP CORS allows `http://localhost:3000`.
- **Backend is canned-free + DAG-correct** (this session): EEP runs the real DAG (TSS ∥ SPINEPS → SCT),
  measurements reads the real masks (G3/G4), SCT 7.0 CLI migration done. Canned demo + DEMO_PASSWORD removed.
- **Auth seed**: `admin@demo` / `demo12345` (POST `/auth/login`). No canned bypass anymore.

## 2) THE ONE BIG GAP — add the 3 seg engines to the local compose
`deployment/compose/docker-compose.yml` currently has eep→measurements but NO seg services, and the EEP
has no `SEG_*_URL`, so an upload won't run the real pipeline locally. Add three services and wire the EEP:
- `seg-tss`  (build `deployment/docker/seg-tss.Dockerfile`,  port 8083, `/segment`)
- `seg-sct`  (build `deployment/docker/seg-sct.Dockerfile`,  port 8084, `/segment-sct`)
- `seg-spineps` (build `deployment/docker/seg-spineps.Dockerfile`, port 8085, `/segment`)
- on the `eep` service add env: `SEG_TSS_URL=http://seg-tss:8083  SEG_SCT_URL=http://seg-sct:8084
  SEG_SPINEPS_URL=http://seg-spineps:8085`
- give `seg-spineps` ≥ ~40 GB memory and a real `/dev/shm` (see RUNBOOK §6 gotchas — CPU OOM + shm).
  NOTE these are HEAVY images (SPINEPS bakes model weights; SCT installs the toolbox). On a laptop the
  DAG takes **~13 min/case on CPU**. The runbook (`docs/RUNBOOK-run-the-3-models.md`) Part A documents the
  exact `docker run` flags if you prefer running them standalone instead of via compose.

## 3) VERIFY THE LIVE API CLIENT MATCHES THE REAL EEP CONTRACT (verified live this session)
The frontend's `live` client must hit exactly these (all under `NEXT_PUBLIC_EEP_URL`):
- `POST /auth/login`  body `{"email","password"}` → `{"token"}`; send `Authorization: Bearer <token>` on /cases*
- `POST /cases`  multipart: `file=<.nii.gz|.nii|DICOM .zip>` + `uploader=<str>` → **202** `{"case_id","status":"queued"}`
- `GET /cases/{id}/job` → `{"stage","stages":["queued","segmenting","measuring","assessing","ready"],"progress","error"}`
- `GET /cases/{id}`  → full case: `measurements`, `flags`, `components`, `assessements`, `report`
- `GET /cases/{id}/report.html`  and  `GET /cases/{id}/report.pdf`
- `GET /cases/{id}/mask` and `GET /cases/{id}/volume` (for the NiiVue viewer)
- worklist/sign-off: `GET /cases`, `POST /cases/{id}/sign-off`

## 4) THE #1 LINKING DETAIL — the async, minutes-long job
Upload returns **202 immediately**; the pipeline runs in a background worker. The UI MUST poll
`GET /cases/{id}/job` and render the stage/progress until `stage=="ready"` (or surface `error`). This is
**minutes** (CPU seg ~13 min), not seconds — make sure the polling UX (and any fetch/proxy timeouts)
tolerate that. On `ready`, fetch `/cases/{id}` + the report. (This is exactly the flow the live e2e used.)

## 5) BUILD + RUN (what the professor will actually do)
```bash
# from repo root, after reconciling branches to main (see PRs #6 + #7):
docker compose -f deployment/compose/docker-compose.yml up --build     # add the 3 seg services first (§2)
# open http://localhost:3000 → log in (admin@demo / demo12345) → Upload an MRI → watch it run → report
```
The frontend image must be built with `NEXT_PUBLIC_API_MODE=live` and `NEXT_PUBLIC_EEP_URL=http://localhost:8080`
(already set in the compose `frontend` service).

## 6) GOTCHAS THAT WILL BITE IF MISSED
- Measurements image MUST be the **SCT-CLI** one (G3 canal/cord/SAC need `sct_process_segmentation`); the
  fixed `measurements.Dockerfile` (branch `feat/eep/auth-async-integration`) installs it. Don't build
  measurements from an older branch.
- `seg-spineps` OOMs under ~32–40 GB on CPU; if the professor's laptop can't give that, the DAG won't run
  SPINEPS (G4 Cobb) — document the RAM requirement to him.
- The C3–C7 global Cobb can no-op when C7 is obscured at the cervicothoracic junction (data, not a bug);
  per-level `segmental_angles` still works.
- Branches not yet merged: app = PR #6 (`feat/eep/auth-async-integration`), seg/runbook = PR #7
  (`feat/seg/deploy`). They diverge (§9) and must be reconciled before the professor pulls one `main`.

## 7) DEFINITION OF DONE FOR RONNIE
`docker compose up --build` on a clean checkout → log in → upload the sample T2
(`deployment/compose/sample_data/sample_volume_T2.nii.gz`) → job runs to `ready` → report renders in the
UI with the NiiVue viewer showing masks. That's the professor-ready linked demo.
═══════════════════════════════════════════════════════════════════════════════════════════════════
