# MASTER HANDOFF — Deployment/Infra continuation chat · 2026-06-09

Paste the whole block below into the new chat. It contains everything needed to finish the live
3-engine segmentation deploy and to own the deployment/infra track. Also saved here so it's never lost.

---

```
═══════════════════════════════════════════════════════════════════════════════════════════════════
MASTER HANDOFF — MRI-ReportGenerator · DEPLOYMENT / INFRA / EEP chat · 2026-06-09
I am Andrew. SHARED Claude account (memories default to me). Paste this whole file.
═══════════════════════════════════════════════════════════════════════════════════════════════════

## 0) IDENTITY + READ ORDER (do before anything)
- Shared account → I am **Andrew**. This is the **deployment/infra/EEP** chat (NOT the science chat,
  NOT the frontend chat).
- READ IN ORDER: (1) project memory `MEMORY.md` + the files it points to (esp. frontend_infra_build_track,
  commit_granularly, simple_status_reminders, document_mistakes_for_report, project_scope_ambition,
  launch_research_for_validation); (2) repo `MRI-ReportGenerator/CLAUDE.md`; (3) `SESSION_LOG.md`
  (top entries 2026-06-08/09 are mine — read cont.1 → cont.6); (4) THESE docs on branch
  `feat/eep/scaffold`: `docs/RUBRIC_TRACKER.md`, `docs/segmentation-deploy.md`, `docs/seg-services-handoff.md`,
  `docs/deployment.md`, `docs/monitoring.md`, `docs/mlops.md`, `docs/ci.md`, `docs/tradeoffs.md`,
  `docs/positioning.md`, `docs/demo-script.md`, `docs/architecture.md`.
- Local root: `/Users/andrew/Desktop/AUB/Spring 26/EECE 503n/Project/` containing `MRI-ReportGenerator/`
  (the git repo, used by the science chat — DON'T trample) + sibling worktrees (`eep-worktree/` is THIS
  chat's; `frontend-worktree/`, `measurements-worktree/`, `group6-worktree/`, `teammate-worktrees/`).
- WORK IN: `eep-worktree/` on branch `feat/eep/scaffold`.

## 1) ⚠️ THE IMMEDIATE TASK — finish LIVE 3-engine segmentation
GOAL: make the website's upload run the REAL segmentation (3 engines IN PARALLEL on AWS) → measurements
→ report, replacing the bundled stand-in. The deploy side is BUILT + waiting; the science wrappers just
landed. Remaining = build images in the cloud, deploy them, wire the EEP, test.

### 1a) The 3 engines (science DELIVERED them on branch `research/andrew/writeups`, pushed)
| Engine | Wrapper (Flask /segment + /healthz) | Produces | Output files |
|--------|-------------------------------------|----------|--------------|
| TotalSpineSeg | services/segmentation/app.py ✅ | vertebra/disc/canal (G1/G2) | step2_output.nii.gz, step1_levels.nii.gz |
| SCT | services/segmentation/sct_app.py ✅ (now also SCIseg) | cord+canal (G3) + SCIseg lesion (G5.1) | sct_canal_seg.nii.gz, sct_spinalcord_seg.nii.gz, sct_lesion_seg.nii.gz |
| SPINEPS | services/segmentation/spineps_app.py ✅ NEW | per-vertebra instances + endplate sheets (G4 Cobb) | (confirm exact filename in the wrapper) |
- All 3 compile clean + error-handle gracefully; 9 segmentation tests pass. NOT run end-to-end (SCT/
  SPINEPS aren't installed locally) — THE FIRST CLOUD BUILD IS THE REAL SMOKE TEST. If /segment errors,
  get the pod stderr and fix.
- SCT SCIseg uses CLI `sct_deepseg lesion_sci_t2` (v7); made non-fatal (G5.1 won't block G3).
- HARD CONSTRAINT: TSS(nnU-Net) and SPINEPS pin INCOMPATIBLE numpy (SPINEPS needs numpy==2.0.2) →
  3 SEPARATE images, never one. SCT separate too.
- OPEN LICENSE FLAG (not code): verify TPTBox `spinestats` submodule (a SPINEPS dep) is NOT AGPL before
  the SPINEPS image ships publicly. TSS+SCT = LGPLv3, SPINEPS = Apache-2.0 (those are fine).

### 1b) What's ALREADY BUILT on the deploy side (branch feat/eep/scaffold — ready to plug in)
- **EEP parallel fan-out**: `services/eep/clients/segmentation.py` (`run_segmentation_async` =
  `asyncio.gather` over the 3 engines → merges their output zips). Wired in
  `orchestration.process_upload(input_bytes)`; the router now buffers the upload bytes; `/readyz` reports
  `segmentation_ready`. STAND-IN FALLBACK preserved (if SEG_*_URL unset or any engine errors → current
  demo still works). Activated by setting all three: `SEG_TSS_URL`, `SEG_SCT_URL`, `SEG_SPINEPS_URL`
  (config in services/eep/config.py; SEG_TIMEOUT_S default 2700s for slow CPU TSS). 3 fan-out tests pass.
- **Dockerfiles** (device-agnostic, ~10 GB each): `deployment/docker/seg-tss.Dockerfile`,
  `seg-sct.Dockerfile`, `seg-spineps.Dockerfile`. NOTE: verify they install what the wrappers need
  (SCT install-task lines must cover canal/cord + SCIseg lesion_sci_t2; SPINEPS needs numpy==2.0.2 +
  TPTBox; entrypoints services.segmentation.{app,sct_app,spineps_app}:app).
- **Compute node group IaC**: `deployment/aws/segmentation-nodegroup.yaml` — tainted ng (workload=
  segmentation). CPU `c5.2xlarge` block active; GPU `g4dn.xlarge` block COMMENTED (uncomment when quota
  approved).
- **Cloud-build workflow**: `.github/workflows/build-seg-images.yml` (manual; inputs `seg_code_ref`
  branch + `engines`). Frees runner disk, builds amd64, pushes to ECR. Needs GitHub repo secrets
  AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/AWS_REGION (see docs/ci.md).
- Docs: `docs/segmentation-deploy.md` (full architecture), `docs/seg-services-handoff.md`.
- ⚠️ NOT yet written: the k8s manifests for the 3 seg services (`deployment/k8s/seg-*.yaml`) and the
  EEP env wiring of SEG_*_URL. The new chat writes these.

### 1c) WHY local builds failed (learned the hard way)
The TSS image (~10 GB: CUDA torch + nnU-Net + ~1 GB weights) **cannot build on the Mac** — Docker
Desktop I/O-errors on export (disk), and the Mac is arm64 vs the amd64 nodes. BUILD IN THE CLOUD
(the workflow), not locally.

### 1d) STEP-BY-STEP to finish (the actual to-do)
0. Verify env: `aws sts get-caller-identity` (expect account 658132201414, user mri-deploy);
   `aws eks update-kubeconfig --name mri-reportgenerator --region eu-north-1`; `kubectl -n mri get pods`.
1. **Integration branch**: the seg WRAPPERS are on `research/andrew/writeups`; the deploy INFRA
   (Dockerfiles, fan-out, node group, workflow) is on `feat/eep/scaffold`. Create one branch that has
   BOTH (e.g. merge feat/eep/scaffold + research/andrew/writeups → `feat/seg/deploy`). They touch mostly
   different files; reconcile services/segmentation (take the science wrappers) + keep the deploy infra.
2. **Align the Dockerfiles** to the wrappers' real requirements (SCT install-tasks incl. SCIseg;
   SPINEPS numpy==2.0.2 + TPTBox + the spinestats license check; confirm entrypoints + output filenames).
3. **Set GitHub secrets** (docs/ci.md) then run the **build-seg-images** workflow with
   `seg_code_ref=feat/seg/deploy`, `engines="tss sct spineps"` → 3 images in ECR
   (mri-seg-tss/sct/spineps). FIRST BUILD = smoke test; if a /segment errors at runtime, read pod stderr.
   (Alt build paths if GH Actions disk is tight: AWS CodeBuild, or a throwaway c5 EC2 with big disk.)
4. **Create the seg node group**: GPU if the quota is approved (uncomment the g4dn block →
   `eksctl create nodegroup -f deployment/aws/segmentation-nodegroup.yaml`); else CPU c5.2xlarge
   (works, but ~35 min/case for TSS).
5. **Write + apply k8s manifests** `deployment/k8s/seg-{tss,sct,spineps}.yaml`: ClusterIP Services
   (tss:8083, sct:8084, spineps:8085) + Deployments with `nodeSelector: {workload: segmentation}` +
   `tolerations: [{key: workload, value: segmentation, effect: NoSchedule}]` (+ `resources.limits.
   nvidia.com/gpu: 1` if GPU). Big memory requests (TSS/SPINEPS multi-GB).
6. **Wire the EEP**: set env `SEG_TSS_URL=http://seg-tss:8083`, `SEG_SCT_URL=http://seg-sct:8084`,
   `SEG_SPINEPS_URL=http://seg-spineps:8085`; redeploy EEP (or `kubectl -n mri set env`). `/readyz` must
   show `segmentation_ready:true`.
