# Engineering Tradeoffs

Three explicit tradeoffs made during system design, each with the choice, the alternative considered, and the evidence.

---

## T1 — Three separate segmentation containers vs. one

**Chosen:** three independent Docker images (`seg-tss`, `seg-sct`, `seg-spineps`), each with its own Python environment and dependencies.

**Alternative considered:** a single segmentation image running all three engines in one process or one container.

**Why we chose this:** SPINEPS pins `numpy==2.0.2`, which is incompatible with nnU-Net (used by TotalSpineSeg) and with the SCT environment. A single image cannot satisfy all three dependency trees simultaneously — any attempt either breaks SPINEPS inference (`.cuda()` crash without the `-cpu` flag in wrong numpy context) or breaks nnU-Net multiprocessing. Separate images also let each engine fail and restart independently.

**What we gave up:** higher operational complexity (three pull/start/health-check steps instead of one; the EEP must know three internal URLs) and ~3× the disk footprint (~7 GB for TSS alone).

**Evidence:** the kornia `<0.8` pin in `seg-tss.Dockerfile` was found because a later kornia removed `kornia.core.Tensor` that TotalSpineSeg's `auglab` imports. Merging environments would have required forking one of the three tools.

---

## T2 — Threshold catalog (cited norms) vs. trained ML classifier for assessment

**Chosen:** a versioned threshold catalog in `services/assessement/thresholds.py` mapping each measurement to a cited normative range, producing per-finding status (`within_reference` / `outside_reference` / `review_only`).

**Alternative considered:** training a supervised classifier on the Duke 481-case dataset to map the full measurement vector directly to a pathology label.

**Why we chose this:** the dataset is CC BY-NC-ND 4.0 (non-commercial, no redistribution of derivatives), making a trained model's licensing unclear for deployment. More importantly, threshold-based assessment is directly explainable to a physician — every flag traces to a citable paper or guideline, which is a clinical requirement. A black-box classifier cannot do that.

**What we gave up:** learned non-linear interactions between measurements. A classifier could in principle pick up joint patterns (e.g. narrow canal + cord compression together) that per-measurement thresholds miss independently. Our Group 3 results (p=0.0001 canal/SAC/cord separation) suggest the individual thresholds are already clinically useful, but a joint model remains an open direction.

**Evidence:** Group 3 canal/SAC/cord achieves strong separation (p=0.0001, AUC not reported — distribution separation on 12 healthy vs. 10 symptomatic). Group 2 disc is partial (disc/VB AP ratio AUC 0.62), which is consistent with disc assessment being harder to capture with a single linear threshold.

---

## T3 — Async job queue (202 + polling) vs. synchronous response

**Chosen:** `POST /cases` returns `202 Accepted` immediately with a case ID; the pipeline runs in a FastAPI `BackgroundTask`; the client polls `GET /cases/{id}/job` until `stage == "ready"`.

**Alternative considered:** a blocking `POST /cases` that waits for the full pipeline to complete before returning the report, as a conventional synchronous REST endpoint would.

**Why we chose this:** end-to-end segmentation wall-clock is ~13.5 min on CPU (TSS ~6.5 min + SPINEPS ~9.4 min in parallel + SCT ~4 min sequentially after TSS). Standard HTTP clients, proxies, and load balancers time out well before that — typically 30–60 s. A synchronous design would either drop the connection mid-pipeline (losing the result entirely) or require clients to hold a raw TCP connection open for over ten minutes, which is impractical across a load balancer. The async design also lets the frontend show a live progress bar through the five pipeline stages (`queued → segmenting → measuring → assessing → ready`).

**What we gave up:** simplicity. The async design requires a case store to persist job state across the request boundary (currently an in-memory dict in `services/eep/store.py`, replaced by Postgres in a production deployment), a separate `/job` polling endpoint, and frontend polling logic. A synchronous endpoint would be a single request/response with no state to manage.

**Evidence:** the constraint is explicit in `services/eep/orchestration.py`: *"Real segmentation takes MINUTES, so it must NOT run inside the upload request."* The `POST /cases` handler in `services/eep/routers/cases.py` uses FastAPI `BackgroundTasks` to hand off to `enqueue_upload`, returning the `202` before the pipeline starts. Wall-clock verified on EKS deployment (2026-06-09): ~13.5 min end-to-end on CPU.
