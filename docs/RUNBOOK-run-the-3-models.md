# Runbook — Stand up the pipeline & run the 3 segmentation models

This is a **copy‑paste, step‑by‑step** guide to (A) run the 3 open segmentation models on one MRI, and
(B) deploy the whole app on AWS. If you only want to **verify the 3 models run**, do **Part A** — it
needs nothing but Docker.

---

## 0. The 3 models and how they connect

| Model | What it does | License | Service | Endpoint | Port |
|-------|--------------|---------|---------|----------|------|
| **TotalSpineSeg** (nnU‑Net) | vertebra + disc + canal labelmap, and the 1 mm‑iso resampled volume | LGPL‑3.0 | `seg-tss` | `POST /segment` | 8083 |
| **SPINEPS** | per‑vertebra instances + endplate sheets (for the C3–C7 Cobb angle) | Apache‑2.0 | `seg-spineps` | `POST /segment` | 8085 |
| **Spinal Cord Toolbox (SCT)** | spinal‑cord & dural‑sac (canal) diameters + SCIseg cord lesion | LGPL‑3.0 | `seg-sct` | `POST /segment-sct` | 8084 |

**They are NOT a flat 3‑way fan‑out.** SCT needs TotalSpineSeg's iso‑resampled volume
(`input_iso.nii.gz`), so the real graph is:

```
            raw sagittal T2 (.nii.gz)
            ├──▶ TotalSpineSeg  POST /segment        ┐  run these two in PARALLEL
            └──▶ SPINEPS        POST /segment        ┘
                       │  (TSS returns a zip containing input_iso.nii.gz + step1/step2 masks)
                       └──▶ SCT  POST /segment-sct  (send it the TSS zip)
```

