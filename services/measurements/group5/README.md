# Group 5 Runtime Modules

This package contains the reusable Group 5 runtime code that is part of the measurements service:

- `vertebral_fracture.py` — validated vertebral-body compression/deformity screen
- `fracture_screen.py` — measurements-service component wrapper for the Group 5.2 screen
- `flags_contract.py` — Group 5 -> Group 6 findings contract builder
- `myelomalacia_specificity.py` — SCIseg healthy-specificity scoring helpers
- `pipeline.py` — end-to-end assembly helper for a step2 mask plus optional lesion mask

Research/support material that used to live in the root `group5/` folder now lives outside the
runtime package:

- `research/group5/` — validation helpers, exploratory scripts, alignment experiments, and the legacy imported README
- `../tests/group5/` — runtime-facing Group 5 unit tests under the shared measurements test tree
