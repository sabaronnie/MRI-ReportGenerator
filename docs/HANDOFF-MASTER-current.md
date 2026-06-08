# MASTER HANDOFF (CURRENT) — paste this whole file into the new chat · 2026-06-09

I am Andrew. SHARED Claude account (memories default to me). This continues the DEPLOYMENT/INFRA/EEP
advisory + the live 3-engine segmentation deploy. Read this top to bottom; it omits nothing.

═══════════════════════════════════════════════════════════════════════════════════════════════════
## 0) IDENTITY + READ ORDER (before anything)
- I am **Andrew**. This is the deployment/infra/EEP chat (NOT the science chat, NOT the frontend chat).
- READ IN ORDER: (1) memory `MEMORY.md` + the files it points to; (2) `MRI-ReportGenerator/CLAUDE.md`;
  (3) `SESSION_LOG.md` (top entries 2026-06-08/09 are mine, cont.1→cont.6); (4) on branch
  `feat/eep/scaffold` (or the integration branch `feat/seg/deploy`): `docs/HANDOFF-deploy-continuation.md`,
  `docs/HANDOFF-addendum.md`, `docs/segmentation-deploy.md`, `docs/seg-services-handoff.md`,
  `docs/RUBRIC_TRACKER.md`, `docs/deployment.md`, `docs/monitoring.md`, `docs/mlops.md`, `docs/ci.md`,
  `docs/tradeoffs.md`, `docs/positioning.md`, `docs/demo-script.md`, `docs/architecture.md`.
- Local root: `/Users/andrew/Desktop/AUB/Spring 26/EECE 503n/Project/` with `MRI-ReportGenerator/` (repo)
  + sibling worktrees (`eep-worktree/` = the deploy/infra worktree). Multiple chats share `~/.aws`.

## 1) ⚠️ THE LIVE TASK — finish real 3-engine segmentation on AWS (IN PROGRESS in the "Deployment v2" chat)
GOAL: the website upload runs REAL segmentation (TotalSpineSeg + SCT + SPINEPS) → measurements → report,
replacing the stand-in. **Path chosen: CPU (no GPU quota yet) → pre-run one MRI and CACHE the real outputs
so the demo shows real segmentation instantly (CPU live = ~35 min/case TSS).**

### LATEST STATE (as of 2026-06-09, the Deployment v2 chat):
- ✅ **All 3 engine IMAGES built clean (first try) + in ECR**: `mri-seg-tss` 7.4 GB, `mri-seg-sct` 3.0 GB,
  `mri-seg-spineps` 3.6 GB. Built on a throwaway **c5.2xlarge** EC2 builder (200 GB disk, IAM instance
  role — NO creds in GitHub), now terminated.
- ✅ **Integration branch `feat/seg/deploy`** pushed = merge of `feat/eep/scaffold` (deploy infra: EEP
  fan-out, Dockerfiles, node group, workflow) + `research/andrew/writeups` (the science wrappers +
  finalized measurements). 170 tests green.
- ✅ **Seg node group**: `m5.2xlarge` (8 vCPU / **32 GB** — memory-optimized so all 3 ML pods schedule +
  run concurrently without OOM; same vCPU quota; ~$0.45/hr). Tainted `workload=segmentation`. Pods'
  gunicorn timeout overridden to 5400s (CPU TSS can exceed 30 min).
- 🔄 **First real run = the predicted SMOKE TEST.** It surfaced **3 upstream dependency bugs (none in our
  code), diagnosed live in-pod + fixed + committed:**
  1. **TSS** — `kornia 0.8` removed `kornia.core.Tensor`, breaking totalspineseg's aug lib → **pin
     `kornia<0.8`**. (Weights 4.1 GB present.)
  2. **SPINEPS** — weights weren't downloading; release ships `checkpoint_final.pth` but loader wants
     `checkpoint_best.pth`; needs a 3rd "labeling" model; hard-defaults to GPU (crashes on CPU) → **bake
     all 3 model downloads + `final→best` copy into the image + add a device-aware `--cpu` flag** to the
     wrapper.
  3. **torch 2.12 is fine** — no downgrade.
- 🔄 Currently running **real CPU inference in the live pods** to validate the fixes BEFORE rebuilding
  (cheaper than guess-and-rebuild). CPU inference is ~10–30 min/engine.
- Pipeline order discovered: **TSS | SPINEPS run in parallel → then SCT** (SCT is staged after). Note this
  for the EEP orchestration (the current fan-out runs all 3 in parallel; SCT may need to wait for/consume
  TSS output — verify against the wrappers).

