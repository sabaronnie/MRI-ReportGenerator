# Radiologist workflow features (batch 1: A/B/C/D)

> Additive workflow layer on the EEP. Makes the worklist operational without touching
> the case store. Decided with Andrew 2026-06-08. Batch: worklist filter/sort (A),
> claim/assign (B), turnaround-time (C), addenda (D). E–H (notes, critical-results,
> dashboard, audit) are queued for a later batch.

## Design — parallel `workflow` layer, zero collision

New `services/eep/workflow/` package with its **own SQLite** (`workflow.db`, gitignored,
keyed by `case_id`). It *reads* the in-memory case store (`store.list_cases` /
`store.get_case`) and the users DB (assignee names) but never edits `store.py` or
`routers/cases.py`. Mounted with **one line in `app.py`** (already an auth-wiring touch).

**Tables:** `case_assignment` (case_id PK, assignee_id, assignee_name, claimed_at) ·
`case_addendum` (id, case_id, author_id, author_name, text, created_at).

## API (`/workflow`, all JWT-guarded)

| Method | Path | Purpose |
|---|---|---|
| GET | `/workflow/worklist?status=&triage=&assignee=&mine=&q=&sort=` | enriched + filtered + sorted summaries; each row gets `assignment` + `tat` |
| GET | `/workflow/cases/{id}` | `{assignment, tat, addenda[]}` for the detail page |
| POST | `/workflow/cases/{id}/claim` | claim to self (assignee = current user) |
| POST | `/workflow/cases/{id}/release` | clear assignment |
| POST | `/workflow/cases/{id}/assign {assignee_id}` | assign to a user (name from users DB) |
| POST | `/workflow/cases/{id}/addendum {text}` | append a timestamped addendum |

- **Sort:** `priority` (urgent → review → none, oldest first within), `oldest`, `newest`.
- **TAT (derived, no storage):** `age_hours` from `created_at`; `tat_status` =
  on_track / warning (≥75% of target) / breach (≥target) / signed (reviewed|signed);
  target = `WORKFLOW_TAT_TARGET_HOURS` (env, default 24).

## Testing

`services/eep/tests/test_workflow.py` (9 cases): auth-guard, enriched worklist,
priority sort, triage filter + search, claim/release + `mine` filter, assign +
unknown-assignee 404, addendum create/list + empty-text 422, unknown-case 404, TAT
bucketing. Hermetic temp DBs via `conftest.py`. Live-smoke verified against Docker.

## Frontend (stage 2)

Worklist: filter bar (status/triage, "My cases", search) + sort + Assignee/TAT columns +
Claim. Case page: assignee + Claim/Release, TAT badge, addenda list + "Add addendum".