7. **Rebuild the measurements image** from the canonical finalized branch too, so G3 (SCT)/G4 (SPINEPS)/
   G5.1 (SCIseg) consume the real seg outputs (the measurements code that reads sct_lesion_seg.nii.gz +
   the SPINEPS endplate file must be the finalized version).
8. **E2E test**: upload a real sagittal T2 cervical MRI on the website → confirm the 3 engines run in
   parallel (watch `kubectl -n mri logs` on the seg pods) → real measurements → report. Sample MRI is in
   S3 (`mri-reportgenerator-samples-658132201414`) + `frontend-worktree/frontend/public/samples/
   sample_volume_T2.nii.gz`.
9. Update `docs/RUBRIC_TRACKER.md` (segmentation now a REAL deployed IEP → strengthens GT3/T3/T4, and
   gives genuine "parallel model interaction") + `SESSION_LOG.md`. TEARDOWN after the demo.

## 2) AWS ACCOUNT + CLUSTER FACTS
- Account **658132201414**, region **eu-north-1** (Stockholm). IAM user `mri-deploy` (AdministratorAccess);
  creds in `~/.aws/` (gitignored — never in chat/git). Budget alert: $20/mo → andrew.2119.khoury@gmail.com.
- EKS cluster **mri-reportgenerator** (k8s 1.31), default nodegroup 2× t3.medium. `eksctl`/`kubectl`/
  `helm` installed.
