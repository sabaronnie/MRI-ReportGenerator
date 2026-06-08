# Positioning — Application (rubric §3.1, P1–P4, GT5)

> DRAFT. `[CONFIRM: …]` = Andrew/team to confirm. `[SCIENCE: …]` = numbers the executor/science chat
> supplies (P2 baseline rigor). Positioning is **Application** (per CLAUDE.md, pending final team sign-off).

## The operational problem (P1)
Cervical-spine MRI reading is **manual and measurement-heavy**: a radiologist visually inspects
sagittal T2 series and hand-measures vertebral, disc, canal, and cord geometry to judge stenosis,
alignment, compression, and cord signal. This is **slow** and suffers **high inter-observer
variability** — the same study can yield materially different measurements between readers. At
volume, that means inconsistent reports and reader time spent on repetitive measurement rather than
judgment.

## The decision being augmented (P1)
[CONFIRM: e.g. "pre-populate the structured measurement table + flag cases whose measurements cross
reference thresholds for radiologist review — augmenting, not replacing, the read."] The system never
diagnoses; every output is a **screen flagged for physician review** (medical hard rule).

## Non-AI baseline + why it's insufficient (P2 — the required explicit baseline)
- **Baseline:** manual radiologist measurement (the current standard of care).
- **Cost of the baseline:** [SCIENCE: measurement/reading time per case, e.g. ~X min] and
  [SCIENCE: inter-observer variability, e.g. ICC / mm-level disagreement, with citations].
- **Why insufficient:** it does not scale, is not reproducible across readers, and consumes specialist
  time on geometry that a deterministic pipeline can compute consistently.
- **Why our (non-LLM) AI approach is justified:** automated segmentation (TotalSpineSeg/SCT) + geometric
  measurement + cited-threshold interpretation produces **reproducible, traceable** measurements in
  ~seconds/case (see `docs/tradeoffs.md` §2 for measured per-component latency), with every flag tied to
  a citation. This is consistency + speed, not a black-box verdict.

## Novelty claim (P3 / C1)
[CONFIRM: one sentence — what is new vs prior cervical-spine tools AND vs the other team's identically
titled project. Candidate angles: healthy-anchored geometric detectors (disease-agnostic, no overfit);
threshold-crossing validation with cited norms; an end-to-end contract-driven service (EEP + 2 IEPs)
with a clinician-facing report + interactive viewer, deployed + observable — not a notebook.]

## Who deploys / pays (P1)
[CONFIRM:] radiology departments and research-hospital workflows (per CLAUDE.md) — the buyer is the
imaging department / research group that wants consistent, fast, auditable cervical measurements.
[CONFIRM: any specific deployer or pilot partner?]

## Value / publishability (P4)
- **Application value:** reproducible measurements + triage flags → less reader time on geometry,
  more consistent reports; auditable (every flag cited).
- **Research upside:** the validation work (healthy-anchored norms, threshold-crossing analysis;
  see `feat/paper/draft` + the validation memories) is a [SCIENCE: benchmark / paper-draft angle +
  target venue]. The project stays Application; publishability is upside, not the bar.

## Honesty / scope guardrails
- Outputs are screens for physician review, **never a diagnosis** (wording enforced in the report).
- Measurements are real pipeline output but **pre-validation** on the demo cases; clinical correlation
  required. Full clinical validation status: see the science chat's write-ups + `docs/validation*`.
