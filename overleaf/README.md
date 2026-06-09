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
    T1_ai_depth.tex          T1 — AI depth / non-triviality   (DONE, compiles)
    P2_baseline.tex          P2 — non-AI baseline rigor        (DONE, compiles; PMID-verified numbers)
    P4_publishability.tex    P4 — value / publishability       (DONE, compiles)
    C1_P3_novelty.tex        C1/P3 — novelty + AI justification (DONE, compiles with tectonic)
```

Local test-compile (optional): `tectonic deliverables/T1_ai_depth.tex` (installed via
`brew install tectonic` — a single-binary engine, no full MacTeX needed). T1, P4 and the paper all
compile clean locally.

## Compiling
- **Paper:** set `paper/main.tex` as the main document → pdfLaTeX (+ BibTeX for `references.bib`).
- **Each deliverable** in `deliverables/` is a **standalone** document with its own preamble and an
  embedded bibliography (`thebibliography`), so it compiles on its own with pdfLaTeX — no shared-bib
  path dependency, no BibTeX pass needed.

## Notes
- The deliverables are kept separate from the paper on purpose: the paper is the master science
  narrative, the deliverables are focused, rubric-facing extracts that reference it (no duplication of
  the underlying claims/numbers — single source of truth in the validation docs + journal).
- Every clinical claim is cited; outputs are "flagged for physician review," never diagnoses
  (project medical hard rule).