Each model pins **incompatible dependencies** (TotalSpineSeg/nnU‑Net vs SPINEPS' `numpy==2.0.2`), so
they are **3 separate Docker images** — never one.

**Inputs/outputs**
- Input to TSS & SPINEPS: the **raw sagittal T2 NIfTI** (`.nii.gz`) — or a zipped DICOM folder.
- Input to SCT: the **zip TotalSpineSeg returns** (it carries `input_iso.nii.gz`).
- Final masks (what the measurements step reads): `step2_output.nii.gz`, `step1_levels.nii.gz`,
  `input_iso.nii.gz` (TSS); `sct_canal_seg.nii.gz`, `sct_spinalcord_seg.nii.gz`,
  `sct_lesion_seg.nii.gz` (SCT); `spineps_seg-vert_msk.nii.gz` (SPINEPS).

---

## 1. Prerequisites

- **Docker** (Part A). Build host needs **plenty of disk** — the TSS image is ~7 GB (CUDA torch +
  nnU‑Net + baked model weights). On a laptop that runs out of space, build on a cloud VM (see 5.2).
- **Compute (important):** these are heavy 3‑D CNNs.
  - **CPU:** works. TotalSpineSeg ≈ **3–4 min/scan**. **SPINEPS CPU inference peaks ~28 GB RAM** — give
    the SPINEPS container/host **≥ 32 GB RAM** or it gets OOM‑killed. SCT ≈ a few minutes.
  - **GPU (recommended):** all three are device‑agnostic and run far faster on an NVIDIA GPU; no special
    RAM tuning needed. Pass `--gpus all` to `docker run` (and install the NVIDIA Container Toolkit).
- For Part B (AWS): `aws` CLI (configured), `eksctl`, `kubectl`, an AWS account.

---

## PART A — Run the 3 models on one MRI (Docker only)

### A.1 Build the 3 images (build context = repo root)

```bash
cd MRI-ReportGenerator           # repo root (the dir with services/ and deployment/)

docker build -f deployment/docker/seg-tss.Dockerfile     -t mri-seg-tss:latest     .
docker build -f deployment/docker/seg-sct.Dockerfile     -t mri-seg-sct:latest     .
docker build -f deployment/docker/seg-spineps.Dockerfile -t mri-seg-spineps:latest .
```

> The images **bake the model weights at build time** (TotalSpineSeg, SPINEPS) so the first request is
> offline and fast. The builds download several GB — be patient and have disk free.

### A.2 Start the 3 services

CPU:
```bash
docker run -d --name seg-tss     -p 8083:8083 --shm-size=4g           mri-seg-tss:latest
docker run -d --name seg-sct     -p 8084:8084 --shm-size=2g           mri-seg-sct:latest
docker run -d --name seg-spineps -p 8085:8085 --shm-size=4g -m 40g    mri-seg-spineps:latest
```
GPU (add `--gpus all`):
```bash
docker run -d --gpus all --name seg-tss     -p 8083:8083 --shm-size=4g mri-seg-tss:latest
docker run -d --gpus all --name seg-sct     -p 8084:8084 --shm-size=2g mri-seg-sct:latest
docker run -d --gpus all --name seg-spineps -p 8085:8085 --shm-size=4g mri-seg-spineps:latest
```
> **`--shm-size`** is required: the default 64 MB `/dev/shm` deadlocks torch/nnU‑Net multiprocessing.
> **`-m 40g`** on SPINEPS gives the CPU run the RAM it needs (skip on GPU).

Confirm they're up:
```bash
for p in 8083 8084 8085; do curl -s localhost:$p/healthz; echo; done   # each prints {"status":"ok"}
```

### A.3 Run one scan through the DAG

```bash
MRI=path/to/sagittal_T2.nii.gz

# Stage 1 — TotalSpineSeg + SPINEPS in parallel on the raw scan
curl -sS -F "file=@${MRI};filename=input.nii.gz" http://localhost:8083/segment -o tss.zip     &
curl -sS -F "file=@${MRI};filename=input.nii.gz" http://localhost:8085/segment -o spineps.zip &
wait

# Stage 2 — SCT on the TotalSpineSeg zip (it carries input_iso.nii.gz)
curl -sS -F "file=@tss.zip;filename=segmentation.zip" http://localhost:8084/segment-sct -o sct.zip
```

Check the outputs:
```bash
unzip -l tss.zip       # step2_output.nii.gz, step1_levels.nii.gz, input_iso.nii.gz
unzip -l spineps.zip   # spineps_seg-vert_msk.nii.gz (endplate voxels 102–107)
unzip -l sct.zip       # the TSS files + sct_canal_seg / sct_spinalcord_seg (+ sct_lesion_seg)
```

To get the **single merged mask zip** the measurements step consumes, combine `sct.zip` (which already
re‑includes the TSS masks) with `spineps.zip`:
```bash
mkdir merged && cd merged && unzip -o ../sct.zip && unzip -o ../spineps.zip && zip -r ../segmentation.zip . && cd ..
```

That `segmentation.zip` is the segmentation stage's output. (Cleanup: `docker rm -f seg-tss seg-sct seg-spineps`.)

---

## PART B — Deploy the whole app on AWS (EKS)

The full app is **6 containers** on Amazon EKS (managed Kubernetes): a public **frontend** (Next.js), a
public **EEP** gateway (FastAPI, orchestrates everything), internal **measurements** + **reporting**
services, and the **3 segmentation services** above. Images live in **ECR**; public access via AWS
load balancers.

### B.1 One‑time AWS setup
```bash
aws configure                      # region eu-north-1 (or yours)
# EKS cluster (control plane + a default node group)
eksctl create cluster -f deployment/aws/cluster.yaml      # ~15 min
aws eks update-kubeconfig --name mri-reportgenerator --region eu-north-1
kubectl apply -f deployment/k8s/namespace.yaml
# ECR repos
for r in mri-eep mri-measurements mri-reporting mri-frontend mri-seg-tss mri-seg-sct mri-seg-spineps; do
  aws ecr create-repository --repository-name $r --region eu-north-1 || true
done
```

### B.2 Build + push the images
The app images (eep/measurements/reporting/frontend) are small — build locally with
`docker buildx --platform linux/amd64 --push`. The **3 seg images are ~3–7 GB** — build them on a VM
with disk (a throwaway EC2, or AWS CodeBuild), then `docker push` to ECR. See `docs/segmentation-deploy.md`.

```bash
REG=<acct>.dkr.ecr.eu-north-1.amazonaws.com
aws ecr get-login-password --region eu-north-1 | docker login --username AWS --password-stdin $REG
# example (repeat per image):
docker buildx build --platform linux/amd64 -f deployment/docker/eep.Dockerfile -t $REG/mri-eep:latest --push .
# seg images: same, but on a big‑disk host: docker build -f deployment/docker/seg-tss.Dockerfile -t $REG/mri-seg-tss:latest . && docker push $REG/mri-seg-tss:latest
```

### B.3 Segmentation compute node group
The seg pods are heavy, so they run on their own **tainted node group** (kept off the app nodes):
```bash
eksctl create nodegroup -f deployment/aws/segmentation-nodegroup.yaml
```
- Default in that file: **`r5.2xlarge` (8 vCPU / 64 GB)** — the 64 GB is sized for **SPINEPS CPU
  inference** (it OOM‑kills on a 32 GB node).
- **For GPU:** uncomment the `g4dn.xlarge` block in that file (needs the "Running On‑Demand G and VT"
  service‑quota raised), and uncomment the `nvidia.com/gpu: 1` limits in
  `deployment/k8s/segmentation.yaml`. eksctl auto‑installs the NVIDIA device plugin.

### B.4 Deploy the services
```bash
export ECR_REGISTRY=$REG IMAGE_TAG=latest
export SAMPLES_BUCKET=<your-samples-bucket> FRONTEND_ORIGIN=http://<frontend-elb>
# app services
envsubst < deployment/k8s/measurements.yaml | kubectl apply -f -
envsubst < deployment/k8s/reporting.yaml    | kubectl apply -f -
# 3 segmentation services
envsubst '${ECR_REGISTRY} ${IMAGE_TAG}' < deployment/k8s/segmentation.yaml | kubectl apply -f -
# EEP — set the 3 seg URLs so uploads run REAL segmentation (leave empty to use the stand-in)
export SEG_TSS_URL=http://seg-tss:8083 SEG_SCT_URL=http://seg-sct:8084 SEG_SPINEPS_URL=http://seg-spineps:8085
envsubst < deployment/k8s/eep.yaml | kubectl apply -f -
# frontend image must be built with NEXT_PUBLIC_EEP_URL=<eep public URL> baked in, then:
envsubst < deployment/k8s/frontend.yaml | kubectl apply -f -
```

### B.5 Verify end‑to‑end
```bash
kubectl -n mri get pods                                   # all Running
kubectl -n mri get svc eep frontend -o wide               # public ELB hostnames
# health of the 3 models from inside the cluster:
kubectl -n mri run t --rm -it --image=curlimages/curl --restart=Never -- \
  sh -c 'for u in seg-tss:8083 seg-sct:8084 seg-spineps:8085; do curl -s $u/healthz; echo; done'
```
Open the frontend ELB → log in → **Upload** an MRI → it runs the 3‑engine DAG → measurements → report.

---

## 6. Gotchas already fixed (don't re‑hit these)

These were debugged during bring‑up and are already baked into the Dockerfiles / wrappers / manifests:

1. **`kornia<0.8`** pinned — newer kornia removed `kornia.core.Tensor` that TotalSpineSeg's `auglab` imports.
2. **`--no-stalling` + a real `/dev/shm`** — the default 64 MB shm deadlocks nnU‑Net multiprocessing (TSS
   silently hangs at "Generating preview images").
3. **SPINEPS weights baked at build** (semantic + instance + labeling) and `checkpoint_final.pth` copied to
   `checkpoint_best.pth` (the release ships `final`, the loader wants `best`).
4. **SPINEPS `-cpu` flag** added when no GPU — it otherwise calls `.cuda()` and crashes on a CPU host.
5. **SPINEPS RAM ≥ ~28 GB on CPU** — OOM‑killed below that.
6. **TotalSpineSeg writes the iso volume to `out_dir/input/`** (not `input_iso/`); the wrapper now reads it
   from there so SCT gets `input_iso.nii.gz`.
7. **DAG, not flat fan‑out** — SCT is `/segment-sct` and consumes the TSS zip (see §0).

---

## 7. Teardown (stop AWS cost)
```bash
eksctl delete nodegroup -f deployment/aws/segmentation-nodegroup.yaml --approve
helm uninstall kps -n monitoring 2>/dev/null || true
eksctl delete cluster --name mri-reportgenerator --region eu-north-1   # removes everything
```
