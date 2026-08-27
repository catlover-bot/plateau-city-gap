"""Report real-city validation cost and a clearly synthetic 500k framework check."""

from __future__ import annotations

import argparse
import json
import resource
import time
from collections import Counter
from pathlib import Path

from backend.citygap_platform.domain.validation import (
    EVIDENCE_DIMENSIONS,
    validate_evidence_strength,
    validation_priority_key,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "analysis/outputs/benchmarks/validation_cost.json"


def _load(name: str) -> dict:
    return json.loads(
        (ROOT / "analysis/outputs/real/validation" / name).read_text(encoding="utf-8")
    )


def _synthetic_scale(count: int) -> dict[str, object]:
    started = time.perf_counter()
    categories: Counter[str] = Counter()
    first_priority: tuple | None = None
    evidence = {dimension: "NO" for dimension in EVIDENCE_DIMENSIONS}
    evidence["source_verified"] = "YES"
    evidence["reproducible"] = "YES"
    validate_evidence_strength(evidence)
    for index in range(count):
        category = (
            "connectivity_disagreement" if index % 97 == 0
            else "large_difference" if index % 19 == 0
            else "moderate_difference" if index % 5 == 0
            else "distance_similar"
        )
        categories[category] += 1
        record = {
            "sample_id": f"synthetic-{index:06d}",
            "connectivity_disagreement": category == "connectivity_disagreement",
            "reference_agreement": category,
            "assumption_sensitive": index % 11 == 0,
            "affected_population_estimate": float(index % 1000),
            "network_disconnected": index % 97 == 0,
            "coverage": (index % 101) / 100,
        }
        key = validation_priority_key(record)
        if first_priority is None or key < first_priority:
            first_priority = key
    return {
        "records": count,
        "generated_from_synthetic_data": True,
        "real_city_result": False,
        "purpose": "validation framework scale check only",
        "runtime_seconds": time.perf_counter() - started,
        "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "processed_count": sum(categories.values()),
        "reference_agreement_counts": dict(categories),
        "evidence_matrix_validated": True,
        "lexicographic_priority_executed": first_priority is not None,
        "combined_confidence_score_created": False,
    }


def benchmark(scale: int = 500_000) -> dict[str, object]:
    network = _load("network_cross_validation.json")
    sensitivity = _load("sensitivity_validation.json")
    rehearsal = _load("municipal_pilot_rehearsal.json")
    network_by_city = {row["city_id"]: row for row in network["cities"]}
    return {
        "schema_version": "citygap-validation-cost-v1.0.0",
        "real_city_components": {
            city: {
                "network_cross_validation": {
                    "runtime_seconds": network_by_city[city]["runtime_seconds"],
                    "peak_rss_mb": network_by_city[city]["peak_rss_mb"],
                    "sample_count": network_by_city[city]["metrics"]["sample_count"],
                },
                "hazard_and_criticality_sensitivity": {
                    "runtime_seconds": sensitivity["cities"][city]["runtime_seconds"],
                    "peak_rss_mb": sensitivity["cities"][city]["peak_rss_mb"],
                    "hazard_model_count": len(
                        sensitivity["cities"][city]["hazard_assumption_matrix"]
                    ),
                },
                "pilot_rehearsal": {
                    "runtime_seconds": rehearsal["runtime_seconds"],
                    "peak_rss_mb": rehearsal["peak_rss_mb"],
                    "shared_public_artifact_rehearsal": True,
                },
            }
            for city in ("maizuru", "fujisawa")
        },
        "synthetic_500k": _synthetic_scale(scale),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", type=int, default=500_000)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = benchmark(args.scale)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
