"""Build lightweight browser assets for a configuration-driven validation city."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from analysis.scripts.build_web_assets import (
    SCHEMA_VERSION,
    _build_boundary,
    _build_mesh_assets,
    _build_point_layers,
    _file_record,
    _generated_at,
    _write_json,
    validate_geojson_geometry,
)
from analysis.src.city_config import load_city_config


def build(config_path: Path, output_dir: Path, generated_at: str | None = None) -> dict[str, object]:
    config = load_city_config(config_path)
    prefix = config.output_prefix
    metrics_path = config.output_dir / f"{prefix}_city_gap.geojson"
    top10_path = config.output_dir / f"{prefix}_city_gap_top10.csv"
    summary_path = config.output_dir / f"{prefix}_summary.json"
    for path in (metrics_path, top10_path, summary_path):
        if not path.is_file():
            raise FileNotFoundError(f"Run the city analysis first: {path}")

    analysis_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    meshes, top10 = _build_mesh_assets(metrics_path, top10_path)
    boundary, boundary_collection, _ = _build_boundary(config.boundary.path)
    stations, buses, medical, point_counts = _build_point_layers(
        config.stations.path,
        config.bus_stops.path,
        config.medical.path,
        boundary,
    )
    for collection in (stations, buses, medical):
        validate_geojson_geometry(collection, expected_types={"Point"})
    validate_geojson_geometry(boundary_collection, expected_types={"Polygon", "MultiPolygon"})

    summary = {
        "schema_version": SCHEMA_VERSION,
        "analysis_status": "real_data",
        "generated_from_synthetic_data": False,
        "city": analysis_summary["city"],
        "distance_method": analysis_summary["distance_method"],
        "analysis_crs": analysis_summary["analysis_crs"],
        "web_crs": "EPSG:4326",
        "record_counts": analysis_summary["record_counts"],
        "primary_ranking": analysis_summary["primary_ranking"],
        "threshold_stability": analysis_summary["threshold_stability"],
        "spatial_sanity": analysis_summary["spatial_sanity"],
        "datasets": analysis_summary["datasets"],
        "limitations": analysis_summary["limitations"],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "mesh_metrics.geojson": meshes,
        "top10.json": top10,
        "summary.json": summary,
        "stations.geojson": stations,
        "bus_stops.geojson": buses,
        "medical_facilities.geojson": medical,
        "boundary.geojson": boundary_collection,
    }
    for filename, value in outputs.items():
        _write_json(output_dir / filename, value, compact=filename.endswith(".geojson"))

    counts = {
        "mesh_metrics.geojson": len(meshes["features"]),
        "top10.json": len(top10["items"]),
        "summary.json": 1,
        "stations.geojson": len(stations["features"]),
        "bus_stops.geojson": len(buses["features"]),
        "medical_facilities.geojson": len(medical["features"]),
        "boundary.geojson": len(boundary_collection["features"]),
    }
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _generated_at(generated_at),
        "analysis_version": "0.2.0",
        "city": analysis_summary["city"],
        "mode": "cross_city_validation",
        "score_comparison": "within_city_only",
        "source_datasets": analysis_summary["datasets"],
        "source_record_counts": point_counts,
        "outputs": [_file_record(output_dir / filename, counts[filename]) for filename in outputs],
        "limitations": analysis_summary["limitations"],
    }
    _write_json(output_dir / "manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--generated-at")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(build(args.config, args.output_dir, args.generated_at), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
