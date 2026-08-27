"""Structured, deterministic annual urban-state comparison metrics."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date


def build_annual_report(
    *,
    city_id: str,
    from_state_id: str,
    to_state_id: str,
    from_effective_date: date,
    to_effective_date: date,
    from_metrics: Mapping[str, float],
    to_metrics: Mapping[str, float],
    feature_change_counts: Mapping[str, int],
) -> dict[str, object]:
    if from_state_id == to_state_id or to_effective_date <= from_effective_date:
        raise ValueError("Annual report requires two chronologically distinct urban states")
    if set(from_metrics) != set(to_metrics):
        raise ValueError("Annual report metric sets must match exactly")
    changes: dict[str, dict[str, float | None]] = {}
    for name in sorted(from_metrics):
        before = float(from_metrics[name])
        after = float(to_metrics[name])
        if not math.isfinite(before) or not math.isfinite(after):
            raise ValueError("Annual report metrics must be finite")
        changes[name] = {
            "from": before,
            "to": after,
            "absolute_change": after - before,
            "percentage_change": ((after - before) / before * 100) if before != 0 else None,
        }
    return {
        "schema_version": "municipal-annual-report-1.0.0",
        "generator": "deterministic structured metrics; no generated narrative",
        "city_id": city_id,
        "from_urban_state_id": from_state_id,
        "to_urban_state_id": to_state_id,
        "from_effective_date": from_effective_date.isoformat(),
        "to_effective_date": to_effective_date.isoformat(),
        "metric_changes": changes,
        "feature_change_counts": {
            key: int(feature_change_counts[key]) for key in sorted(feature_change_counts)
        },
        "causal_effect_claimed": False,
    }
