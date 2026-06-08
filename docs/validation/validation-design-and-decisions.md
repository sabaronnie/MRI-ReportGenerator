# Validation Design & Decision Log (report-facing)

> The scientific rationale behind how we validate the measurement pipeline — **and how we arrived at
> each decision**. Written for the final report/paper: it records not just *what* we did but *why*,
> including the reasoning we worked through and the limitations we accept. Distinct from
> `docs/validation.md` (which is only about test-file layout) and `DEVELOPMENT_JOURNEY.md` (the
> per-mistake fix narrative). Date: 2026-06-07.
>
> **Results update (2026-06-09):** this is the *design rationale* (still current). The actual per-group
> verdicts have since been finalized — see `results-final-2026-06-08.md` (single source of truth):
> **G3 strong (p=0.0001) · G2 partial (disc/VB AP ratio AUC 0.62; signal & bulge negative) · G4 NOT a
> discriminator (balanced d=0.28, p=0.32 → validated measurement, not a screen) · G1/G5.1 screens · G6
> wired**. The §5 matrix below is annotated with these outcomes.

---

## 1. The validation problem and our definition of "validated"
There is **no public dataset that pairs cervical MRI with per-case expert measurements** (confirmed
across repeated dataset hunts — the standing "KIND-B / AUBMC gap"). We therefore **cannot compute true
per-case sensitivity/specificity** against a radiologist gold standard.

So we define **"validated"** operationally as:
> **healthy cases land on the normal side of each cited threshold and never cross; pathology-enriched
> cases shift/cross into the abnormal side — with documented limits.**

This is a **threshold-crossing + distribution-separation** design, not gold-standard clinical proof. We
state this honestly everywhere rather than overclaim.

## 2. The cohorts (and why each)
- **HEALTHY anchor — Spine-Generic** (open, multi-vendor healthy controls; 12 necks validated, ~260
  available). This is the **anchor**: it defines/confirms the normal side of every measurement.
- **UNHEALTHY demonstration — MMCSD** (Synapse `syn63903115`, Yu 2025 *Sci Data*; ~250 **surgical
  cervical spondylosis** cases with per-case **CSM/CSR** labels) + **Duke CSpineSeg** (clinical cervical
  T2, distribution-only, no per-case labels). These show the abnormal side actually moves.

## 3. The decision that makes the whole design work: our measurements are **geometry/signal detectors, not disease classifiers**
Each measurement reports a **physical quantity** (canal AP in mm, disc bulge in mm, Ha/Hp ratio, cord
signal present/absent). The normal range for each is anchored on **healthy anatomy + cited normative
literature** (e.g., canal normal >13 mm from Nell 2019) — **independent of any disease**.

**Consequences (these are the load-bearing decisions):**
1. **We are not learning a disease-specific range.** Nothing of ours is *trained* on the unhealthy cohort;
   the segmentation models (TSS/SCT/SPINEPS) are pre-trained and frozen, and our thresholds are cited.
   → **No overfitting-to-spondylosis risk.** The unhealthy cohort is a *demonstration set*, not a training set.
2. **A measurement crosses its threshold whenever the anatomy is abnormal, regardless of which disease
   caused it.** A canal narrowed to 8 mm reads "stenosis" whether from spondylosis, tumor, congenital
   narrowing, or trauma — a millimetre is a millimetre. → **abnormal-detection generalizes across diseases
   that produce the same geometric/signal change**, so we do *not* need a separate validation dataset per
   disease to trust that a measurement trips on abnormal anatomy.
3. **The healthy anchor is the real guarantee.** If the normal range is correctly calibrated (healthy
   validation + the threshold corrections), then a value outside it is a flagged *finding*. We report
   "measurement outside reference, flagged for physician review" — **never a diagnosis** (medical-AI rule).
4. **"Outside range" ≠ "has disease X" and not even "definitely symptomatic."** Some measurements are
   non-specific (e.g. ~88% of asymptomatic adults have a disc bulge >1 mm; ~93% of healthy men have
   Torg <0.8). So an abnormal value is a finding for clinical correlation, handled via multi-metric +
   no-diagnosis wording, not a claim of disease.

## 4. Terminology that caused a real confusion — resolved here
**Spondyl*osis* ≠ spondyl*olisthesis*.** They sound alike but are different conditions, and conflating
them inverts which groups MMCSD validates:
- **Spondylosis** = cervical **degenerative disease** (the umbrella): disc degeneration, osteophytes,
  **canal stenosis, cord compression**, loss of lordosis. **This is what MMCSD contains.**
- **Spondylolisthesis** = one vertebra **slipping** relative to another — the single finding
  `spondylolisthesis.py` measures, and only a *minor, incidental* part of spondylosis.

MMCSD's labels are **CSM** (Cervical Spondylotic **Myelopathy**, ~108 — cord dysfunction from
**stenosis + cord compression**) and **CSR** (Cervical Spondylotic **Radiculopathy**, ~122 — nerve-root
compression, usually **disc** disease). So MMCSD's pathology is **primarily disc (G2) and canal/cord
stenosis (G3)** — the *opposite* of "only Group 1 / only the slip measurement."

