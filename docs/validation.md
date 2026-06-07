# Validation

Validation assets are split by purpose:

- service-local unit tests live under each service's `tests/`
- cross-service tests belong under `tests/integration/`
- full pipeline smoke tests belong under `tests/e2e/`
- research validation scripts live under `research/group5/validation/`

This keeps product runtime validation separate from exploratory method validation.
