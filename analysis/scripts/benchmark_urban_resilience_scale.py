"""Benchmark the production resilience algorithms on clearly synthetic scale fixtures."""

from __future__ import annotations

import argparse
import gc
import json
import resource
import time
from pathlib import Path

from analysis.src.urban_resilience import (
    BuildingDemand,
    NetworkEdge,
    network_criticality_candidates,
    run_network_stress_test,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "analysis/outputs/benchmarks/urban_resilience_scale.json"


def _rss_mib() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def benchmark(scale: int) -> dict[str, object]:
    if scale < 3:
        raise ValueError("Synthetic scale must contain at least three nodes/buildings")
    generated = time.perf_counter()
    edges = tuple(
        NetworkEdge(f"e-{index}", f"n-{index}", f"n-{index + 1}", 10.0)
        for index in range(scale - 1)
    ) + (NetworkEdge(f"e-{scale - 1}", f"n-{scale - 1}", "n-0", 10.0),)
    buildings = tuple(
        BuildingDemand(
            f"b-{index}",
            f"n-{index}",
            2.0,
            1.0,
            0.25,
            {"medical": min(index, scale - index) * 10.0 + 2.0},
        )
        for index in range(scale)
    )
    generation_seconds = time.perf_counter() - generated

    # One explicitly selected closure per 10k edges. The ring is a deliberate
    # synthetic topology and must never be described as a real city.
    closed = frozenset(f"e-{index}" for index in range(0, scale, 10_000))
    stress_started = time.perf_counter()
    stress = run_network_stress_test(edges, buildings, {"medical": {"n-0": 0.0}}, closed)
    stress_seconds = time.perf_counter() - stress_started

    criticality_started = time.perf_counter()
    criticality = network_criticality_candidates(
        edges, buildings, {"medical": {"n-0": 0.0}}
    )
    criticality_seconds = time.perf_counter() - criticality_started
    result = {
        "fixture": "synthetic_ring_one_building_per_node",
        "generated_from_synthetic_data": True,
        "road_nodes": scale,
        "road_edges": len(edges),
        "buildings": len(buildings),
        "explicit_closed_edges": len(closed),
        "generation_seconds": generation_seconds,
        "stress_test_seconds": stress_seconds,
        "criticality_seconds": criticality_seconds,
        "total_algorithm_seconds": stress_seconds + criticality_seconds,
        "peak_rss_mib": _rss_mib(),
        "stress_result": {
            "scenario_component_count": stress.scenario_component_count,
            "newly_unreachable_buildings": stress.service_metrics["medical"][
                "newly_unreachable_buildings"
            ],
        },
        "criticality_candidate_count": len(criticality),
        "algorithm_note": "No edges x full-city Dijkstra loop; O(V+E) bridge analysis.",
    }
    del criticality, stress, buildings, edges
    gc.collect()
    return result


def build(scales: tuple[int, ...], output: Path) -> dict[str, object]:
    rows = [benchmark(scale) for scale in scales]
    result = {
        "schema_version": "urban-resilience-scale-1.0.0",
        "classification": "synthetic_performance_fixture_not_real_city_data",
        "benchmarks": rows,
        "all_requested_scales_executed": set(scales) == {100_000, 250_000, 500_000},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scales", nargs="+", type=int, default=[100_000, 250_000, 500_000])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build(tuple(args.scales), args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
