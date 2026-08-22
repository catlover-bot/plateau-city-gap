"""Attach Euclidean nearest-target distances to an area layer."""
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd

from .accessibility import nearest_distance


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("areas", type=Path)
    parser.add_argument("--stations", type=Path, required=True)
    parser.add_argument("--bus-stops", type=Path, required=True)
    parser.add_argument("--medical", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/maizuru_areas.geojson")
    )
    args = parser.parse_args()
    areas = gpd.read_file(args.areas)
    for column, path in (("station_distance_m", args.stations), ("bus_stop_distance_m", args.bus_stops), ("medical_distance_m", args.medical)):
        areas[column] = nearest_distance(areas, gpd.read_file(path))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    areas.to_file(args.output, driver="GeoJSON")


if __name__ == "__main__":
    main()
