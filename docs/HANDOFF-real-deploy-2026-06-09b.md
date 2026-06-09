═══════════════════════════════════════════════════════════════════════════════════════════════════
MASTER HANDOFF — MRI-ReportGenerator · REAL (live 3-engine) DEPLOYMENT chat · 2026-06-09 (evening)
I am Andrew. SHARED Claude account (memories default to me). Paste this whole file into the new chat.
═══════════════════════════════════════════════════════════════════════════════════════════════════

## 0) IDENTITY + WHAT THIS CHAT IS
- Shared account → I am **Andrew**. This is the **deployment / infra** chat. ONLY this chat runs AWS /
  kubectl / eksctl (one cluster, one kubeconfig).
- Local root: `/Users/andrew/Desktop/AUB/Spring 26/EECE 503n/Project/` with the repo `MRI-ReportGenerator/`
  + sibling git WORKTREES (all one repo, shared .git): `eep-worktree/` (branch `feat/seg/deploy`),
  `integration-worktree/` (branch `feat/eep/auth-async-integration`), `frontend-worktree/`,
  `measurements-worktree/`, etc.

## 1) ⚠️ THE GOAL CHANGED — read this first
The **professor gave permission to TURN OFF the AWS deployment**. He will **run the 3 open segmentation
models himself, on his own compute**. So:
- The AWS deployment is now just a **validation environment** (prove the infra works), not a permanent
  demo. **We can tear it down to stop cost once validated.**
- The real DELIVERABLE = **correct, reproducible, documented infrastructure** in the repo: the 3 seg
  Dockerfiles, the k8s manifests, the node-group IaC, the EEP orchestration, and the **runbook**.
- GPU quota / our own compute no longer matters — he brings his own.

