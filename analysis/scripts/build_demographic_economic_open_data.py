"""Build real demographic and economic open-data fabric for both pilot cities."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd

from backend.citygap_platform.domain.open_data import (
    DiscoveredResource,
    DiscoveryRequest,
    RawResourceReceipt,
    SchemaInspection,
)
from backend.citygap_platform.open_data.demographic_activity import (
    ECONOMIC_METRICS,
    PROJECTION_YEARS,
    canonicalize_economic_activity,
    canonicalize_future_population,
    economic_metric_dictionary,
)
from backend.citygap_platform.open_data.demographics import (
    EStatEconomicCensusAdapter,
    MlitFuturePopulationAdapter,
)
from backend.citygap_platform.open_data.http import SafeHttpClient
from backend.citygap_platform.open_data.storage import ContentAddressedObjectStore

ROOT = Path(__file__).resolve().parents[2]
RAW_STORE = ROOT / "data/raw/open_data"
OUTPUT_DIR = ROOT / "analysis/outputs/real/open_data"
SOURCE_REPORT = OUTPUT_DIR / "demographic_economic_source_report.json"
CANONICAL = OUTPUT_DIR / "demographic_economic_canonical.jsonl"
MESH_CONTEXT = OUTPUT_DIR / "demographic_economic_mesh_context.geojson"
SUMMARY = OUTPUT_DIR / "demographic_economic_summary.json"

CITY_CONFIGS = {
    "maizuru": {
        "city_code": "26202",
        "city_name": "舞鶴市",
        "meshes": ROOT / "analysis/outputs/real/maizuru_city_gap.geojson",
        "plateau_meshes": ROOT / "analysis/outputs/real/maizuru_plateau_detail_meshes.csv",
    },
    "fujisawa": {
        "city_code": "14205",
        "city_name": "藤沢市",
        "meshes": ROOT / "analysis/outputs/real/fujisawa_city_gap.geojson",
        "plateau_meshes": ROOT / "analysis/outputs/real/fujisawa_plateau_detail_meshes.csv",
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _observed_at(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("observed-at must include a timezone")
    return parsed.isoformat().replace("+00:00", "Z")


def _optional_float(value: Any) -> float | None:
    if value is None or bool(pd.isna(value)):
        return None
    return float(value)


def _plateau_aggregate(row: pd.Series) -> dict[str, Any]:
    return {
        "method": "deterministic_500m_mesh_aggregate",
        "source": "PLATEAU 2025 building-derived demographic context",
        "status": "modeled_context_not_observed_population",
        "residential_building_count": int(row["residential_building_count"]),
        "estimated_population_allocated": _optional_float(row["estimated_population_allocated"]),
        "estimated_elderly_allocated": _optional_float(row["estimated_elderly_allocated"]),
    }


def _mesh_context(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    meshes = gpd.read_file(config["meshes"], engine="pyogrio").to_crs("EPSG:4326")
    if meshes["mesh_code"].astype(str).duplicated().any():
        raise ValueError(f"Audited mesh identifiers are not unique: {config['city_code']}")
    plateau = pd.read_csv(config["plateau_meshes"], dtype={"mesh_code": str})
    if plateau["mesh_code"].duplicated().any():
        raise ValueError(f"PLATEAU mesh aggregates are not unique: {config['city_code']}")
    plateau_by_mesh = {
        str(row["mesh_code"]): _plateau_aggregate(row) for _, row in plateau.iterrows()
    }
    return {
        str(row["mesh_code"]): {
            "geometry": row.geometry.__geo_interface__,
            "city_area_fraction": _optional_float(row.get("city_area_fraction")),
            "centroid_within_city": bool(row.get("centroid_within_city")),
            "plateau_aggregate": plateau_by_mesh.get(str(row["mesh_code"])),
        }
        for _, row in meshes.sort_values("mesh_code").iterrows()
    }


def _resource_report(
    resource: DiscoveredResource,
    receipt: RawResourceReceipt,
    inspection: SchemaInspection,
    *,
    observed_at: str,
    city_key: str,
    city_record_count: int,
    adapter_version: str,
) -> dict[str, Any]:
    return {
        "city": city_key,
        "provider": (
            "国土交通省 国土数値情報"
            if resource.external_dataset_id.startswith("mlit-")
            else "e-Stat / 総務省・経済産業省"
        ),
        "title": resource.title,
        "resource_url": resource.resource_url,
        "manifest_url": resource.source_metadata["manifest_url"],
        "external_dataset_id": resource.external_dataset_id,
        "external_resource_id": resource.external_resource_id,
        "format": resource.format,
        "license_id": resource.license_id,
        "reference_date": resource.reference_date,
        "retrieved_at": observed_at,
        "version_signals": resource.version_signals,
        "source_metadata": resource.source_metadata,
        "raw_sha256": receipt.sha256,
        "raw_size_bytes": receipt.size_bytes,
        "raw_object_key": receipt.object_key,
        "raw_publication": False,
        "raw_publication_reason": "immutable official bytes stay outside public web assets",
        "adapter_version": adapter_version,
        "schema_version": inspection.schema_version,
        "encoding": inspection.encoding,
        "source_crs": inspection.source_crs,
        "source_row_count": inspection.row_count,
        "field_names": inspection.field_names,
        "quality_results": inspection.quality_results,
        "city_canonical_record_count": city_record_count,
    }


def _projection_summary(records: list[dict[str, Any]], quality: dict[str, Any]) -> dict[str, Any]:
    totals: dict[int, dict[str, float]] = {
        year: {
            "population_before_privacy_aggregation": 0.0,
            "published_privacy_adjusted_population": 0.0,
            "published_privacy_adjusted_age_65_plus": 0.0,
        }
        for year in PROJECTION_YEARS
    }
    for record in records:
        for projection in record["attributes"]["projections"]:
            year = int(projection["year"])
            before = projection["total_population_before_privacy_aggregation"]
            published = projection["published_privacy_adjusted_total_population"]
            elderly = projection["broad_age_population"]["65_plus"]
            if before is not None:
                totals[year]["population_before_privacy_aggregation"] += before
            if published is not None:
                totals[year]["published_privacy_adjusted_population"] += published
            if elderly is not None:
                totals[year]["published_privacy_adjusted_age_65_plus"] += elderly
    series = []
    outside_by_year = quality["privacy_aggregation_targets_outside_city_by_year"]
    for year, values in totals.items():
        partial_published = values["published_privacy_adjusted_population"]
        is_complete = str(year) not in outside_by_year
        series.append(
            {
                "year": year,
                "population_before_privacy_aggregation": round(
                    values["population_before_privacy_aggregation"], 4
                ),
                "published_privacy_adjusted_population": (
                    round(partial_published, 4) if is_complete else None
                ),
                "published_privacy_adjusted_population_partial_city_code_extract": round(
                    partial_published, 4
                ),
                "published_privacy_adjusted_age_65_plus": (
                    round(values["published_privacy_adjusted_age_65_plus"], 4)
                    if is_complete
                    else None
                ),
                "published_privacy_adjusted_age_65_plus_ratio": (
                    round(
                        values["published_privacy_adjusted_age_65_plus"] / partial_published,
                        6,
                    )
                    if is_complete and partial_published
                    else None
                ),
                "published_city_total_status": (
                    "complete_within_exact_city_code_extract"
                    if is_complete
                    else "unavailable_due_to_outside_city_privacy_aggregation_target"
                ),
                "status": "official_trial_projection_not_observation",
            }
        )
    start = totals[2025]["population_before_privacy_aggregation"]
    end = totals[2050]["population_before_privacy_aggregation"]
    return {
        "series": series,
        "change_2025_to_2050": {
            "absolute_persons": round(end - start, 4),
            "rate": round((end - start) / start, 6) if start else None,
            "semantics": (
                "difference_between_official_trial_projection_values_before_privacy_aggregation"
            ),
        },
        "aggregation_note": (
            "The before-privacy series sums exact city-code rows. A published privacy-adjusted "
            "city total is withheld for any year whose aggregation target leaves that extract; "
            "the partial sum remains labeled for audit only."
        ),
    }


def _economic_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    sums: dict[str, int] = defaultdict(int)
    nulls: dict[str, int] = defaultdict(int)
    for record in records:
        for key, value in record["attributes"]["metrics"].items():
            if value is None:
                nulls[key] += 1
            else:
                sums[key] += int(value)
    return {
        "published_mesh_row_sums": {
            metric.metric_key: {
                "value": sums[metric.metric_key],
                "null_row_count": nulls[metric.metric_key],
                "unit": metric.unit,
            }
            for metric in ECONOMIC_METRICS
        },
        "claim_boundary": (
            "Sums cover rows published in T001162 that match audited city meshes. Missing rows "
            "and suppressed cells are not converted to zero, and no need score is inferred."
        ),
    }


def _mesh_features(
    *,
    city_code: str,
    city_name: str,
    context: dict[str, dict[str, Any]],
    future_records: list[dict[str, Any]],
    economic_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    future_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in future_records:
        parent = record["spatial_links"]["parent_500m_mesh"]["mesh_code"]
        future_by_parent[parent].append(record)
    economic_by_mesh = {record["external_record_id"]: record for record in economic_records}
    features = []
    for mesh_code, mesh in sorted(context.items()):
        children = future_by_parent.get(mesh_code, [])
        future_values: dict[int, float | None] = {}
        for year in (2025, 2050, 2070):
            values = [
                projection["published_privacy_adjusted_total_population"]
                for child in children
                for projection in child["attributes"]["projections"]
                if projection["year"] == year
                and projection["published_privacy_adjusted_total_population"] is not None
            ]
            future_values[year] = round(sum(values), 4) if values else None
        activity = economic_by_mesh.get(mesh_code)
        metrics = activity["attributes"]["metrics"] if activity is not None else {}
        plateau = mesh.get("plateau_aggregate")
        features.append(
            {
                "type": "Feature",
                "id": f"{city_code}:{mesh_code}",
                "geometry": mesh["geometry"],
                "properties": {
                    "city_code": city_code,
                    "city_name": city_name,
                    "mesh_code": mesh_code,
                    "city_area_fraction": mesh["city_area_fraction"],
                    "centroid_within_city": mesh["centroid_within_city"],
                    "future_population_status": (
                        "available_official_projection"
                        if children
                        else "unavailable_not_published_for_city_code"
                    ),
                    "future_population_250m_child_count": len(children),
                    "future_population_2025": future_values[2025],
                    "future_population_2050": future_values[2050],
                    "future_population_2070": future_values[2070],
                    "economic_activity_status": (
                        "available_published_row"
                        if activity is not None
                        else "unavailable_not_published_in_selected_table"
                    ),
                    "economic_establishments_all_a_s": metrics.get("establishments_all_a_s"),
                    "economic_employees_all_a_s": metrics.get("employees_all_a_s"),
                    "economic_employees_medical_welfare_p": metrics.get(
                        "employees_medical_welfare_p"
                    ),
                    "plateau_aggregate_status": (
                        "available_modeled_context" if plateau is not None else "unavailable"
                    ),
                    "plateau_residential_building_count": (
                        plateau["residential_building_count"] if plateau is not None else None
                    ),
                    "temporal_alignment": "mixed",
                },
            }
        )
    return features


def build(observed_at: str, raw_store: Path) -> dict[str, Any]:
    client = SafeHttpClient(
        allowed_hosts={"nlftp.mlit.go.jp", "www.e-stat.go.jp"}, timeout_seconds=120
    )
    store = ContentAddressedObjectStore(raw_store)
    future_adapter = MlitFuturePopulationAdapter(client=client, object_store=store)
    economic_adapter = EStatEconomicCensusAdapter(client=client, object_store=store)

    all_records: list[dict[str, Any]] = []
    all_features: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    city_summaries: dict[str, Any] = {}
    for city_key, config in CITY_CONFIGS.items():
        request = DiscoveryRequest(config["city_code"], config["city_name"])
        context = _mesh_context(config)

        future_resource = future_adapter.discover(request)[0]
        future_receipt = future_adapter.download(future_resource, max_bytes=64 * 1024 * 1024)
        future_inspection = future_adapter.inspect_schema(future_resource, future_receipt)
        future_frame = future_adapter.read_frame(future_receipt, future_inspection)
        future_records, future_quality = canonicalize_future_population(
            future_frame,
            city_code=config["city_code"],
            city_name=config["city_name"],
            resource_id=future_resource.external_resource_id,
            raw_sha256=future_receipt.sha256,
            reference_date=str(future_resource.reference_date),
            mesh_context=context,
        )

        economic_resource = economic_adapter.discover(request)[0]
        economic_receipt = economic_adapter.download(economic_resource, max_bytes=64 * 1024 * 1024)
        economic_inspection = economic_adapter.inspect_schema(economic_resource, economic_receipt)
        normalized_economic = list(
            economic_adapter.normalize(economic_resource, economic_receipt, economic_inspection)
        )
        economic_records, economic_quality = canonicalize_economic_activity(
            normalized_economic,
            city_code=config["city_code"],
            city_name=config["city_name"],
            resource_id=economic_resource.external_resource_id,
            raw_sha256=economic_receipt.sha256,
            reference_date=str(economic_resource.reference_date),
            mesh_context=context,
        )

        resources.extend(
            (
                _resource_report(
                    future_resource,
                    future_receipt,
                    future_inspection,
                    observed_at=observed_at,
                    city_key=city_key,
                    city_record_count=len(future_records),
                    adapter_version="mlit-future-population-250m@2024",
                ),
                _resource_report(
                    economic_resource,
                    economic_receipt,
                    economic_inspection,
                    observed_at=observed_at,
                    city_key=city_key,
                    city_record_count=len(economic_records),
                    adapter_version="estat-economic-census-500m@2021",
                ),
            )
        )
        plateau_future_links = sum(
            record["spatial_links"]["plateau_aggregate"] is not None for record in future_records
        )
        plateau_economic_links = sum(
            record["spatial_links"]["plateau_aggregate"] is not None for record in economic_records
        )
        city_summaries[city_key] = {
            "city_code": config["city_code"],
            "city_name": config["city_name"],
            "audited_500m_mesh_count": len(context),
            "canonical_record_count": len(future_records) + len(economic_records),
            "future_population": {
                "quality": future_quality,
                "analysis": _projection_summary(future_records, future_quality),
            },
            "economic_activity": {
                "quality": economic_quality,
                "analysis": _economic_summary(economic_records),
            },
            "spatial_links": {
                "future_to_parent_500m": len(future_records),
                "economic_to_500m_exact": len(economic_records),
                "future_with_plateau_aggregate_context": plateau_future_links,
                "economic_with_plateau_aggregate_context": plateau_economic_links,
            },
            "temporal_alignment": {
                "status": "mixed",
                "future_population_baseline": 2020,
                "economic_census_reference_date": "2021-06-01",
                "plateau_reference_year": 2025,
                "projection_years": list(PROJECTION_YEARS),
                "hidden_as_single_year": False,
            },
        }
        all_records.extend(future_records)
        all_records.extend(economic_records)
        all_features.extend(
            _mesh_features(
                city_code=config["city_code"],
                city_name=config["city_name"],
                context=context,
                future_records=future_records,
                economic_records=economic_records,
            )
        )

    all_records.sort(
        key=lambda item: (item["city_code"], item["record_type"], item["canonical_id"])
    )
    resources.sort(key=lambda item: (item["city"], item["external_dataset_id"]))
    source_report = {
        "schema_version": "citygap-demographic-economic-source-report@1",
        "observed_at": observed_at,
        "resources": resources,
        "economic_metric_dictionary": economic_metric_dictionary(),
        "source_definitions": {
            "future_population": (
                "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-mesh250r6.html"
            ),
            "economic_census": (
                "https://www.e-stat.go.jp/help/data-definition-information/downloaddata/T001162.pdf"
            ),
        },
        "licence_attribution": {
            "future_population": "国土数値情報, CC BY 4.0",
            "economic_census": "e-Stat, 政府標準利用規約（第2.0版）",
        },
        "promotion_status": "analysis_ready_with_explicit_claim_boundaries",
        "claim_boundary": (
            "Future population is a trial projection and economic census values are activity "
            "observations. Neither is current availability, capacity, demand, need, or a "
            "policy recommendation."
        ),
    }
    _write_json(SOURCE_REPORT, source_report)

    CANONICAL.parent.mkdir(parents=True, exist_ok=True)
    CANONICAL.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in all_records
        ),
        encoding="utf-8",
    )
    _write_json(
        MESH_CONTEXT,
        {
            "type": "FeatureCollection",
            "name": "citygap_demographic_economic_mesh_context",
            "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
            "features": sorted(all_features, key=lambda item: str(item["id"])),
        },
    )
    summary = {
        "schema_version": "citygap-demographic-economic-summary@1",
        "observed_at": observed_at,
        "source_report": SOURCE_REPORT.relative_to(ROOT).as_posix(),
        "source_report_sha256": _sha256(SOURCE_REPORT),
        "canonical_artifact": CANONICAL.relative_to(ROOT).as_posix(),
        "canonical_artifact_sha256": _sha256(CANONICAL),
        "mesh_context_artifact": MESH_CONTEXT.relative_to(ROOT).as_posix(),
        "mesh_context_artifact_sha256": _sha256(MESH_CONTEXT),
        "canonical_record_count": len(all_records),
        "mesh_context_feature_count": len(all_features),
        "raw_resource_count": len(resources),
        "raw_unique_sha256_count": len({item["raw_sha256"] for item in resources}),
        "cities": city_summaries,
        "privacy": "Raw official archives remain outside public assets; canonical data is aggregate mesh data.",
        "temporal_alignment": "mixed_and_explicit",
        "automatic_best_projection_selected": False,
    }
    _write_json(SUMMARY, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--raw-store", type=Path, default=RAW_STORE)
    args = parser.parse_args()
    print(
        json.dumps(
            build(_observed_at(args.observed_at), args.raw_store),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