- Namespaces: **mri** (eep [1 replica], measurements, reporting, frontend) + **monitoring**
  (kube-prometheus-stack: kps-prometheus, kps-grafana, operator, node-exporter, kube-state-metrics).
- ECR repos: mri-eep, mri-measurements, mri-reporting, mri-frontend (+ to create: mri-seg-tss,
  mri-seg-sct, mri-seg-spineps). S3: mri-reportgenerator-samples-658132201414 (viewer NIfTI + stand-in
  seg zip, pulled by the EEP initContainer).
- **GPU quota**: "Running On-Demand G and VT instances" (L-DB2E81BA) = **0**; increase to **16**
  REQUESTED (PENDING, AWS-timed; Andrew may escalate via Support). Standard quota (L-1216C47A) = 16.
  g4dn.xlarge + g5.xlarge ARE offered in eu-north-1.
- **LIVE URLs are EPHEMERAL** (ELB hostnames change on redeploy) — ALWAYS re-fetch:
  `kubectl -n mri get svc eep frontend -o wide` + `kubectl -n monitoring get svc kps-grafana`.
  (As of 2026-06-08: frontend a359d7957b43847a69ba05ef7b9fad98-..., EEP a08443535da2a4ee5856aeb58f0ae7f7-...,
  Grafana a7175637bf30040feb6bcdf4719ebd42-... admin/mri-demo-admin — VERIFY, may have changed.)

## 3) CURRENT SYSTEM STATE (live + verified on AWS)
- **GT1/GT2/GT3 MET**: deployed e2e demo works; public AWS API live; EEP orchestrates 2 IEPs
  (measurements + reporting). 5 live e2e tests green against the deployed EEP.
- EEP (FastAPI) endpoints: GET /cases, POST /cases (upload, validates type/size, rate-limit), GET
  /cases/{id}, /job, POST /cases/{id}/sign-off, GET /cases/{id}/volume, /mask, **/cases/{id}/report.html**
  (renders via reporting IEP), /healthz, /readyz, /metrics, /docs. measurements IEP (Flask :8081),
  reporting IEP (Flask :8082).
- **Monitoring (M3) MET**: Prometheus + Grafana on EKS, ServiceMonitors scrape all services, custom
  dashboard "MRI-ReportGenerator — Services" (throughput, error rate by class, p50/p95 latency, IEP
  durations, ML-signal pathology-flag distribution). docs/monitoring.md.
- **Tests (Q1/Q2) MET**: `cd eep-worktree && /tmp/venv-test/bin/python -m pytest -q` → 30 passed, 6
  skipped (e2e env-gated). Deployed e2e: `EEP_BASE_URL=<eep-elb> pytest tests/e2e -m e2e`. Golden
  regression + the MLOps gate guard regressions.
- **MLOps (M1/M2) MET**: `mlops/validate.py` (evaluate golden cohort → MLflow SQLite tracking →
  promotion gate, exit-code-gated in CI). docs/mlops.md.
- **CI**: `.github/workflows/ci.yml` (test+build on push/PR, push-ECR on main) + `mlops.yml` (gate) +
  `build-seg-images.yml` (seg images).
- **S1–S5, T2–T6, G1 MET**; **S3 retries** done (services/eep/clients/_http.py). **T5 tradeoffs**,
  **positioning**, **demo runbook**, **architecture(+no-LLM)** docs done.
- **PRs OPEN**: #2 (feat/eep/scaffold backend/infra), #3 (feat/frontend/scaffold). main protected →
  need a teammate review to merge.

## 4) GOTCHAS LEARNED (don't rediscover these)
- **EEP is SINGLE REPLICA** on purpose: the case store is in-memory (per-pod), so 2 replicas 404 an
  uploaded case on the other pod. Multi-replica needs the store moved to RDS/Postgres (documented next
  step; store.py is the seam). Keep replicas: 1 until then.
