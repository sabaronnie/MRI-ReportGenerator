# Interpretation Service Logic (Phase 4 / Group 6)

This package holds the Phase 4 interpretation layer that sits after raw measurement extraction and before final report generation.

## Files

- `interpretation.py` — converts raw measurement outputs into standard interpreted rows and provisional syndrome indicators
- `thresholds.py` — central cited threshold catalog used by the interpretation layer
- `REPORTING_HANDOFF_CONTRACT.md` — JSON contract that the EEP should pass from interpretation into reporting

## Current consumers

- [`services/measurements/orchestrator.py`](../measurements/orchestrator.py) imports `build_interpreted_measurements(...)`
- Group 5's flags contract from [`services/measurements/group5/flags_contract.py`](../measurements/group5/flags_contract.py) can be ingested via `interpret_group5_contract(...)`

This package is code-only for now; it is not a standalone Flask service yet.
