"""CLI for computing CITY GAP metrics from a prepared GeoJSON layer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd

from .metrics import add_gap_metrics

REQUIRED = {
    "area_id",
    "population",
    "elderly_population",
    "elderly_ratio",
    "station_distance_m",
    "bus_stop_distance_m",
    "medical_distance_m",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Prepared area GeoJSON")
    parser.add_argument("--output-dir", type=Path, default=Path("analysis/outputs"))
    args = parser.parse_args()

    areas = gpd.read_file(args.input)
    missing = REQUIRED - set(areas.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    result = add_gap_metrics(areas)
    result = result.sort_values(["rank", "area_id"])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    geojson_path = args.output_dir / "maizuru_city_gap.geojson"
    csv_path = args.output_dir / "maizuru_city_gap.csv"
    result.to_file(geojson_path, driver="GeoJSON")
    result.drop(columns="geometry").to_csv(csv_path, index=False)
    valid = result.dropna(subset=["gap_score"])
    summary = {
        "status": "real analysis output; source provenance must match input",
        "area_count": len(result),
        "scored_area_count": len(valid),
        "top_area_id": None if valid.empty else str(valid.iloc[0]["area_id"]),
        "method": "percentile demographic need x mean Euclidean accessibility deficit",
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()

