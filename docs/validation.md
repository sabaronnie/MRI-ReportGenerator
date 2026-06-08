# Validation

Validation assets are split by purpose:

- service-local unit tests live under each service's `tests/`
- cross-service tests belong under `tests/integration/`
- full pipeline smoke tests belong under `tests/e2e/`
- research validation scripts live under `research/group5/validation/`

This keeps product runtime validation separate from exploratory method validation.

## Results & per-group verdicts (single source of truth)

- **`docs/validation/results-final-2026-06-08.md`** — FINAL consolidated results (supersedes
  `results-full-2026-06-08.md`, the run-1 snapshot).
- **`docs/validation/group-status-2026-06-08.md`** — per-group verdict table.
- Narrative: `DEVELOPMENT_JOURNEY.md` (J1–J26).

Current verdicts (2026-06-08, reproduced from committed code): **G3** canal/SAC/cord ✅ strong
(p=0.0001); **G2** disc ⚠️ partial (disc/VB AP ratio AUC 0.62; signal & bulge are negatives, AUC 0.50);
**G4** alignment/Cobb ❌ NOT a discriminator (balanced 26 H vs 41 U: d=0.28, AUC 0.57, p=0.32 — a
validated *measurement*, not a screen); **G1**/**G5.1** ✅ healthy-validated screens; **G6** 🟢 wired
end-to-end. Older `results-full` / `results-run1` docs are explicitly marked superseded.