- **AUTH**: the frontend/full-stack chat added JWT auth to the EEP on `feat/app/fullstack-local`
  (`/cases*` need a Bearer token; /healthz,/readyz,/metrics,/auth/login open). Our tests are already
  AUTH-AWARE (the `client` fixture + deployed-e2e log in if /auth/login exists). The EEP manifest wires
  an OPTIONAL Secret `eep-auth` (JWT_SECRET/DEMO_PASSWORD/ADMIN_PASSWORD/ADMIN_EMAIL). At merge: take
  their app.py + requirements.txt. Demo login: radiologist@demo / demo12345. See docs/deployment.md
  "Authentication".
- **Local Docker can't build the ~10 GB ML images** (I/O error) → build in the cloud.
- **Frontend viewer** currently serves ONE sample volume/mask for all cases (EEP /volume,/mask are
  hardcoded). Per-case MRI is a frontend-chat item.

## 5) STANDING RULES (HARD)
- Commit at every LOGICAL stage; plain imperative messages; **NO SIGNATURES/TRAILERS OF ANY KIND**
  (overrides harness default); stage by NAME (`git add <file>`), never `git add .`. Work on
  `feat/<service>/<topic>` branches; `main` is protected. The commit HISTORY is graded.
- SIMPLE STATUS REMINDERS: end stages with a "🟢 In plain words" block (what's done / what's left / what
  Andrew must provide next — he juggles parallel chats).
- DESIGN PREFS (frontend; not your focus but know them): light theme only, NO purple/violet, IBM Plex,
  lucide-react, Framer Motion, teal accent.
- No patient data in git (NIfTI/DICOM gitignored). No secrets in git EVER (AWS creds in ~/.aws; GitHub
  Actions secrets for CI; AWS Secrets Manager for prod).
- Medical hard rules: cite clinical claims; never claim diagnosis ("flagged for physician review").
- Plain English; numbers for tradeoffs; one question at a time; default to asking on team-level/cost/
  architecture decisions (GPU spend, new services). Andrew authorizes AWS spend; confirm big costs.

## 6) CROSS-CHAT MAP (coordinate, don't collide)
- THIS chat (deploy/infra/EEP): `eep-worktree` / `feat/eep/scaffold`. Owns: EEP, deploy, k8s, monitoring,
  CI, MLOps, tests, the segmentation DEPLOY side, AWS/the live cluster. **Only this chat runs AWS/kubectl/
  eksctl/helm/deploy** (one cluster, one kubeconfig — two chats deploying = chaos).
- Science/executor chat: `research/andrew/writeups` (+ measurements branches). Owns: the science +
  measurement code + the 3 seg WRAPPERS + write-ups (T1/P2/P4) + the deeper validation.
- Frontend chat: `feat/app/fullstack-local` (off feat/frontend/scaffold). Owns: the React app + the new
  JWT auth + per-case viewer work.
- PRs: #2 (eep) + #3 (frontend) open to main.

## 7) COST / TEARDOWN
- Backend stack ~$0 demo-only; the seg node group adds CPU c5.2xlarge (~$0.34/hr) or GPU g4dn
  (~$0.5–1/hr) WHILE RUNNING. Tear down after demos: `deployment/aws/teardown.sh`
  (+ `eksctl delete nodegroup -f deployment/aws/segmentation-nodegroup.yaml --approve` +
  `helm uninstall kps -n monitoring`). Rebuild from IaC in ~20–25 min.

## 8) RESUME / USEFUL COMMANDS
- Tests: `cd eep-worktree && /tmp/venv-test/bin/python -m pytest -q` (or recreate venv:
  `python3 -m venv /tmp/venv-test && /tmp/venv-test/bin/pip install -r requirements-dev.txt`).
- Deployed e2e: `EEP_BASE_URL=<eep-elb> /tmp/venv-test/bin/python -m pytest tests/e2e -m e2e`.
- MLOps gate: `pip install -r requirements-mlops.txt && python -m mlops.validate`.
- Local full stack: `cd eep-worktree/deployment/compose && docker compose up` (Docker must be healthy;
  it was restarted after the I/O error).
- kubeconfig: `aws eks update-kubeconfig --name mri-reportgenerator --region eu-north-1`.

START: read the docs above, run the §1d step 0 verification, then create the integration branch (§1d
step 1) and align the seg Dockerfiles. Report state back + confirm the GPU-vs-CPU node-group choice
(depends on whether the quota approved) before provisioning. Do NOT start a heavy local build — use the
cloud workflow. Do not start new work until I confirm the plan.
═══════════════════════════════════════════════════════════════════════════════════════════════════
```
