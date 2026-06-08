# Live segmentation deployment — 3 engines, in parallel

Goal: make the website run the **real segmentation** on upload (replacing the bundled stand-in), with
the **3 engines fanned out in parallel** by the EEP → masks merged → measurements → report.

## The 3 engines
| Engine | Produces | Image | License | Notes |
|--------|----------|-------|---------|-------|
| **TotalSpineSeg** | vertebra/disc/canal labelmap (G1/G2) — `step2_output`, `step1_levels` | `mri-seg-tss` | LGPLv3 | nnU-Net based; ~10 GB image; ~35 min/case on CPU |
| **SCT** | cord & canal diameters (G3) + SCIseg cord-lesion (G5.1) | `mri-seg-sct` | LGPLv3 | `sct_deepseg` / `sct_process_segmentation` |
| **SPINEPS** | per-vertebra instances + endplate sheets (G4 Cobb) | `mri-seg-spineps` | Apache-2.0 | uses TPTBox; **pins `numpy==2.0.2`** |

**Why 3 separate images:** TSS (nnU-Net) and SPINEPS pin **incompatible numpy** versions → they cannot
share a process/image. Each is an independent service taking the raw sagittal T2 NIfTI.

## Orchestration (the parallel part — already built)
The EEP fans out to all three concurrently and merges their masks:
```
upload ─▶ EEP ─┬─▶ POST tss:/segment      ┐
               ├─▶ POST sct:/segment      ├─ asyncio.gather (PARALLEL) ─▶ merge zip ─▶ measurements ─▶ report
               └─▶ POST spineps:/segment  ┘
```
- Code: `services/eep/clients/segmentation.py` (`run_segmentation_async` = `asyncio.gather` over the 3),
  wired in `orchestration.process_upload`. Filename-agnostic merge (copies whatever each engine returns).
- **Activation:** set `SEG_TSS_URL`, `SEG_SCT_URL`, `SEG_SPINEPS_URL`. When all three are set, uploads
  run real segmentation; otherwise the EEP uses the stand-in (current demo keeps working). `/readyz`
  reports `segmentation_ready`.
- Failure-safe: any engine error falls back to the stand-in, never crashes the upload.

## Build (in the cloud — NOT on a laptop)
The images are ~10 GB each (CUDA torch + model weights) — local Docker Desktop can't reliably build them
(disk I/O error on export). Build on amd64 with disk via **`.github/workflows/build-seg-images.yml`**
(manual trigger; pick the finalized seg-code branch + which engines), which frees disk, builds, and
pushes to ECR. Dockerfiles: `deployment/docker/seg-{tss,sct,spineps}.Dockerfile` (device-agnostic).

## Compute (node group)
`deployment/aws/segmentation-nodegroup.yaml` — a tainted node group so the heavy/long model pods don't
crowd the EEP/measurements/reporting:
- **CPU now:** `c5.2xlarge` (8 vCPU/16 GB) — deployable without GPU quota, but **~35 min/case** for TSS.
- **GPU when approved:** `g4dn.xlarge` (commented block) — the On-Demand G/VT quota was 0 on the new
  account; an increase to 16 is **pending** (AWS-timed). Same images run far faster on GPU.

Seg pods need `tolerations: [{key: workload, value: segmentation, effect: NoSchedule}]` +
`nodeSelector: {workload: segmentation}`.

## Dependencies / status (what's blocking real, finalized segmentation)
1. **Science chat must deliver the finalized, service-wrapped engines** (esp. SPINEPS, which has no
   service wrapper yet — only `colab/` + `research/group5/run_spineps_alignment.py`) on a canonical
   branch, with pinned requirements + the exact output filenames. ← the seg-services handoff.
2. **Cloud build** the 3 images from that branch → ECR.
3. **GPU quota** (pending) for usable live latency — else CPU (~35 min/case) or a pre-segmented demo case.
4. Then: deploy the seg node group + 3 services, set `SEG_*_URL` on the EEP, end-to-end test on a real MRI.

**Done on the deploy side (ready to plug in):** the EEP parallel fan-out + `segmentation_ready` +
upload-bytes capture + the node-group IaC + the 3 Dockerfiles + the cloud-build workflow. The blocker is
the finalized, wrapped engine code from the science chat.
