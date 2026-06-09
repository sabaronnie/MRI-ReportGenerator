# HANDOFF → Science/measurements chat: wrap the 3 segmentation engines as deployable services

> Paste the block below into the science/executor chat. The deploy side (parallel orchestration, node
> group, Dockerfiles, cloud-build) is already built and waiting — see `docs/segmentation-deploy.md`.
> This is the one thing blocking real, finalized live segmentation.

---

```
═══════════════════════════════════════════════════════════════════════════════
HANDOFF — Science/measurements chat: finalize + SERVICE-WRAP the 3 segmentation engines · 2026-06-08
Paste whole. I am Andrew. Shared account.
═══════════════════════════════════════════════════════════════════════════════

## WHY
The deployment chat is making the website run REAL segmentation (3 engines in parallel on AWS),
replacing the stand-in. The EEP parallel fan-out + node group + Dockerfiles + cloud-build are DONE and
waiting. The blocker: each engine must be a deployable HTTP service running the FINALIZED code. Today
TSS + SCT have wrappers (on scattered branches); SPINEPS has NONE — only colab/group5/...ipynb +
research/group5/run_spineps_alignment.py. You own the science; please deliver the wrapped engines.

## DELIVER (on ONE canonical branch — tell the deploy chat its name)
For EACH engine, a small Flask service (POST /segment multipart NIfTI in → a zip of its mask outputs;
+ GET /healthz), using the FINALIZED measurement-aligned code:
1. TotalSpineSeg — vertebra/disc/canal labelmap (step2_output + step1_levels). (services/segmentation/
   app.py exists — confirm it's the finalized version.)
2. SCT — cord + canal (G3) via sct_deepseg/sct_process_segmentation + SCIseg cord-lesion (G5.1).
   (services/segmentation/sct_app.py exists — confirm finalized + which tasks/outputs.)
3. SPINEPS — per-vertebra instances + endplate-voxel sheets (G4 C1 Cobb). NEW wrapper needed — adapt
   research/group5/run_spineps_alignment.py into a Flask /segment (services/segmentation/spineps_app.py).

## WHAT THE DEPLOY CHAT NEEDS BACK (the exact gaps — answer all 6 per engine)
1. The Flask service file path + entrypoint (e.g. services.segmentation.spineps_app:app).
2. PINNED requirements (exact numpy/torch/package versions). NOTE: TSS(nnU-Net) and SPINEPS(numpy==2.0.2)
   are incompatible → they MUST be separate images. Confirm each engine's pins.
3. The exact INPUT each expects: raw sagittal T2 NIfTI, or TSS's iso-resampled output, or DICOM?
4. The exact OUTPUT filenames each emits (measurements reads: step2_output.nii.gz, step1_levels.nii.gz,
   sct_canal_seg.nii.gz, sct_spinalcord_seg.nii.gz, + the SPINEPS instance/endplate file the G4 Cobb uses).
5. DEPENDENCY ORDER: does each run independently on the raw MRI (→ run all 3 in parallel), or does
   SCT/SPINEPS need TSS's output first (→ staged)? This decides the orchestration.
6. The canonical BRANCH NAME with this finalized code (segmentation + the measurement code that consumes
   it: G1/G2 via TSS, G3 via SCT, G4 via SPINEPS endplate Cobb, G5.1 via SCIseg).

## CONSTRAINTS (deploy chat will containerize to these)
- Device-agnostic (GPU if present, else CPU). TSS is ~35 min/case on CPU → GPU strongly preferred
  (deploy chat is handling the AWS GPU quota).
- Licenses: TSS+SCT LGPLv3, SPINEPS Apache-2.0 — confirm TPTBox `spinestats` submodule is NOT AGPL
  before bundling.

## RULES
Granular commits, NO signatures, stage by name, feat/<topic> branch + PR, update SESSION_LOG. No patient
data/secrets in git. You may launch research to verify SPINEPS/TPTBox licensing + the env pins.

START: name the canonical branch, then for each engine give the 6 items above. Wrap SPINEPS first (it's
the gap). Once delivered, the deploy chat cloud-builds the 3 images → ECR → deploys → sets SEG_*_URL.
═══════════════════════════════════════════════════════════════════════════════
```
