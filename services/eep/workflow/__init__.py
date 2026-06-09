"""Radiologist workflow layer for the EEP.

Additive features on top of the read-only case store: worklist filtering/sorting +
turnaround-time, case claim/assign, and report addenda. State lives in its own SQLite
DB (workflow.db) keyed by case_id — the in-memory case store and routers/cases.py are
never modified. See docs/workflow-features.md.
"""
