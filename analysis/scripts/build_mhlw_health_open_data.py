"""Build real MHLW medical/care canonical data for Maizuru and Fujisawa."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import resource as process_resource
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import geopandas as gpd

from analysis.src.plateau_buildings import read_buildings
from backend.citygap_platform.domain.open_data import (
    DiscoveredResource,
    DiscoveryRequest,
    RawResourceReceipt,
    SchemaInspection,
)
from backend.citygap_platform.open_data.health import (
    canonicalize_care_rows,
    canonicalize_medical_facilities,
    canonicalize_medical_services,
    care_schema_audit,
    compare_facility_identities,
    medical_schema_audit,
)
from backend.citygap_platform.open_data.http import SafeHttpClient
from backend.citygap_platform.open_data.mhlw import MhlwCareAdapter, MhlwMedicalAdapter
from backend.citygap_platform.open_data.spatial_link import link_canonical_points
from backend.citygap_platform.open_data.storage import ContentAddressedObjectStore

ROOT = Path(__file__).resolve().parents[2]
RAW_STORE = ROOT / "data/raw/open_data"
OUTPUT_DIR = ROOT / "analysis/outputs/real/open_data"
SOURCE_REPORT = OUTPUT_DIR / "mhlw_health_source_report.json"
CANONICAL = OUTPUT_DIR / "mhlw_health_canonical.jsonl"
IDENTITY = OUTPUT_DIR / "mhlw_medical_identity_comparison.json"
SUMMARY = OUTPUT_DIR / "mhlw_health_summary.json"
MUNICIPAL_CANONICAL = OUTPUT_DIR / "maizuru_p0_canonical.jsonl"

CITY_CONFIGS = {
    "maizuru": {
        "city_code": "26202",
        "city_name": "舞鶴市",
        "analysis_crs": "EPSG:6674",
        "plateau_archive": ROOT
        / "data/raw/plateau_citygml/26202_maizuru-shi_city_2025_citygml_1_op.zip",
        "plateau_inventory": ROOT / "analysis/outputs/real/maizuru_plateau_inventory.json",
        "meshes": ROOT / "analysis/outputs/real/maizuru_city_gap.geojson",
        "p04": ROOT / "data/raw/medical/P04-20_26_GML/P04-20_26_GML/P04-20_26.geojson",
        "p04_city_name": "舞鶴市",
    },
    "fujisawa": {
        "city_code": "14205",
        "city_name": "藤沢市",
        "analysis_crs": "EPSG:6677",
        "plateau_archive": ROOT
        / "data/raw/plateau_citygml/14205_fujisawa-shi_city_2025_citygml_1_op.zip",
        "plateau_inventory": ROOT / "analysis/outputs/real/fujisawa_plateau_inventory.json",
        "meshes": ROOT / "analysis/outputs/real/fujisawa_city_gap.geojson",
        "p04": ROOT / "data/raw/medical/P04-20_14_GML/P04-20_14_GML/P04-20_14.geojson",
        "p04_city_name": "藤沢市",
    },
}


@dataclass(frozen=True, slots=True)
class MaterializedResource:
    resource: DiscoveredResource
    receipt: RawResourceReceipt
    inspection: SchemaInspection
    schema_audit: dict[str, Any]


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


def _one_value(values: set[str], label: str) -> str:
    if len(values) != 1:
        raise ValueError(f"Expected one {label}, found: {sorted(values)}")
    return next(iter(values))


def _stamp_date(value: str) -> str:
    return date(int(value[:4]), int(value[4:6]), int(value[6:8])).isoformat()


def _materialize(
    adapter: MhlwMedicalAdapter | MhlwCareAdapter,
    request: DiscoveryRequest,
    *,
    max_bytes: int,
) -> list[MaterializedResource]:
    result = []
    for discovered in adapter.discover(request):
        receipt = adapter.download(discovered, max_bytes=max_bytes)
        inspection = adapter.inspect_schema(discovered, receipt)
        if adapter.family == "medical":
            audit = medical_schema_audit(
                str(discovered.source_metadata["medical_resource_code"]),
                inspection.field_names,
            )
        else:
            audit = care_schema_audit(inspection.field_names)
        if audit["status"] != "passed":
            raise ValueError(
                f"Official MHLW schema requires review: {discovered.external_resource_id}"
            )
        result.append(MaterializedResource(discovered, receipt, inspection, audit))
    return result


def _medical_records(
    adapter: MhlwMedicalAdapter,
    resources: list[MaterializedResource],
    city_code: str,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    records = []
    resource_counts: dict[str, int] = {}
    rejected_counts: dict[str, int] = {}
    facilities_by_category: dict[str, dict[str, dict[str, Any]]] = {}
    for item in resources:
        code = str(item.resource.source_metadata["medical_resource_code"])
        if code.endswith("-2"):
            continue
        facility_rows, quality = canonicalize_medical_facilities(
            resource_code=code,
            resource_id=item.resource.external_resource_id,
            raw_sha256=item.receipt.sha256,
            reference_date=str(item.resource.reference_date),
            city_code=city_code,
            normalized_rows=adapter.normalize(item.resource, item.receipt, item.inspection),
        )
        category = code.split("-", maxsplit=1)[0]
        facilities_by_category[category] = {row["external_record_id"]: row for row in facility_rows}
        records.extend(facility_rows)
        resource_counts[item.resource.external_resource_id] = len(facility_rows)
        rejected_counts[item.resource.external_resource_id] = len(quality["rejected_rows"])
    for item in resources:
        code = str(item.resource.source_metadata["medical_resource_code"])
        if not code.endswith("-2"):
            continue
        category = code.split("-", maxsplit=1)[0]
        service_rows, quality = canonicalize_medical_services(
            resource_code=code,
            resource_id=item.resource.external_resource_id,
            raw_sha256=item.receipt.sha256,
            reference_date=str(item.resource.reference_date),
            facility_ids=facilities_by_category.get(category, {}),
            normalized_rows=adapter.normalize(item.resource, item.receipt, item.inspection),
        )
        records.extend(service_rows)
        resource_counts[item.resource.external_resource_id] = len(service_rows)
        rejected_counts[item.resource.external_resource_id] = len(quality["rejected_rows"])
    return records, resource_counts, rejected_counts


def _care_records(
    adapter: MhlwCareAdapter,
    resources: list[MaterializedResource],
    city_code: str,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    records = []
    resource_counts: dict[str, int] = {}
    rejected_counts: dict[str, int] = {}
    for item in resources:
        service_code = str(item.resource.source_metadata["official_service_code"])
        service_rows, quality = canonicalize_care_rows(
            service_code=service_code,
            resource_id=item.resource.external_resource_id,
            raw_sha256=item.receipt.sha256,
            reference_date=str(item.resource.reference_date),
            city_code=city_code,
            normalized_rows=adapter.normalize(item.resource, item.receipt, item.inspection),
        )
        records.extend(service_rows)
        resource_counts[item.resource.external_resource_id] = len(service_rows)
        rejected_counts[item.resource.external_resource_id] = len(quality["rejected_rows"])
    return records, resource_counts, rejected_counts


def _p04_references(config: dict[str, Any]) -> list[dict[str, Any]]:
    frame = gpd.read_file(config["p04"], engine="pyogrio").to_crs("EPSG:4326")
    selected = frame.loc[
        frame["P04_003"].fillna("").astype(str).str.contains(config["p04_city_name"], regex=False)
    ]
    return [
        {
            "source": "MLIT P04 medical facilities 2020",
            "reference_id": f"P04:{config['city_code']}:{index}",
            "official_ids": (),
            "name": str(row.P04_002 or ""),
            "address": str(row.P04_003 or ""),
            "geometry": row.geometry.__geo_interface__ if row.geometry is not None else None,
        }
        for index, row in selected.iterrows()
    ]


def _municipal_medical_references(city_code: str) -> list[dict[str, Any]]:
    if city_code != "26202":
        return []
    result = []
    with MUNICIPAL_CANONICAL.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("attributes", {}).get("entity_kind") != "medical_institution":
                continue
            attributes = row["attributes"]
            result.append(
                {
                    "source": "Maizuru Municipal Standard ODS medical",
                    "reference_id": row["canonical_id"],
                    "official_ids": tuple(
                        value
                        for value in (
                            row.get("external_record_id"),
                            attributes.get("medical_code"),
                        )
                        if value
                    ),
                    "name": row.get("display_name"),
                    "address": attributes.get("address"),
                    "geometry": row.get("geometry"),
                }
            )
    return result


def _link_to_plateau(
    records: list[dict[str, Any]], config: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, Any]]:
    inventory = json.loads(Path(config["plateau_inventory"]).read_text(encoding="utf-8"))
    archive = Path(config["plateau_archive"])
    if _sha256(archive) != inventory["archive"]["sha256"]:
        raise ValueError(f"PLATEAU archive checksum changed for {config['city_code']}")
    buildings = read_buildings(archive)
    expected = inventory["themes"]["bldg"]["feature_count"]
    if len(buildings) != expected or buildings["gml_id"].duplicated().any():
        raise ValueError(f"PLATEAU building inventory changed for {config['city_code']}")
    meshes = gpd.read_file(config["meshes"], engine="pyogrio")
    linked, counts = link_canonical_points(
        records,
        city_code=config["city_code"],
        meshes=meshes,
        buildings=buildings,
        analysis_crs=config["analysis_crs"],
        city_link_explanation=(
            "The national official row carries the municipality code used for this exact city filter."
        ),
    )
    plateau = {
        "archive_sha256": inventory["archive"]["sha256"],
        "building_count": len(buildings),
        "product_specification_version": inventory["dataset"]["product_specification_version"],
    }
    del buildings, meshes
    gc.collect()
    return linked, counts, plateau


def _resource_report(
    item: MaterializedResource,
    city_counts: dict[str, dict[str, int]],
    *,
    observed_at: str,
) -> dict[str, Any]:
    resource = item.resource
    family = "medical" if resource.external_dataset_id.startswith("mhlw-medical-") else "care"
    published_at = (
        _stamp_date(str(resource.source_metadata["version_stamp"])) if family == "care" else None
    )
    return {
        "provider": (
            "厚生労働省 医療情報ネット"
            if family == "medical"
            else "厚生労働省 介護サービス情報公表システム"
        ),
        "source_title": resource.title,
        "source_url": resource.resource_url,
        "external_dataset_id": resource.external_dataset_id,
        "external_resource_id": resource.external_resource_id,
        "title": resource.title,
        "resource_url": resource.resource_url,
        "format": resource.format,
        "license_id": resource.license_id,
        "retrieved_at": observed_at,
        "published_at": published_at,
        "reference_date": resource.reference_date,
        "update_frequency": "not_declared",
        "version_signals": resource.version_signals,
        "source_metadata": resource.source_metadata,
        "raw_sha256": item.receipt.sha256,
        "raw_size_bytes": item.receipt.size_bytes,
        "content_length": item.receipt.size_bytes,
        "raw_object_key": item.receipt.object_key,
        "raw_reuse_scope": "public_verified",
        "encoding": item.inspection.encoding,
        "national_row_count": item.inspection.row_count,
        "field_names": item.inspection.field_names,
        "schema_version": item.inspection.schema_version,
        "adapter_version": f"mhlw-{family}@2026-06",
        "source_crs": item.inspection.source_crs,
        "schema_audit": item.schema_audit,
        "quality_results": item.inspection.quality_results,
        "city_canonical_record_counts": {
            city: counts.get(resource.external_resource_id, 0)
            for city, counts in city_counts.items()
        },
        "analysis_readiness": "requires_review",
        "analysis_readiness_reasons": [
            "source_horizontal_datum_not_declared",
            "facility_identity_candidates_require_review",
            "published_schedule_or_capacity_is_not_current_availability",
        ],
    }


def build(observed_at: str, raw_store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    client = SafeHttpClient(allowed_hosts={"www.mhlw.go.jp"}, timeout_seconds=120)
    store = ContentAddressedObjectStore(raw_store)
    medical_adapter = MhlwMedicalAdapter(client=client, object_store=store)
    care_adapter = MhlwCareAdapter(client=client, object_store=store)
    discovery_request = DiscoveryRequest("26202", "舞鶴市")
    materialize_started = time.perf_counter()
    medical_resources = _materialize(medical_adapter, discovery_request, max_bytes=32 * 1024 * 1024)
    care_resources = _materialize(care_adapter, discovery_request, max_bytes=64 * 1024 * 1024)
    materialize_seconds = time.perf_counter() - materialize_started
    medical_reference_date = _one_value(
        {str(item.resource.reference_date) for item in medical_resources},
        "MHLW medical reference date",
    )
    care_reference_date = _one_value(
        {str(item.resource.reference_date) for item in care_resources},
        "MHLW care reference date",
    )
    care_output_date = _one_value(
        {
            _stamp_date(str(item.resource.source_metadata["version_stamp"]))
            for item in care_resources
        },
        "MHLW care output date",
    )

    all_records = []
    city_summaries = {}
    identity_rows = {}
    medical_city_counts: dict[str, dict[str, int]] = {}
    care_city_counts: dict[str, dict[str, int]] = {}
    rejected_by_city = {}
    for city_key, config in CITY_CONFIGS.items():
        city_started = time.perf_counter()
        medical, medical_counts, medical_rejected = _medical_records(
            medical_adapter, medical_resources, config["city_code"]
        )
        care, care_counts, care_rejected = _care_records(
            care_adapter, care_resources, config["city_code"]
        )
        medical_city_counts[city_key] = medical_counts
        care_city_counts[city_key] = care_counts
        rejected_by_city[city_key] = {
            "medical": medical_rejected,
            "care": care_rejected,
        }
        linked, spatial_counts, plateau = _link_to_plateau(medical + care, config)
        linked.sort(key=lambda item: item["canonical_id"])
        for row in linked:
            row["city_code"] = config["city_code"]
            row["city_name"] = config["city_name"]
        medical_facilities = [
            row
            for row in linked
            if row["record_type"] == "facility"
            and row["attributes"]["entity_kind"] == "medical_facility"
        ]
        references = _p04_references(config) + _municipal_medical_references(config["city_code"])
        comparison = compare_facility_identities(medical_facilities, references)
        identity_rows[city_key] = comparison
        identity_counts = Counter(row["status"] for row in comparison)
        type_counts = Counter(row["record_type"] for row in linked)
        kind_counts = Counter(row["attributes"]["entity_kind"] for row in linked)
        city_summaries[city_key] = {
            "city_code": config["city_code"],
            "city_name": config["city_name"],
            "canonical_record_count": len(linked),
            "record_type_counts": dict(sorted(type_counts.items())),
            "entity_kind_counts": dict(sorted(kind_counts.items())),
            "medical_identity_counts": dict(sorted(identity_counts.items())),
            "medical_reference_record_count": len(references),
            "spatial_link_counts": spatial_counts,
            "plateau": plateau,
            "temporal_alignment": {
                "status": "mixed",
                "plateau_reference_year": 2025,
                "medical_reference_date": medical_reference_date,
                "care_reference_date": care_reference_date,
                "hidden_as_single_year": False,
            },
            "runtime_seconds": round(time.perf_counter() - city_started, 6),
        }
        all_records.extend(linked)
    all_records.sort(key=lambda item: (item["city_code"], item["canonical_id"]))

    source_report = {
        "schema_version": "citygap-mhlw-health-source-report@1",
        "observed_at": observed_at,
        "providers": {
            "medical": {
                "provider": "厚生労働省 医療情報ネット",
                "manifest_url": medical_adapter.manifest_url,
                "reference_date": medical_reference_date,
                "license_id": "pdl-1.0",
                "resource_count": len(medical_resources),
            },
            "care": {
                "provider": "厚生労働省 介護サービス情報公表システム",
                "manifest_url": care_adapter.manifest_url,
                "reference_date": care_reference_date,
                "output_date": care_output_date,
                "license_id": "cc-by-4.0",
                "resource_count": len(care_resources),
            },
        },
        "resources": {
            "medical": [
                _resource_report(item, medical_city_counts, observed_at=observed_at)
                for item in medical_resources
            ],
            "care": [
                _resource_report(item, care_city_counts, observed_at=observed_at)
                for item in care_resources
            ],
        },
        "rejected_rows": rejected_by_city,
        "promotion_status": "requires_review",
        "claim_boundary": (
            "Published facilities, departments, schedules and capacity fields are snapshot "
            "information. They do not establish current acceptance, vacancy, eligibility, "
            "emergency intake or real-time availability."
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
    identity_report = {
        "schema_version": "citygap-medical-identity-comparison@1",
        "observed_at": observed_at,
        "comparison_sources": [
            f"MHLW medical {medical_reference_date}",
            "MLIT P04 medical facilities 2020",
            "Maizuru Municipal Standard ODS where available",
        ],
        "cities": identity_rows,
        "status_semantics": {
            "matched": "one unique shared official identifier",
            "probable": "one normalized name/address or name/coordinate candidate",
            "ambiguous": "multiple candidates or conflicting identity evidence",
            "unmatched": "no candidate under the declared rules",
        },
        "automatic_merge": False,
    }
    _write_json(IDENTITY, identity_report)
    summary = {
        "schema_version": "citygap-mhlw-health-summary@1",
        "observed_at": observed_at,
        "source_report": SOURCE_REPORT.relative_to(ROOT).as_posix(),
        "source_report_sha256": _sha256(SOURCE_REPORT),
        "canonical_artifact": CANONICAL.relative_to(ROOT).as_posix(),
        "canonical_artifact_sha256": _sha256(CANONICAL),
        "identity_report": IDENTITY.relative_to(ROOT).as_posix(),
        "identity_report_sha256": _sha256(IDENTITY),
        "canonical_version": "citygap-canonical-health@1",
        "canonical_record_count": len(all_records),
        "raw_resource_count": len(medical_resources) + len(care_resources),
        "raw_unique_sha256_count": len(
            {item.receipt.sha256 for item in medical_resources + care_resources}
        ),
        "cities": city_summaries,
        "performance": {
            "materialize_and_schema_seconds": round(materialize_seconds, 6),
            "total_seconds": round(time.perf_counter() - started, 6),
            "peak_rss_mib": round(
                process_resource.getrusage(process_resource.RUSAGE_SELF).ru_maxrss / 1024,
                3,
            ),
        },
        "privacy": (
            "Canonical records exclude telephone, fax, free-form notes, contact URLs and "
            "corporate contact details. Raw official bytes remain outside public assets."
        ),
        "analysis_readiness": "requires_review",
        "unavailable_reason": "not_verified",
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