## 5. Per-group unhealthy coverage matrix
| Group / measurement | Pathology it flags | Does MMCSD (CSM/CSR) exercise it? | Abnormal source used | Status / gap |
|---|---|---|---|---|
| **G3** canal AP / SAC / cord AP | stenosis, cord compression | ✅✅ (stenosis *is* CSM) | MMCSD + Duke | **✅ VALIDATED STRONG** — canal/SAC p=0.0001, cord p=0.009 (via SCT) |
| **G2** disc bulge / DHI / height / grade | disc degeneration/herniation | ✅✅ (disc disease *is* CSR) | MMCSD + Duke | **⚠️ PARTIAL** — code wired (J25); within-MMCSD: disc/VB AP ratio AUC 0.62, signal & bulge negative (AUC 0.50) |
| **G5.1** myelomalacia | cord T2 signal / myelopathy | ✅ (CSM) | MMCSD + SCIseg ref | ✅ covered; ~91% healthy specificity; sensitivity from SCIseg paper |
| **G4** Cobb / segmental / lordosis | kyphosis / loss of lordosis | ✅ (degenerative) | MMCSD + Duke | **❌ NOT a discriminator** — balanced 26H/41U d=0.28, p=0.32 (method-valid only; J26). Reported as a *measurement*, not a screen |
| **G1** spondylolisthesis (slip) | degenerative listhesis | ⚠️ incidental (minor in spondylosis) | MMCSD + Duke | partial; slip method still experimental |
| **G1** Ha/Hp + heights / **G5.2** | **vertebral compression fracture** | ❌ wrong disease (osteoporosis/trauma) | Duke DCM + RSNA-2022 (separate, done) | **genuine gap — weakest axis** (see §6) |
| **G5.3** tumor/mass | tumor | ❌ | none | scoped out — no labeled cervical-tumor MRI exists |
| **G5.4** post-op scar | fibrosis | ❌ | none | out of scope — needs gadolinium |

**Key reading:** MMCSD is a **multi-group** unhealthy cohort — strongest for **G3, G2, G5.1, G4**, weakest
for **G1**. The "reads healthy = false negative" worry is valid **only** for the vertebral-**compression**
axis (G1 Ha/Hp, G5.2): those patients genuinely have normal vertebral heights, so a normal reading there
is a *true* negative, not a measurement failure — MMCSD is simply the wrong cohort for that one axis.

## 6. The genuine gaps (honest limitations for the report)
1. **Vertebral compression fracture (G1 Ha/Hp, G5.2).** Spondylosis doesn't cause it; our existing G5.2
   "unhealthy" was Duke **DCM** (itself degenerative) + RSNA fracture **CT** (mostly non-compression). A
   labeled cervical *vertebral-compression-fracture MRI* set would strengthen it. → **The targeted hunt
   COMPLETED (2026-06-07, negative): no such public dataset exists** — VerSe authors note cervical
   fractures are rare and usually non-osteoporotic (PMC8082364). This is now a documented, citeable
   limitation; the one external lead is an access-blocked Penn cohort (Madi 2025, PMC11718528).
2. **Findings we don't measure at all** (not a range error — a scope limit): tumor mass without geometric
   change, foraminal stenosis (not measurable on sagittal), inflammatory/infectious signal we don't screen.
   These we would *miss*, and we say so.
3. **Mild disease / specificity overlap:** abnormal values occur in asymptomatic people → flag-for-review,
   not diagnosis; multi-metric where possible.
4. **Spectrum/selection bias:** MMCSD is *surgical* (severe end of spondylosis). Claims are scoped to the
   cervical-spondylosis spectrum; generalization beyond it is a stated limitation. Mitigated by the healthy
   anchor (not spondylosis) + Duke (different selection) + the separate fracture-axis validation.

## 7. Decision log (how we came to each)
- **Threshold-crossing instead of sensitivity/specificity** — because no per-case GT exists (repeated hunts).
- **Healthy = Spine-Generic; unhealthy = MMCSD + Duke** — the only segmentable cervical cohorts; MMCSD is
  the only one with per-case pathology labels (104-agent research, 2026-06-07).
- **Measurements treated as disease-agnostic geometry** — this is *why* one demonstration cohort suffices
  for the groups it exercises, and why we don't chase a dataset per disease.
- **MMCSD validates G2/G3/G4/G5.1 (not "only G1")** — resolved the spondylosis≠spondylolisthesis mix-up
  with the dataset's own CSM/CSR definitions (Yu 2025).
- **Compression axis gets its own (separate) treatment** — Duke DCM + RSNA already; a targeted hunt for a
  true cervical compression-fracture MRI set is the only outstanding data request.
- **Three segmenters by structure** — TSS (vertebra/disc → G1/G2/G4-fallback), SCT (canal/cord → G3, +SCIseg
  → G5.1), SPINEPS (endplate voxels → G4 best Cobb). Best tool per structure, not competing.
- **No-diagnosis posture throughout** — every flag is "finding for physician review; clinical correlation
  required," consistent with the medical-AI rules.

## 8. What this buys us (and what it doesn't)
- **Buys:** a defensible demonstration on real cervical MRI with cited thresholds and documented limits.
  **Final outcomes:** G3 separates strongly (p=0.0001); G2 partial (disc/VB AP ratio AUC 0.62, signal/bulge
  negative); G5.1 healthy-validated; **G4 did NOT separate** once a balanced healthy cohort was used
  (d=0.28, p=0.32) — reported honestly as a validated measurement, not a screen.
- **Doesn't buy:** true per-case sensitivity/specificity (no GT); coverage of non-degenerative pathologies
  we don't measure; a strong compression-fracture abnormal arm (the one open data gap, now confirmed
  unfillable on public data); a cervical-alignment disease screen (G4 is non-specific).

*Cross-refs:* `DEVELOPMENT_JOURNEY.md` (J1–J13, per-mistake fixes), memory `cervical-unhealthy-validation-plan`
(thresholds + cohort detail), `docs/contracts/` (the output data contract).
