# Tradeoffs

Rubric §5 requires explicit engineering tradeoffs: what we chose, what we rejected, and evidence.
Each entry below is a decision we actually made on this system, with the data that drove it.

---

## 1. Deployment platform — EKS vs ECS Fargate vs k3s-on-EC2
**Axis:** rubric-fit + reliability vs cost vs complexity.
**Chose:** AWS **EKS** (managed Kubernetes), spun up for demos and torn down after.
**Why:** it satisfies both "Kubernetes required" (§9) and "public cloud API" (§10) in one deployment, and the k8s manifests are genuinely exercised. Managed control plane removes the hardest ops.
**Rejected:** *ECS Fargate* — cheapest managed option (~$45/mo) but it is **not** Kubernetes, so we'd need a second throwaway cluster just to satisfy §9, splitting the story. *k3s-on-EC2* — ~$30/mo and real k8s, but single-node (no HA) and we self-manage the control plane.
**Evidence:** measured cost ≈ **$170/mo if left 24/7** vs **~$5–10 total** with teardown between demos (control plane $0.10/hr + 2×t3.medium + 2 ELBs). Re-provision from IaC takes ~20 min, so uptime — not capability — is the only thing we trade away by tearing down. Verified end-to-end on the deployed cluster (4/4 e2e tests green against the live URL).

## 2. Orchestration latency — synchronous EEP→IEP call vs async job queue
**Axis:** latency/simplicity vs throughput/decoupling.
**Chose:** the EEP calls the measurements IEP **synchronously** during `POST /cases`, then a short simulated clock drives the UX "processing" state.
**Why:** the measurement workload is CPU-bound and **sub-second**, so a queue (SQS + workers) would add infrastructure and failure modes for no user-visible benefit at demo scale.
**Rejected:** an async queue + polling — correct at high concurrency, but premature here.
**Evidence:** measured per-component compute on a real neck: `cervical_body_morphometry` 0.357s, `segmental_angles` 0.052s, `group5_fracture_screen` 0.032s, others <0.001s — a full case completes well under ~1.5s, far below any threshold where queueing pays off. (Documented as the scaling lever if real GPU segmentation moves in-process.)

## 3. Reporting/interpretation — rule-based vs LLM-generated
**Axis:** determinism/testability/safety vs flexibility.
**Chose:** **rule-based** thresholds + template rendering (no LLM in the report path).
**Why:** medical output must be reproducible and citable; a deterministic pipeline can be **golden-tested** and never invents findings. Fits the "flagged for physician review, never a diagnosis" rule.
**Rejected:** an LLM report writer — fluent prose, but non-deterministic output needs statistical eval harnesses and risks confabulation on clinical text.
**Evidence:** because the chain is deterministic we ship a **golden regression test** (`tests/integration/test_golden_report.py`): fixed contract → byte-stable summary/impression/status set. An LLM path could not be pinned this way.

## 4. Frontend data source — mock-first (contract-driven) vs build-against-live-backend
**Axis:** parallelism/decoupling vs integration realism.
**Chose:** a typed client with a `mock | live` switch behind one seam (`src/lib/api/client.ts`), built entirely against frozen contract fixtures first.
**Why:** the whole UI (6 screens + viewer) could be built and reviewed before the backend existed, then flipped to the live EEP with **no component changes**.
**Rejected:** coupling the UI build to a running backend — would have serialized two workstreams.
**Evidence:** frontend M1–M6 shipped against mocks; flipping to live surfaced exactly **4 integration bugs** (optional report fields, Base-UI button API, dev route-handler store sharing, font-var mismatch) — all caught at the seam, none requiring a rewrite.

## 5. Viewer data delivery — S3 + initContainer vs baking data into the image
**Axis:** clean separation / patient-data hygiene vs simplicity.
**Chose:** the EEP pod pulls the NIfTI volume/mask from **S3 via an initContainer** into an `emptyDir`.
**Why:** keeps imaging data **out of container images** — the pattern that becomes mandatory with real patient data — at the cost of one scoped IAM policy + an init step.
**Rejected:** `COPY`-ing samples into the image — simpler, but normalizes data-in-image and bloats the registry.
**Evidence:** the measurements image is already 518 MB; baking a 7.5 MB volume per build (and per real case) doesn't scale, and our medical-data rules forbid imaging data in git/images regardless.

## 6. Public routing — 2× LoadBalancer Services vs 1× shared ALB Ingress
**Axis:** zero-dependency simplicity vs cost + same-origin cleanliness.
**Chose:** two plain `type: LoadBalancer` Services (EEP + frontend) for the first deploy.
**Why:** works out of the box with no extra controller to install; got us to a live public URL fastest.
**Rejected (for now):** the AWS Load Balancer Controller + a single ALB Ingress — saves one ELB (~$16/mo), removes CORS (same origin), and removes the two-phase frontend build, but adds a controller dependency.
**Evidence:** the second ELB measurably adds ~$0.025/hr (~$16/mo) and forces the two-phase build (frontend image rebuilt once the EEP URL is known) + a CORS patch step — documented as the next optimization in `docs/deployment.md`.

---

### Also-rans (smaller, still deliberate)
- **Per-component graceful errors vs all-or-nothing:** the measurements contract captures per-component `status`/`error`, so a case with only TSS masks still returns 4/10 real components instead of failing whole — evidence in the live report (cord/canal error because SCT masks are upstream/Colab, the rest compute).
- **Prebuilt wheels on `python:3.12-slim` vs compiling:** scipy/numpy/nibabel install from manylinux wheels → measurements image builds with **no compiler toolchain** (no `build-essential`), keeping the image lean and the build ~tens of seconds.
- **kube-prometheus-stack vs hand-rolled Prometheus:** adopted the standard Helm chart (Operator + ServiceMonitors) instead of static scrape configs, so adding a service is one ServiceMonitor, not a Prometheus redeploy.
