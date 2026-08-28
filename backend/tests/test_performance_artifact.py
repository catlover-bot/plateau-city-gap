import json
from pathlib import Path


def test_pilot_performance_artifact_preserves_real_synthetic_boundary() -> None:
    report = json.loads(
        Path("analysis/outputs/real/pilot_performance.json").read_text(encoding="utf-8")
    )
    assert report["classification"] == {
        "api_database": "SYNTHETIC_SCALE",
        "concurrency_result_is_sla": False,
        "production_sla_claimed": False,
        "real_pipeline": "REAL_MUNICIPAL_DATA",
    }
    assert report["synthetic_scale"]["buildings"] == 100_000
    assert report["synthetic_scale"]["road_edges"] == 100_000
    expected = {
        "cities",
        "bbox_buildings",
        "mesh_detail",
        "scenario_detail",
        "scenario_comparison",
        "route_detail",
        "tile_cached",
        "tile_cold",
        "tile_uncached",
        "tile_warm",
        "municipal_city_home",
        "municipal_data_hub",
    }
    measurements = report["synthetic_scale"]["api_p50_p95"]
    assert set(measurements) == expected
    assert all(
        value["p50_ms"] <= value["p95_ms"] <= value["maximum_ms"] for value in measurements.values()
    )
    assert set(report["real_pipeline"]) == {"maizuru", "fujisawa"}
    concurrency = report["synthetic_scale"]["concurrency_1_10_25_50"]
    assert set(concurrency) == {"bbox_buildings", "warm_vector_tile"}
    assert all(set(workload) == {"1", "10", "25", "50"} for workload in concurrency.values())
    assert all(
        sample["p50_ms"] <= sample["p95_ms"] <= sample["maximum_ms"]
        and sample["throughput_requests_per_second"] > 0
        for workload in concurrency.values()
        for sample in workload.values()
    )
