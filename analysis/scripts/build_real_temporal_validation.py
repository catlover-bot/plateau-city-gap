"""Validate CITY GAP temporal diff with official Kunitachi 2023/2025 CityGML.

Kunitachi is a validation-only dataset, not a third CITY GAP product city.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analysis.src.temporal_validation import (
    TEMPORAL_ALGORITHM_VERSION,
    classify_version_diff,
    incremental_rebuild_check,
    read_citygml_theme,
    state_digest,
)

ROOT = Path(__file__).resolve().parents[2]
ARCHIVES = {
    "2023": {
        "path": ROOT / "data/raw/temporal_validation/13215_kunitachi_2023_citygml.zip",
        "sha256": "6d437f8808a136cf278ee230e306120ede5674da105040273ca24408f6890e59",
        "catalog": "https://www.geospatial.jp/ckan/dataset/plateau-13215-kunitachi-shi-2023",
        "asset": "https://assets.cms.plateau.reearth.io/assets/fe/8aa8a6-0d53-4d20-bcb9-c0a1299b0536/13215_kunitachi-shi_pref_2023_citygml_2_op.zip",
        "product_specification": "4.x catalog resource",
    },
    "2025": {
        "path": ROOT / "data/raw/temporal_validation/13215_kunitachi_2025_citygml.zip",
        "sha256": "bfd34c91a642518d3a8fe7b34f4da23a0c660cfe2bb3968d4f74db28d0c43a51",
        "catalog": "https://www.geospatial.jp/ckan/dataset/plateau-13215-kunitachi-shi-2025",
        "asset": "https://assets.cms.plateau.reearth.io/assets/b6/21288f-f49b-432d-a569-4961e9ed1688/13215_kunitachi-shi_pref_2025_citygml_1_op.zip",
        "product_specification": "5.x catalog resource",
    },
}
THEMES = ("bldg", "tran", "luse", "urf")
OUTPUT = ROOT / "analysis/outputs/real/validation/kunitachi_real_temporal_validation.json"
PUBLIC_OUTPUT = ROOT / "frontend/public/data/validation/real_temporal_validation.json"
PUBLIC_MAP = ROOT / "frontend/public/data/validation/temporal_change_samples.geojson"
CACHE = ROOT / "data/interim/validation"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if pd.isna(value) or not np.isfinite(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def _load_or_parse(year: str, theme: str, *, use_cache: bool) -> pd.DataFrame:
    cache_path = CACHE / f"kunitachi_{year}_{theme}_features.parquet"
    if use_cache and cache_path.exists():
        return pd.read_parquet(cache_path)
    frame = read_citygml_theme(ARCHIVES[year]["path"], theme)
    CACHE.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(cache_path, index=False)
    return frame


def _change_sample_features(theme: str, changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    for group in ("added", "removed", "changed"):
        eligible = [
            item for item in changes
            if item["change_type"] == group
            or (group == "changed" and item["change_type"] in {"geometry_changed", "attribute_changed"})
        ]
        eligible = sorted(
            eligible,
            key=lambda item: hashlib.sha256(
                f"{theme}|{group}|{item.get('old_id')}|{item.get('new_id')}".encode()
            ).hexdigest(),
        )[:30]
        for item in eligible:
            lon = item.get("centroid_lon")
            lat = item.get("centroid_lat")
            if lon is None or lat is None or pd.isna(lon) or pd.isna(lat):
                continue
            sample_id = hashlib.sha256(
                f"{theme}|{item.get('old_id')}|{item.get('new_id')}".encode()
            ).hexdigest()[:18]
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "sample_id": f"temporal-{sample_id}",
                        "theme": theme,
                        "review_group": group,
                        "change_type": item["change_type"],
                        "match_method": item["method"],
                        "review_status": "not_reviewed",
                        "automatic_correctness_claimed": False,
                    },
                    "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                }
            )
    return features


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    for year, source in ARCHIVES.items():
        if not source["path"].exists():
            raise FileNotFoundError(source["path"])
        actual = _sha256(source["path"])
        if actual != source["sha256"]:
            raise ValueError(f"Kunitachi {year} archive checksum mismatch")
        source["bytes"] = source["path"].stat().st_size
    results: dict[str, Any] = {}
    map_features: list[dict[str, Any]] = []
    all_incremental_agree = True
    for theme in THEMES:
        theme_started = time.perf_counter()
        old = _load_or_parse("2023", theme, use_cache=not args.no_cache)
        new = _load_or_parse("2025", theme, use_cache=not args.no_cache)
        diff = classify_version_diff(old, new)
        incremental = incremental_rebuild_check(old, new)
        all_incremental_agree &= incremental["count_agreement"] and incremental["hash_agreement"]
        map_features.extend(_change_sample_features(theme, diff["changes"]))
        results[theme] = {
            "theme_label": {
                "bldg": "building",
                "tran": "road",
                "luse": "land_use",
                "urf": "urban_planning",
            }[theme],
            "diff_counts": diff["counts"],
            "both_geometry_and_attribute_changed": diff["both_geometry_and_attribute_changed"],
            "match_audit": diff["match_audit"],
            "old_state_sha256": state_digest(old),
            "new_state_sha256": state_digest(new),
            "incremental_vs_full": incremental,
            "map_review_samples": {
                group: sum(
                    feature["properties"]["theme"] == theme
                    and feature["properties"]["review_group"] == group
                    for feature in map_features
                )
                for group in ("added", "removed", "changed")
            },
            "runtime_seconds": time.perf_counter() - theme_started,
        }
    payload = {
        "schema_version": "real-temporal-validation-v1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "city": {
            "city_id": "kunitachi-temporal-validation-only",
            "city_code": "13215",
            "city_name": "国立市",
            "purpose": "real PLATEAU version-to-version diff validation only",
            "product_city": False,
            "ui_product_registration": False,
        },
        "algorithm_version": TEMPORAL_ALGORITHM_VERSION,
        "sources": {
            year: {
                key: value for key, value in source.items() if key != "path"
            }
            for year, source in ARCHIVES.items()
        },
        "themes": results,
        "incremental_vs_full_overall": {
            "all_theme_count_and_hash_agreement": all_incremental_agree,
            "building_allocation": "NOT_AVAILABLE: validation-only city has no census allocation product setup",
            "mesh_metrics": "NOT_AVAILABLE: validation-only city has no CITY GAP mesh state",
            "network_affected_scope": results["tran"]["diff_counts"],
            "context_join_affected_scope": {
                "land_use": results["luse"]["diff_counts"],
                "urban_planning": results["urf"]["diff_counts"],
            },
        },
        "validation_status": "cross_validated",
        "municipal_review": "not_reviewed",
        "field_validation": "awaiting_field_validation",
        "limitations": [
            "A version difference is not automatically a real-world construction or demolition event.",
            "Specification, capture, geometry LOD, and attribute schema changes can contribute to differences.",
            "Unique geometry/attribute fallbacks are conservative; ambiguous matches remain unmatched.",
            "Map samples are awaiting human review and are not automatically marked correct.",
        ],
        "runtime_seconds": time.perf_counter() - started,
        "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(_json_value(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    PUBLIC_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_OUTPUT.write_text(
        json.dumps(_json_value(payload), ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    PUBLIC_MAP.write_text(
        json.dumps({"type": "FeatureCollection", "features": map_features}, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(OUTPUT), "themes": {key: value["diff_counts"] for key, value in results.items()}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
