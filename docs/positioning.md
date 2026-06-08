# Positioning — Application (rubric §3.1, P1–P4, GT5)

Positioning: **Application** (per `CLAUDE.md`). This is the product/business framing; the deeper
methods/validation write-ups (T1 AI depth, detailed clinical validation, publishability) live in the
science-track docs and are referenced here.

> **Sources note (medical hard rule):** the **clinical inter-observer / measurement-time figures (P2)
> are PMID-verified** (Crossref/PubMed, 2026-06-09 — see Sources + `manual_baseline_cost`). The
> **workforce / wait-time figures** come from a literature/web scan and are attributed to the named
> organization/journal + year — treat those as directional for positioning.

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
- **Why insufficient — it's slow:** a cervical-MRI read is ≈ **2.7 min median / 3.8 min mean** of PACS
  interaction (Forsberg 2017, PMID 27714473), plus a self-reported **5–10 min/case** of manual geometry
  (Zhu 2024, PMID 38269650). No formal time-motion study isolates the geometry step — itself a gap.
- **Why insufficient — it's not reproducible:** inter-observer agreement collapses for exactly the
  structures we automate (human-reader, cervical MRI unless noted):
  cervical **disc-degeneration grading** (original Pfirrmann) **κ ≈ 0.265** (Urbanschitz 2021,
  PMID 34966859) — the grading axis, *not* lumbar stenosis; **cord AP diameter** ICC **0.82 midsagittal /
  0.66 axial** (Grochmal 2018, PMID 29913296); **cord-compression** metrics ICC **0.35–0.56** (Fehlings
  2006, PMID 16816769); **Cobb angle** ≈ **0.88** single trained reader vs **≈ 0.55** mixed readers
  (Sevin 2025, PMID 41011045). Structured/automated measurement measurably reduces disagreement
  (structured-reporting literature; CAR study in Sources). A pipeline computes the same geometry every time.
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
- **Research upside:** the validation work (healthy-anchored norms, threshold-crossing analysis) is
  written up as a full paper (`overleaf/paper/`) with standalone rubric deliverables (`overleaf/
  deliverables/` — T1 AI-depth, P2 baseline, P4 publishability, C1/P3 novelty). The methodological
  contribution — a no-per-case-ground-truth validation design + the honest negatives (G4 alignment is
  not a discriminator; disc signal/bulge are dead) — is the publishable angle. The project stays
  **Application**; publishability is upside, not the bar.

## Honesty / scope guardrails
- Outputs are screens for physician review, **never a diagnosis** (wording enforced in the report).
- Demo measurements are real pipeline output but **pre-validation**; clinical correlation required.
  Full clinical-validation status: science-track docs + `docs/validation*`.

## Sources
**Inter-observer / time (PMID-verified, 2026-06-09):** Forsberg 2017 (PMID 27714473, read time) · Zhu 2024
(PMID 38269650, geometry time) · Urbanschitz 2021 (PMID 34966859, cervical Pfirrmann κ 0.265) · Grochmal
2018 (PMID 29913296, cord AP ICC) · Fehlings 2006 (PMID 16816769, compression ICC) · Sevin 2025
(PMID 41011045, Cobb ICC). Full table + caveats: memory `manual_baseline_cost`, deliverable
`overleaf/deliverables/P2_baseline.tex`.
**Workforce / wait-time (directional, attributed):** AAMC physician-workforce projections (2024) · HRSA
Workforce Analysis (2025) · US BLS Occupational Outlook (radiologists) · Neiman Health Policy Institute,
*JACR* (2025) · Royal College of Radiologists, *State of the Wait* · Fraser Institute, *Waiting Your Turn*
(2024) · AMN Healthcare imaging-access survey (2025) · CAR structured-reporting study.
