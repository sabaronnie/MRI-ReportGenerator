# AWS deploy runbook (EKS)

Deploys the 3 services to a managed Kubernetes cluster on AWS and exposes the EEP + frontend
publicly. Designed to be **stood up for a demo and torn down after** to keep cost near zero.

## Prerequisites (one-time)
- Tools: `aws`, `eksctl`, `kubectl`, `helm`, `docker` (Docker Desktop running). Installed via Homebrew.
- AWS credentials configured locally:
  1. AWS Console → IAM → create user `mri-deploy` with **AdministratorAccess**.
  2. Create an access key (CLI) → run `aws configure` (region `us-east-1`). Creds land in
     `~/.aws/` — never in git or this repo.
  3. Verify: `aws sts get-caller-identity`.

## Deploy (≈ 20-25 min, mostly the cluster)
```bash
cd <repo root of the eep worktree>
./deployment/aws/01-provision.sh        # EKS cluster + ECR repos + samples S3 bucket
./deployment/aws/02-deploy-backend.sh   # build/push measurements + eep, print EEP public URL
./deployment/aws/03-deploy-frontend.sh  # build/push frontend (EEP URL baked), patch EEP CORS
```
The final script prints the **frontend URL** (open it) and the **EEP API URL** (`/docs`, `/healthz`,
`/metrics`). New ELB DNS can take a few minutes to resolve.

## Tear down (stop the bill)
```bash
./deployment/aws/teardown.sh            # delete LoadBalancers + EKS cluster (keeps ECR + S3)
./deployment/aws/teardown.sh --all      # also delete ECR repos + samples bucket
```

## What gets created
| Resource | Purpose |
|----------|---------|
| EKS cluster `mri-reportgenerator` + 2× t3.medium nodes | runs the pods |
| ECR repos `mri-eep`, `mri-measurements`, `mri-frontend` | image registry |
| S3 bucket `mri-reportgenerator-samples-<acct>` | viewer NIfTI + stand-in segmentation (node role has read-only) |
| 2× Classic ELB | public EEP + public frontend |
| namespace `mri` | measurements (ClusterIP) + eep (LB) + frontend (LB) |

## Notes / gotchas
- **Image arch:** built `--platform linux/amd64` (EKS nodes are x86; your Mac is arm64).
- **Two-phase frontend:** `NEXT_PUBLIC_*` is inlined at build, so the frontend image is built
  *after* the EEP URL is known (phase 3). CORS is patched after the frontend URL is known.
- **Samples not in images:** the EEP initContainer pulls them from S3 — mirrors the "no patient
  data baked into images" rule even though this sample is open Spine-Generic data.
- See `docs/deployment.md` for the architecture diagram, secrets approach, cost, and tradeoffs.
