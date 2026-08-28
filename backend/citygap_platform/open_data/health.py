"""Canonical health/service records and conservative cross-source identity comparison."""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Iterable
from typing import Any

from backend.citygap_platform.domain.open_data import CanonicalRecordType

MEDICAL_FACILITY_NAMES = ("正式名称", "名称")
MEDICAL_FACILITY_REQUIRED = (
    "ID",
    "都道府県コード",
    "市区町村コード",
    "所在地",
    "所在地座標（緯度）",
    "所在地座標（経度）",
)
MEDICAL_SERVICE_REQUIRED = ("ID", "診療科目コード", "診療科目名", "診療時間帯")
CARE_REQUIRED = (
    "都道府県コード又は市町村コード",
    "事業所名",
    "サービスの種類",
    "住所",
    "緯度",
    "経度",
    "事業所番号",
)

MEDICAL_CATEGORY = {
    "01": "hospital",
    "02": "clinic",
    "03": "dental_clinic",
    "04": "maternity_home",
    "05": "pharmacy",
}

MEDICAL_SCHEDULE_MARKERS = (
    "休診",
    "休業",
    "営業日",
    "閉店",
    "開店時間",
    "就業時間",
    "外来受付時間",
)


def _first(values: dict[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = values.get(name, "").strip()
        if value:
            return value
    return None


def _point(
    values: dict[str, str], latitude: str, longitude: str
) -> tuple[dict[str, Any] | None, str | None]:
    lat = values.get(latitude, "").strip()
    lon = values.get(longitude, "").strip()
    if not lat and not lon:
        return None, "coordinates_not_published"
    if not lat or not lon:
        return None, "coordinate_pair_incomplete"
    try:
        coordinates = (float(lon), float(lat))
    except ValueError:
        return None, "coordinates_not_numeric"
    if coordinates == (0.0, 0.0):
        return None, "published_zero_coordinates"
    if not (122 <= coordinates[0] <= 154 and 20 <= coordinates[1] <= 46):
        return None, "coordinates_outside_japan_review_bounds"
    return {"type": "Point", "coordinates": list(coordinates)}, None


def _source(
    *,
    family: str,
    resource_id: str,
    raw_sha256: str,
    source_row_locator: str,
    reference_date: str,
    license_id: str,
) -> dict[str, str]:
    return {
        "external_dataset_id": f"mhlw-{family}",
        "external_resource_id": resource_id,
        "source_row_locator": source_row_locator,
        "raw_sha256": raw_sha256,
        "adapter_id": f"mhlw-{family}@2026-06",
        "canonical_version": "citygap-canonical-health@1",
        "reference_date": reference_date,
        "license_id": license_id,
    }


def medical_schema_audit(resource_code: str, columns: Iterable[str]) -> dict[str, Any]:
    available = set(columns)
    is_service = resource_code.endswith("-2")
    required = set(MEDICAL_SERVICE_REQUIRED if is_service else MEDICAL_FACILITY_REQUIRED)
    if not is_service and not available.intersection(MEDICAL_FACILITY_NAMES):
        required.add("正式名称|名称")
    missing = sorted(required - available)
    return {
        "schema_id": f"mhlw-medical:{resource_code}@2026-06",
        "resource_role": "service_offering" if is_service else "facility",
        "missing_required_fields": missing,
        "status": "passed" if not missing else "failed",
    }


def care_schema_audit(columns: Iterable[str]) -> dict[str, Any]:
    missing = sorted(set(CARE_REQUIRED) - set(columns))
    return {
        "schema_id": "mhlw-care:recommended-open-data@2026-06",
        "missing_required_fields": missing,
        "status": "passed" if not missing else "failed",
    }


def _medical_city_match(values: dict[str, str], city_code: str) -> bool:
    prefecture = values.get("都道府県コード", "").strip().zfill(2)
    municipality = values.get("市区町村コード", "").strip().zfill(3)
    return prefecture + municipality == city_code


def _published_medical_schedule(values: dict[str, str]) -> dict[str, str]:
    return {
        field: value.strip()
        for field, value in values.items()
        if value.strip()
        and (field == "祝日" or any(marker in field for marker in MEDICAL_SCHEDULE_MARKERS))
    }


def canonicalize_medical_facilities(
    *,
    resource_code: str,
    resource_id: str,
    raw_sha256: str,
    reference_date: str,
    city_code: str,
    normalized_rows: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    category = MEDICAL_CATEGORY[resource_code.split("-", maxsplit=1)[0]]
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    geometry_reasons: dict[str, int] = {}
    identities: set[str] = set()
    for row in normalized_rows:
        values = {str(key): str(value) for key, value in row["values"].items()}
        if not _medical_city_match(values, city_code):
            continue
        locator = str(row["source_row_locator"])
        external_id = values.get("ID", "").strip()
        name = _first(values, MEDICAL_FACILITY_NAMES)
        if not external_id or not name:
            rejected.append({"source_row_locator": locator, "reason": "missing_official_identity"})
            continue
        identity = f"{category}:{external_id}"
        if identity in identities:
            rejected.append(
                {"source_row_locator": locator, "reason": "duplicate_official_identity"}
            )
            continue
        identities.add(identity)
        geometry, reason = _point(values, "所在地座標（緯度）", "所在地座標（経度）")
        if reason:
            geometry_reasons[reason] = geometry_reasons.get(reason, 0) + 1
        beds = values.get("合計病床数", "").strip()
        published_schedule = _published_medical_schedule(values)
        attributes: dict[str, Any] = {
            "entity_kind": "medical_facility",
            "medical_category": category,
            "reported_facility_type": values.get("機関区分", "").strip() or None,
            "address": values.get("所在地", "").strip() or None,
            "published_total_beds": int(beds) if beds.isdigit() else None,
            "published_schedule": published_schedule or None,
            "current_acceptance": "unknown",
            "emergency_acceptance": "unknown",
            "real_time_occupancy": "unknown",
            "coordinate_reference_status": "horizontal_datum_not_declared",
        }
        records.append(
            {
                "canonical_id": f"mhlw-medical:{category}:{external_id}",
                "record_type": CanonicalRecordType.FACILITY.value,
                "external_record_id": external_id,
                "display_name": name,
                "source_row_locator": locator,
                "reference_date": reference_date,
                "attributes": {
                    key: value for key, value in attributes.items() if value is not None
                },
                "geometry": geometry,
                "source": _source(
                    family="medical",
                    resource_id=resource_id,
                    raw_sha256=raw_sha256,
                    source_row_locator=locator,
                    reference_date=reference_date,
                    license_id="pdl-1.0",
                ),
                "spatial_links": [],
            }
        )
    return records, {
        "canonical_records": len(records),
        "rejected_rows": rejected,
        "geometry_records": sum(item["geometry"] is not None for item in records),
        "geometry_absence_reasons": geometry_reasons,
    }


def canonicalize_medical_services(
    *,
    resource_code: str,
    resource_id: str,
    raw_sha256: str,
    reference_date: str,
    facility_ids: dict[str, dict[str, Any]],
    normalized_rows: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    category = MEDICAL_CATEGORY[resource_code.split("-", maxsplit=1)[0]]
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    duplicate_sequence: dict[tuple[str, str, str], int] = {}
    for row in normalized_rows:
        values = {str(key): str(value) for key, value in row["values"].items()}
        facility_id = values.get("ID", "").strip()
        if facility_id not in facility_ids:
            continue
        locator = str(row["source_row_locator"])
        department_code = values.get("診療科目コード", "").strip()
        department_name = values.get("診療科目名", "").strip()
        time_band = values.get("診療時間帯", "").strip()
        if not department_code or not department_name:
            rejected.append(
                {"source_row_locator": locator, "reason": "missing_department_identity"}
            )
            continue
        key = (facility_id, department_code, time_band)
        sequence = duplicate_sequence.get(key, 0) + 1
        duplicate_sequence[key] = sequence
        schedule = {
            field: value.strip()
            for field, value in values.items()
            if value.strip() and field not in {"ID", "診療科目コード", "診療科目名", "診療時間帯"}
        }
        parent = facility_ids[facility_id]
        records.append(
            {
                "canonical_id": (
                    f"mhlw-medical-service:{category}:{facility_id}:"
                    f"{department_code}:{time_band or 'unspecified'}:{sequence}"
                ),
                "record_type": CanonicalRecordType.SERVICE_OFFERING.value,
                "external_record_id": f"{facility_id}:{department_code}:{time_band}:{sequence}",
                "display_name": department_name,
                "source_row_locator": locator,
                "reference_date": reference_date,
                "attributes": {
                    "entity_kind": "medical_service_offering",
                    "medical_category": category,
                    "parent_facility_id": parent["canonical_id"],
                    "department_code": department_code,
                    "department_name": department_name,
                    "reported_time_band": time_band or None,
                    "published_schedule": schedule,
                    "current_availability": "unknown",
                    "appointment_availability": "unknown",
                    "emergency_acceptance": "unknown",
                },
                "geometry": parent["geometry"],
                "source": _source(
                    family="medical",
                    resource_id=resource_id,
                    raw_sha256=raw_sha256,
                    source_row_locator=locator,
                    reference_date=reference_date,
                    license_id="pdl-1.0",
                ),
                "spatial_links": [
                    {
                        "link_type": "facility",
                        "target_id": parent["canonical_id"],
                        "match_method": "exact",
                        "rule_version": "mhlw-reported-facility-id@1",
                        "distance_m": None,
                        "explanation": "The service row carries the same published MHLW facility ID.",
                    }
                ],
            }
        )
    return records, {"canonical_records": len(records), "rejected_rows": rejected}


def canonicalize_care_rows(
    *,
    service_code: str,
    resource_id: str,
    raw_sha256: str,
    reference_date: str,
    city_code: str,
    normalized_rows: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    geometry_reasons: dict[str, int] = {}
    identities: set[str] = set()
    for row in normalized_rows:
        values = {str(key): str(value) for key, value in row["values"].items()}
        official_city_code = re.sub(r"\D", "", values.get("都道府県コード又は市町村コード", ""))
        if official_city_code[:5] != city_code:
            continue
        locator = str(row["source_row_locator"])
        establishment_id = values.get("事業所番号", "").strip() or values.get("No", "").strip()
        name = values.get("事業所名", "").strip()
        service_name = values.get("サービスの種類", "").strip()
        if not establishment_id or not name or not service_name:
            rejected.append({"source_row_locator": locator, "reason": "missing_official_identity"})
            continue
        identity = f"{service_code}:{establishment_id}"
        if identity in identities:
            rejected.append(
                {"source_row_locator": locator, "reason": "duplicate_official_identity"}
            )
            continue
        identities.add(identity)
        geometry, reason = _point(values, "緯度", "経度")
        if reason:
            geometry_reasons[reason] = geometry_reasons.get(reason, 0) + 1
        capacity = values.get("定員", "").strip()
        facility_id = f"mhlw-care:{service_code}:{establishment_id}"
        common_source = _source(
            family="care",
            resource_id=resource_id,
            raw_sha256=raw_sha256,
            source_row_locator=locator,
            reference_date=reference_date,
            license_id="cc-by-4.0",
        )
        facility = {
            "canonical_id": facility_id,
            "record_type": CanonicalRecordType.FACILITY.value,
            "external_record_id": establishment_id,
            "display_name": name,
            "source_row_locator": locator,
            "reference_date": reference_date,
            "attributes": {
                "entity_kind": "care_service_establishment",
                "official_service_code": service_code,
                "official_service_name": service_name,
                "address": " ".join(
                    value
                    for value in (
                        values.get("住所", "").strip(),
                        values.get("方書（ビル名等）", "").strip(),
                    )
                    if value
                )
                or None,
                "published_capacity": int(capacity) if capacity.isdigit() else None,
                "current_capacity": "unknown",
                "current_availability": "unknown",
                "user_eligibility": "unknown",
                "coordinate_reference_status": "horizontal_datum_not_declared",
            },
            "geometry": geometry,
            "source": common_source,
            "spatial_links": [],
        }
        facility["attributes"] = {
            key: value for key, value in facility["attributes"].items() if value is not None
        }
        offering = {
            "canonical_id": f"{facility_id}:service",
            "record_type": CanonicalRecordType.SERVICE_OFFERING.value,
            "external_record_id": f"{establishment_id}:{service_code}",
            "display_name": service_name,
            "source_row_locator": locator,
            "reference_date": reference_date,
            "attributes": {
                "entity_kind": "care_service_offering",
                "parent_facility_id": facility_id,
                "official_service_code": service_code,
                "official_service_name": service_name,
                "published_available_days": values.get("利用可能曜日", "").strip() or None,
                "current_availability": "unknown",
                "user_eligibility": "unknown",
            },
            "geometry": geometry,
            "source": common_source,
            "spatial_links": [
                {
                    "link_type": "facility",
                    "target_id": facility_id,
                    "match_method": "exact",
                    "rule_version": "mhlw-care-establishment-id@1",
                    "distance_m": None,
                    "explanation": "Facility and service row share the published establishment ID.",
                }
            ],
        }
        offering["attributes"] = {
            key: value for key, value in offering["attributes"].items() if value is not None
        }
        records.extend((facility, offering))
    return records, {
        "canonical_records": len(records),
        "facility_records": len(records) // 2,
        "service_offering_records": len(records) // 2,
        "rejected_rows": rejected,
        "geometry_records": sum(item["geometry"] is not None for item in records),
        "geometry_absence_reasons": geometry_reasons,
    }


def _normalized_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    return "".join(character for character in normalized if character.isalnum())


def _distance_m(left: dict[str, Any] | None, right: dict[str, Any] | None) -> float | None:
    if not left or not right or left.get("type") != "Point" or right.get("type") != "Point":
        return None
    lon1, lat1 = (math.radians(float(value)) for value in left["coordinates"])
    lon2, lat2 = (math.radians(float(value)) for value in right["coordinates"])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    angle = 2 * math.asin(
        math.sqrt(
            math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
    )
    return 6_371_008.8 * angle


def compare_facility_identities(
    primary: Iterable[dict[str, Any]],
    references: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Classify identity evidence without converting candidates into asserted truth."""

    reference_rows = list(references)
    result = []
    for facility in primary:
        attributes = facility.get("attributes", {})
        primary_ids = {
            _normalized_text(str(value))
            for value in (facility.get("external_record_id"), *attributes.get("official_ids", ()))
            if value
        }
        primary_name = _normalized_text(facility.get("display_name"))
        primary_address = _normalized_text(attributes.get("address"))
        candidates = []
        for reference in reference_rows:
            official_ids = {
                _normalized_text(str(value)) for value in reference.get("official_ids", ()) if value
            }
            id_match = bool(primary_ids & official_ids)
            name_match = bool(
                primary_name and primary_name == _normalized_text(reference.get("name"))
            )
            address_match = bool(
                primary_address and primary_address == _normalized_text(reference.get("address"))
            )
            distance = _distance_m(facility.get("geometry"), reference.get("geometry"))
            if id_match:
                evidence = "official_id"
            elif name_match and address_match:
                evidence = "normalized_name_and_address"
            elif name_match and distance is not None and distance <= 250:
                evidence = "normalized_name_and_coordinate_proximity"
            else:
                continue
            candidates.append(
                {
                    "source": reference["source"],
                    "reference_id": reference["reference_id"],
                    "evidence": evidence,
                    "distance_m": round(distance, 3) if distance is not None else None,
                }
            )
        official = [item for item in candidates if item["evidence"] == "official_id"]
        if len(official) == 1:
            status = "matched"
            candidates = official
        elif len(official) > 1 or len(candidates) > 1:
            status = "ambiguous"
        elif len(candidates) == 1:
            status = "probable"
        else:
            status = "unmatched"
        result.append(
            {
                "primary_id": facility["canonical_id"],
                "status": status,
                "candidates": candidates,
                "claim_boundary": "candidate comparison; only a unique shared official ID is matched",
            }
        )
    return result
