# Deployment

Deployment assets live under:

- `deployment/docker/`
- `deployment/compose/`
- `deployment/k8s/`

The intended deployment model is:

1. expose `services/eep/` as the public API
2. run `services/segmentation/` and `services/measurements/` as internal services
3. keep interpretation/reporting either in-process with the EEP or as separate internal services later
