"""Canonical mapping for reviewed Municipal Standard ODS-style resource schemas."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from backend.citygap_platform.domain.open_data import CanonicalRecordType


@dataclass(frozen=True, slots=True)
class OdsSchema:
    dataset_id: str
    record_type: CanonicalRecordType
    entity_kind: str
    id_aliases: tuple[str, ...]
    name_aliases: tuple[str, ...]
    reference_date_aliases: tuple[str, ...] = ()
    selected_attributes: tuple[tuple[str, tuple[str, ...]], ...] = ()
    requires_coordinates: bool = False
    identity_includes_reference_date: bool = False


COMMON_FACILITY_ATTRIBUTES = (
    ("municipality_code", ("全国地方公共団体コード", "都道府県コード又は市区町村コード")),
)

SCHEMAS = {
    schema.dataset_id: schema
    for schema in (
        OdsSchema(
            "262021_aed",
            CanonicalRecordType.FACILITY,
            "aed",
            ("ID", "NO", "レコード番号"),
            ("名称",),
            selected_attributes=COMMON_FACILITY_ATTRIBUTES
            + (
                ("placement", ("設置位置",)),
                ("pediatric_support", ("小児対応設備の有無",)),
            ),
            requires_coordinates=True,
        ),
        OdsSchema(
            "262021_care_service",
            CanonicalRecordType.FACILITY,
            "care_service",
            ("ID", "事業所番号"),
            ("介護サービス事業所名称", "名称"),
            selected_attributes=COMMON_FACILITY_ATTRIBUTES
            + (
                ("services", ("実施サービス",)),
                ("capacity", ("定員",)),
                ("establishment_number", ("事業所番号",)),
            ),
            requires_coordinates=True,
        ),
        OdsSchema(
            "262021_educational_institution",
            CanonicalRecordType.FACILITY,
            "educational_institution",
            ("学校コード", "ID"),
            ("学校名", "名称"),
            reference_date_aliases=("属性情報設定年月日",),
            selected_attributes=(
                ("school_code", ("学校コード",)),
                ("school_type", ("学校種",)),
                ("operator", ("設置者情報",)),
                ("closed_at", ("属性情報廃止年月日",)),
            ),
            requires_coordinates=True,
        ),
        OdsSchema(
            "262021_evacuation_space",
            CanonicalRecordType.FACILITY,
            "emergency_shelter",
            ("ID",),
            ("名称",),
            selected_attributes=COMMON_FACILITY_ATTRIBUTES
            + (
                ("flood", ("災害種別_洪水",)),
                ("landslide", ("災害種別_崖崩れ、土石流及び地滑り",)),
                ("storm_surge", ("災害種別_高潮",)),
                ("earthquake", ("災害種別_地震",)),
                ("tsunami", ("災害種別_津波",)),
                ("large_fire", ("災害種別_大規模な火事",)),
                ("inland_flood", ("災害種別_内水氾濫",)),
                ("capacity", ("想定収容人数",)),
                ("designated_shelter_overlap", ("指定避難所との重複",)),
            ),
            requires_coordinates=True,
        ),
        OdsSchema(
            "262021_hospital",
            CanonicalRecordType.FACILITY,
            "medical_institution",
            ("ID", "医療機関コード"),
            ("名称",),
            selected_attributes=COMMON_FACILITY_ATTRIBUTES
            + (
                ("medical_type", ("医療機関の種類",)),
                ("medical_code", ("医療機関コード",)),
                ("departments", ("診療科目",)),
                ("beds", ("病床数",)),
                ("status", ("状況",)),
                ("disaster_base_classification", ("災害拠点分類",)),
            ),
            requires_coordinates=True,
        ),
        OdsSchema(
            "262021_preschool",
            CanonicalRecordType.FACILITY,
            "childcare_facility",
            ("ID",),
            ("名称",),
            reference_date_aliases=("認可等年月日",),
            selected_attributes=COMMON_FACILITY_ATTRIBUTES
            + (
                ("facility_type", ("種別",)),
                ("capacity", ("収容定員",)),
                ("accepted_ages", ("受入年齢",)),
                ("temporary_care", ("一時預かりの有無",)),
                ("sick_child_care", ("病児保育の有無",)),
            ),
            requires_coordinates=True,
        ),
        OdsSchema(
            "262021_public_facility",
            CanonicalRecordType.FACILITY,
            "public_facility",
            ("ID", "NO"),
            ("名称",),
            selected_attributes=COMMON_FACILITY_ATTRIBUTES
            + (
                ("poi_code", ("POIコード",)),
                ("description", ("説明",)),
                ("accessibility", ("バリアフリー情報",)),
            ),
            requires_coordinates=True,
        ),
        OdsSchema(
            "262021_population",
            CanonicalRecordType.POPULATION_OBSERVATION,
            "administrative_area_population",
            ("行政区コード",),
            ("行政区名",),
            reference_date_aliases=("調査年月日",),
            selected_attributes=tuple(
                (field, (field,))
                for field in (
                    "0－4歳",
                    "5－9歳",
                    "10－14歳",
                    "15－19歳",
                    "20－24歳",
                    "25－29歳",
                    "30－34歳",
                    "35－39歳",
                    "40－44歳",
                    "45－49歳",
                    "50－54歳",
                    "55－59歳",
                    "60－64歳",
                    "65－69歳",
                    "70－74歳",
                    "75－79歳",
                    "80－84歳",
                    "85－89歳",
                    "90－94歳",
                    "95－99歳",
                    "100歳以上",
                    "計",
                    "世帯数",
                )
            ),
            identity_includes_reference_date=True,
        ),
        OdsSchema(
            "262021_jidoseitosu",
            CanonicalRecordType.ACTIVITY_OBSERVATION,
            "school_enrollment",
            ("ID",),
            ("学校名",),
            reference_date_aliases=("時点",),
            selected_attributes=tuple(
                (field, (field,))
                for field in (
                    "学校コード",
                    "学級数（複式）",
                    "学級数（単式・1年）",
                    "学級数（単式・2年）",
                    "学級数（単式・3年）",
                    "学級数（単式・4年）",
                    "学級数（単式・5年）",
                    "学級数（単式・6年）",
                    "特別支援学級数",
                    "学級数合計",
                    "児童生徒数（1年）",
                    "児童生徒数（2年）",
                    "児童生徒数（3年）",
                    "児童数（4年）",
                    "児童数（5年）",
                    "児童数（6年）",
                    "児童生徒数合計",
                )
            ),
        ),
    )
}

ADDRESS_ALIASES = ("所在地_連結表記", "住所")
ADDRESS_COMPONENTS = (
    "所在地_都道府県",
    "所在地_市区町村",
    "所在地_町字",
    "所在地_番地以下",
    "建物名等(方書)",
    "学校所在地（市区町村）",
    "学校所在地（町字）",
    "学校所在地（番地以下）",
)


def _first(values: dict[str, str], aliases: tuple[str, ...]) -> tuple[str | None, str | None]:
    for alias in aliases:
        value = values.get(alias, "").strip()
        if value:
            return value, alias
    return None, None


def _number(value: str | None) -> int | float | str | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip().replace(",", "")
    try:
        number = float(normalized)
    except ValueError:
        return value.strip()
    return int(number) if number.is_integer() else number


def _address(values: dict[str, str]) -> str | None:
    direct, _ = _first(values, ADDRESS_ALIASES)
    if direct:
        return direct
    parts = [values.get(field, "").strip() for field in ADDRESS_COMPONENTS]
    combined = "".join(part for part in parts if part)
    return combined or None


def _geometry(values: dict[str, str]) -> tuple[dict[str, Any] | None, str | None]:
    latitude, _ = _first(values, ("緯度",))
    longitude, _ = _first(values, ("経度",))
    if latitude is None and longitude is None:
        return None, "coordinates_not_published"
    if latitude is None or longitude is None:
        return None, "coordinate_pair_incomplete"
    try:
        lat = float(latitude)
        lon = float(longitude)
    except ValueError:
        return None, "coordinates_not_numeric"
    if not (34 <= lat <= 36 and 134 <= lon <= 136):
        return None, "coordinates_outside_maizuru_review_bounds"
    return {"type": "Point", "coordinates": [lon, lat]}, None


def schema_audit(dataset_id: str, columns: Iterable[str]) -> dict[str, Any]:
    schema = SCHEMAS[dataset_id]
    available = set(columns)
    resolved: dict[str, str] = {}
    required = {"external_record_id": schema.id_aliases, "display_name": schema.name_aliases}
    if schema.requires_coordinates:
        required |= {"latitude": ("緯度",), "longitude": ("経度",)}
    missing = []
    for canonical, aliases in required.items():
        match = next((alias for alias in aliases if alias in available), None)
        if match is None:
            missing.append(canonical)
        else:
            resolved[canonical] = match
    selected = {
        alias
        for _, aliases in schema.selected_attributes
        for alias in aliases
        if alias in available
    }
    retained = set(resolved.values()) | selected | set(schema.reference_date_aliases)
    retained |= set(ADDRESS_ALIASES) | set(ADDRESS_COMPONENTS)
    fingerprint = hashlib.sha256(
        json.dumps(sorted(available), ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema_id": f"municipal-standard-ods:{dataset_id}@1",
        "schema_fingerprint": fingerprint,
        "resolved_aliases": resolved,
        "missing_required_fields": sorted(missing),
        "retained_fields": sorted(available & retained),
        "excluded_fields": sorted(available - retained),
        "status": "passed" if not missing else "failed",
    }


def canonicalize_rows(
    *,
    dataset_id: str,
    resource_id: str,
    source_sha256: str,
    normalized_rows: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    schema = SCHEMAS[dataset_id]
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    geometry_reasons: dict[str, int] = {}
    identities: set[str] = set()
    for row in normalized_rows:
        values = {str(key): str(value) for key, value in row["values"].items()}
        locator = str(row["source_row_locator"])
        external_id, _ = _first(values, schema.id_aliases)
        display_name, _ = _first(values, schema.name_aliases)
        reference_date, _ = _first(values, schema.reference_date_aliases)
        if external_id is None or display_name is None:
            rejected.append({"source_row_locator": locator, "reason": "missing_official_identity"})
            continue
        if schema.identity_includes_reference_date:
            if reference_date is None:
                rejected.append(
                    {"source_row_locator": locator, "reason": "missing_official_reference_date"}
                )
                continue
            external_id = f"{external_id}|{reference_date}"
        if external_id in identities:
            rejected.append(
                {"source_row_locator": locator, "reason": "duplicate_official_identity"}
            )
            continue
        identities.add(external_id)
        attributes: dict[str, Any] = {
            "entity_kind": schema.entity_kind,
            "address": _address(values),
        }
        for key, aliases in schema.selected_attributes:
            value, _ = _first(values, aliases)
            parsed = _number(value)
            if parsed is not None:
                attributes[key] = parsed
        geometry, geometry_reason = _geometry(values)
        if geometry_reason:
            geometry_reasons[geometry_reason] = geometry_reasons.get(geometry_reason, 0) + 1
        records.append(
            {
                "canonical_id": f"{dataset_id}:{external_id}",
                "record_type": schema.record_type.value,
                "external_record_id": external_id,
                "display_name": display_name,
                "source_row_locator": locator,
                "reference_date": reference_date,
                "attributes": {
                    key: value for key, value in attributes.items() if value is not None
                },
                "geometry": geometry,
                "source": {
                    "external_dataset_id": dataset_id,
                    "external_resource_id": resource_id,
                    "raw_sha256": source_sha256,
                    "adapter_id": "municipal-standard-ods@2026-08",
                    "canonical_version": "citygap-canonical-open-data@1",
                },
                "spatial_links": [],
            }
        )
    return records, {
        "input_rows": len(records) + len(rejected),
        "canonical_records": len(records),
        "rejected_rows": rejected,
        "geometry_records": sum(item["geometry"] is not None for item in records),
        "geometry_absence_reasons": geometry_reasons,
    }
