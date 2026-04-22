# CLAUDE.md — MRI-ReportGenerator

> This file is auto-loaded by Claude Code at session start. Read it first, every time.

## Project

**MRI-ReportGenerator** is a cervical spine MRI analysis pipeline: sagittal T2 MRI (DICOM or NIfTI) in, structured radiology-style report out. Report includes vertebral/disc/canal/cord measurements, threshold-based interpretation, and anomaly flags for physician review.

**Course context:** EECE503N / EECE798N (AI Engineering, AUB), Final Project — 40% of course grade.

**Team (shared Claude account):**
- Andrew Khoury
- Roni (sabaronnie)
- Hamad

**Positioning (provisional — pending team sign-off):** **Application**.
- Non-AI baseline: manual radiologist measurement (slow, high inter-observer variability)
- Target deployer: radiology departments, research-hospital workflows
- Flip to Research only after explicit team decision; Research has a publishability hard-stop (rubric GT5)

**Repo:** https://github.com/sabaronnie/MRI-ReportGenerator

**Pipeline:**
```
Input → Segmentation → Measurements → Interpretation → Report
```

---

## How to start a new session (MANDATORY read order)

When any team member opens a new Claude chat for this project, read these files in order before doing anything:

1. **`CLAUDE.md`** (this file) — rules and context
2. **`SESSION_LOG.md`** — the latest session's handoff, what's pending
3. **`plans/`** — open the most recently edited file; it's where active work lives
4. **`cervical-spine-master-plan.md`** — top-level scope and index

Only after reading all four do you start work.

---

## Session identity (hard rule — shared account)

Three people share one Claude account. Claude's memories default to Andrew. To avoid mis-attribution:

**Every session starts with:**
> "Hi, this is [Andrew | Roni | Hamad]."

If you forget, Claude will assume Andrew, and memory writes will accumulate under the wrong name. State your name first, always.

---

## Session start ritual

```bash
cd <your-local-path>/MRI-ReportGenerator
git pull origin main
git checkout -b <branch-prefix>/<name>/<topic>
# e.g. research/roni/phase-3b-cord  or  feat/iep-seg/totalspineseg-wrapper
```

Tell Claude which branch you're on and what you're doing this session. Claude should not start work without this context.

---

## Session end ritual (MANDATORY — non-negotiable)

Before you close the chat, ALWAYS:

1. **Update `SESSION_LOG.md`** with a new entry at the top:
   - Date, your name, branch
   - What you did in 2–3 lines
   - Files changed
   - **The ONE thing the next person needs to know to continue**
2. **Commit** your changes
3. **Push** your branch
4. If the work is reviewable, **open a PR**

If you skip the SESSION_LOG update, the next teammate starts cold and loses 20+ minutes reconstructing context. This is the single most important rule in this file.

---

## Branching and file ownership

- `main` is protected. Never push directly to it.
- Branches follow: `research/<name>/<topic>` for research/plan work, `feat/<service>/<topic>` for code
- Phase files in `plans/` have an **Owner** in their header — respect it
- Editing another owner's phase file = PR required, not direct commit
- Editing the root `cervical-spine-master-plan.md` = PR required
- `SESSION_LOG.md` is append-only; direct commit OK (rebase handles the rare conflict)

---

## Commit and staging rules

- **ALWAYS** stage files by name: `git add plans/phase-3b-cord.md`
- **NEVER** `git add .` — too easy to commit `.env`, caches, or raw patient data by accident
- Docs / plan updates: commit directly to your branch
- Code changes: PR with at least one reviewer from the team
- Commit messages: imperative, scoped — `phase-3b: add SCT integration notes`

---

## Secrets and credentials (hard rule)

- **Never** commit credentials. Not once.
- No AWS keys, no MIDRC tokens, no MLflow API keys, no database passwords in code/configs/commit history
- Use `.env` files (already in `.gitignore`) for local dev
- Use AWS Secrets Manager and GitHub Actions Secrets for deployed systems
- If you accidentally commit a secret: rotate it immediately, do not just revert the commit

---

## Medical AI hard rules

These rules are specific to this domain and are not negotiable:

1. **Cite sources for every medical/clinical claim.** Link the paper, guideline, or normative-value study. If you can't cite it, don't claim it.
2. **Never claim diagnoses.** Output wording: *"finding flagged for physician review"* or *"pattern consistent with possible X; clinical correlation required"* — never *"patient has X"*.
3. **Separate training from evaluation data.** Duke's 481 expert-annotated cases → train/val/test split committed once, never re-shuffled. Test set is not touched during development.
4. **License respect:**
   - TotalSpineSeg (LGPLv3) — redistribution complies with LGPL
   - Spinal Cord Toolbox (LGPLv3) — same
   - Duke CSpineSeg (CC BY-NC-ND 4.0) — **non-commercial only, no redistribution of derivatives**
5. **Prove on one case before scaling.** Before running on all 1,255 Duke cases, prove the pipeline works end-to-end on one. Scale only after verification.
6. **No patient data in git.** NIfTI and DICOM files are `.gitignore`d. Store data locally or on cloud storage, not in the repo.

---

## Decision rules

- Team decisions stay with the team. Claude does not unilaterally decide:
  - Architecture (EEP structure, IEP split, which services)
  - Role assignments
  - Cloud provider (already decided: AWS)
  - Application vs Research framing (provisional: Application)
  - Which cases to include in the validation set
- If uncertain whether a decision is Claude's or the team's, **default to asking**
- Decisions that are already made (written in CLAUDE.md or the master plan) are not re-litigated — they're followed. Change via PR, not chat drift.

---

## Communication rules

- Plain English. No jargon-drowning for the sake of looking smart.
- Explain tradeoffs with numbers when possible (latency, accuracy, cost, complexity).
- If Claude is not sure, say so. Uncertainty is information, not a failure.
- One question at a time when eliciting decisions.

---

## Testing discipline

- Every code change is tested before it is marked done
- Unit + integration + one E2E test on the deployed system (rubric Q1)
- Golden-dataset regression tests gate merges to `main` for core measurement code (rubric Q2)
- Prove on one case before scaling to the corpus

---

## Rubric awareness (EECE503N — hard stops)

Every architectural decision is checked against the rubric. The 5 hard-stop gates are non-negotiable:

- **GT1** — live demo works end-to-end
- **GT2** — public cloud API functional on **AWS** (project decision)
- **GT3** — EEP + ≥2 IEPs, each with non-trivial logic
- **GT4** — all deliverables complete (repo, docs, deployment, demo)
- **GT5** — clear Application positioning (or Research publishability if we flip)

If a proposed change weakens any of these, **stop and ask the team**. Hard-stop violations = project rejection.

---

## Resume prompt (copy-paste into a new chat)

```
I'm continuing work on the MRI-ReportGenerator project (cervical spine MRI pipeline for EECE503N). This is a shared Claude account — I am [Andrew | Roni | Hamad].

Please read these files in order before doing anything:
1. CLAUDE.md
2. SESSION_LOG.md
3. The most recently edited file in plans/
4. cervical-spine-master-plan.md

Then tell me what the last session was working on and what the pending item is. Do not start new work until I confirm.
```