## 2) ⚠️⚠️ TWO THINGS ANDREW EXPLICITLY WANTS DONE
A. **REMOVE the dummy / "canned demo" entirely** (code + deployed). It maps demo MRI uploads to prepared
   PDFs — built ONLY to survive the live presentation, which is now OVER. It must be gone. **It was NEVER
   committed to git** (kept local per Andrew's "no record on GitHub" instruction). See §6 for exactly
   where the canned code lives and how to remove it. NOTE: **the currently-DEPLOYED `mri-eep:latest`
   (digest sha256:6a3c2ff1e243) IS the canned version** — redeploying the clean integration EEP removes it.
B. **The RUNBOOK is the most important deliverable** — "how to stand this up and run the 3 models", as
   detailed/clear as possible. DONE (see §5) but keep improving it (Andrew wants sample outputs added).

## 3) WHERE WE ARE (the real-deployment track)
### DONE
- **3 seg engines containerized + deployed on EKS** (TotalSpineSeg, SCT, SPINEPS). 5 first-run dep/env
  bugs fixed (kornia<0.8, --no-stalling, /dev/shm, SPINEPS weights bake + -cpu + RAM). All committed on
  `feat/seg/deploy`.
- **Corrected seg images in ECR + DEPLOYED** (running on the seg node now):
  `mri-seg-tss` = **sha256:2385df2a34c2** (the LATEST fix: TSS now exports the iso volume for SCT),
  `mri-seg-sct` = sha256:9598022edff1, `mri-seg-spineps` = sha256:de5d899c1375. All 3 pods Running, healthz ok.
- **Seg node group swapped to `r5.2xlarge` (8 vCPU / 64 GB)** because **SPINEPS CPU inference OOM-killed at a
  28 Gi limit on the 32 GB m5 node**. SPINEPS mem limit raised to 40 Gi. IaC: `eep-worktree/deployment/aws/
  segmentation-nodegroup.yaml` + `deployment/k8s/segmentation.yaml`. Committed.
- **EEP segmentation client REWRITTEN to the real DAG** (was a wrong 3-way parallel `/segment` fan-out):
  now **TSS ∥ SPINEPS on /segment (parallel) → SCT on /segment-sct (consuming the TSS zip's input_iso)**;
  SCT/SPINEPS non-fatal. File: `integration-worktree/services/eep/clients/segmentation.py`. Tests updated
  (test_segmentation_fanout.py + test_async_upload.py, 49 EEP tests pass). **Committed on the integration
  branch: `feat/eep/auth-async-integration` @ 7c84911.**
- **RUNBOOK written + committed** on `feat/seg/deploy` @ 04c1924:
  `eep-worktree/docs/RUNBOOK-run-the-3-models.md`.

### VALIDATION RESULT SO FAR (partial — re-run cleanly to finish)
- **SPINEPS ✅ PROVEN** on the 64 GB node: returned http=200, 165 KB zip with `spineps_seg-vert_msk.nii.gz`
  + `spineps_seg-spine_msk.nii.gz`, **NO OOM** (the r5 swap + 40 Gi limit fixed the previous OOM-kill).
- **TSS ❌ disrupted, NOT a bug:** a leftover watcher did `kubectl rollout restart deploy/seg-tss` MID-RUN
  → the TSS pod was killed mid-request → "empty reply". The iso-fixed TSS image (2385df2a) is correctly
  deployed; a clean run (no concurrent rollout) should work.
- **SCT ❌ only downstream:** failed because the TSS zip was empty (TSS failed). Should chain once TSS runs.

### IN PROGRESS / NEXT (do in this order)
1. **RE-VALIDATE the pipeline (CLEAN run — no concurrent rollouts).** See §7. Expect TSS→SCT to now chain
   (input_iso fix) — SPINEPS already proven. Confirm all 3 produce masks + a merged zip. CAVEAT learned:
   `kubectl cp` of the 7 MB sample sometimes truncates on an I/O timeout → engines 500 on the corrupt
   file. Verify the in-pod input is **7437117 bytes** before launching.
2. **REMOVE the canned demo** (§6 + §2A).
3. **Rebuild the CLEAN integration EEP** (has the DAG fix, NO canned) → push `mri-eep:latest` → deploy.
   Then **wire SEG_*_URL** (`SEG_TSS_URL=http://seg-tss:8083 SEG_SCT_URL=http://seg-sct:8084
   SEG_SPINEPS_URL=http://seg-spineps:8085`) on the EEP so a real upload runs the live DAG. NOTE the EEP
   has the **async-upload** path (202 + background worker) for the minutes-long seg.
4. **Rebuild the measurements image** from the finalized branch so G3 (SCT) / G4 (SPINEPS endplate) / G5.1
   (SCIseg lesion) read the real seg outputs (`sct_lesion_seg.nii.gz`, `spineps_seg-vert_msk.nii.gz`).
5. **Live e2e** on AWS: real upload → live DAG → measurements → report (proof the infra is complete).
6. **TEARDOWN AWS** to stop cost (§8). Make sure the repo infra is complete + the runbook is final FIRST.

## 4) AWS FACTS
- Account **658132201414**, region **eu-north-1**. IAM user `mri-deploy` (AdministratorAccess); creds in
  `~/.aws` (gitignored). EKS cluster **mri-reportgenerator** (k8s 1.31). `eksctl`/`kubectl`/`helm` installed.
- Namespace **mri**: eep (1 replica), frontend, measurements, reporting, + seg-tss/sct/spineps (+ a helper
  pod `segdriver`). Seg node group **ng-seg-cpu** = 1× r5.2xlarge (taint workload=segmentation).
- ECR repos: mri-eep, mri-measurements, mri-reporting, mri-frontend, mri-seg-tss/sct/spineps.
  S3: `mri-reportgenerator-samples-658132201414` (has the stand-in seg zip + a `builds/` prefix used for
  cloud-build contexts). IAM role/instance-profile **mri-seg-builder** (ECR push + SSM + S3) for EC2 builders.
- **LIVE URLs (ephemeral ELB; re-fetch `kubectl -n mri get svc eep frontend -o wide`):**
  FE  http://a359d7957b43847a69ba05ef7b9fad98-1651813190.eu-north-1.elb.amazonaws.com
  EEP http://a08443535da2a4ee5856aeb58f0ae7f7-167484581.eu-north-1.elb.amazonaws.com
- **GPU quota still 0** ("Running On-Demand G and VT", L-DB2E81BA; request to 16 = CASE_OPENED, never
  approved). Standard On-Demand quota = 16 vCPU → EKS default (2× t3.medium = 4) + seg node (8) = 12; a
  cloud builder must be ≤ 4 vCPU (c5.xlarge) to stay ≤ 16. **Local Docker is DEAD** (Docker Desktop crashed
  on a full disk) → BUILD IN THE CLOUD: launch an ephemeral EC2 (AMI ami-05ec2ffaee0a0e6d4, profile
  mri-seg-builder, subnet subnet-06af28598a535e550), userdata installs docker + pulls a tarball from
  `s3://.../builds/` + `docker build` + push. Pattern proven this session (see /tmp/ud-*.sh examples).

## 5) THE RUNBOOK (the key deliverable)
`eep-worktree/docs/RUNBOOK-run-the-3-models.md` (committed @ 04c1924). Contents: the 3-model table + the
DAG diagram; **Part A** = run the 3 models with Docker only (build 3 images, `docker run` with the exact
`--shm-size`/`-m 40g`/`--gpus all` flags, 4 curls for TSS∥SPINEPS→SCT, inspect masks); **Part B** = full
AWS EKS deploy; compute requirements (TSS ~3.5 min CPU, SPINEPS ≥32 GB RAM CPU, GPU option); and a
"gotchas already fixed" list. TODO: add a real sample output bundle / screenshots once §3.1 validates.

## 6) CANNED-DEMO REMOVAL — exact locations (NONE of this is in git; remove all)
- `/tmp/eep-build/` — a COPY of the integration EEP **patched with the canned demo** (this is what built
  the deployed `mri-eep:latest` 6a3c2ff). Files added/edited there: `services/eep/demo.py`,
  `services/eep/demo_assets/*.pdf`, and demo branches in `config.py`, `store.py` (create_demo_case),
  `orchestration.py` (process_upload demo check), `routers/cases.py` (report.html PDF embed),
  `workflow/router.py` (report.pdf). **Just delete `/tmp/eep-build`.** The integration-worktree itself is
  CLEAN (canned was never applied there) — so rebuilding `mri-eep` from `integration-worktree` gives a
  canned-free image. Deploy that to remove canned from the cluster.
- `eep-worktree/` working tree — the FIRST canned demo (earlier, on feat/seg/deploy) is present as
  UNTRACKED/uncommitted local files: `services/eep/demo.py`, `services/eep/demo_assets/`,
  `services/eep/fixtures/case-demo-*.json`, plus uncommitted edits to config/store/orchestration/cases/
  eep.yaml. Git history was already scrubbed (force-pushed). **Run `git -C eep-worktree status` and
  `git checkout`/`rm` to drop them**; also delete local branch `_local_canned_demo` (`git branch -D`).
- The 2 prepared demo PDFs came from `~/Downloads/Demo.zip` (MRI_mmcsd-csm-002 + MRI_sub-amu01 + their
  report PDFs). Keep the zip; just don't ship the canned code.

## 7) RESUME COMMANDS
```bash
aws eks update-kubeconfig --name mri-reportgenerator --region eu-north-1
kubectl -n mri get pods                                   # seg-tss(2385df2a)/sct/spineps Running on r5
# (re)validate the 3-engine DAG on one MRI via the in-cluster helper pod 'segdriver':
S="frontend-worktree/deployment/compose/sample_data/sample_volume_T2.nii.gz"   # a real sagittal T2 (7.4MB)
kubectl -n mri exec segdriver -- rm -f /tmp/input.nii.gz
kubectl -n mri cp "$S" segdriver:/tmp/input.nii.gz
kubectl -n mri exec segdriver -- sh -c 'test $(wc -c </tmp/input.nii.gz) -gt 7000000 && echo OK'   # MUST be 7437117
# /tmp/pipe.sh already in segdriver runs TSS∥SPINEPS→SCT; relaunch:
kubectl -n mri exec segdriver -- sh -c 'rm -f /tmp/*.zip /tmp/STATUS; nohup sh /tmp/pipe.sh >/tmp/pipe.log 2>&1 &'
# poll: kubectl -n mri exec segdriver -- cat /tmp/STATUS   (expect TSS http=200 big, SPINEPS http=200, SCT http=200)
# EEP tests: cd integration-worktree && /tmp/venv-test/bin/python -m pytest services/eep/tests -q  (recreate venv: python3 -m venv /tmp/venv-test && pip install -r services/eep/requirements.txt pytest)
```
Seg service ports/endpoints: TSS seg-tss:8083 `/segment`; SCT seg-sct:8084 `/segment-sct`; SPINEPS
seg-spineps:8085 `/segment`. Cloud-build context tarballs live in `s3://.../builds/`.

## 8) TEARDOWN (after validation + repo/runbook final)
```bash
eksctl delete nodegroup -f eep-worktree/deployment/aws/segmentation-nodegroup.yaml --approve
# optional full: eksctl delete cluster --name mri-reportgenerator --region eu-north-1
aws ec2 describe-instances --filters Name=tag:ephemeral,Values=true Name=instance-state-name,Values=running \
  --query 'Reservations[].Instances[].InstanceId' --output text --region eu-north-1   # any leftover builders -> terminate
```

## 9) STANDING RULES
Commit at logical stages; plain imperative messages; **NO signatures/trailers**; stage by name; never
`git add .`; `main` protected. No patient data / no secrets in git. The canned demo must NOT be committed.
Cite clinical claims; never claim diagnosis. The DAG fix is on `feat/eep/auth-async-integration`; the seg
images/Dockerfiles/manifests/runbook are on `feat/seg/deploy` — these two branches need reconciling
(both descend from the same seg work; the integration branch is the canonical app, feat/seg/deploy has the
newest seg Dockerfile/segmenter fixes + runbook). Decide the merge with the team.

START: read this, run the §7 kubeconfig + `kubectl -n mri get pods`, re-validate the DAG (§3.1/§7), then
do §2A (remove canned) + §3.3 (clean EEP + wire SEG_*_URL). Don't start a heavy LOCAL docker build (Docker
is dead) — use a cloud builder. Confirm with Andrew before tearing down AWS.
═══════════════════════════════════════════════════════════════════════════════════════════════════
