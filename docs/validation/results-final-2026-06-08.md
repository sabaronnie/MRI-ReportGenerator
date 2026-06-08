# Validation Results — FINAL (consolidated) — 2026-06-08

> **This supersedes `results-full-2026-06-08.md`** (the run-1 doc, which still shows G2 "backwards" and
> G4 "directional" — both since revised). Every number below was **reproduced from the current committed
> service/measurement code** (re-ran 2026-06-08 after all J19–J26 fixes). Single source of truth for the
> per-group verdict: `group-status-2026-06-08.md`; the full narrative is `DEVELOPMENT_JOURNEY.md` (J1–J26).

## Methodology (recap)
No public dataset pairs cervical MRI with per-case expert measurements, so validation =
**threshold-crossing + distribution separation**, never per-case sensitivity/specificity. Physical-dimension
(mm) metrics are scanner-immune and validate cross-dataset; intensity/ratio metrics are acquisition-sensitive
and are validated **within** one dataset. Cohorts: healthy = Spine-Generic; symptomatic = MMCSD (CSM/CSR).

## Final per-group verdict
| Group | Cohort | Result | Verdict |
|---|---|---|---|
| **G3** canal/SAC/cord | 12 H vs 10 U | canal 11.7→8.6 mm **p=0.0001**; SAC 4.7→2.3 mm **p=0.0001**; cord 6.3→5.5 mm p=0.009 | ✅ **VALIDATED (strong)** |
| **G2** disc | within-MMCSD, 46/49 cases, 276 disc-levels | disc/VB AP ratio **AUC 0.62, p=0.0018** (level-controlled); signal AUC 0.50, bulge AUC 0.50 | ⚠️ **PARTIAL** (geometric spread only) |
| **G4** alignment (Cobb) | 26 H vs 41 U | +10.7° vs +8.0°, **d=0.28, AUC 0.57, p=0.32** | ❌ **NOT a discriminator** (method-valid) |
| **G1** Ha/Hp compression screen | 12 H vs 10 U | 0% healthy false-flag; correctly null on spondylosis | ✅ **validated as a screen** (abnormal arm untested) |
| **G5.1** myelomalacia (SCIseg) | 11 healthy | ~91% healthy specificity; sensitivity from SCIseg publication | ✅ **validated** |
| **G6** interpretation | end-to-end run | cited catalog + classify + demographics; §A over-flag corrections applied | 🟢 **wired end-to-end** |

## Per-group detail

### G3 — canal/cord/SAC: VALIDATED (strong) — the headline
Canal-AP min and SAC min separate at **p=0.0001** (healthy canal floor 10.5 mm vs unhealthy ceiling 9.97 mm);
cord AP thinner (p=0.009). Physical-dimension mm metrics → scanner-immune, validate cross-dataset.
Figures: `figures/canal_min.png`, `figures/sac_min.png`, `figures/cord_min.png`. Script: `run_validation_master.py`.
**Open (accepted, not run):** the 10 unhealthy were lesion-selected; a random MMCSD draw (needs SCT/Colab) would
confirm robustness — documented as a limitation, not executed.

### G2 — disc: PARTIAL (within-MMCSD, level-stratified)
Lesion vs non-lesion discs, 46/49 cases, 276 disc-levels, stratified by level (lesions cluster at wider
mid-cervical levels — an apparent disc-AP-width AUC 0.79 collapses to 0.61 once controlled):
- **disc/VB AP ratio: AUC 0.62, p=0.0018** — the discriminator (disc spreads toward VB width with degeneration).
- disc AP width: AUC 0.61 (p=0.0022, level-controlled). DHI: AUC 0.59 (weak).
- **disc signal grade: AUC 0.50** and **posterior bulge: AUC 0.50** — clean negatives.
No per-case cut-point claimed (no GT). The J22 fixes removed the prior backwards/over-flag artifacts.
Figure: `figures/g2_discvb_ratio.png`. Script: `run_g2_within_mmcsd.py`.

### G4 — alignment: method-valid, NOT a discriminator
SPINEPS endplate-voxel C1 Cobb reads correct lordosis and is precise, but on a representative multi-site
healthy cohort (26) the healthy mean (+10.7°) sits on the symptomatic mean (+8.0°): **d=0.28, AUC 0.57,
p=0.32**. The earlier n=11 result (+15.2°, d=0.76, p=0.070) was a lordosis-biased small sample. Cervical
lordosis is too variable (SD ±10°, range −13° to +32°) and supine positioning is a cross-cohort confound.
Reported as a validated *measurement*, not a screen. Figure: `figures/g4_balanced_cobb.png`. Script:
`run_g4_balanced_validation.py`.

### G1 — compression screen: validated; abnormal arm untested
Ha/Hp screen (endplate-line, cohort-calibrated 0.94±0.13, flag <0.68): 0% healthy false-flag, correctly
silent on the non-compression spondylosis cohort (true negatives). Confirmed on 49 unhealthy (0% over-flag).
The **compression-fracture abnormal arm is untested** — no labelled cervical compression-fracture MRI exists
(documented data gap). Figure: `figures/hahp_min.png`.

### G5 — screens: validated on healthy
5.1 myelomalacia (SCIseg) ~91% healthy specificity; sensitivity rests on the SCIseg publication (no diseased
cohort needed by design). 5.2 compression = G1 screen. 5.3 tumour / 5.4 scar out of scope.

### G6 — interpretation: wired end-to-end
Cited threshold catalog (`thresholds.py`) + `classify` + demographic-aware (sex-specific dural-sac cut) +
syndrome indicators (provisional). §A over-flag corrections applied: SAC demoted (1–3 mm review, <1 mm hard),
Torg supporting-only (never standalone), the confabulated 1.35 mm bulge cut removed.

## Reproducibility
All numbers above were re-run from the committed code on 2026-06-08:
`run_validation_master.py` (G3/G1), `run_g2_within_mmcsd.py` (G2), `run_g4_balanced_validation.py` (G4).
138 service tests pass. (Local G3 uses SCT's precomputed per-slice output, since the SCT CLI runs in the
segmentation environment, not on the analysis host; the deployed pipeline runs SCT live.)

## Open items (state honestly; not executed)
1. **G3 random-draw robustness** — would need SCT on a non-selected MMCSD draw (Colab); accepted as a
   documented caveat, not run.
2. **Compression-fracture arm (G1/G5.2)** — blocked: no labelled cervical compression-fracture MRI exists
   (PMC8082364: cervical fractures rare / usually non-osteoporotic → graded TL-only). One external lead =
   access-blocked Penn cohort (Madi 2025, PMC11718528).
3. **Per-case accuracy + G2 disc/VB cut + demographic-threshold accuracy** — need a radiologist read (AUBMC).

## Documented negatives (absent baselines — searched, do not exist)
No public reference exists to benchmark against, so these are stated as limitations, not measured:
no cervical-MRI VB-height (Ha/Hp) inter-observer ICC; no cervical SAC-mm ICC; no published cervical
disc-AP/VB-AP ratio norm (our ≥1.10 cut is cohort-derived; mechanism = disc AP widens with degeneration,
Machino 2021 PMID 34098133); no healthy cervical-MRI Cobb ground truth (only an n=77 spondylosis MRI+Cobb
set). Several thresholds are documented radiograph/CT/lumbar borrows (Torg, some canal cuts, lumbar disc
rules), flagged in the G6 catalog.
