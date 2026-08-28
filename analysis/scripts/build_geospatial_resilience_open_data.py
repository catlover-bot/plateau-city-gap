"""Build official geospatial-reference, ground and traffic-safety evidence artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import Point, mapping
from shapely.ops import transform

from analysis.src.mesh import mesh_polygon_250m
from backend.citygap_platform.domain.open_data import DiscoveryRequest
from backend.citygap_platform.open_data.http import SafeHttpClient
from backend.citygap_platform.open_data.resilience import (
    JShisSurfaceGroundAdapter,
    NpaTrafficAccidentAdapter,
)
from backend.citygap_platform.open_data.storage import ContentAddressedObjectStore

ROOT = Path(__file__).resolve().parents[2]
RAW_STORE = ROOT / "data/raw/open_data"
OUTPUT_DIR = ROOT / "analysis/outputs/real/open_data"
SOURCE_REPORT = OUTPUT_DIR / "geospatial_resilience_source_report.json"
CANONICAL = OUTPUT_DIR / "geospatial_resilience_canonical.jsonl"
SUMMARY = OUTPUT_DIR / "geospatial_resilience_summary.json"

CITY_CONFIGS = {
    "maizuru": {
        "city_code": "26202",
        "city_name": "舞鶴市",
        "npa_prefecture_code": "61",
        "npa_municipality_code": "202",
        "jshis_first_mesh": "5335",
        "meshes": ROOT / "analysis/outputs/real/maizuru_city_gap.geojson",
    },
    "fujisawa": {
        "city_code": "14205",
        "city_name": "藤沢市",
        "npa_prefecture_code": "45",
        "npa_municipality_code": "205",
        "jshis_first_mesh": "5339",
        "meshes": ROOT / "analysis/outputs/real/fujisawa_city_gap.geojson",
    },
}

REFERENCE_COVERAGE = {
    "gsi_foundation_map": {
        "status": "requires_review",
        "unavailable_reason": "requires_credentials",
        "official_url": "https://service.gsi.go.jp/kiban/app/help/",
        "specification_version": "5.3",
        "specification_updated": "2026-07-31",
        "schema_version": "5.1",
        "schema_applies_from": "2025-04-01",
        "datum": "JGD2024",
        "finding": (
            "Download requires a registered account and the intended reproduction/use must "
            "be reviewed under the Survey Act. No Foundation Map bytes were ingested."
        ),
        "comparison_with_plateau_performed": False,
    },
    "pedestrian_network": {
        "official_url": "https://ckan.hokonavi.go.jp/dataset/",
        "specification_url": (
            "https://www.mlit.go.jp/sogoseisaku/soukou/sogoseisaku_soukou_tk_000056.html"
        ),
        "catalog_api": "https://ckan.hokonavi.go.jp/api/3/action/package_search?rows=1000",
        "catalog_dataset_count": 31,
        "catalog_latest_modified": "2026-04-14",
        "specification_date": "2024-07",
        "finding": (
            "Neither pilot city has a published walking-network package in the current "
            "official catalog. Fujisawa legacy facility barrier-free metadata is not a "
            "walking network, and PLATEAU road surfaces are not relabeled as one."
        ),
    },
    "xroad_traffic": {
        "official_url": "https://www.jartic-open-traffic.org/",
        "api_specification_url": "https://www.jartic-open-traffic.org/action_method.pdf",
        "api_specification_date": "2026-01",
        "terms_date": "2025-05-12",
        "probe_at": "2026-08-28T21:00:00+09:00",
        "probe_scope": "route_type_3 within each audited 500m mesh context",
        "finding": (
            "The API exposes rolling reference observations without staff validation. A "
            "single bounded probe is coverage evidence only, not a stable snapshot, official "
            "survey result, capacity, congestion measure, risk, or prediction."
        ),
    },
    "gtfs": {
        "audit_artifact": "analysis/outputs/real/gtfs_official_source_audit.json",
        "finding": (
            "No stable, downloadable official GTFS/GTFS-JP feed was published for either "
            "pilot city at recheck. P11 is never converted into GTFS."
        ),
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


def _mesh_context(config: dict[str, Any]) -> tuple[gpd.GeoDataFrame, dict[str, dict[str, Any]]]:
    frame = gpd.read_file(config["meshes"], engine="pyogrio").to_crs("EPSG:4326")
    frame["mesh_code"] = frame["mesh_code"].astype(str)
    if frame["mesh_code"].duplicated().any():
        raise ValueError(f"Audited mesh identifiers are not unique: {config['city_code']}")
    frame = frame.sort_values("mesh_code").reset_index(drop=True)
    context = {
        str(row.mesh_code): {
            "geometry": row.geometry,
            "city_area_fraction": (
                None if row.city_area_fraction is None else float(row.city_area_fraction)
            ),
            "centroid_within_city": bool(row.centroid_within_city),
        }
        for row in frame.itertuples()
    }
    return frame, context


def _jshis_canonical(
    *,
    row: dict[str, Any],
    config: dict[str, Any],
    context: dict[str, dict[str, Any]],
    resource_id: str,
    raw_sha256: str,
    source_row_number: int,
    transformer: Transformer,
) -> dict[str, Any]:
    mesh_code = row["mesh_code_250m"]
    parent = row["parent_500m_mesh_code"]
    geometry = transform(transformer.transform, mesh_polygon_250m(mesh_code))
    return {
        "canonical_id": f"jshis-ground:{raw_sha256[:16]}:{mesh_code}",
        "canonical_version": "citygap-canonical-ground-context@1",
        "record_type": "ground_observation",
        "city_code": config["city_code"],
        "city_name": config["city_name"],
        "external_record_id": mesh_code,
        "display_name": f"J-SHIS 250m mesh {mesh_code}",
        "reference_date": "2020",
        "geometry": mapping(geometry),
        "attributes": {
            "entity_kind": "jshis_surface_ground_model_mesh",
            "mesh_size_m": 250,
            **{
                key: value
                for key, value in row.items()
                if key not in {"mesh_code_250m", "parent_500m_mesh_code"}
            },
            "claim_boundary": (
                "J-SHIS V4 surface-ground model context, not an in-situ observation, "
                "earthquake probability, damage forecast, or policy risk score."
            ),
        },
        "spatial_links": {
            "audited_500m_mesh": {
                "mesh_code": parent,
                "method": "deterministic_parent_mesh",
                "city_area_fraction": context[parent]["city_area_fraction"],
                "scope": "published 250m cell inside audited 500m mesh context",
            }
        },
        "provenance": {
            "provider": "防災科学技術研究所 J-SHIS",
            "resource_id": resource_id,
            "raw_sha256": raw_sha256,
            "source_row_locator": f"{resource_id}:data-row:{source_row_number}",
            "source_crs": "JGD2000 geographic coordinates (EPSG:4612)",
            "canonical_crs": "EPSG:4326",
            "transformation_method": "PROJ EPSG:4612 to EPSG:4326",
        },
    }


def _covering_mesh(point: Point, context: dict[str, dict[str, Any]]) -> str | None:
    matches = [code for code, value in context.items() if value["geometry"].covers(point)]
    if len(matches) > 1:
        raise ValueError("Historical accident point matched multiple audited meshes")
    return matches[0] if matches else None


def _npa_canonical(
    *,
    row: dict[str, Any],
    config: dict[str, Any],
    context: dict[str, dict[str, Any]],
    resource_id: str,
    raw_sha256: str,
) -> dict[str, Any]:
    point = Point(row["longitude"], row["latitude"])
    matched_mesh = _covering_mesh(point, context)
    mesh_link: dict[str, Any] = {
        "mesh_code": matched_mesh,
        "method": "point_in_audited_mesh" if matched_mesh else "unmatched",
        "scope": "audited 500m mesh context, not an exact municipal-boundary assertion",
    }
    if matched_mesh:
        mesh_link["city_area_fraction"] = context[matched_mesh]["city_area_fraction"]
    return {
        "canonical_id": f"npa-accident:{raw_sha256[:16]}:{row['external_record_id']}",
        "canonical_version": "citygap-canonical-historical-traffic-accident@1",
        "record_type": "road_observation",
        "city_code": config["city_code"],
        "city_name": config["city_name"],
        "external_record_id": row["external_record_id"],
        "display_name": f"Historical traffic accident {row['external_record_id']}",
        "reference_date": row["occurred_at"],
        "geometry": mapping(point),
        "attributes": {
            **{
                key: value
                for key, value in row.items()
                if key not in {"longitude", "latitude", "external_record_id"}
            },
            "event_coordinate": {
                "longitude": row["longitude"],
                "latitude": row["latitude"],
            },
            "claim_boundary": (
                "Historical injury/fatal accident record only. Property-only accidents are "
                "excluded, and no frequency denominator, current hazard, probability, risk "
                "surface, causal effect, or prediction is inferred."
            ),
        },
        "spatial_links": {"audited_500m_mesh": mesh_link},
        "provenance": {
            "provider": "警察庁",
            "resource_id": resource_id,
            "raw_sha256": raw_sha256,
            "source_record_key": row["external_record_id"],
            "source_crs": "published world-geodetic DMS",
            "canonical_crs": "EPSG:4326",
            "annual_file_year": row["annual_file_year"],
            "occurrence_time_preserved_separately": True,
        },
    }


def _resource_report(
    *,
    provider: str,
    resource: Any,
    receipt: Any,
    inspection: Any,
    observed_at: str,
    canonical_by_city: dict[str, int],
    adapter_version: str,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "title": resource.title,
        "resource_url": resource.resource_url,
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
        "raw_publication_reason": "official raw bytes stay outside public web assets",
        "adapter_version": adapter_version,
        "schema_version": inspection.schema_version,
        "encoding": inspection.encoding,
        "source_crs": inspection.source_crs,
        "source_row_count": inspection.row_count,
        "field_names": inspection.field_names,
        "quality_results": inspection.quality_results,
        "canonical_record_count_by_city": canonical_by_city,
    }


def _coverage_by_city() -> dict[str, dict[str, Any]]:
    return {
        "maizuru": {
            "gsi_foundation_map": {
                "status": "requires_review",
                "unavailable_reason": "requires_credentials",
            },
            "pedestrian_network": {
                "status": "unavailable",
                "unavailable_reason": "outside_coverage",
            },
            "xroad_traffic": {
                "status": "partial",
                "constant_traffic_points_within_context": 0,
                "cctv_points_within_context": 3,
                "cctv_station_codes": ["6810660", "6810667", "6810670"],
                "stable_snapshot_ingested": False,
            },
            "gtfs": {"status": "unavailable", "unavailable_reason": "not_published"},
        },
        "fujisawa": {
            "gsi_foundation_map": {
                "status": "requires_review",
                "unavailable_reason": "requires_credentials",
            },
            "pedestrian_network": {
                "status": "unavailable",
                "unavailable_reason": "outside_coverage",
            },
            "xroad_traffic": {
                "status": "unknown",
                "constant_traffic_points_within_context": 0,
                "cctv_points_within_context": 0,
                "stable_snapshot_ingested": False,
                "note": "one timestamp with no in-context points is not proof of no coverage",
            },
            "gtfs": {"status": "unavailable", "unavailable_reason": "not_published"},
        },
    }


def build(observed_at: str, raw_store: Path) -> dict[str, Any]:
    client = SafeHttpClient(
        allowed_hosts={"www.j-shis.bosai.go.jp", "www.npa.go.jp"}, timeout_seconds=120
    )
    store = ContentAddressedObjectStore(raw_store)
    jshis = JShisSurfaceGroundAdapter(
        client=client,
        object_store=store,
        first_mesh_by_municipality={
            config["city_code"]: config["jshis_first_mesh"]
            for config in CITY_CONFIGS.values()
        },
    )
    npa = NpaTrafficAccidentAdapter(client=client, object_store=store)
    transformer = Transformer.from_crs("EPSG:4612", "EPSG:4326", always_xy=True)

    contexts: dict[str, dict[str, dict[str, Any]]] = {}
    for city_key, config in CITY_CONFIGS.items():
        _, contexts[city_key] = _mesh_context(config)

    all_records: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    jshis_counts: dict[str, int] = {}
    jshis_parent_counts: dict[str, int] = {}
    jshis_jcodes: dict[str, Counter[int]] = {}
    for city_key, config in CITY_CONFIGS.items():
        request = DiscoveryRequest(config["city_code"], config["city_name"])
        resource = jshis.discover(request)[0]
        receipt = jshis.download(resource, max_bytes=4 * 1024 * 1024)
        inspection = jshis.inspect_schema(resource, receipt)
        context = contexts[city_key]
        selected: list[dict[str, Any]] = []
        for source_row_number, row in enumerate(
            jshis.normalize(resource, receipt, inspection), start=1
        ):
            if row["parent_500m_mesh_code"] in context:
                selected.append(
                    _jshis_canonical(
                        row=row,
                        config=config,
                        context=context,
                        resource_id=resource.external_resource_id,
                        raw_sha256=receipt.sha256,
                        source_row_number=source_row_number,
                        transformer=transformer,
                    )
                )
        jshis_counts[city_key] = len(selected)
        jshis_parent_counts[city_key] = len(
            {item["spatial_links"]["audited_500m_mesh"]["mesh_code"] for item in selected}
        )
        jshis_jcodes[city_key] = Counter(
            item["attributes"]["microtopography_code"] for item in selected
        )
        all_records.extend(selected)
        resources.append(
            _resource_report(
                provider="防災科学技術研究所 J-SHIS",
                resource=resource,
                receipt=receipt,
                inspection=inspection,
                observed_at=observed_at,
                canonical_by_city={city_key: len(selected)},
                adapter_version="jshis-surface-ground-v4@2020",
            )
        )

    npa_resource = npa.discover(DiscoveryRequest("26202", "舞鶴市"))[0]
    npa_receipt = npa.download(npa_resource, max_bytes=80 * 1024 * 1024)
    npa_inspection = npa.inspect_schema(npa_resource, npa_receipt)
    supporting_resources = []
    for kind, url in (
        ("schema_workbook", npa_resource.source_metadata["schema_url"]),
        ("codebook_workbook", npa_resource.source_metadata["codebook_url"]),
    ):
        receipt = store.fetch(client, url, max_bytes=4 * 1024 * 1024)
        supporting_resources.append(
            {
                "kind": kind,
                "resource_url": url,
                "raw_sha256": receipt.sha256,
                "raw_size_bytes": receipt.size_bytes,
                "raw_object_key": receipt.object_key,
                "raw_publication": False,
                "retrieved_at": observed_at,
            }
        )

    npa_records: dict[str, list[dict[str, Any]]] = {key: [] for key in CITY_CONFIGS}
    for row in npa.normalize(npa_resource, npa_receipt, npa_inspection):
        for city_key, config in CITY_CONFIGS.items():
            if (
                row["prefecture_code_npa"] == config["npa_prefecture_code"]
                and row["municipality_code_npa"] == config["npa_municipality_code"]
            ):
                npa_records[city_key].append(
                    _npa_canonical(
                        row=row,
                        config=config,
                        context=contexts[city_key],
                        resource_id=npa_resource.external_resource_id,
                        raw_sha256=npa_receipt.sha256,
                    )
                )
    for records in npa_records.values():
        all_records.extend(records)
    resources.append(
        _resource_report(
            provider="警察庁",
            resource=npa_resource,
            receipt=npa_receipt,
            inspection=npa_inspection,
            observed_at=observed_at,
            canonical_by_city={key: len(value) for key, value in npa_records.items()},
            adapter_version="npa-traffic-accident@2024",
        )
    )

    coverage = _coverage_by_city()
    city_summaries: dict[str, Any] = {}
    for city_key, config in CITY_CONFIGS.items():
        context_count = len(contexts[city_key])
        accidents = npa_records[city_key]
        linked_accidents = sum(
            item["spatial_links"]["audited_500m_mesh"]["method"]
            == "point_in_audited_mesh"
            for item in accidents
        )
        occurrence_years = Counter(
            int(item["attributes"]["occurred_at"][:4]) for item in accidents
        )
        city_summaries[city_key] = {
            "city_code": config["city_code"],
            "city_name": config["city_name"],
            "audited_500m_mesh_count": context_count,
            "jshis_surface_ground": {
                "published_250m_cell_count": jshis_counts[city_key],
                "linked_parent_500m_mesh_count": jshis_parent_counts[city_key],
                "audited_parent_meshes_without_published_cell_count": (
                    context_count - jshis_parent_counts[city_key]
                ),
                "microtopography_counts": {
                    str(key): value for key, value in sorted(jshis_jcodes[city_key].items())
                },
                "scope": "published 250m cells inside audited 500m mesh context",
            },
            "historical_traffic_accidents": {
                "record_count": len(accidents),
                "occurrence_year_counts": {
                    str(key): value for key, value in sorted(occurrence_years.items())
                },
                "linked_to_audited_mesh_count": linked_accidents,
                "outside_audited_mesh_context_count": len(accidents) - linked_accidents,
                "fatalities_sum": sum(item["attributes"]["fatalities"] for item in accidents),
                "injuries_sum": sum(item["attributes"]["injuries"] for item in accidents),
                "claim_boundary": "historical context only; no prediction or risk probability",
            },
            "researched_capabilities": coverage[city_key],
        }

    all_records.sort(
        key=lambda item: (item["city_code"], item["record_type"], item["canonical_id"])
    )
    CANONICAL.parent.mkdir(parents=True, exist_ok=True)
    CANONICAL.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in all_records
        ),
        encoding="utf-8",
    )
    source_report = {
        "schema_version": "citygap-geospatial-resilience-source-report@1",
        "observed_at": observed_at,
        "resources": sorted(resources, key=lambda item: item["external_resource_id"]),
        "supporting_resources": supporting_resources,
        "reference_coverage": REFERENCE_COVERAGE,
        "coverage_by_city": coverage,
        "license_and_publication": {
            "jshis": {
                "license_id": "jshis-terms-2025-03",
                "raw_redistribution": False,
                "derivative_use": True,
                "attribution_required": True,
                "unknown_terms": True,
            },
            "npa": {
                "license_id": "pdl-1.0",
                "raw_redistribution_under_source_terms": True,
                "project_raw_publication": False,
                "attribution_required": True,
                "edited_or_processed_notice_required": True,
            },
            "gsi": {
                "license_id": "gsi-survey-act-review",
                "raw_redistribution": None,
                "unknown_terms": True,
            },
            "xroad": {
                "license_id": "xroad-api-terms-2025-05",
                "raw_redistribution": None,
                "attribution_required": True,
                "unknown_terms": True,
            },
        },
        "promotion_status": "analysis_ready_for_jshis_and_npa_only",
        "claim_boundary": (
            "J-SHIS is modeled ground context and NPA records are historical injury/fatal "
            "accidents. GSI, pedestrian, xROAD and GTFS research statuses do not create data "
            "rows. No current availability, capacity, congestion, risk, causal effect or "
            "prediction is asserted."
        ),
    }
    _write_json(SOURCE_REPORT, source_report)
    summary = {
        "schema_version": "citygap-geospatial-resilience-summary@1",
        "observed_at": observed_at,
        "source_report": SOURCE_REPORT.relative_to(ROOT).as_posix(),
        "source_report_sha256": _sha256(SOURCE_REPORT),
        "canonical_artifact": CANONICAL.relative_to(ROOT).as_posix(),
        "canonical_artifact_sha256": _sha256(CANONICAL),
        "canonical_record_count": len(all_records),
        "raw_primary_resource_count": len(resources),
        "raw_supporting_resource_count": len(supporting_resources),
        "raw_unique_sha256_count": len(
            {item["raw_sha256"] for item in resources}
            | {item["raw_sha256"] for item in supporting_resources}
        ),
        "cities": city_summaries,
        "prediction_generated": False,
        "risk_probability_generated": False,
        "unavailable_sources_fabricated_as_rows": False,
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
