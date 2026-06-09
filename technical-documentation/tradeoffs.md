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

## T3 — CPU inference on EKS vs. GPU instances

**Chosen:** CPU inference on `r5.2xlarge` nodes (8 vCPU / 64 GB RAM) for the segmentation node group, with GPU-ready manifests available but not default.

**Alternative considered:** `g4dn.xlarge` GPU instances as the default compute, which are available in the EKS node group config and would reduce per-scan wall-clock significantly.

**Why we chose this:** GPU instances cost roughly 3–4× more per hour than `r5.2xlarge` on eu-north-1 (g4dn.xlarge ~$0.526/hr vs r5.2xlarge ~$0.126/hr at on-demand pricing). For a radiology assistant that processes a handful of scans at a time rather than a batch pipeline, the latency difference does not justify the cost. CPU inference is also more reproducible across environments (no CUDA version dependency, no driver mismatch).

**What we gave up:** significant latency. Wall-clock on `r5.2xlarge` CPU: TSS ~6.5 min, SPINEPS ~9.4 min (parallel with TSS), SCT ~4 min after TSS — ~13.5 min end-to-end. GPU would reduce this to under 2 min per scan for TSS/SPINEPS. For a real-time radiology workflow this matters; for a research pipeline or asynchronous review queue it does not.

**Evidence:** verified run on EKS deployment (2026-06-09) on `r5.2xlarge`, all three engines HTTP 200. GPU path is pre-wired: `--gpus all` flag documented in RUNBOOK Part A, `nvidia.com/gpu: 1` resource limits commented out in `deployment/k8s/segmentation.yaml`, and `g4dn.xlarge` block commented out in `deployment/aws/segmentation-nodegroup.yaml`.
