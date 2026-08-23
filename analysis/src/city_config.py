"""Validated city configuration for the shared CITY GAP analysis engine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class DatasetConfig:
    path: Path
    provider: str
    title: str
    year: int
    license: str
    source_url: str
    source_crs: str


@dataclass(frozen=True)
class CityConfig:
    city_id: str
    city_code: str
    city_name: str
    prefecture_code: str
    prefecture_name: str
    mode: str
    analysis_crs: str
    map_view: dict[str, float]
    plateau_dataset: dict[str, Any]
    population: DatasetConfig
    boundary: DatasetConfig
    stations: DatasetConfig
    bus_stops: DatasetConfig
    medical: DatasetConfig
    minimum_population: int
    minimum_elderly_population: int
    require_centroid_within_city: bool
    output_dir: Path

    @property
    def output_prefix(self) -> str:
        return self.city_id


def _dataset(value: object, label: str, root: Path) -> DatasetConfig:
    if not isinstance(value, dict):
        raise TypeError(f"datasets.{label} must be an object")
    required = {"path", "provider", "title", "year", "license", "source_url", "source_crs"}
    missing = required.difference(value)
    if missing:
        raise ValueError(f"datasets.{label} is missing: {', '.join(sorted(missing))}")
    path = Path(str(value["path"]))
    if not path.is_absolute():
        path = root / path
    return DatasetConfig(
        path=path,
        provider=str(value["provider"]),
        title=str(value["title"]),
        year=int(value["year"]),
        license=str(value["license"]),
        source_url=str(value["source_url"]),
        source_crs=str(value["source_crs"]),
    )


def load_city_config(path: Path, *, repository_root: Path | None = None) -> CityConfig:
    """Load a YAML city definition and resolve data paths against the repository."""
    config_path = path.resolve()
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("City config must contain a YAML object")
    root = (repository_root or config_path.parents[2]).resolve()
    datasets = raw.get("datasets")
    thresholds = raw.get("thresholds")
    output = raw.get("output")
    if not isinstance(datasets, dict) or not isinstance(thresholds, dict) or not isinstance(output, dict):
        raise TypeError("City config requires datasets, thresholds, and output objects")
    output_dir = Path(str(output.get("directory", "analysis/outputs/real")))
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    view = raw.get("map_view")
    plateau = raw.get("plateau_dataset")
    if not isinstance(view, dict) or not isinstance(plateau, dict):
        raise TypeError("City config requires map_view and plateau_dataset objects")
    required_top = {
        "city_id", "city_code", "city_name", "prefecture_code", "prefecture_name",
        "mode", "analysis_crs",
    }
    missing = required_top.difference(raw)
    if missing:
        raise ValueError(f"City config is missing: {', '.join(sorted(missing))}")
    return CityConfig(
        city_id=str(raw["city_id"]),
        city_code=str(raw["city_code"]),
        city_name=str(raw["city_name"]),
        prefecture_code=str(raw["prefecture_code"]),
        prefecture_name=str(raw["prefecture_name"]),
        mode=str(raw["mode"]),
        analysis_crs=str(raw["analysis_crs"]),
        map_view={key: float(view[key]) for key in ("longitude", "latitude", "height")},
        plateau_dataset=plateau,
        population=_dataset(datasets.get("population"), "population", root),
        boundary=_dataset(datasets.get("boundary"), "boundary", root),
        stations=_dataset(datasets.get("stations"), "stations", root),
        bus_stops=_dataset(datasets.get("bus_stops"), "bus_stops", root),
        medical=_dataset(datasets.get("medical"), "medical", root),
        minimum_population=int(thresholds.get("minimum_population", 20)),
        minimum_elderly_population=int(thresholds.get("minimum_elderly_population", 10)),
        require_centroid_within_city=bool(thresholds.get("require_centroid_within_city", True)),
        output_dir=output_dir,
    )
