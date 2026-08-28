"""Download, inspect and canonicalize selected real Maizuru official open data."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import geopandas as gpd

from analysis.src.plateau_buildings import read_buildings
from backend.citygap_platform.domain.open_data import DiscoveryRequest
from backend.citygap_platform.open_data.ckan import CkanCatalogAdapter
from backend.citygap_platform.open_data.http import SafeHttpClient
from backend.citygap_platform.open_data.spatial_link import link_canonical_points
from backend.citygap_platform.open_data.standard_ods import canonicalize_rows, schema_audit
from backend.citygap_platform.open_data.storage import ContentAddressedObjectStore

ROOT = Path(__file__).resolve().parents[2]
RAW_STORE = ROOT / "data/raw/open_data"
OUTPUT_DIR = ROOT / "analysis/outputs/real/open_data"
SOURCE_REPORT = OUTPUT_DIR / "maizuru_p0_source_report.json"
CANONICAL_JSONL = OUTPUT_DIR / "maizuru_p0_canonical.jsonl"
CANONICAL_SUMMARY = OUTPUT_DIR / "maizuru_p0_canonical_summary.json"
MESHES = ROOT / "analysis/outputs/real/maizuru_city_gap.geojson"
PLATEAU_ARCHIVE = ROOT / "data/raw/plateau_citygml/26202_maizuru-shi_city_2025_citygml_1_op.zip"
PLATEAU_INVENTORY = ROOT / "analysis/outputs/real/maizuru_plateau_inventory.json"

SELECTED_DATASETS = (
    "262021_aed",
    "262021_care_service",
    "262021_educational_institution",
    "262021_evacuation_space",
    "262021_hospital",
    "262021_jidoseitosu",
    "262021_population",
    "262021_preschool",
    "262021_public_facility",
)


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


def _validate_observed_at(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("observed-at must include a timezone")
    return parsed.isoformat().replace("+00:00", "Z")


def build(observed_at: str, raw_store: Path) -> dict[str, Any]:
    client = SafeHttpClient(allowed_hosts={"data.bodik.jp"})
    adapter = CkanCatalogAdapter(
        api_url="https://data.bodik.jp/api/3/action/package_search",
        organization_id="262021",
        municipality_code="26202",
        client=client,
        object_store=ContentAddressedObjectStore(raw_store),
    )
    discovered = adapter.discover(DiscoveryRequest("26202", "舞鶴市"))
    selected = {
        item.external_dataset_id: item
        for item in discovered
        if item.external_dataset_id in SELECTED_DATASETS and item.format == "CSV"
    }
    missing = set(SELECTED_DATASETS) - set(selected)
    if missing:
        raise ValueError(f"Selected official resources are missing: {sorted(missing)}")

    source_datasets = []
    all_records: list[dict[str, Any]] = []
    for dataset_id in SELECTED_DATASETS:
        resource = selected[dataset_id]
        if resource.license_id != "cc-by-4.0":
            raise ValueError(f"Selected resource license is not approved: {dataset_id}")
        receipt = adapter.download(resource, max_bytes=16 * 1024 * 1024)
        inspection = adapter.inspect_schema(resource, receipt)
        audit = schema_audit(dataset_id, inspection.field_names)
        if audit["status"] != "passed":
            raise ValueError(f"Selected resource schema failed: {dataset_id}")
        records, canonical_quality = canonicalize_rows(
            dataset_id=dataset_id,
            resource_id=resource.external_resource_id,
            source_sha256=receipt.sha256,
            normalized_rows=adapter.normalize(resource, receipt, inspection),
        )
        all_records.extend(records)
        source_datasets.append(
            {
                "external_dataset_id": dataset_id,
                "external_resource_id": resource.external_resource_id,
                "title": resource.title,
                "resource_url": resource.resource_url,
                "license_id": resource.license_id,
                "source_license_id": resource.source_metadata.get("source_license_id"),
                "metadata_modified": resource.source_metadata.get("metadata_modified"),
                "resource_last_modified": resource.source_metadata.get("resource_last_modified"),
                "raw_sha256": receipt.sha256,
                "raw_size_bytes": receipt.size_bytes,
                "raw_object_key": receipt.object_key,
                "raw_reuse_scope": "public_verified",
                "encoding": inspection.encoding,
                "row_count": inspection.row_count,
                "field_names": inspection.field_names,
                "schema_audit": audit,
                "canonical_quality": canonical_quality,
                "analysis_readiness": "requires_review",
                "analysis_readiness_reasons": [
                    "source_horizontal_datum_not_declared",
                    "dataset_reference_date_requires_row_or_metadata_review",
                    "facility_to_plateau_building_identity_not_verified",
                ],
            }
        )

    plateau_inventory = json.loads(PLATEAU_INVENTORY.read_text(encoding="utf-8"))
    expected_plateau_sha256 = plateau_inventory["archive"]["sha256"]
    if _sha256(PLATEAU_ARCHIVE) != expected_plateau_sha256:
        raise ValueError("PLATEAU archive checksum differs from audited inventory")
    buildings = read_buildings(PLATEAU_ARCHIVE)
    expected_buildings = plateau_inventory["themes"]["bldg"]["feature_count"]
    if len(buildings) != expected_buildings or buildings["gml_id"].duplicated().any():
        raise ValueError("PLATEAU building inventory count or identity is invalid")
    meshes = gpd.read_file(MESHES)
    linked_records, spatial_counts = link_canonical_points(
        all_records,
        city_code="26202",
        meshes=meshes,
        buildings=buildings,
        analysis_crs="EPSG:6674",
    )
    linked_records.sort(key=lambda item: item["canonical_id"])

    source_report = {
        "schema_version": "citygap-open-data-source-report@1",
        "city_code": "26202",
        "city_name": "舞鶴市",
        "observed_at": observed_at,
        "official_catalog_url": "https://data.bodik.jp/organization/262021",
        "official_catalog_api": "https://data.bodik.jp/api/3/action/package_search",
        "adapter_id": "ckan-v3@1",
        "canonical_adapter_id": "municipal-standard-ods@2026-08",
        "selected_dataset_count": len(source_datasets),
        "datasets": source_datasets,
        "license_attribution": {
            "provider": "舞鶴市 / BODIK",
            "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
        },
        "promotion_status": "requires_review",
        "claim_boundary": (
            "Raw bytes, schema and canonical rows were verified. This report does not promote "
            "the datasets for policy analysis or assert facility-to-building identity."
        ),
    }
    _write_json(SOURCE_REPORT, source_report)

    CANONICAL_JSONL.parent.mkdir(parents=True, exist_ok=True)
    CANONICAL_JSONL.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for record in linked_records
        ),
        encoding="utf-8",
    )
    record_types = Counter(item["record_type"] for item in linked_records)
    entity_kinds = Counter(item["attributes"]["entity_kind"] for item in linked_records)
    summary = {
        "schema_version": "citygap-canonical-open-data-summary@1",
        "city_code": "26202",
        "observed_at": observed_at,
        "source_report": SOURCE_REPORT.relative_to(ROOT).as_posix(),
        "source_report_sha256": _sha256(SOURCE_REPORT),
        "canonical_artifact": CANONICAL_JSONL.relative_to(ROOT).as_posix(),
        "canonical_artifact_sha256": _sha256(CANONICAL_JSONL),
        "canonical_version": "citygap-canonical-open-data@1",
        "canonical_record_count": len(linked_records),
        "record_type_counts": dict(sorted(record_types.items())),
        "entity_kind_counts": dict(sorted(entity_kinds.items())),
        "geometry_record_count": sum(item["geometry"] is not None for item in linked_records),
        "spatial_link_counts": spatial_counts,
        "plateau": {
            "archive_sha256": expected_plateau_sha256,
            "building_count": len(buildings),
            "product_specification_version": plateau_inventory["dataset"][
                "product_specification_version"
            ],
        },
        "privacy": (
            "Canonical attributes exclude phone, email, contact form, image and free-form notes. "
            "No building-level population estimate is included."
        ),
        "analysis_readiness": "requires_review",
        "unavailable_reason": "not_verified",
    }
    _write_json(CANONICAL_SUMMARY, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--raw-store", type=Path, default=RAW_STORE)
    args = parser.parse_args()
    summary = build(_validate_observed_at(args.observed_at), args.raw_store)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
