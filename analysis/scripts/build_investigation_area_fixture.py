"""Build the public West Maizuru 500m/800m Investigation Area fixture.

All values are derived from checked-in audited outputs. Missing categories stay
partial/unavailable; the script never fabricates field evidence.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from analysis.src.plateau_buildings import read_buildings

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "frontend/public/data"
REAL = ROOT / "analysis/outputs/real"
OPEN_DATA = REAL / "open_data"
OUTPUT = PUBLIC / "investigation_area_summary.json"
ANALYSIS_CRS = "EPSG:6674"
RULE_VERSION = "citygap-investigation-area@1.0.0"
SCHEMA_VERSION = "citygap.area-summary@1"
STATION_NAME = "西舞鶴駅"
RADII = (500, 800)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def plain(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def source(path: Path, dataset: str, source_date: str) -> dict[str, Any]:
    return {
        "dataset": dataset,
        "source_date": source_date,
        "artifact": str(path.relative_to(ROOT)),
        "sha256": sha256(path),
    }


def area_weight(frame: gpd.GeoDataFrame, area, value_column: str) -> tuple[float, float, int]:
    total = 0.0
    covered_area = 0.0
    records = 0
    for row in frame.itertuples():
        intersection_area = row.geometry.intersection(area).area
        if intersection_area <= 0:
            continue
        value = getattr(row, value_column)
        if pd.isna(value):
            continue
        ratio = min(1.0, intersection_area / row.geometry.area)
        total += float(value) * ratio
        covered_area += intersection_area
        records += 1
    return total, min(1.0, covered_area / area.area), records


def point_features(path: Path) -> gpd.GeoDataFrame:
    return gpd.read_file(path).to_crs(ANALYSIS_CRS)


def wgs_point(geometry) -> Point:
    return gpd.GeoSeries([geometry], crs=ANALYSIS_CRS).to_crs(4326).iloc[0]


def build() -> dict[str, Any]:
    mesh_path = PUBLIC / "mesh_metrics.geojson"
    economic_path = OPEN_DATA / "demographic_economic_mesh_context.geojson"
    building_path = ROOT / "data/raw/plateau_citygml/26202_maizuru-shi_city_2025_citygml_1_op.zip"
    usage_path = REAL / "maizuru_building_usage_audit.csv"
    planning_path = REAL / "maizuru_plateau_urban_planning.parquet"
    roads_path = REAL / "maizuru_road_graph_nodes.parquet"
    stations_path = PUBLIC / "stations.geojson"
    bus_path = PUBLIC / "bus_stops.geojson"
    medical_path = PUBLIC / "medical_facilities.geojson"
    boundary_path = PUBLIC / "maizuru_boundary.geojson"

    meshes = gpd.read_file(mesh_path).to_crs(ANALYSIS_CRS)
    economic = gpd.read_file(economic_path).to_crs(ANALYSIS_CRS)
    boundary = gpd.read_file(boundary_path).to_crs(ANALYSIS_CRS).geometry.union_all()
    stations = point_features(stations_path)
    buses = point_features(bus_path)
    medical = point_features(medical_path)
    station_row = stations.loc[stations["name"].eq(STATION_NAME)].iloc[0]
    station = station_row.geometry

    usage_mapping = pd.read_csv(usage_path, dtype={"usage_code": "string"})
    usage_labels = usage_mapping.set_index("usage_code")["official_label"]
    buildings = read_buildings(building_path)
    buildings = buildings.loc[
        buildings.geometry.notna() & ~buildings.geometry.is_empty
    ].copy()
    buildings["usage_code"] = buildings["usage"].astype("string")
    buildings["usage_label"] = buildings["usage_code"].map(usage_labels)
    buildings = (
        buildings.sort_values(["gml_id", "source_gml"])
        .drop_duplicates("gml_id")
        .to_crs(ANALYSIS_CRS)
    )
    planning = gpd.read_parquet(planning_path).to_crs(ANALYSIS_CRS)
    roads = gpd.read_parquet(roads_path).to_crs(ANALYSIS_CRS)

    sources = {
        "population": source(mesh_path, "2020国勢調査500mメッシュ", "2020-10-01"),
        "economic": source(economic_path, "2021経済センサス500mメッシュ", "2021-06-01"),
        "buildings": source(building_path, "PLATEAU舞鶴市建築物LOD0/1 footprint", "2020-01-01"),
        "planning": source(planning_path, "PLATEAU舞鶴市都市計画決定情報", "2020-01-01"),
        "transport": source(stations_path, "国土数値情報 鉄道データ", "2025-01-01"),
        "roads": source(roads_path, "PLATEAU舞鶴市道路LOD1", "2020-01-01"),
    }
    areas: list[dict[str, Any]] = []
    for radius in RADII:
        requested = station.buffer(radius, quad_segs=64)
        effective = requested.intersection(boundary)
        population, population_coverage, population_records = area_weight(
            meshes, effective, "population"
        )
        elderly, elderly_coverage, _ = area_weight(meshes, effective, "elderly_population")
        establishments, establishment_coverage, establishment_records = area_weight(
            economic, effective, "economic_establishments_all_a_s"
        )
        employee_count, _, _ = area_weight(economic, effective, "economic_employees_all_a_s")

        area_buildings = buildings.loc[buildings.geometry.intersects(effective)].copy()
        usage_counts = Counter(
            str(value) if pd.notna(value) else "用途属性なし"
            for value in area_buildings["usage_label"]
        )
        area_planning = planning.loc[planning.geometry.intersects(effective)].copy()
        planning_rows = []
        for row in area_planning.sort_values("gml_id").itertuples():
            clipped_area = row.geometry.intersection(effective).area
            if clipped_area <= 0:
                continue
            planning_rows.append(
                {
                    "gml_id": str(row.gml_id),
                    "label": plain(row.planning_label) or plain(row.name) or str(row.planning_type),
                    "building_coverage_rate": plain(row.building_coverage_rate),
                    "floor_area_rate": plain(row.floor_area_rate),
                    "clipped_area_m2": round(clipped_area, 1),
                }
            )
        planning_rows.sort(
            key=lambda item: (-item["clipped_area_m2"], item["gml_id"])
        )
        area_stations = stations.loc[stations.geometry.within(effective)]
        area_buses = buses.loc[buses.geometry.within(effective)]
        area_medical = medical.loc[medical.geometry.within(effective)]

        nearest_building = area_buildings.iloc[area_buildings.distance(station).argmin()]
        area_roads = roads.loc[roads.geometry.within(effective)]
        nearest_road = area_roads.iloc[area_roads.distance(station).argmin()]
        nearest_medical = (
            area_medical.iloc[area_medical.distance(station).argmin()]
            if len(area_medical)
            else None
        )
        containing_mesh = meshes.loc[meshes.geometry.covers(station)].iloc[0]
        unknowns = [
            {
                "id": "walking-connectivity",
                "title": "駅から周辺へ実際に歩いて通れる経路",
                "importance": f"半径{radius}mは分析上の目安で、横断・階段・通行制限を含む実際の到達性は判断できません。",
                "status": "unknown",
                "action_type": "field_verification",
                "reason_code": "model_limit",
                "source_boundary": "半径集計とPLATEAU LOD1道路面。validated pedestrian networkではありません。",
                "target": {
                    "scope": "plateau_object",
                    "object_type": "road",
                    "source_object_id": str(nearest_road.gml_id),
                    "label": "西舞鶴駅に近いPLATEAU道路面",
                    "longitude": round(float(wgs_point(nearest_road.geometry).x), 7),
                    "latitude": round(float(wgs_point(nearest_road.geometry).y), 7),
                    "dataset": sources["roads"]["dataset"],
                    "role": "primary",
                },
                "checks": [
                    "歩行者が連続して通れるか",
                    "横断箇所や通行制限があるか",
                    "階段・段差・狭窄があるか",
                    "迂回が必要な区間があるか",
                ],
            },
            {
                "id": "building-current-use",
                "title": "PLATEAU建物の現在の使われ方",
                "importance": "PLATEAU用途属性は基準時点の記録で、現在の利用や空き状況により周辺像の解釈が変わります。",
                "status": "unknown",
                "action_type": "field_verification",
                "reason_code": "source_time_limit",
                "source_boundary": "PLATEAU建物属性の基準時点と代表点。現在利用は含みません。",
                "target": {
                    "scope": "plateau_object",
                    "object_type": "building",
                    "source_object_id": str(nearest_building.gml_id),
                    "label": plain(nearest_building.usage_label) or "用途属性なしのPLATEAU建物",
                    "longitude": round(
                        float(wgs_point(nearest_building.geometry.representative_point()).x), 7
                    ),
                    "latitude": round(
                        float(wgs_point(nearest_building.geometry.representative_point()).y), 7
                    ),
                    "dataset": sources["buildings"]["dataset"],
                    "role": "primary",
                },
                "checks": [
                    "建物が現存しているか",
                    "現在利用されているか",
                    "表示された用途と現況が一致するか",
                    "入口や利用案内を確認できるか",
                    "周辺から安全にアクセスできるか",
                ],
            },
            {
                "id": "facility-availability",
                "title": "登録施設が現在も利用できるか",
                "importance": "公開データ上の登録地点だけでは、開設状況・時間帯・入口を判断できません。",
                "status": "unknown",
                "action_type": "field_verification",
                "reason_code": "requires_field_observation",
                "source_boundary": "公開施設台帳の登録地点。現在の営業・診療状態は含みません。",
                "target": (
                    {
                        "scope": "facility",
                        "object_type": "facility",
                        "source_object_id": str(nearest_medical.get("id", "medical-source-record")),
                        "label": str(nearest_medical.get("name", "範囲内の医療施設")),
                        "longitude": round(float(wgs_point(nearest_medical.geometry).x), 7),
                        "latitude": round(float(wgs_point(nearest_medical.geometry).y), 7),
                        "dataset": "国土数値情報 医療機関データ",
                        "role": "primary",
                    }
                    if nearest_medical is not None
                    else {
                        "scope": "mesh",
                        "object_type": "mesh",
                        "source_object_id": str(containing_mesh.mesh_code),
                        "label": "西舞鶴駅を含む500mメッシュ（施設object fallback）",
                        "longitude": round(float(wgs_point(station).x), 7),
                        "latitude": round(float(wgs_point(station).y), 7),
                        "dataset": sources["population"]["dataset"],
                        "role": "primary",
                    }
                ),
                "checks": [
                    "施設が現地に存在するか",
                    "現在利用できる状態か",
                    "利用時間や対象者の掲示があるか",
                    "閉鎖時は移転先の手掛かりがあるか",
                ],
            },
        ]
        methodology = (
            "mlit_elderly_walk_reference_500m"
            if radius == 500
            else "mlit_general_walk_reference_800m"
        )
        metrics = [
            {
                "key": "population",
                "group": "population",
                "label": "人口",
                "status": "known" if population_coverage >= 0.999 else "partial",
                "value": round(population),
                "unit": "人（面積按分推計）",
                "coverage_ratio": round(population_coverage, 4),
                "calculation": "area_weighted_estimate",
                "records": population_records,
                "source": sources["population"],
                "limitation": "500mメッシュ値をAOIとの面積重複率で按分。秘匿・欠損は0補完しません。",
            },
            {
                "key": "age_distribution",
                "group": "age_distribution",
                "label": "年齢分布",
                "status": "partial",
                "value": {"age_65_plus": round(elderly), "total": round(population)},
                "unit": "人（面積按分推計）",
                "coverage_ratio": round(min(population_coverage, elderly_coverage), 4),
                "calculation": "area_weighted_estimate",
                "source": sources["population"],
                "limitation": "P0公開値は総人口と65歳以上のみ。全年齢階級の分布ではありません。",
            },
            {
                "key": "building_use",
                "group": "building_use",
                "label": "建物用途分布",
                "status": "partial",
                "value": [
                    {"label": label, "count": count}
                    for label, count in usage_counts.most_common(5)
                ],
                "unit": "棟（footprint交差）",
                "coverage_ratio": None,
                "calculation": "observation_count",
                "source": sources["buildings"],
                "limitation": "PLATEAU建物footprintがAOIと交差するunique GML IDを公式用途属性で集計。現在用途は保証しません。",
            },
            {
                "key": "establishments",
                "group": "establishments",
                "label": "事業所",
                "status": "known" if establishment_coverage >= 0.999 else "partial",
                "value": {
                    "establishments": round(establishments),
                    "employees": round(employee_count),
                },
                "unit": "件・人（面積按分推計）",
                "coverage_ratio": round(establishment_coverage, 4),
                "calculation": "area_weighted_estimate",
                "records": establishment_records,
                "source": sources["economic"],
                "limitation": "2021経済センサスメッシュを面積按分。現時点の営業状況を示しません。",
            },
            {
                "key": "urban_planning",
                "group": "urban_planning",
                "label": "都市計画",
                "status": "partial" if planning_rows else "unavailable",
                "value": planning_rows[:8],
                "unit": "公式object",
                "coverage_ratio": None,
                "calculation": "exact",
                "source": sources["planning"],
                "limitation": "利用可能なPLATEAU都市計画objectのみ。自治体が必要とする制約項目を網羅するとは限りません。",
            },
            {
                "key": "transport",
                "group": "transport",
                "label": "交通",
                "status": "known",
                "value": {
                    "stations": len(area_stations),
                    "bus_stops": len(area_buses),
                },
                "unit": "登録地点",
                "coverage_ratio": 1,
                "calculation": "observation_count",
                "source": sources["transport"],
                "limitation": "駅・バス停のsource上の登録地点数。運行・利用可能性・徒歩到達性は含みません。医療施設は第一表示へ混在させません。",
            },
        ]
        geometry_wgs84 = gpd.GeoSeries([effective], crs=ANALYSIS_CRS).to_crs(4326).iloc[0]
        payload = {
            "id": f"nishi-maizuru-{radius}m-v1",
            "area_series_id": f"nishi-maizuru-radius-{radius}m",
            "version": 1,
            "label": f"西舞鶴駅周辺{radius}m",
            "geometry_kind": "point_radius",
            "origin": {
                "kind": "station",
                "source_feature_id": str(station_row["id"]),
                "label": STATION_NAME,
                "coordinates": [
                    round(float(wgs_point(station).x), 7),
                    round(float(wgs_point(station).y), 7),
                ],
            },
            "radius_m": radius,
            "radius_methodology": methodology,
            "clipped_area_ratio": round(effective.area / requested.area, 6),
            "effective_geometry": geometry_wgs84.__geo_interface__,
            "metrics": metrics,
            "unknowns": unknowns,
            "status": "unverified",
        }
        payload["content_sha256"] = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        areas.append(payload)

    return {
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "generated_from": "checked-in audited Maizuru outputs",
        "validation_status": {
            "aoi_need": "DIRECT_MUNICIPAL_NEED_CONFIRMED",
            "area_summary_content": "DIRECT_MUNICIPAL_NEED_PARTIALLY_CONFIRMED",
            "known_unknown_value": "DIRECT_MUNICIPAL_VALUE_SIGNAL_CONFIRMED",
            "unknown_to_field_task_workflow": "AWAITING_MUNICIPAL_WORKFLOW_REVIEW",
            "human": "AWAITING_HUMAN_TEST",
        },
        "area_summary_priority": [
            "population",
            "age_distribution",
            "building_use",
            "establishments",
            "urban_planning",
            "transport",
        ],
        "areas": areas,
    }


def main() -> None:
    result = build()
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT.relative_to(ROOT)} with {len(result['areas'])} areas")


if __name__ == "__main__":
    main()
