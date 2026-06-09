# Deployment

The system is deployed to **AWS EKS** (managed Kubernetes) — this satisfies both the "Kubernetes
required" (§9) and "public cloud API on AWS" (§10) requirements with one deployment. IaC + runbook
live in [`deployment/aws/`](../deployment/aws/README.md); manifests in [`deployment/k8s/`](../deployment/k8s/).
Local equivalents: [`deployment/docker/`](../deployment/docker/) (images) + [`deployment/compose/`](../deployment/compose/) (compose).

## Architecture

```
                       Internet
                          │
          ┌───────────────┴────────────────┐
          ▼                                 ▼
   ELB (frontend)                      ELB (eep)              ── public AWS load balancers
          │                                 │
   ┌──────┴───────┐                  ┌──────┴───────┐
   │  frontend    │  browser calls   │     EEP      │         ── namespace: mri
   │  (Next.js)   │  EEP directly →  │  (FastAPI)   │
   │  :3000       │                  │  :8080       │
   └──────────────┘                  └──────┬───────┘
                                            │ in-cluster (ClusterIP)
                                            ▼
                                     ┌──────────────┐
                                     │ measurements │  ← IEP (Flask): geometric + SCT +
                                     │  (Flask)     │     group5 + interpretation
                                     │  :8081       │
                                     └──────────────┘
   initContainer on EEP pulls viewer NIfTI + stand-in segmentation from S3 → emptyDir.
   (Segmentation is upstream/GPU-Colab; reporting IEP wires in next.)
```

- **EEP** (public, FastAPI): validates uploads, rate-limits, exposes `/metrics`, orchestrates the
  measurements IEP over the cluster network. `Service type: LoadBalancer` → Classic ELB.
- **measurements** (internal, Flask): `ClusterIP` — never publicly reachable; only the EEP calls it.
- **frontend** (public, Next.js standalone): the EEP URL is baked at build time; talks to the EEP.
- **S3**: holds the viewer volume/mask + the stand-in `segmentation.zip`. The node group's IAM role
  has read-only access; the EEP initContainer `aws s3 sync`s them into an `emptyDir`. No data in images.

## Secrets management
- **No secrets in git, ever** (enforced by `.gitignore` + project rules). AWS credentials live only
  in `~/.aws/` locally; in CI they will be GitHub Actions Secrets / OIDC.
- **In-cluster:** the demo carries no app secrets (no DB password yet — store is in-memory). When the
  datastore moves to RDS, the connection string goes in **AWS Secrets Manager** and is mounted via the
  Secrets Store CSI driver (or an External Secrets operator) — *not* a plain k8s Secret in a manifest.
- **Image pulls:** nodes pull from ECR via the node IAM role (no registry password needed).
- **S3 access:** scoped IAM policy on the node role (`s3:GetObject`/`ListBucket` on the samples bucket
  ARN only), not broad S3 access.

## Authentication (full-stack branch `feat/app/fullstack-local`)
The EEP gained JWT auth (HS256 + Argon2id + a SQLite user store; see `services/eep/auth/` +
`docs/auth-design.md`). `/cases*` then require a Bearer token; `/healthz`, `/readyz`, `/metrics`,
`/auth/login` stay open (so Prometheus scraping and the deployed e2e's login step are unaffected).
- **Env (set as a k8s Secret, never committed):** `JWT_SECRET` (≥32 bytes, REQUIRED in prod so tokens
  verify across pods), `DEMO_PASSWORD`/`ADMIN_PASSWORD`/`ADMIN_EMAIL` (seed creds), optional
  `JWT_TTL_HOURS`, `USERS_DB_PATH`. The EEP manifest already wires these from an **optional** Secret
  `eep-auth` (so the pre-auth image still starts). Create it before deploying the auth image:
  ```bash
  kubectl -n mri create secret generic eep-auth \
    --from-literal=JWT_SECRET="$(openssl rand -hex 32)" \
    --from-literal=DEMO_PASSWORD='demo12345' \
    --from-literal=ADMIN_PASSWORD='demo12345'
  ```
- **User store + replicas:** the SQLite store auto-seeds the 4 demo accounts per pod on boot. Combined
  with the single-replica EEP (below) this is consistent for the demo. For multi-replica or
  runtime-created users surviving restarts, point `USERS_DB_PATH` at a PersistentVolume (or move users
  to RDS alongside the case store).
- **Merge note (2 shared files):** at integration, take the full-stack branch's `services/eep/app.py`
  (adds the auth router + `Depends(get_current_user)` guard on `/cases`) and `services/eep/requirements.txt`
  (`pyjwt`, `argon2-cffi`). All other auth files are new (no conflict). Our test suite is already
  auth-aware (the `client` fixture + the deployed-e2e log in if `/auth/login` exists), so it stays green
  after the merge.

## Single-replica EEP (state)
The EEP runs **1 replica** because the case store is in-process (in-memory): an uploaded case lives on
the pod that received it, so a second replica would 404 that case on a different pod (fixtures are
seeded everywhere; uploads are not). Horizontal scale is gated on moving the store to **RDS/Postgres**
(the documented next step; `store.py` is written as the seam). This is a deliberate
reliability-vs-complexity tradeoff for the demo.

## Cost estimate (eu-north-1 / Stockholm — closest region to the deploying team)
| Item | If left running 24/7 | Demo-only (spin up/tear down) |
|------|---------------------:|------------------------------:|
| EKS control plane ($0.10/hr) | ~$73/mo | ~$1-2 per demo day |
| 2× t3.medium nodes | ~$60/mo | ~$1 per demo day |
| 2× Classic ELB (~$0.025/hr ea) | ~$36/mo | <$1 per demo day |
| ECR storage + S3 (~8 MB) | <$1/mo | <$1/mo |
| **Total** | **~$170/mo** | **~$5-10 total for the project** |

**Cost driver = wall-clock uptime.** We provision for a demo and run `teardown.sh` after, so the real
bill is single-digit dollars. `01-provision.sh` rebuilds the whole stack in ~20 min from IaC.

## Tradeoffs (deployment-specific — see also docs/tradeoffs.md)
- **EKS vs ECS Fargate vs k3s.** Chose EKS: satisfies the k8s requirement *and* public-API in one,
  and the k8s manifests are genuinely exercised. Rejected Fargate (not Kubernetes → would need a
  separate throwaway cluster just for §9, splitting the story) and k3s-on-EC2 (cheaper but single-node,
  weaker HA story). Cost is mitigated by tearing down between demos.
- **2× Classic ELB vs 1× shared ALB (Ingress).** Chose two plain `LoadBalancer` Services for the first
  deploy: zero extra controllers to install, works out of the box. The next optimization is the AWS
  Load Balancer Controller + a single ALB Ingress routing one hostname to both services — saves one ELB
  (~$16/mo), removes CORS (same origin), and removes the two-phase frontend build. Deferred to keep the
  first deploy dependency-free.
- **S3 + initContainer vs baking samples into the image.** Chose S3: keeps data out of images (the
  pattern that's mandatory once real patient data is involved) at the cost of one IAM policy + an
  initContainer. Baking would be simpler but normalizes data-in-image, which we explicitly avoid.

## Failure modes
- measurements pod down → EEP `/readyz` reports `measurements_ready:false`; uploads fall back to the
  cloned-fixture core (degraded, not a crash).
- S3 fetch fails at init → EEP pod stays in `Init`; `/volume`/`/mask` would 404 (viewer only).
- ELB DNS not yet propagated → transient; resolves in a few minutes.
