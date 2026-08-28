"""Canonical demographic projections and economic-activity observations."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Any

import geopandas as gpd
import pandas as pd

PROJECTION_YEARS = tuple(range(2025, 2071, 5))

FIVE_YEAR_AGE_FIELDS = {
    f"PT{index:02d}": label
    for index, label in enumerate(
        (
            "0_4",
            "5_9",
            "10_14",
            "15_19",
            "20_24",
            "25_29",
            "30_34",
            "35_39",
            "40_44",
            "45_49",
            "50_54",
            "55_59",
            "60_64",
            "65_69",
            "70_74",
            "75_79",
            "80_84",
            "85_89",
            "90_94",
            "95_plus",
        ),
        start=1,
    )
}

BROAD_AGE_FIELDS = {
    "PTA": "0_14",
    "PTB": "15_64",
    "PTC": "65_plus",
    "PTD": "75_plus",
    "PTE": "80_plus",
}

BROAD_AGE_RATIO_FIELDS = {
    "RTA": "0_14",
    "RTB": "15_64",
    "RTC": "65_plus",
    "RTD": "75_plus",
    "RTE": "80_plus",
}


@dataclass(frozen=True, slots=True)
class EconomicMetric:
    source_field: str
    metric_key: str
    official_label_ja: str
    unit: str
    public_entity_semantics: str


_INDUSTRIES = (
    ("all_a_s", "Ａ～Ｓ全産業"),
    ("all_a_r_private", "Ａ～Ｒ全産業（Ｓ公務を除く）"),
    ("secondary_c_e", "Ｃ～Ｅ第２次産業"),
    ("mining_c", "Ｃ鉱業，採石業，砂利採取業"),
    ("construction_d", "Ｄ建設業"),
    ("manufacturing_e", "Ｅ製造業"),
    ("tertiary_f_s", "Ｆ～Ｓ第３次産業"),
    ("utilities_f", "Ｆ電気・ガス・熱供給・水道業"),
    ("information_g", "Ｇ情報通信業"),
    ("transport_postal_h", "Ｈ運輸業，郵便業"),
    ("wholesale_retail_i", "Ｉ卸売業，小売業"),
    ("finance_insurance_j", "Ｊ金融業，保険業"),
    ("real_estate_leasing_k", "Ｋ不動産業，物品賃貸業"),
    ("professional_technical_l", "Ｌ学術研究，専門・技術サービス業"),
    ("accommodation_food_m", "Ｍ宿泊業，飲食サービス業"),
    ("personal_services_entertainment_n", "Ｎ生活関連サービス業，娯楽業"),
    ("education_o", "Ｏ教育，学習支援業"),
    ("medical_welfare_p", "Ｐ医療，福祉"),
    ("compound_services_q", "Ｑ複合サービス事業"),
    ("other_services_r", "Ｒサービス業（他に分類されないもの）"),
    ("government_s", "Ｓ公務（他に分類されるものを除く）"),
)


def _public_semantics(index: int) -> str:
    if index == 2:
        return "private_establishments_only; public entities excluded"
    return "national_and_local_public_entities_included"


ECONOMIC_METRICS = (
    tuple(
        EconomicMetric(
            source_field=f"T001162{index:03d}",
            metric_key=f"establishments_{slug}",
            official_label_ja=label,
            unit="establishments",
            public_entity_semantics=_public_semantics(index),
        )
        for index, (slug, label) in enumerate(_INDUSTRIES, start=1)
    )
    + tuple(
        EconomicMetric(
            source_field=f"T001162{index + 21:03d}",
            metric_key=f"employees_{slug}",
            official_label_ja=label,
            unit="persons",
            public_entity_semantics=_public_semantics(index),
        )
        for index, (slug, label) in enumerate(_INDUSTRIES, start=1)
    )
    + (
        EconomicMetric(
            "T001162043",
            "employees_male_all_a_s",
            "男-Ａ～Ｓ全産業",
            "persons",
            "national_and_local_public_entities_included",
        ),
        EconomicMetric(
            "T001162044",
            "employees_female_all_a_s",
            "女-Ａ～Ｓ全産業",
            "persons",
            "national_and_local_public_entities_included",
        ),
        EconomicMetric(
            "T001162045",
            "employees_male_all_a_r_private",
            "男-Ａ～Ｒ全産業（Ｓ公務を除く）",
            "persons",
            "private_establishments_only; public entities excluded",
        ),
        EconomicMetric(
            "T001162046",
            "employees_female_all_a_r_private",
            "女-Ａ～Ｒ全産業（Ｓ公務を除く）",
            "persons",
            "private_establishments_only; public entities excluded",
        ),
    )
)

_MESH_250 = re.compile(r"\d{10}\Z")
_MESH_500 = re.compile(r"\d{9}\Z")
_SUPPRESSION_SYMBOLS = frozenset({"X", "x", "*", "-", "…", "..."})


def economic_metric_dictionary() -> list[dict[str, str]]:
    """Return the complete official T001162 field contract in source order."""

    return [asdict(metric) for metric in ECONOMIC_METRICS]


def _optional_text(value: Any) -> str | None:
    if value is None or bool(pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _number(value: Any, field: str) -> float | None:
    if value is None or bool(pd.isna(value)):
        return None
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"Future-population field {field} must be finite and non-negative")
    return result


def _ratio(value: Any, field: str) -> float | None:
    result = _number(value, field)
    if result is not None and result > 1:
        raise ValueError(f"Future-population ratio field {field} must be between zero and one")
    return result


def _year_projection(row: Any, year: int) -> dict[str, Any]:
    return {
        "year": year,
        "status": "official_trial_projection_not_observation",
        "total_population_before_privacy_aggregation": _number(row[f"PTN_{year}"], f"PTN_{year}"),
        "published_privacy_adjusted_total_population": _number(row[f"PT00_{year}"], f"PT00_{year}"),
        "five_year_age_population": {
            label: _number(row[f"{prefix}_{year}"], f"{prefix}_{year}")
            for prefix, label in FIVE_YEAR_AGE_FIELDS.items()
        },
        "broad_age_population": {
            label: _number(row[f"{prefix}_{year}"], f"{prefix}_{year}")
            for prefix, label in BROAD_AGE_FIELDS.items()
        },
        "broad_age_ratio": {
            label: _ratio(row[f"{prefix}_{year}"], f"{prefix}_{year}")
            for prefix, label in BROAD_AGE_RATIO_FIELDS.items()
        },
        "broad_age_ratio_unit": "proportion_0_to_1",
        "privacy_aggregation": {
            "official_marker": _optional_text(row[f"HITOKU{year}"]),
            "target_250m_mesh_code": _optional_text(row[f"GASSAN{year}"]),
            "source_fields": {
                "marker": f"HITOKU{year}",
                "target": f"GASSAN{year}",
            },
        },
    }


def canonicalize_future_population(
    frame: gpd.GeoDataFrame,
    *,
    city_code: str,
    city_name: str,
    resource_id: str,
    raw_sha256: str,
    reference_date: str,
    mesh_context: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Filter an official prefectural frame and preserve its projection semantics."""

    required = {"MESH_ID", "SHICODE", "PTN_2020"}
    for year in PROJECTION_YEARS:
        required.update(
            {
                f"HITOKU{year}",
                f"GASSAN{year}",
                f"PTN_{year}",
                f"PT00_{year}",
                *(f"{prefix}_{year}" for prefix in FIVE_YEAR_AGE_FIELDS),
                *(f"{prefix}_{year}" for prefix in BROAD_AGE_FIELDS),
                *(f"{prefix}_{year}" for prefix in BROAD_AGE_RATIO_FIELDS),
            }
        )
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Future-population schema is missing fields: {missing}")
    if frame.crs is None:
        raise ValueError("Future-population frame has no declared CRS")
    city = frame.loc[frame["SHICODE"].astype(str) == city_code].to_crs("EPSG:4326")
    if city.empty:
        raise ValueError(f"Future-population frame has no records for city {city_code}")
    if city["MESH_ID"].astype(str).duplicated().any():
        raise ValueError("Future-population 250 m mesh identifiers must be unique")

    records = []
    parent_counts: dict[str, int] = {}
    markers: dict[str, int] = {}
    city_mesh_ids = set(city["MESH_ID"].astype(str))
    missing_targets_by_year: dict[int, set[str]] = {year: set() for year in PROJECTION_YEARS}
    for _, row in city.sort_values("MESH_ID").iterrows():
        mesh_id = str(row["MESH_ID"])
        if _MESH_250.fullmatch(mesh_id) is None:
            raise ValueError(f"Invalid official 250 m mesh code: {mesh_id}")
        parent_mesh = mesh_id[:-1]
        if parent_mesh not in mesh_context:
            raise ValueError(f"Official 250 m mesh has no audited parent 500 m mesh: {mesh_id}")
        projections = [_year_projection(row, year) for year in PROJECTION_YEARS]
        for projection in projections:
            privacy = projection["privacy_aggregation"]
            marker = privacy["official_marker"] or "none"
            markers[marker] = markers.get(marker, 0) + 1
            target = privacy["target_250m_mesh_code"]
            if target is None:
                privacy["target_scope"] = "not_applicable"
            elif target in city_mesh_ids:
                privacy["target_scope"] = "within_exact_city_code_extract"
            else:
                privacy["target_scope"] = "outside_exact_city_code_extract"
                missing_targets_by_year[int(projection["year"])].add(target)
        parent_counts[parent_mesh] = parent_counts.get(parent_mesh, 0) + 1
        context = mesh_context[parent_mesh]
        records.append(
            {
                "canonical_id": f"mlit-future-population:{raw_sha256[:16]}:{mesh_id}",
                "canonical_version": "citygap-canonical-population-projection@1",
                "record_type": "population_observation",
                "external_record_id": mesh_id,
                "display_name": f"250m mesh {mesh_id}",
                "city_code": city_code,
                "city_name": city_name,
                "reference_date": reference_date,
                "geometry": row.geometry.__geo_interface__,
                "attributes": {
                    "entity_kind": "official_future_population_projection_series",
                    "mesh_size_m": 250,
                    "baseline": {
                        "year": 2020,
                        "value": _number(row["PTN_2020"], "PTN_2020"),
                        "source_field": "PTN_2020",
                        "status": "modeled_baseline_from_2020_census_input_not_census_observation",
                    },
                    "projections": projections,
                    "automatic_best_scenario_selected": False,
                    "claim_boundary": (
                        "The MLIT R6 series is an official trial projection, not an observed "
                        "population, forecast guarantee, or automatically selected best scenario."
                    ),
                },
                "spatial_links": {
                    "city": {
                        "method": "exact",
                        "official_field": "SHICODE",
                        "value": city_code,
                    },
                    "parent_500m_mesh": {
                        "method": "deterministic",
                        "rule": "JIS X 0410 250m code without its final subdivision digit",
                        "mesh_code": parent_mesh,
                        "city_area_fraction": context.get("city_area_fraction"),
                    },
                    "plateau_aggregate": context.get("plateau_aggregate"),
                },
                "provenance": {
                    "provider": "国土交通省 国土数値情報",
                    "resource_id": resource_id,
                    "raw_sha256": raw_sha256,
                    "source_crs": str(frame.crs),
                    "canonical_crs": "EPSG:4326",
                },
            }
        )
    external_targets = sorted(set().union(*missing_targets_by_year.values()))
    return records, {
        "prefectural_feature_count": len(frame),
        "city_feature_count": len(records),
        "parent_500m_mesh_count": len(parent_counts),
        "maximum_250m_children_per_parent": max(parent_counts.values()),
        "privacy_marker_counts_across_projection_years": dict(sorted(markers.items())),
        "privacy_aggregation_targets_outside_city_count": len(external_targets),
        "privacy_aggregation_targets_outside_city": external_targets,
        "privacy_aggregation_targets_outside_city_by_year": {
            str(year): sorted(targets)
            for year, targets in missing_targets_by_year.items()
            if targets
        },
        "city_published_total_semantics": (
            "unavailable for years with an outside-city privacy aggregation target; "
            "the partial city-code extract is never presented as a city total"
        ),
        "audited_500m_meshes_without_official_city_250m_child": sorted(
            set(mesh_context) - set(parent_counts)
        ),
    }


