# Architecture

The runtime pipeline is organized as:

1. `services/eep/` - public orchestration entrypoint
2. `services/segmentation/` - segmentation service and SCT helpers
3. `services/measurements/` - geometric, cord, signal, and Group 5 measurement logic
4. `services/interpretation/` - threshold catalog and interpretation layer
5. `services/reporting/` - report assembly and rendering scaffolds

Supporting non-runtime work is intentionally separated:

- `research/group5/` - validation scripts, exploratory detectors, method comparisons
- `colab/group5/` - GPU notebooks used to generate external segmentation artifacts
- `tests/` - cross-service integration and end-to-end test homes
- `deployment/` - Docker / compose / Kubernetes deployment assets
