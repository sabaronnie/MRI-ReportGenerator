"""Phase 4 / Group 6 interpretation package."""

from .interpretation import (
    InterpretedMeasurement,
    build_interpreted_measurements,
    detect_syndromes,
    interpret_group5_contract,
)
from .thresholds import THRESHOLDS, classify

__all__ = [
    "InterpretedMeasurement",
    "THRESHOLDS",
    "build_interpreted_measurements",
    "classify",
    "detect_syndromes",
    "interpret_group5_contract",
]
