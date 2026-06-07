# Group 5 Runtime Modules

This package contains the reusable Group 5 runtime code that is part of the measurements service:

- `vertebral_fracture.py` — validated vertebral-body compression/deformity screen
- `fracture_screen.py` — measurements-service component wrapper for the Group 5.2 screen
- `flags_contract.py` — Group 5 -> Group 6 findings contract builder
- `myelomalacia_specificity.py` — SCIseg healthy-specificity scoring helpers
- `pipeline.py` — end-to-end assembly helper for a step2 mask plus optional lesion mask

Research/support material that used to live in the root `group5/` folder is now colocated here:

- `research/` — validation helpers, exploratory scripts, and alignment / SCIseg comparison work
- `../tests/group5/` — legacy Group 5 tests now under the shared measurements test tree
- `README.group5.md` — the imported standalone Group 5 documentation snapshot