def _estat_count(raw: str, field: str) -> tuple[int | None, dict[str, str] | None]:
    value = raw.strip()
    if not value:
        return None, {"reason": "blank_in_official_table", "raw_value": raw}
    if value in _SUPPRESSION_SYMBOLS:
        return None, {"reason": "official_suppression_or_missing_symbol", "raw_value": value}
    if not value.isdigit():
        raise ValueError(f"Unexpected e-Stat count in {field}: {raw!r}")
    return int(value), None


def canonicalize_economic_activity(
    rows: list[dict[str, Any]],
    *,
    city_code: str,
    city_name: str,
    resource_id: str,
    raw_sha256: str,
    reference_date: str,
    mesh_context: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select audited 500 m meshes and retain official null/suppression semantics."""

    records = []
    seen: set[str] = set()
    suppression_counts: dict[str, int] = {}
    required_fields = {metric.source_field for metric in ECONOMIC_METRICS}
    for normalized in rows:
        values = normalized.get("values")
        if not isinstance(values, dict):
            raise TypeError("Normalized e-Stat row values must be an object")
        mesh_id = str(values.get("KEY_CODE", ""))
        if _MESH_500.fullmatch(mesh_id) is None:
            raise ValueError(f"Invalid official 500 m mesh code: {mesh_id}")
        if mesh_id not in mesh_context:
            continue
        if mesh_id in seen:
            raise ValueError(f"Duplicate official economic 500 m mesh code: {mesh_id}")
        seen.add(mesh_id)
        missing = sorted(required_fields - set(values))
        if missing:
            raise ValueError(f"Economic-census schema is missing fields: {missing}")
        metrics: dict[str, int | None] = {}
        suppressed: dict[str, dict[str, str]] = {}
        for metric in ECONOMIC_METRICS:
            value, reason = _estat_count(str(values[metric.source_field]), metric.source_field)
            metrics[metric.metric_key] = value
            if reason is not None:
                suppressed[metric.metric_key] = reason
                suppression_counts[reason["reason"]] = (
                    suppression_counts.get(reason["reason"], 0) + 1
                )
        context = mesh_context[mesh_id]
        records.append(
            {
                "canonical_id": f"estat-economic-census:{raw_sha256[:16]}:{mesh_id}",
                "canonical_version": "citygap-canonical-economic-activity@1",
                "record_type": "activity_observation",
                "external_record_id": mesh_id,
                "display_name": f"500m mesh {mesh_id}",
                "city_code": city_code,
                "city_name": city_name,
                "reference_date": reference_date,
                "geometry": context["geometry"],
                "attributes": {
                    "entity_kind": "economic_census_mesh_activity",
                    "mesh_size_m": 500,
                    "statistics_id": "T001162",
                    "metrics": metrics,
                    "null_reasons": suppressed,
                    "claim_boundary": (
                        "These are published establishment and employee counts by industry. "
                        "They are activity context, not a need, demand, capacity, or policy score."
                    ),
                },
                "spatial_links": {
                    "audited_500m_mesh": {
                        "method": "exact",
                        "official_field": "KEY_CODE",
                        "mesh_code": mesh_id,
                        "city_area_fraction": context.get("city_area_fraction"),
                    },
                    "plateau_aggregate": context.get("plateau_aggregate"),
                },
                "provenance": {
                    "provider": "e-Stat 令和3年経済センサス‐活動調査",
                    "resource_id": resource_id,
                    "raw_sha256": raw_sha256,
                    "source_crs": "JGD2011 regional mesh code",
                    "canonical_crs": "EPSG:4326",
                    "source_row_locator": normalized.get("source_row_locator"),
                },
            }
        )
    records.sort(key=lambda item: item["external_record_id"])
    missing_meshes = sorted(set(mesh_context) - seen)
    return records, {
        "prefectural_row_count": len(rows),
        "city_published_mesh_row_count": len(records),
        "audited_500m_mesh_count": len(mesh_context),
        "audited_500m_meshes_without_published_row_count": len(missing_meshes),
        "audited_500m_meshes_without_published_row": missing_meshes,
        "missing_row_semantics": "not_available_from_selected_table; never imputed as zero",
        "null_reason_counts": dict(sorted(suppression_counts.items())),
    }
