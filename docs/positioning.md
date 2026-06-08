# Positioning — Application (rubric §3.1, P1–P4, GT5)

Positioning: **Application** (per `CLAUDE.md`). This is the product/business framing; the deeper
methods/validation write-ups (T1 AI depth, detailed clinical validation, publishability) live in the
science-track docs and are referenced here.

> **Sources note (medical hard rule):** the figures below come from a literature/web scan and are
> attributed to the named organization/journal + year. Treat them as directional for positioning;
> the science track should confirm primary sources before final submission. Items the scan itself
> hedged are marked *(approx.)*.

## The operational problem (P1)
Demand for imaging is outrunning the people who read it, and patients pay for it in delay:
- **Radiologist shortage.** The US faces a projected physician shortfall of **up to ~86,000 by 2036**
  (AAMC, 2024); there are only ~**41,000** radiologists and BLS projects ~**4%** employment growth over
  2023–2033, while imaging demand rises ~**3–4%/yr** vs ~**1%/yr** supply growth (BLS; Medicus/Anderson
  Healthcare, 2025). The UK reports a **31%** radiologist shortfall, forecast to **41%** within 5 years
  (Royal College of Radiologists, *State of the Wait*).
- **Patients wait — for the scan and the result.** Routine MRI scheduling runs **2–3+ weeks** in the US
  (AMN Healthcare, 2025); Canada's **median MRI wait is 16.2 weeks** (Fraser Institute, *Waiting Your
  Turn*, 2024). Report turnaround has worsened **+113% (2014–2023)**, and **+256% for MRI specifically**
  (Neiman HPI, *JACR*, 2025).
- **Overloaded readers, real error rates.** Per-radiologist image volume has risen sharply (one network:
  monthly images **+399%**, 2009–2022); burnout sits around **40–50%** (Medscape/AMA syntheses); and the
  real-time interpretive **error rate is ~3–5%**, with retrospective discrepancy ~**30%** (error-review
  literature).

Cervical-spine MRI is squarely in this squeeze: it is **measurement-heavy** — vertebral, disc, canal,
and cord geometry hand-measured per study — so it consumes scarce specialist time on repetitive
geometry rather than judgment.

## The decision being augmented (P1)
Auto-compute the **structured cervical measurement table** (vertebra / disc / canal / cord) and **flag
cases whose measurements cross cited reference thresholds for radiologist review**. The radiologist
still interprets and signs off; the system **never diagnoses** — every output is a *screen flagged for
physician review* (medical hard rule). The goal is to give the radiologist consistent measurements and
a triaged worklist, shortening time-to-report for the cases that are clearly normal and surfacing the
ones that need a careful look.

## Non-AI baseline + why it's insufficient (P2 — the required explicit baseline)
- **Baseline:** manual radiologist measurement (current standard of care).
- **Why insufficient — it's not reproducible:** manual cervical/spinal measurement shows substantial
  **inter-observer variability** — e.g. qualitative stenosis grading at **κ ≈ 0.26** (lumbar, *Spine*);
  quantitative cervical-myelopathy metrics at interobserver **ICC ≈ 0.75–0.86**; T2 cord-signal grading
  **κ ≈ 0.74**; AP cord diameter **ICC ≈ 0.82 (sagittal)** — and **structured/automated measurement
  measurably reduces disagreement** (e.g. neural-foraminal-stenosis disagreement **46%→35%**, facet OA
  **45%→22%** with structured reporting). *(Some cervical ICC/κ values approx.; science track to confirm.)*
- **And it doesn't scale:** see the shortage + wait-time figures above — there simply aren't enough
  reader-hours, and the hours that exist are spent partly on geometry a deterministic pipeline computes
  identically every time.
- **Why our (non-LLM) AI approach is justified:** automated segmentation (TotalSpineSeg/SCT) + geometric
  measurement + **cited-threshold** interpretation yields **reproducible, traceable** measurements in
  ~seconds/case (per-component latency in `docs/tradeoffs.md` §2), with every flag tied to a citation.
  This directly attacks the baseline's two failures — *variability* and *throughput* — without a
  black-box verdict.

## Novelty claim (P3 / C1)
An **end-to-end, contract-driven, deployed and observable service** (EEP + 2 IEPs) that turns sagittal
T2 cervical MRI into **reproducible, cited, threshold-screened measurements** with a clinician-facing
report + interactive viewer — built on **healthy-anchored, disease-agnostic geometric detectors**
validated by threshold-crossing / distribution separation, *not* a notebook or a single black-box
classifier. (vs. prior tools and the cohort's similarly-titled project: the differentiator is the
full productionized system + the healthy-anchored, cited-threshold validation approach.)

## Who deploys / pays (P1)
**Radiology departments and research-hospital spine/imaging groups** — the imaging department or
research group that wants consistent, fast, **auditable** cervical measurements and a triaged worklist.
The buyer's pain is exactly the shortage + turnaround problem above; the system's value is reader-time
saved on geometry + consistency across readers, with a clear physician-in-the-loop safety story.

## Value / publishability (P4)
- **Application value:** reproducible measurements + triage flags → less reader time on geometry, more
  consistent reports, faster turnaround on clearly-normal cases; fully auditable (every flag cited).
- **Research upside:** the validation work (healthy-anchored norms, threshold-crossing analysis; see
  the science-track docs + `feat/paper/draft`) is a benchmark/paper-draft angle. The project stays
  **Application**; publishability is upside, not the bar.

## Honesty / scope guardrails
- Outputs are screens for physician review, **never a diagnosis** (wording enforced in the report).
- Demo measurements are real pipeline output but **pre-validation**; clinical correlation required.
  Full clinical-validation status: science-track docs + `docs/validation*`.

## Sources (attributions — verify primaries before submission)
AAMC physician-workforce projections (2024) · HRSA Workforce Analysis (2025) · US BLS Occupational
Outlook (radiologists) · Neiman Health Policy Institute, *JACR* (2025) · Royal College of Radiologists,
*State of the Wait* · Fraser Institute, *Waiting Your Turn* (2024) · AMN Healthcare imaging-access survey
(2025) · *Spine* inter-observer stenosis-grading study · cervical-myelopathy MRI reliability studies
(ICC/κ — some author/year to be confirmed by the science track) · CAR structured-reporting study.
