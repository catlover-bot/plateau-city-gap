"""Build a deterministic inventory from current official municipal catalog metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.citygap_platform.domain.open_data import DiscoveryRequest
from backend.citygap_platform.open_data.ckan import CkanCatalogAdapter
from backend.citygap_platform.open_data.http import SafeHttpClient
from backend.citygap_platform.open_data.static_catalog import StaticSectionCatalogAdapter
from backend.citygap_platform.open_data.storage import ContentAddressedObjectStore

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "analysis/outputs/real/open_data/municipal_catalog_inventory.json"

MAIZURU_CATALOG = "https://data.bodik.jp/organization/262021"
MAIZURU_API = "https://data.bodik.jp/api/3/action/package_search"
FUJISAWA_CATALOG = (
    "https://www.city.fujisawa.kanagawa.jp/kyoso/shise/kekaku/kakushu/datalibrary.html"
)
FUJISAWA_TERMS = "https://www.city.fujisawa.kanagawa.jp/documents/13230/riyoukiyaku20250401.pdf"

FAMILY_RULES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("hospital", "医療機関"), "medical", "P0"),
    (("care_service", "介護保険", "介護サービス"), "care", "P0"),
    (("population", "opendatamap", "人口と世帯"), "population", "P0"),
    (("aed", "AED"), "aed", "P0"),
    (("educational", "jidoseitosu", "gakkokoku", "中学校給食"), "education", "P0"),
    (("preschool", "byojihoiku", "ichijiazukari", "mushokataisho"), "childcare", "P0"),
    (("evacuation", "防災施設"), "shelter", "P0"),
    (("public_facility", "shiteikanri"), "facilities", "P0"),
    (("fire_hydrant", "emergency_radio"), "hazard_support", "P1"),
    (("bicycle_parking", "car_park"), "transport_facility", "P1"),
    (("toshikoen", "tourism", "wirelesslan", "pollingstation"), "facilities", "P1"),
    (("食品衛生", "理容所", "美容所", "クリーニング所"), "economic_activity", "P1"),
    (("文化財", "cultural_property"), "cultural_asset", "P1"),
    (("地理空間情報",), "reference", "P1"),
)


def _family(identifier: str, title: str) -> tuple[str, str]:
    haystack = f"{identifier} {title}".lower()
    for terms, family, priority in FAMILY_RULES:
        if any(term.lower() in haystack for term in terms):
            return family, priority
    return "municipal_other", "P2"


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _resource_payload(resource: Any) -> dict[str, Any]:
    payload = asdict(resource)
    payload["source_metadata"] = {
        key: value for key, value in payload["source_metadata"].items() if value is not None
    }
    return payload


def _maizuru_inventory(store: ContentAddressedObjectStore) -> dict[str, Any]:
    adapter = CkanCatalogAdapter(
        api_url=MAIZURU_API,
        organization_id="262021",
        municipality_code="26202",
        client=SafeHttpClient(allowed_hosts={"data.bodik.jp"}),
        object_store=store,
    )
    resources = adapter.discover(DiscoveryRequest("26202", "舞鶴市"))
    grouped: dict[str, list[Any]] = defaultdict(list)
    for resource in resources:
        grouped[resource.external_dataset_id].append(resource)
    datasets = []
    for dataset_id, items in sorted(grouped.items()):
        first = items[0]
        title = str(first.source_metadata.get("package_title") or first.title)
        family, priority = _family(dataset_id, title)
        datasets.append(
            {
                "external_dataset_id": dataset_id,
                "title": title,
                "dataset_family": family,
                "priority": priority,
                "availability": "available",
                "analysis_readiness": "requires_review",
                "analysis_readiness_reason": "not_verified",
                "license_id": first.license_id,
                "metadata_modified": first.source_metadata.get("metadata_modified"),
                "resources": [_resource_payload(item) for item in items],
            }
        )
    normalized_metadata = [
        {
            "dataset": item["external_dataset_id"],
            "modified": item["metadata_modified"],
            "resources": [
                {
                    "id": resource["external_resource_id"],
                    "url": resource["resource_url"],
                    "format": resource["format"],
                    "version_signals": resource["version_signals"],
                }
                for resource in item["resources"]
            ],
        }
        for item in datasets
    ]
    return {
        "city_code": "26202",
        "city_name": "舞鶴市",
        "source_key": "bodik-maizuru",
        "catalog_url": MAIZURU_CATALOG,
        "catalog_api": MAIZURU_API,
        "adapter_id": adapter.definition.adapter_id,
        "catalog_license_id": "cc-by-4.0",
        "dataset_count": len(datasets),
        "resource_count": len(resources),
        "catalog_version": max(
            str(item["metadata_modified"]) for item in datasets if item["metadata_modified"]
        ),
        "normalized_catalog_sha256": _canonical_sha256(normalized_metadata),
        "datasets": datasets,
    }


def _fujisawa_inventory() -> dict[str, Any]:
    client = SafeHttpClient(
        allowed_hosts={
            "www.city.fujisawa.kanagawa.jp",
            "webgis.alandis.jp",
            "bosaiinfo.city.fujisawa.kanagawa.jp",
        }
    )
    adapter = StaticSectionCatalogAdapter(
        catalog_url=FUJISAWA_CATALOG,
        municipality_code="14205",
        section_heading="掲載データ一覧",
        stop_heading="関連リンク集",
        client=client,
    )
    resources = adapter.discover(DiscoveryRequest("14205", "藤沢市"))
    datasets = []
    for resource in resources:
        family, priority = _family(resource.external_dataset_id, resource.title)
        datasets.append(
            {
                "external_dataset_id": resource.external_dataset_id,
                "title": resource.title,
                "dataset_family": family,
                "priority": priority,
                "availability": "requires_review",
                "unavailable_reason": "not_verified",
                "analysis_readiness": "requires_review",
                "analysis_readiness_reason": "not_verified",
                "license_id": "unknown",
                "resources": [_resource_payload(resource)],
            }
        )
    catalog_hashes = {item.version_signals[0] for item in resources}
    if len(catalog_hashes) != 1:
        raise ValueError("Fujisawa resources do not share one official catalog checksum")
    return {
        "city_code": "14205",
        "city_name": "藤沢市",
        "source_key": "fujisawa-open-data-library",
        "catalog_url": FUJISAWA_CATALOG,
        "catalog_terms_url": FUJISAWA_TERMS,
        "adapter_id": adapter.definition.adapter_id,
        "catalog_license_id": "cc-by-4.0",
        "linked_resource_license_id": "unknown",
        "dataset_count": len(datasets),
        "resource_count": len(resources),
        "catalog_sha256": next(iter(catalog_hashes)),
        "datasets": datasets,
    }


def build_inventory(observed_at: str) -> dict[str, Any]:
    parsed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("observed-at must include a timezone")
    with tempfile.TemporaryDirectory(prefix="citygap-open-data-inventory-") as directory:
        cities = [_maizuru_inventory(ContentAddressedObjectStore(directory)), _fujisawa_inventory()]
    coverage_families = sorted(
        {dataset["dataset_family"] for city in cities for dataset in city["datasets"]}
    )
    coverage = []
    for city in cities:
        available = {dataset["dataset_family"] for dataset in city["datasets"]}
        for family in coverage_families:
            if family in available:
                status = "requires_review"
                reason = "not_verified"
                explanation = "Official catalog entry discovered; resource promotion is pending."
            else:
                status = "unavailable"
                reason = "not_published"
                explanation = "No entry was published in the audited municipal catalog section."
            coverage.append(
                {
                    "city_code": city["city_code"],
                    "dataset_family": family,
                    "status": status,
                    "unavailable_reason": reason,
                    "explanation": explanation,
                }
            )
    return {
        "schema_version": "citygap-municipal-open-data-inventory@1",
        "observed_at": parsed.isoformat().replace("+00:00", "Z"),
        "official_sources_only": True,
        "analysis_ready_dataset_count": 0,
        "cities": cities,
        "coverage": coverage,
        "claim_boundary": (
            "Discovery proves catalog publication only. It does not prove schema quality, "
            "analysis fitness, current service operation, or linked-resource redistribution rights."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    inventory = build_inventory(args.observed_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
                "city_dataset_counts": {
                    item["city_code"]: item["dataset_count"] for item in inventory["cities"]
                },
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
