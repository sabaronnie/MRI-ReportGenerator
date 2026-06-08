# Handoff ADDENDUM — the non-obvious things (so the new chat needs nobody)

Read alongside `docs/HANDOFF-deploy-continuation.md` + `docs/segmentation-deploy.md`. These are the
gotchas, the latent bug, and the artifacts I added so steps are pre-done.

## 🔴 #1 CRITICAL — the upload path MUST become asynchronous before real segmentation goes live
Real segmentation takes **minutes** (CPU ~35 min/case for TSS; GPU still tens of seconds–minutes). The
current code runs it **synchronously inside the upload request**, which has TWO problems:
1. **Latent crash:** `orchestration.process_upload` calls `seg.run_segmentation()` →
   `asyncio.run(run_segmentation_async(...))`. But `process_upload` is invoked from the **async** route
   `upload_case`, i.e. inside a running event loop → `asyncio.run()` raises *"cannot be called from a
   running event loop"*. So the moment `SEG_*_URL` are set, uploads would error (and fall back to the
   stand-in via the try/except — masking it). FIX THIS.
2. **Timeout:** even if it ran, a blocking request of minutes exceeds the **Classic ELB idle timeout
   (60s)** + the client + uvicorn → the upload would time out / 504.

**Required change (do this BEFORE wiring SEG_*_URL on the live EEP):** make uploads return `202 queued`
immediately and run segmentation→measurements in the **background**, updating the case as it progresses.
Concrete approach:
- `upload_case` (already async): create the case as `queued` and return `{case_id, status:queued}`
  immediately; schedule the heavy work with FastAPI `BackgroundTasks` (or `asyncio.create_task`).
- The background worker: `await run_segmentation_async(bytes, filename)` (no `asyncio.run` — you're async)
  → write merged seg zip → `MeasurementsClient().measure(...)` → `store.update_case_core(cid, core)` +
  set status `ready` (add a `store.set_core/set_status` method; today only the sim clock mutates it).
- Disable the simulated clock for real-seg cases (drive status from the worker: queued→segmenting→
  measuring→ready), and surface real failures (status `error` + the failed stage) instead of silent
  fallback when seg is supposed to be live.
- Keep the **stand-in fast path synchronous** (it's ~1–2 s) so the current demo is unchanged.
- `run_segmentation` (the sync wrapper) is only safe to call from a NON-async context; prefer the async
  path everywhere in the request flow.

Tests: add an async test that monkeypatches the 3 engine calls + asserts the case goes queued→ready with
the merged core. The existing fan-out tests (test_segmentation_fanout.py) cover the merge.

## 🟢 #2 Pre-done artifacts (so you skip design work)
- **k8s manifests written:** `deployment/k8s/segmentation.yaml` — the 3 Deployments + ClusterIP Services
  (seg-tss:8083, seg-sct:8084, seg-spineps:8085) with the segmentation nodeSelector + toleration + memory
  requests + a commented `nvidia.com/gpu: 1` to uncomment on GPU. Apply with the deploy scripts'
  `apply_template` (it now renders SEG_* too) or `envsubst | kubectl apply`.
- **EEP env wired:** `deployment/k8s/eep.yaml` now has `SEG_TSS_URL/SEG_SCT_URL/SEG_SPINEPS_URL` (empty by
  default → stand-in; set to `http://seg-tss:8083` etc. to go live). `lib.sh apply_template` renders them.
- So your live-wire step is just: deploy `segmentation.yaml`, then re-render eep.yaml with
  `SEG_TSS_URL=http://seg-tss:8083 SEG_SCT_URL=http://seg-sct:8084 SEG_SPINEPS_URL=http://seg-spineps:8085`
  exported, `apply_template eep.yaml`, rollout.

## #3 GPU scheduling math (when the quota lands)
- g4dn.xlarge = **1 GPU / 4 vCPU**. Each seg pod requests 1 GPU → **3 pods need 3 GPUs** for true
  parallel. Your On-Demand G/VT quota request is **16 vCPU** → fits **3× g4dn.xlarge (12 vCPU)** = 3 GPUs.
  Set the GPU node group `desiredCapacity: 3`. (g4dn.12xlarge = 4 GPUs but 48 vCPU > 16 quota — won't fit.)
- eksctl auto-installs the **NVIDIA device plugin** for GPU instance types; verify:
  `kubectl get pods -n kube-system | grep nvidia`. If absent: install the plugin DaemonSet.
- Uncomment the `nvidia.com/gpu: 1` limits in `segmentation.yaml` and the GPU block in
  `segmentation-nodegroup.yaml`. On CPU, leave them commented (works, slow).

## #4 Integration-branch merge (research/andrew/writeups + feat/eep/scaffold)
They touch mostly different files, so the merge is light. Likely conflicts:
- `SESSION_LOG.md` — keep BOTH (append/union).
- `services/segmentation/*` — take the **science** versions (the finalized wrappers: app.py, sct_app.py,
  spineps_app.py). Keep the deploy infra (deployment/*, services/eep/*) from feat/eep/scaffold.
- `docs/*` — keep both where they don't overlap.
Verify after merge: `pytest -q` still green; the 3 wrappers import.

## #5 Build the MEASUREMENTS image from the same finalized branch
The measurement code that consumes the seg outputs (G3 via SCT incl. `sct_lesion_seg.nii.gz`, G4 via
SPINEPS endplate, G5.1 via SCIseg) must be the finalized version. Build `mri-measurements` from the
integration branch too (its `deployment/docker/measurements.Dockerfile`), push, redeploy — else the
measurements IEP won't read the new SCT/SPINEPS outputs correctly.

## #6 Debug a single engine before the full pipeline
After the first cloud build + deploy, smoke-test each engine in isolation:
```
kubectl -n mri port-forward deploy/seg-tss 8083:8083 &
curl -F "file=@<a real sagittal T2 .nii.gz>" http://localhost:8083/segment -o out.zip   # expect a zip
kubectl -n mri logs deploy/seg-tss            # read stderr if /segment 500s (THE smoke test)
```
SCT/SPINEPS were never run end-to-end locally (not installed) — the **first real run is in-cluster**, so
expect 1–2 fix iterations (missing model task, wrong output path, a dep pin). That's normal.

## #7 License loose-end (carry it, don't forget)
SPINEPS dep **TPTBox `spinestats`** — confirm it's NOT AGPL before the SPINEPS image ships publicly
(everything else: TSS/SCT LGPLv3, SPINEPS Apache-2.0 — fine). The science chat flagged this; verify
before a public push.

## #8 Frontend processing UX (heads-up, frontend chat owns it)
With real (minutes-long) segmentation, the frontend's 8s simulated "processing" clock will say *ready*
too early. Once the upload is async (#1) and the case carries real status, the frontend should poll
`/cases/{id}/job` and show real progress. Coordinate with the frontend chat.

## #9 Don't forget
- Re-fetch live URLs (`kubectl -n mri get svc ... -o wide`) — they change per deploy.
- Teardown the seg node group after demos (it's the expensive part): `eksctl delete nodegroup -f
  deployment/aws/segmentation-nodegroup.yaml --approve`.
- Update `docs/RUBRIC_TRACKER.md` once segmentation is a real deployed IEP (it upgrades GT3/T3/T4 to
  genuine *parallel* model interaction — a strong demo point).
