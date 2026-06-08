# Overleaf project — MRI-ReportGenerator

This is the **single Overleaf project folder** for all written deliverables: the research paper and the
rubric write-ups. Upload/sync this whole `overleaf/` folder to Overleaf as one project; pick the "main
document" per compile (each document below compiles independently with **pdfLaTeX**).

## Structure
```
overleaf/
  paper/                     <- the research paper (compile paper/main.tex)
    main.tex                 18 sections + 4 appendices
    sections/  appendix/  figures/
    references.bib           the paper's bibliography
  deliverables/              <- rubric write-ups, each self-contained
    T1_ai_depth.tex          T1 — AI depth / non-triviality  (DONE)
    P2_baseline.tex          P2 — non-AI baseline rigor       (TODO: needs research numbers)
    P4_publishability.tex    P4 — value / publishability      (TODO)
```

## Compiling
- **Paper:** set `paper/main.tex` as the main document → pdfLaTeX (+ BibTeX for `references.bib`).
- **Each deliverable** in `deliverables/` is a **standalone** document with its own preamble and an
  embedded bibliography (`thebibliography`), so it compiles on its own with pdfLaTeX — no shared-bib
  path dependency, no BibTeX pass needed.

## Notes
- The deliverables are kept separate from the paper on purpose: the paper is the master science
  narrative, the deliverables are focused, rubric-facing extracts that reference it (no duplication of
  the underlying claims/numbers — single source of truth in the validation docs + journal).
- `docs/ai-depth.md` in the repo is the **markdown mirror** of T1 (repo-readable, with clickable file
  links). `deliverables/T1_ai_depth.tex` is the **submission version**. Keep them in sync, or retire the
  markdown if the LaTeX becomes canonical.
- Every clinical claim is cited; outputs are "flagged for physician review," never diagnoses
  (project medical hard rule).
