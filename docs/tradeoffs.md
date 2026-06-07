# Tradeoffs

- Group 5 runtime logic stays under `services/measurements/group5/` because it contributes measurement-stage findings.
- Group 5 exploratory and validation scripts moved to `research/group5/` so runtime service code stays clean.
- Interpretation is separated from measurements because thresholds and syndrome-style inference are a downstream stage.
- Reporting has its own scaffold so the repo can show a clean end-to-end path even before the final PDF renderer is complete.