### REMAINING STEPS (the Deployment v2 chat's open to-dos):
1. Confirm both TSS + SPINEPS produce masks on CPU in-pod (validation in progress).
2. **Rebuild corrected TSS+SPINEPS images** on the EC2 builder → ECR → redeploy.
3. Run the **full staged pipeline (TSS|SPINEPS → SCT) via HTTP** → real merged outputs.
4. Merge outputs + run **finalized measurements** (G4 via SPINEPS endplate, G5.1 via SCIseg `sct_lesion_seg.nii.gz`).
5. **Seed the merged real seg zip as the served output** (cache) → redeploy EEP → **e2e on the website** →
   update `RUBRIC_TRACKER` + `SESSION_LOG` + `DEVELOPMENT_JOURNEY`.

### ⚠️ CRITICAL latent bug to fix before live-upload segmentation (see docs/HANDOFF-addendum.md §1):
The EEP runs segmentation **synchronously** in the upload request → (a) `asyncio.run()` inside the async
route will crash when `SEG_*_URL` are set; (b) a minutes-long request exceeds the 60s ELB timeout. For the
**cached-output demo this may be sidestepped** (serve the pre-run zip), but for genuine live upload the
upload must become **async/background** (return 202, run seg→measure in a background task, update status).

## 2) ⚠️ COORDINATION — the website/auth deploy MUST fold into this (don't deploy twice)
- The currently-deployed EEP (`feat/eep/scaffold`) does NOT have the frontend chat's **JWT auth + PDF +
  demo cases + latest frontend** (those are on `feat/app/fullstack-local`).
- There can be only **one EEP image** — it needs BOTH auth AND the seg fan-out. So **`feat/app/fullstack-
  local` MUST be merged into `feat/seg/deploy`** before the final EEP deploy, or the website ships without
  auth/latest frontend.
- New infra the auth needs: the optional **`eep-auth` Secret** (JWT_SECRET/DEMO_PASSWORD/ADMIN_PASSWORD/
  ADMIN_EMAIL — already wired in eep.yaml; demo login `radiologist@demo`/`demo12345`) + a **PersistentVolume
  for the SQLite user DB**. See `docs/deployment.md` "Authentication".
- RULE: **only ONE chat runs AWS/kubectl/eksctl** (the deploy owner = the Deployment v2 chat). Other chats
  PREP + hand off a runbook. Two chats deploying = cluster corruption.

## 3) AWS ACCOUNT + CLUSTER
- Account **658132201414**, region **eu-north-1**. IAM user `mri-deploy` (AdministratorAccess), creds in
  `~/.aws`. Budget alert $20/mo → andrew.2119.khoury@gmail.com. (NOTE: a secret key was shown in a
  screenshot once — optionally rotate via IAM.)
- EKS cluster **mri-reportgenerator** (k8s 1.31): default ng 2× t3.medium + seg ng **m5.2xlarge** (tainted).
- Namespaces: **mri** (eep [**1 replica** — in-memory store is per-pod], measurements, reporting, frontend,
  + seg-tss/seg-sct/seg-spineps coming) + **monitoring** (kube-prometheus-stack: Prometheus + Grafana).
- ECR: mri-eep, mri-measurements, mri-reporting, mri-frontend, mri-seg-tss, mri-seg-sct, mri-seg-spineps.
  S3: mri-reportgenerator-samples-658132201414 (viewer NIfTI + stand-in seg zip).
- **GPU quota** "Running On-Demand G and VT instances" (L-DB2E81BA) = **0**; increase to **16** PENDING
  (Andrew can escalate via AWS Support case). Standard quota = 16 (cluster uses ~12 now incl. seg node).
- **GPU toggle when approved (no rebuild, ~10 min):** uncomment the g4dn block in
  `deployment/aws/segmentation-nodegroup.yaml` (desiredCapacity 3) → `eksctl create nodegroup`; verify
  `kubectl get pods -n kube-system | grep nvidia`; uncomment `nvidia.com/gpu: 1` in
  `deployment/k8s/segmentation.yaml` → re-apply. Images are device-agnostic (already have `--cpu`/GPU paths).
- **LIVE URLs are EPHEMERAL** — re-fetch: `kubectl -n mri get svc eep frontend -o wide`;
  `kubectl -n monitoring get svc kps-grafana` (Grafana admin/mri-demo-admin).

## 4) CURRENT SYSTEM STATE (live + verified, before seg)
- **GT1/GT2/GT3 MET**; deployed e2e 5/5 green. EEP (FastAPI) orchestrates measurements + reporting IEPs;
  endpoints: /cases, POST /cases (upload, validation, rate-limit), /cases/{id}, /job, /sign-off, /volume,
  /mask, **/cases/{id}/report.html**, /healthz, /readyz (has segmentation_ready), /metrics, /docs.
- **Monitoring (M3) MET**: Prometheus+Grafana, ServiceMonitors, dashboard "MRI-ReportGenerator — Services"
  (throughput, error rate by class, p50/p95 latency, IEP durations, ML-signal pathology-flag panel).
  Public Grafana URL works; can embed in the app via an iframe + `GF_SECURITY_ALLOW_EMBEDDING=true` if wanted.
