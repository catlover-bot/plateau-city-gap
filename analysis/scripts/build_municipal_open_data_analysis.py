"""Connect promoted official open data to bounded municipal review contexts."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import mapping

from backend.citygap_platform.domain.municipal_service import (
    ANALYSIS_CATALOG,
    evaluate_analysis_tier,
)
from backend.citygap_platform.ingestion.open_data_evidence import (
    export_open_data_evidence,
)

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "analysis/outputs/real"
OPEN_DATA = REAL / "open_data"
HEALTH = OPEN_DATA / "mhlw_health_canonical.jsonl"
DEMOGRAPHIC = OPEN_DATA / "demographic_economic_canonical.jsonl"
RESILIENCE = OPEN_DATA / "geospatial_resilience_canonical.jsonl"
ANALYSIS_OUTPUT = OPEN_DATA / "municipal_open_data_analysis.geojson"
FINDINGS_OUTPUT = OPEN_DATA / "municipal_open_data_findings.json"
SUMMARY_OUTPUT = OPEN_DATA / "municipal_open_data_analysis_summary.json"
ALGORITHM_VERSION = "municipal-open-data-analysis-1.0.0"

CITY_CONFIGS = {
    "maizuru": {
        "city_code": "26202",
        "city_name": "舞鶴市",
        "analysis_crs": "EPSG:6674",
        "urban_state": "maizuru-2025-observed",
        "meshes": REAL / "maizuru_city_gap.geojson",
        "network": REAL / "maizuru_network_accessibility_meshes.csv",
        "plateau": REAL / "maizuru_plateau_detail_meshes.csv",
        "plateau_summary": REAL / "maizuru_plateau_context_summary.json",
    },
    "fujisawa": {
        "city_code": "14205",
        "city_name": "藤沢市",
        "analysis_crs": "EPSG:6677",
        "urban_state": "fujisawa-2025-observed",
        "meshes": REAL / "fujisawa_city_gap.geojson",
        "network": REAL / "fujisawa_network_accessibility_meshes.csv",
        "plateau": REAL / "fujisawa_plateau_detail_meshes.csv",
        "plateau_summary": REAL / "fujisawa_plateau_context_summary.json",
    },
}

ANALYSIS_IDS = (
    "medical-access-v2",
    "care-access",
    "future-population-spatial",
    "daytime-activity-context",
    "earthquake-ground-context",
    "historical-traffic-safety-context",
)

AVAILABLE_FAMILIES = frozenset(
    {
        "census_population_500m",
        "census_elderly_population_500m",
        "mhlw_medical",
        "mhlw_care",
        "plateau_buildings",
        "road_network",
        "mlit_future_population_250m",
        "economic_census_500m",
        "transport_points",
        "jshis_surface_ground",
        "npa_traffic_accident",
    }
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
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _number(value: Any, digits: int = 3) -> float | int | None:
    if value is None or bool(pd.isna(value)):
        return None
    if isinstance(value, (int, np.integer)):
        return int(value)
    return round(float(value), digits)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("Cannot calculate a threshold without observed values")
    return float(np.percentile(np.asarray(values, dtype=float), percentile, method="linear"))


def _records(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _health_index(
    records: list[dict[str, Any]], city_code: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, set[str]]]:
    city = [record for record in records if record["city_code"] == city_code]
    medical = sorted(
        (
            record
            for record in city
            if record["record_type"] == "facility"
            and record["attributes"]["entity_kind"] == "medical_facility"
        ),
        key=lambda record: record["canonical_id"],
    )
    care_by_key: dict[tuple[str, tuple[float, float]], dict[str, Any]] = {}
    for record in city:
        if (
            record["record_type"] == "facility"
            and record["attributes"]["entity_kind"] == "care_service_establishment"
        ):
            coordinates = (
                tuple(record["geometry"]["coordinates"])
                if record.get("geometry") is not None
                else ()
            )
            key = (record["external_record_id"], coordinates)
            care_by_key.setdefault(key, record)
    departments: dict[str, set[str]] = defaultdict(set)
    for record in city:
        attributes = record["attributes"]
        if attributes.get("entity_kind") != "medical_service_offering":
            continue
        department = attributes.get("department_name")
        parent = attributes.get("parent_facility_id")
        if department and parent:
            departments[str(department)].add(str(parent))
    return medical, sorted(care_by_key.values(), key=lambda item: item["canonical_id"]), departments


def _projected_targets(
    records: list[dict[str, Any]], transformer: Transformer
) -> list[dict[str, Any]]:
    targets = []
    for record in records:
        if record.get("geometry") is None:
            continue
        longitude, latitude = record["geometry"]["coordinates"]
        x, y = transformer.transform(longitude, latitude)
        targets.append(
            {
                "id": record["canonical_id"],
                "name": record["display_name"],
                "x": x,
                "y": y,
            }
        )
    return targets


def _nearest(x: float, y: float, targets: list[dict[str, Any]]) -> dict[str, Any]:
    if not targets:
        return {"status": "unavailable", "distance_m": None, "target_id": None, "name": None}
    distances = np.asarray(
        [np.hypot(x - target["x"], y - target["y"]) for target in targets], dtype=float
    )
    index = int(np.argmin(distances))
    return {
        "status": "requires_review_horizontal_datum_not_declared",
        "distance_m": round(float(distances[index]), 3),
        "target_id": targets[index]["id"],
        "name": targets[index]["name"],
    }


def _future_index(records: list[dict[str, Any]], city_code: str) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"published_250m_cell_count": 0, "years": defaultdict(float)}
    )
    for record in records:
        if record["city_code"] != city_code or record["record_type"] != "population_observation":
            continue
        parent = record["spatial_links"]["parent_500m_mesh"]["mesh_code"]
        values[parent]["published_250m_cell_count"] += 1
        for projection in record["attributes"]["projections"]:
            if int(projection["year"]) not in {2025, 2050, 2070}:
                continue
            population = projection["total_population_before_privacy_aggregation"]
            if population is not None:
                values[parent]["years"][int(projection["year"])] += float(population)
    return values


def _activity_index(records: list[dict[str, Any]], city_code: str) -> dict[str, dict[str, Any]]:
    values = {}
    for record in records:
        if record["city_code"] != city_code or record["record_type"] != "activity_observation":
            continue
        mesh = record["spatial_links"]["audited_500m_mesh"]["mesh_code"]
        metrics = record["attributes"]["metrics"]
        values[mesh] = {
            "reference_year": 2021,
            "employees_all_industries": metrics.get("employees_all_a_s"),
            "establishments_all_industries": metrics.get("establishments_all_a_s"),
            "employees_medical_welfare": metrics.get("employees_medical_welfare_p"),
            "status": "published_observation_not_daytime_population",
        }
    return values


def _ground_index(records: list[dict[str, Any]], city_code: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record["city_code"] == city_code and record["record_type"] == "ground_observation":
            grouped[record["spatial_links"]["audited_500m_mesh"]["mesh_code"]].append(record)
    result = {}
    for mesh, rows in grouped.items():
        velocities = [
            row["attributes"]["average_shear_wave_velocity_m_s"]
            for row in rows
            if row["attributes"]["average_shear_wave_velocity_m_s"] is not None
        ]
        ratios = [
            row["attributes"]["amplification_ratio"]
            for row in rows
            if row["attributes"]["amplification_ratio"] is not None
        ]
        topography = Counter(row["attributes"]["microtopography"] for row in rows)
        coastal = sum(row["attributes"]["value_status"] == "coastal_no_model_value" for row in rows)
        result[mesh] = {
            "reference_year": 2020,
            "published_250m_cell_count": len(rows),
            "modeled_value_cell_count": len(velocities),
            "coastal_no_model_value_cell_count": coastal,
            "average_shear_wave_velocity_m_s": {
                "minimum": _number(min(velocities) if velocities else None),
                "median": _number(np.median(velocities) if velocities else None),
                "maximum": _number(max(velocities) if velocities else None),
            },
            "amplification_ratio": {
                "minimum": _number(min(ratios) if ratios else None, 4),
                "median": _number(np.median(ratios) if ratios else None, 4),
                "maximum": _number(max(ratios) if ratios else None, 4),
            },
            "microtopography_cell_counts": dict(sorted(topography.items())),
            "status": "modeled_ground_context_not_risk",
        }
    return result


def _accident_index(
    records: list[dict[str, Any]], city_code: str
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unmatched = []
    city_records = [
        record
        for record in records
        if record["city_code"] == city_code and record["record_type"] == "road_observation"
    ]
    for record in city_records:
        mesh = record["spatial_links"]["audited_500m_mesh"]["mesh_code"]
        if mesh is None:
            unmatched.append(record["canonical_id"])
        else:
            grouped[mesh].append(record)
    result = {}
    for mesh, rows in grouped.items():
        years = sorted({int(row["attributes"]["occurred_at"][:4]) for row in rows})
        result[mesh] = {
            "event_record_count": len(rows),
            "fatalities": sum(int(row["attributes"]["fatalities"]) for row in rows),
            "injuries": sum(int(row["attributes"]["injuries"]) for row in rows),
            "occurrence_years": years,
            "annual_file_year": 2024,
            "status": "historical_injury_fatal_accident_context_without_denominator",
        }
    return result, {
        "municipality_filtered_record_count": len(city_records),
        "linked_to_audited_mesh_count": len(city_records) - len(unmatched),
        "unmatched_to_audited_mesh_count": len(unmatched),
        "unmatched_record_ids": sorted(unmatched),
    }


def _spatial_link_coverage(records: list[dict[str, Any]], city_code: str) -> dict[str, Any]:
    coverage: dict[str, Counter[str]] = {
        "medical": Counter(),
        "care": Counter(),
    }
    for record in records:
        if record["city_code"] != city_code or record["record_type"] != "facility":
            continue
        kind = record["attributes"]["entity_kind"]
        family = "medical" if kind == "medical_facility" else "care"
        link = next(
            (item for item in record["spatial_links"] if item["link_type"] == "plateau_building"),
            None,
        )
        coverage[family]["facility_count"] += 1
        coverage[family][link["match_method"] if link else "unmatched"] += 1
    return {
        family: {
            **dict(sorted(counts.items())),
            "identity_claimed": False,
            "method": "nearest footprint candidate; proximity is not official identity",
        }
        for family, counts in coverage.items()
    }


def _change_percent(current: float | None, baseline: float | None) -> float | None:
    if current is None or baseline in {None, 0.0}:
        return None
    return round((current - baseline) / baseline * 100.0, 3)


def _finding_id(city: str, kind: str, mesh: str) -> str:
    key = f"{ALGORITHM_VERSION}:{city}:{kind}:{mesh}".encode()
    return f"finding-{hashlib.sha256(key).hexdigest()[:24]}"


def _city_analysis(
    city_id: str,
    config: dict[str, Any],
    health: list[dict[str, Any]],
    demographic: list[dict[str, Any]],
    resilience: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    meshes = gpd.read_file(config["meshes"], engine="pyogrio").to_crs("EPSG:4326")
    meshes["mesh_code"] = meshes["mesh_code"].astype(str)
    meshes = meshes.sort_values("mesh_code").reset_index(drop=True)
    if meshes["mesh_code"].duplicated().any():
        raise ValueError(f"Duplicate audited mesh: {city_id}")
    network_frame = pd.read_csv(config["network"], dtype={"mesh_code": str})
    network = {str(row["mesh_code"]): row for _, row in network_frame.iterrows()}
    plateau_frame = pd.read_csv(config["plateau"], dtype={"mesh_code": str})
    plateau = {str(row["mesh_code"]): row for _, row in plateau_frame.iterrows()}
    transformer = Transformer.from_crs("EPSG:4326", config["analysis_crs"], always_xy=True)
    medical, care, departments = _health_index(health, config["city_code"])
    medical_by_id = {record["canonical_id"]: record for record in medical}
    target_sets = {
        "all": _projected_targets(medical, transformer),
        "general_medical": _projected_targets(
            [
                record
                for record in medical
                if record["attributes"]["medical_category"] in {"hospital", "clinic"}
            ],
            transformer,
        ),
        "hospital": _projected_targets(
            [
                record
                for record in medical
                if record["attributes"]["medical_category"] == "hospital"
            ],
            transformer,
        ),
        "clinic": _projected_targets(
            [record for record in medical if record["attributes"]["medical_category"] == "clinic"],
            transformer,
        ),
        "dental": _projected_targets(
            [
                record
                for record in medical
                if record["attributes"]["medical_category"] == "dental_clinic"
            ],
            transformer,
        ),
        "internal_medicine": _projected_targets(
            [
                medical_by_id[parent]
                for name, parents in departments.items()
                if "内科" in name
                for parent in sorted(parents)
                if parent in medical_by_id
            ],
            transformer,
        ),
        "pediatrics": _projected_targets(
            [
                medical_by_id[parent]
                for name, parents in departments.items()
                if name == "小児科"
                for parent in sorted(parents)
                if parent in medical_by_id
            ],
            transformer,
        ),
    }
    for key, targets in target_sets.items():
        target_sets[key] = list({target["id"]: target for target in targets}.values())
    care_targets = _projected_targets(care, transformer)
    future = _future_index(demographic, config["city_code"])
    activity = _activity_index(demographic, config["city_code"])
    ground = _ground_index(resilience, config["city_code"])
    accidents, accident_coverage = _accident_index(resilience, config["city_code"])

    features = []
    metric_rows = []
    for row in meshes.itertuples():
        mesh = str(row.mesh_code)
        x, y = transformer.transform(float(row.centroid_lon), float(row.centroid_lat))
        medical_metrics = {key: _nearest(x, y, targets) for key, targets in target_sets.items()}
        care_metric = _nearest(x, y, care_targets)
        network_row = network.get(mesh)
        plateau_row = plateau.get(mesh)
        future_row = future.get(mesh)
        future_values = {
            year: (_number(future_row["years"].get(year), 4) if future_row else None)
            for year in (2025, 2050, 2070)
        }
        activity_row = activity.get(mesh)
        network_transport = (
            _number(network_row.get("network_transport_weighted_mean_distance_m"))
            if network_row is not None
            else None
        )
        old_medical_network = (
            _number(network_row.get("network_medical_weighted_mean_distance_m"))
            if network_row is not None
            else None
        )
        properties = {
            "feature_id": f"{city_id}:{mesh}",
            "city_id": city_id,
            "city_code": config["city_code"],
            "city_name": config["city_name"],
            "urban_state": config["urban_state"],
            "mesh_code": mesh,
            "city_area_fraction": _number(row.city_area_fraction, 8),
            "centroid_within_city": bool(row.centroid_within_city),
            "census_2020": {
                "population": _number(row.population),
                "elderly_population": _number(row.elderly_population),
                "disclosure_status": row.disclosure_status,
                "eligible_for_candidate_rules": bool(row.primary_eligible_disclosure),
            },
            "plateau_spatial_model": {
                "dataset_year": 2025,
                "version": 5,
                "mesh_link_method": "exact JIS 500m mesh aggregate",
                "building_context_status": "available"
                if plateau_row is not None
                else "no_residential_building_aggregate",
                "residential_building_count": _number(plateau_row.get("residential_building_count"))
                if plateau_row is not None
                else None,
                "estimated_population_allocated": _number(
                    plateau_row.get("estimated_population_allocated")
                )
                if plateau_row is not None
                else None,
                "value_semantics": "modeled building allocation, not an observed building population",
            },
            "medical_access_v2": {
                "analysis_tier": "BASE",
                "reference_date": "2026-06-01",
                "distance_method": f"mesh centroid to published point in {config['analysis_crs']}",
                "straight_line": medical_metrics,
                "experimental_network_p04_2020": {
                    "status": "available_context_only_not_same_destination_dataset"
                    if old_medical_network is not None
                    else "unavailable_for_mesh",
                    "weighted_mean_distance_m": old_medical_network,
                    "destination_source": "MLIT P04 2020, not MHLW 2026",
                    "comparable_with_mhlw_straight_line": False,
                },
                "official_pedestrian_network": {
                    "status": "unavailable",
                    "reason": "outside_coverage",
                },
                "current_acceptance": "unknown",
                "claim_boundary": "distance context, not travel time, acceptance, capacity, shortage or priority",
            },
            "care_access": {
                "analysis_tier": "BASE",
                "reference_date": "2026-06-30",
                "nearest_establishment": care_metric,
                "experimental_plateau_network_transport_context": {
                    "status": "available"
                    if network_transport is not None
                    else "unavailable_for_mesh",
                    "weighted_mean_distance_m": network_transport,
                    "semantics": "experimental road graph to transport, not pedestrian or care-facility travel",
                },
                "current_capacity": "unknown",
                "user_eligibility": "unknown",
                "social_participation": {
                    "status": "unavailable",
                    "reason": "no_qualified_official_source",
                },
                "claim_boundary": "review context, not care shortage, demand, vacancy, eligibility or priority",
            },
            "future_population_spatial": {
                "analysis_tier": "BASE",
                "source_status": "official_trial_projection_not_observation"
                if future_row
                else "no_published_250m_cell_in_audited_mesh",
                "published_250m_cell_count": future_row["published_250m_cell_count"]
                if future_row
                else 0,
                "population_before_privacy_aggregation_internal_only": future_values,
                "change_percent": {
                    "2050_vs_2025": _change_percent(future_values[2050], future_values[2025]),
                    "2070_vs_2025": _change_percent(future_values[2070], future_values[2025]),
                },
                "automatic_best_scenario_selected": False,
                "public_distribution": False,
                "claim_boundary": "official trial projection, not observation or guaranteed forecast",
            },
            "daytime_activity_context": {
                "analysis_tier": "BASE",
                **(
                    activity_row
                    or {
                        "reference_year": 2021,
                        "employees_all_industries": None,
                        "establishments_all_industries": None,
                        "employees_medical_welfare": None,
                        "status": "no_published_activity_record_in_audited_mesh",
                    }
                ),
                "separate_service_context": {
                    "mhlw_general_medical_straight_line_distance_m": medical_metrics[
                        "general_medical"
                    ]["distance_m"],
                    "p11_2022_transport_straight_line_distance_m": _number(
                        row.nearest_public_transport_distance_m
                    ),
                },
                "employees_are_daytime_population": False,
                "claim_boundary": "employees are activity context, not daytime population, demand, congestion or shortage",
            },
            "earthquake_ground_context": ground.get(
                mesh,
                {
                    "reference_year": 2020,
                    "published_250m_cell_count": 0,
                    "status": "no_published_jshis_cell_in_audited_mesh",
                },
            ),
            "historical_traffic_safety_context": accidents.get(
                mesh,
                {
                    "event_record_count": 0,
                    "fatalities": 0,
                    "injuries": 0,
                    "occurrence_years": [],
                    "annual_file_year": 2024,
                    "status": "no_linked_historical_injury_fatal_accident_record",
                },
            ),
        }
        feature = {
            "type": "Feature",
            "id": properties["feature_id"],
            "geometry": mapping(row.geometry),
            "properties": properties,
        }
        features.append(feature)
        metric_rows.append(
            {
                "feature": feature,
                "mesh": mesh,
                "eligible": bool(row.primary_eligible_disclosure),
                "population": _number(row.population),
                "elderly": _number(row.elderly_population),
                "medical_distance": medical_metrics["general_medical"]["distance_m"],
                "care_distance": care_metric["distance_m"],
                "network_transport": network_transport,
                "employees": activity_row["employees_all_industries"] if activity_row else None,
                "transport_distance": _number(row.nearest_public_transport_distance_m),
            }
        )

    eligible = [row for row in metric_rows if row["eligible"]]
    activity_rows = [row for row in metric_rows if row["employees"] is not None]
    thresholds = {
        "medical": {
            "population_median": _percentile(
                [float(row["population"]) for row in eligible if row["population"] is not None], 50
            ),
            "distance_p75_m": _percentile(
                [
                    float(row["medical_distance"])
                    for row in eligible
                    if row["medical_distance"] is not None
                ],
                75,
            ),
        },
        "care": {
            "elderly_p65": _percentile(
                [float(row["elderly"]) for row in eligible if row["elderly"] is not None], 65
            ),
            "distance_p65_m": _percentile(
                [
                    float(row["care_distance"])
                    for row in eligible
                    if row["care_distance"] is not None
                ],
                65,
            ),
            "network_transport_median_m": _percentile(
                [
                    float(row["network_transport"])
                    for row in eligible
                    if row["network_transport"] is not None
                ],
                50,
            ),
        },
        "activity": {
            "employees_p75": _percentile([float(row["employees"]) for row in activity_rows], 75),
            "medical_distance_p75_m": _percentile(
                [
                    float(row["medical_distance"])
                    for row in activity_rows
                    if row["medical_distance"] is not None
                ],
                75,
            ),
            "transport_distance_p75_m": _percentile(
                [
                    float(row["transport_distance"])
                    for row in activity_rows
                    if row["transport_distance"] is not None
                ],
                75,
            ),
        },
    }
    findings = []
    for row in metric_rows:
        finding_specs = []
        if (
            row["eligible"]
            and row["population"] is not None
            and row["medical_distance"] is not None
            and row["population"] >= thresholds["medical"]["population_median"]
            and row["medical_distance"] >= thresholds["medical"]["distance_p75_m"]
        ):
            finding_specs.append(
                (
                    "accessibility_gap",
                    "medical_access_review_candidate",
                    "医療アクセス現地確認候補",
                    {
                        "population": row["population"],
                        "straight_line_distance_m": row["medical_distance"],
                    },
                    thresholds["medical"],
                    ["e-Stat census 2020", "MHLW medical 2026", "PLATEAU 2025"],
                )
            )
        if (
            row["eligible"]
            and row["elderly"] is not None
            and row["care_distance"] is not None
            and row["network_transport"] is not None
            and row["elderly"] >= thresholds["care"]["elderly_p65"]
            and row["care_distance"] >= thresholds["care"]["distance_p65_m"]
            and row["network_transport"] >= thresholds["care"]["network_transport_median_m"]
        ):
            finding_specs.append(
                (
                    "care_access_review_candidate",
                    "care_access_review_candidate",
                    "介護アクセス現地確認候補",
                    {
                        "elderly_population": row["elderly"],
                        "straight_line_distance_m": row["care_distance"],
                        "experimental_transport_network_distance_m": row["network_transport"],
                    },
                    thresholds["care"],
                    ["e-Stat census 2020", "MHLW care 2026", "PLATEAU 2025 experimental graph"],
                )
            )
        weak_service_context = (
            row["medical_distance"] is not None
            and row["medical_distance"] >= thresholds["activity"]["medical_distance_p75_m"]
        ) or (
            row["transport_distance"] is not None
            and row["transport_distance"] >= thresholds["activity"]["transport_distance_p75_m"]
        )
        if (
            row["employees"] is not None
            and row["employees"] >= thresholds["activity"]["employees_p75"]
            and weak_service_context
        ):
            finding_specs.append(
                (
                    "activity_service_gap_candidate",
                    "activity_service_gap_candidate",
                    "活動・サービス文脈確認候補",
                    {
                        "published_employees": row["employees"],
                        "medical_straight_line_distance_m": row["medical_distance"],
                        "transport_straight_line_distance_m": row["transport_distance"],
                    },
                    thresholds["activity"],
                    ["Economic Census 2021", "MHLW medical 2026", "MLIT P11 2022"],
                )
            )
        for (
            finding_type,
            subtype,
            title,
            metrics,
            applied_thresholds,
            contributions,
        ) in finding_specs:
            finding_id = _finding_id(city_id, subtype, row["mesh"])
            findings.append(
                {
                    "finding_id": finding_id,
                    "finding_type": finding_type,
                    "finding_subtype": subtype,
                    "city_id": city_id,
                    "city_code": config["city_code"],
                    "urban_state": config["urban_state"],
                    "mesh_code": row["mesh"],
                    "related_feature_id": row["feature"]["id"],
                    "title": title,
                    "summary": "独立した閾値条件に該当した未検証の追加調査候補です。",
                    "status": "new",
                    "validation_status": "unvalidated",
                    "review_required": True,
                    "investigation_id": None,
                    "decision_id": None,
                    "metrics": metrics,
                    "thresholds": {
                        key: _number(value) for key, value in applied_thresholds.items()
                    },
                    "threshold_scope": f"within {city_id}; not comparable across cities",
                    "source_contributions": contributions,
                    "combined_score": None,
                    "priority_rank": None,
                    "claim_boundary": "review candidate only; not a shortage, risk, recommendation, or administrative priority",
                }
            )

    finding_counts = Counter(finding["finding_subtype"] for finding in findings)
    city_summary = {
        "city_id": city_id,
        "city_code": config["city_code"],
        "city_name": config["city_name"],
        "urban_state": config["urban_state"],
        "mesh_count": len(features),
        "analysis_crs": config["analysis_crs"],
        "facility_counts": {
            "medical": len(medical),
            "care_deduplicated_establishments": len(care),
        },
        "plateau_link_coverage": _spatial_link_coverage(health, config["city_code"]),
        "accident_coverage": accident_coverage,
        "finding_counts": dict(sorted(finding_counts.items())),
        "thresholds": {
            family: {key: _number(value) for key, value in values.items()}
            for family, values in thresholds.items()
        },
        "context_only_no_finding_types": [
            "earthquake_ground_context",
            "historical_traffic_safety_context",
            "future_population_spatial",
        ],
    }
    return features, sorted(findings, key=lambda item: item["finding_id"]), city_summary


def _analysis_availability() -> list[dict[str, Any]]:
    catalog = {definition.analysis_id: definition for definition in ANALYSIS_CATALOG}
    result = []
    for analysis_id in ANALYSIS_IDS:
        definition = catalog[analysis_id]
        evaluation = evaluate_analysis_tier(definition, AVAILABLE_FAMILIES)
        result.append(
            {
                "analysis_id": analysis_id,
                "algorithm_version": definition.algorithm_version,
                "tier": evaluation.tier.value,
                "missing_required": list(evaluation.missing_required),
                "missing_optional": list(evaluation.missing_optional),
                "missing_enhancement": list(evaluation.missing_enhancement),
                "claim_boundary": definition.claim_boundary,
            }
        )
    return result


def _source_timeline(city_summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "source_family": "census_population",
            "reference_period": "2020",
            "role": "observed mesh population and disclosure controls",
        },
        {
            "source_family": "jshis_surface_ground",
            "reference_period": "2020",
            "role": "modeled ground context",
        },
        {
            "source_family": "economic_census",
            "reference_period": "2021",
            "role": "establishment and employee observations; employees are not daytime population",
        },
        {
            "source_family": "mlit_p11_transport_points",
            "reference_period": "2022",
            "role": "straight-line transport-point context",
        },
        {
            "source_family": "npa_traffic_accident",
            "reference_period": "2023/2024 occurrence dates in 2024 annual file",
            "role": "historical injury/fatal accident context",
            "unmatched_records": city_summary["accident_coverage"][
                "unmatched_to_audited_mesh_count"
            ],
        },
        {
            "source_family": "plateau",
            "reference_period": "2025",
            "role": "primary spatial model and experimental graph context",
        },
        {
            "source_family": "mlit_future_population",
            "reference_period": "2025/2050/2070 official trial projection years",
            "role": "internal 250m-to-500m spatial comparison",
        },
        {
            "source_family": "mhlw_medical",
            "reference_period": "2026-06-01",
            "role": "published facility and department snapshot; current acceptance unknown",
        },
        {
            "source_family": "mhlw_care",
            "reference_period": "2026-06-30",
            "role": "published establishment snapshot; current capacity and eligibility unknown",
        },
    ]


def build() -> dict[str, Any]:
    health = _records(HEALTH)
    demographic = _records(DEMOGRAPHIC)
    resilience = _records(RESILIENCE)
    all_features = []
    all_findings = []
    city_summaries = {}
    for city_id, config in CITY_CONFIGS.items():
        features, findings, summary = _city_analysis(
            city_id, config, health, demographic, resilience
        )
        all_features.extend(features)
        all_findings.extend(findings)
        city_summaries[city_id] = summary

    availability = _analysis_availability()
    feature_collection = {
        "type": "FeatureCollection",
        "schema_version": "municipal-open-data-analysis-1.0.0",
        "algorithm_version": ALGORITHM_VERSION,
        "data_classification": "internal",
        "public_distribution": False,
        "generated_from_synthetic_data": False,
        "feature_count": len(all_features),
        "features": sorted(all_features, key=lambda item: item["id"]),
    }
    _write_json(ANALYSIS_OUTPUT, feature_collection)
    findings_artifact = {
        "schema_version": "municipal-open-data-findings-1.0.0",
        "algorithm_version": ALGORITHM_VERSION,
        "generated_from_synthetic_data": False,
        "finding_count": len(all_findings),
        "automatic_investigation_creation": False,
        "automatic_decision_creation": False,
        "findings": sorted(all_findings, key=lambda item: item["finding_id"]),
    }
    _write_json(FINDINGS_OUTPUT, findings_artifact)

    input_artifacts = [
        HEALTH,
        OPEN_DATA / "mhlw_health_source_report.json",
        DEMOGRAPHIC,
        OPEN_DATA / "demographic_economic_source_report.json",
        RESILIENCE,
        OPEN_DATA / "geospatial_resilience_source_report.json",
        *(config["meshes"] for config in CITY_CONFIGS.values()),
        *(config["network"] for config in CITY_CONFIGS.values()),
        *(config["plateau"] for config in CITY_CONFIGS.values()),
    ]
    raw_hashes = sorted(
        {
            (record.get("source") or record.get("provenance") or {}).get("raw_sha256")
            for record in health + demographic + resilience
            if (record.get("source") or record.get("provenance") or {}).get("raw_sha256")
        }
    )
    source_contributions = [
        {
            "analysis_id": "medical-access-v2",
            "sources": [
                "e-Stat census 2020",
                "MHLW medical 2026",
                "PLATEAU 2025",
                "experimental graph/P04 2020 shown separately",
            ],
        },
        {
            "analysis_id": "care-access",
            "sources": [
                "e-Stat census 2020",
                "MHLW care 2026",
                "PLATEAU 2025",
                "experimental transport graph context",
            ],
        },
        {
            "analysis_id": "future-population-spatial",
            "sources": [
                "MLIT R6 official trial projection 250m",
                "audited 500m mesh",
                "PLATEAU spatial context",
            ],
        },
        {
            "analysis_id": "daytime-activity-context",
            "sources": ["Economic Census 2021", "MHLW medical 2026", "MLIT P11 2022"],
        },
        {
            "analysis_id": "earthquake-ground-context",
            "sources": ["J-SHIS V4 2020", "audited 500m mesh"],
        },
        {
            "analysis_id": "historical-traffic-safety-context",
            "sources": ["NPA 2024 annual file", "audited 500m mesh"],
        },
    ]
    evidence_package = {
        "cities": [
            {"city_id": city_id, "city_code": config["city_code"], "city_name": config["city_name"]}
            for city_id, config in CITY_CONFIGS.items()
        ],
        "urban_states": [config["urban_state"] for config in CITY_CONFIGS.values()],
        "source_timeline": {
            city_id: _source_timeline(city_summaries[city_id]) for city_id in CITY_CONFIGS
        },
        "analyses": availability,
        "findings": all_findings,
        "source_contributions": source_contributions,
        "lineage": {
            "algorithm_version": ALGORITHM_VERSION,
            "input_artifact_sha256": {
                str(path.relative_to(ROOT)): _sha256(path) for path in input_artifacts
            },
            "canonical_raw_sha256": raw_hashes,
            "analysis_artifact_sha256": _sha256(ANALYSIS_OUTPUT),
            "findings_artifact_sha256": _sha256(FINDINGS_OUTPUT),
        },
        "missing_data": [
            {
                "dataset_family": "official_pedestrian_network",
                "cities": list(CITY_CONFIGS),
                "status": "unavailable",
                "reason": "outside_coverage",
            },
            {
                "dataset_family": "social_participation",
                "cities": list(CITY_CONFIGS),
                "status": "unavailable",
                "reason": "no_qualified_official_source",
            },
            {
                "dataset_family": "traffic_volume",
                "cities": list(CITY_CONFIGS),
                "status": "unavailable",
                "reason": "no_stable_matching_snapshot",
            },
            {
                "dataset_family": "gtfs",
                "cities": list(CITY_CONFIGS),
                "status": "unavailable",
                "reason": "not_published",
            },
            {
                "dataset_family": "gsi_foundation_map",
                "cities": list(CITY_CONFIGS),
                "status": "requires_review",
                "reason": "credentials_and_survey_act_review",
            },
        ],
        "limitations": [
            "No universal quality, need, risk, or priority score is calculated.",
            "MHLW point coordinates do not declare their horizontal datum; straight-line results require review.",
            "The PLATEAU road graph is experimental and is not an official pedestrian network.",
            "Employees are not treated as daytime population.",
            "J-SHIS model values and historical accident counts do not create risk findings.",
            "Mixed reference years remain visible and are not interpolated into a common date.",
        ],
        "review_status": "unvalidated_review_candidates",
        "human_workflow": {
            "investigations_created": False,
            "decisions_created": False,
            "investigation_templates": [
                {
                    "city_id": city_id,
                    "creation_status": "not_created_requires_human",
                    "related_finding_ids": [
                        finding["finding_id"]
                        for finding in all_findings
                        if finding["city_id"] == city_id
                    ],
                    "source_timeline_included": True,
                }
                for city_id in CITY_CONFIGS
            ],
            "next_action": "authorized municipal user explicitly triages a finding before creating an investigation",
        },
        "public_distribution": False,
    }
    evidence = export_open_data_evidence(
        evidence_package, OPEN_DATA, package_key="municipal_open_data"
    )
    summary = {
        "schema_version": "municipal-open-data-analysis-summary-1.0.0",
        "algorithm_version": ALGORITHM_VERSION,
        "generated_from_synthetic_data": False,
        "public_distribution": False,
        "mesh_count": len(all_features),
        "finding_count": len(all_findings),
        "cities": city_summaries,
        "analysis_availability": availability,
        "source_contributions": source_contributions,
        "quality_model": {
            "single_quality_score": False,
            "dimensions": [
                "source authority",
                "temporal fitness",
                "spatial linkage",
                "schema validity",
                "claim boundary",
            ],
        },
        "artifacts": {
            str(ANALYSIS_OUTPUT.relative_to(ROOT)): _sha256(ANALYSIS_OUTPUT),
            str(FINDINGS_OUTPUT.relative_to(ROOT)): _sha256(FINDINGS_OUTPUT),
            str(evidence.manifest_path.relative_to(ROOT)): evidence.sha256["json"],
            str(evidence.csv_path.relative_to(ROOT)): evidence.sha256["csv"],
            str(evidence.html_path.relative_to(ROOT)): evidence.sha256["html"],
        },
    }
    _write_json(SUMMARY_OUTPUT, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2, sort_keys=True))
