"""Measurement registry + dispatcher.

Each measurement is a pluggable component (a module exporting NAME, DEPENDS_ON, compute()).
The orchestrator runs them in dependency order, instruments each call with Prometheus
counters/histograms, and returns a flat report.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from prometheus_client import Counter, Histogram

from .cord import functional_canal_ap
from .context import MeasurementContext, MeasurementError
from .geometric import cervical_body_morphometry, spondylolisthesis


MEASUREMENT_DURATION = Histogram(
    "measurement_duration_seconds",
    "Wall-clock time spent computing one measurement component",
    ["measurement"],
)
MEASUREMENT_RESULTS = Counter(
    "measurement_results_total",
    "Per-component completion outcomes",
    ["measurement", "status"],
)
PATHOLOGY_FLAGS = Counter(
    "measurement_pathology_flags_total",
    "Pathology flags raised by measurement components",
    ["measurement", "flag"],
)


# Registry: name -> module. Each module must expose NAME, DEPENDS_ON, compute(ctx, prior).
COMPONENTS = {
    cervical_body_morphometry.NAME: cervical_body_morphometry,
    spondylolisthesis.NAME: spondylolisthesis,
    functional_canal_ap.NAME: functional_canal_ap,
}


def run_all(ctx: MeasurementContext, enabled: list[str] | None = None) -> dict[str, Any]:
    """Execute the requested measurement components, returning a JSON-serialisable report."""
    selected = list(COMPONENTS.keys()) if enabled is None else [n for n in enabled if n in COMPONENTS]
    ordered = _topo_order(selected)

    report: dict[str, Any] = {"components": {}, "measurements": {}, "flags": {}}
    prior: dict[str, Any] = {}

    for name in ordered:
        component = COMPONENTS[name]
        start = time.perf_counter()
        try:
            result = component.compute(ctx, prior)
            elapsed = time.perf_counter() - start
            MEASUREMENT_DURATION.labels(measurement=name).observe(elapsed)
            MEASUREMENT_RESULTS.labels(measurement=name, status="ok").inc()

            for measurement_key, per_level in result.measurements.items():
                report["measurements"].setdefault(measurement_key, {}).update(per_level)
            for flag_key, per_level in result.flags.items():
                report["flags"].setdefault(flag_key, {}).update(per_level)
                for level, raised in per_level.items():
                    if raised:
                        PATHOLOGY_FLAGS.labels(measurement=name, flag=flag_key).inc()

            report["components"][name] = {
                "status": "ok",
                "duration_s": elapsed,
                "metadata": result.metadata,
            }
            prior[name] = result
        except MeasurementError as e:
            elapsed = time.perf_counter() - start
            MEASUREMENT_DURATION.labels(measurement=name).observe(elapsed)
            MEASUREMENT_RESULTS.labels(measurement=name, status="error").inc()
            report["components"][name] = {
                "status": "error",
                "duration_s": elapsed,
                "error": str(e),
            }
    return report


def _topo_order(names: list[str]) -> list[str]:
    """Return `names` in dependency order; raise on missing deps or cycles."""
    visited: set[str] = set()
    ordered: list[str] = []

    def visit(n: str, stack: tuple[str, ...]) -> None:
        if n in visited:
            return
        if n in stack:
            raise ValueError(f"dependency cycle through {n} -> {' -> '.join(stack)}")
        component = COMPONENTS.get(n)
        if component is None:
            raise ValueError(f"unknown measurement component: {n}")
        for dep in getattr(component, "DEPENDS_ON", []):
            visit(dep, stack + (n,))
        visited.add(n)
        ordered.append(n)

    for n in names:
        visit(n, ())
    return ordered