- **Tests (Q1/Q2) MET**: `cd eep-worktree && /tmp/venv-test/bin/python -m pytest -q` → 30 passed (unit +
  integration + golden; deployed e2e env-gated + auth-aware). **MLOps (M1/M2) MET**: `mlops/validate.py` +
  MLflow + gate. **CI**: ci.yml + mlops.yml + build-seg-images.yml. **S1–S5/T2–T6/G1 MET**; S3 retries done.
- Docs DONE: tradeoffs (6, evidence), positioning (P1–P4, cited shortage/wait-time/inter-observer numbers;
  [SCIENCE] placeholders for the science chat), architecture (+no-LLM §6 N/A), demo-script, deployment,
  monitoring, mlops, ci.
- **PRs OPEN**: #2 (feat/eep/scaffold), #3 (feat/frontend/scaffold) → main (protected; need teammate review).

## 5) RUBRIC STATUS (what's left)
- GREEN: GT1/2/3, S1–S5, T2–T6, Q1/Q2, M1–M4, G1, C2, D5, CI.
- LEFT (mostly NOT deploy): live segmentation finishing (in progress → upgrades GT3/T3/T4 to genuine
  PARALLEL model interaction + makes the pipeline truly end-to-end); merge PRs #2/#3 (teammate review);
  the website/auth merge into feat/seg/deploy; slides + Q&A (D1–D4, use demo-script.md); science write-ups
  (T1/P2/P4 — other chat); business one-pager + novelty vs the duplicate-title team (C1/P3 — team).

## 6) GOTCHAS (don't rediscover)
- EEP **single replica** (in-memory store per-pod; 2 replicas 404 uploaded cases; RDS = multi-replica path).
- **Local Docker can't build the ~10 GB ML images** (I/O error) → build on a throwaway EC2 (c5/m5 + big EBS).
- **Builder must be terminated before the seg node group** (shared 16-vCPU standard quota).
- Seg first-run = smoke test; upstream dep bugs are normal (kornia, SPINEPS weights/CPU — already fixed).
- Auth-aware tests: the `client` fixture + deployed-e2e log in if `/auth/login` exists.

## 7) STANDING RULES (HARD)
- Commit every logical stage; plain imperative messages; **NO SIGNATURES/TRAILERS OF ANY KIND**; stage by
  NAME, never `git add .`; feat/<topic> branches; main protected; history is graded.
- End stages with a "🟢 In plain words" status (done / left / what Andrew must provide). No patient data /
  no secrets in git. Cite clinical claims; never claim diagnosis. Confirm big AWS costs before provisioning.
- ONLY the deploy-owner chat runs AWS/kubectl/eksctl/helm.

## 8) CROSS-CHAT MAP
- Deploy/infra (this track): `feat/seg/deploy` (integration) / `feat/eep/scaffold`. Owns EEP/deploy/k8s/
  monitoring/CI/MLOps/tests/seg-deploy + the live cluster.
- Science chat: `research/andrew/writeups` — science + measurements + the 3 seg wrappers + write-ups.
- Frontend chat: `feat/app/fullstack-local` — React app + JWT auth + PDF + per-case viewer.

## 9) COST / TEARDOWN (after the demo)
`deployment/aws/teardown.sh` + `eksctl delete nodegroup -f deployment/aws/segmentation-nodegroup.yaml
--approve` + `helm uninstall kps -n monitoring`. The seg m5.2xlarge (~$0.45/hr) + GPU (if added) are the
costly parts. Rebuild from IaC in ~25 min.

## 10) RESUME COMMANDS
- kubeconfig: `aws eks update-kubeconfig --name mri-reportgenerator --region eu-north-1`.
- Tests: `cd eep-worktree && /tmp/venv-test/bin/python -m pytest -q` (venv: `python3 -m venv /tmp/venv-test
  && /tmp/venv-test/bin/pip install -r requirements-dev.txt`).
- Deployed e2e: `EEP_BASE_URL=<eep-elb> /tmp/venv-test/bin/python -m pytest tests/e2e -m e2e`.
- MLOps: `python -m mlops.validate`. Local stack: `cd eep-worktree/deployment/compose && docker compose up`.

START: read the docs; confirm whether the Deployment v2 chat is still the live AWS owner (don't double-
deploy); then continue the seg finish (§1 remaining steps) AND ensure the frontend/auth merge into
feat/seg/deploy (§2) lands before the final EEP deploy. Do NOT run heavy local builds (use EC2). Report
state back + confirm before provisioning/teardown. Don't start new work until Andrew confirms.
═══════════════════════════════════════════════════════════════════════════════════════════════════
