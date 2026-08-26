"""Build the small, privacy-safe map package used by the municipal Workspace.

The public package is intentionally limited to the two reviewed story plans.
It contains affected building *locations* and improvement bands, never the
building-level population estimates used internally by the optimizer.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point, mapping
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "analysis/outputs/real"
PUBLIC = ROOT / "frontend/public/data"
STORY_PATH = PUBLIC / "network_scenario_story.json"
WORKSPACE_STORY_PATH = PUBLIC / "municipal_workspace_story.json"
FULL_SCENARIOS_PATH = REAL / "maizuru_network_scenarios.json"
OUTPUT_PATH = PUBLIC / "network_scenario_map.geojson"
BUILDING_POINTS_PATH = PUBLIC / "network_scenario_building_points.json"
MANIFEST_PATH = REAL / "maizuru_municipal_workspace_manifest.json"

NETWORK_PATH = REAL / "maizuru_building_network_accessibility.parquet"
DEMOGRAPHICS_PATH = REAL / "maizuru_building_demographics.parquet"
GAINS_PATH = REAL / "maizuru_network_scenario_candidate_gains.parquet"
NODES_PATH = REAL / "maizuru_road_graph_nodes.parquet"
CANDIDATE_CONTEXT_PATH = REAL / "maizuru_scenario_candidate_context.parquet"

CONTEXT_SOURCES = {
    "landuse": (REAL / "maizuru_plateau_landuse.parquet", "landuse_context"),
    "planning": (
        REAL / "maizuru_plateau_urban_planning.parquet",
        "planning_context",
    ),
    "hazard": (REAL / "maizuru_plateau_hazards.parquet", "hazard_context"),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _clean(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        value = value.item()
    return value


def _feature(geometry: Any, properties: dict[str, Any], feature_id: str) -> dict[str, Any]:
    return {
        "type": "Feature",
        "id": feature_id,
        "geometry": mapping(geometry),
        "properties": {key: _clean(value) for key, value in properties.items()},
    }


def _improvement_band(value: float) -> tuple[str, str]:
    if value >= 500:
        return "500_plus", "500m以上"
    if value >= 250:
        return "250_499", "250–499m"
    return "under_250", "250m未満"


def _affected_buildings(
    story: dict[str, Any],
    network: pd.DataFrame,
    building_points: pd.DataFrame,
    gains: pd.DataFrame,
) -> list[dict[str, Any]]:
    selected = {site["candidate_id"] for site in story["sites"]}
    selected_gains = gains.loc[gains.candidate_id.isin(selected)].copy()
    if selected_gains.empty:
        raise ValueError(f"No sparse gains found for {story['plan_id']}")
    best_rows = selected_gains.loc[
        selected_gains.groupby("demand_node_id").distance_reduction_m.idxmax()
    ].rename(columns={"candidate_id": "assigned_site_id", "demand_node_id": "node_id"})
    affected = (
        network[["gml_id", "node_id"]]
        .merge(
            best_rows[["node_id", "assigned_site_id", "distance_reduction_m"]],
            on="node_id",
            how="inner",
            validate="many_to_one",
        )
        .merge(building_points, on="gml_id", how="inner", validate="one_to_one")
    )
    affected = affected.loc[affected.distance_reduction_m.gt(0)].sort_values("gml_id")
    expected = int(story["impact"]["improved_building_count"])
    if len(affected) != expected:
        raise ValueError(
            f"{story['plan_id']} affected building count {len(affected):,} != report {expected:,}"
        )

    features: list[dict[str, Any]] = []
    for feature_index, row in enumerate(affected.itertuples(index=False), start=1):
        band, _ = _improvement_band(float(row.distance_reduction_m))
        features.append(
            _feature(
                Point(float(row.longitude), float(row.latitude)),
                {
                    "layer_type": "affected_building",
                    "story_id": story["story_id"],
                    "distance_reduction_band": band,
                },
                f"{story['story_id']}:building:{feature_index}",
            )
        )
    return features


def _scenario_sites(story: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _feature(
            Point(float(site["longitude"]), float(site["latitude"])),
            {
                "layer_type": "scenario_site",
                "story_id": story["story_id"],
                "plan_id": story["plan_id"],
                "site_order": site["site_order"],
                "candidate_id": site["candidate_id"],
                "road_gml_id": site["road_gml_id"],
                "road_name": site.get("road_name"),
                "siting_feasibility": site["siting_feasibility"],
                "hazard_review_status": site["hazard_review_status"],
            },
            f"{story['story_id']}:site:{site['site_order']}",
        )
        for site in story["sites"]
    ]


def _representative_routes(
    story: dict[str, Any], nodes_wgs84: gpd.GeoDataFrame
) -> list[dict[str, Any]]:
    evidence = story["representative_evidence"]
    indexed = nodes_wgs84.set_index("node_id", drop=False)
    features: list[dict[str, Any]] = []
    for route_kind in ("before", "after"):
        route = evidence[route_kind]
        node_ids = route["road_node_sequence"]
        missing = [node_id for node_id in node_ids if node_id not in indexed.index]
        if missing:
            raise ValueError(f"Missing route nodes for {story['plan_id']}: {missing[:3]}")
        coordinates = [
            (float(indexed.loc[node_id].geometry.x), float(indexed.loc[node_id].geometry.y))
            for node_id in node_ids
        ]
        if len(coordinates) < 2:
            raise ValueError(f"Representative {route_kind} route has fewer than two nodes")
        features.append(
            _feature(
                LineString(coordinates),
                {
                    "layer_type": "representative_route",
                    "story_id": story["story_id"],
                    "plan_id": story["plan_id"],
                    "route_kind": route_kind,
                    "network_distance_m": route["network_distance_m"],
                    "route_semantics": evidence["route_semantics"],
                    "destination_name": route.get("destination_name"),
                    "virtual_candidate_id": route.get("virtual_scenario_candidate_id"),
                },
                f"{story['story_id']}:route:{route_kind}",
            )
        )
    origin = evidence["origin_representative_point"]
    features.append(
        _feature(
            Point(float(origin["longitude"]), float(origin["latitude"])),
            {
                "layer_type": "representative_building",
                "story_id": story["story_id"],
                "plan_id": story["plan_id"],
                "building_gml_id": evidence["building_gml_id"],
                "before_network_distance_m": evidence["before"]["network_distance_m"],
                "after_network_distance_m": evidence["after"]["network_distance_m"],
                "route_semantics": evidence["route_semantics"],
                "privacy": "no per-building person estimate exported",
            },
            f"{story['story_id']}:representative-building",
        )
    )
    return features


def _context_label(context_type: str, row: pd.Series) -> str:
    candidates = {
        "landuse": ("class_label",),
        "planning": ("planning_label", "function_label", "name"),
        "hazard": (
            "rank_label",
            "description_label",
            "area_type_label",
            "name",
            "hazard_type",
        ),
    }[context_type]
    for key in candidates:
        value = _clean(row.get(key))
        if isinstance(value, str) and value.strip():
            return value
    return "公式属性に表示名なし"


def _scenario_context(
    story: dict[str, Any],
    candidate_context: pd.DataFrame,
    context_frames: dict[str, gpd.GeoDataFrame],
) -> list[dict[str, Any]]:
    selected_sites = {site["candidate_id"]: site for site in story["sites"]}
    selected = candidate_context.loc[
        candidate_context.candidate_id.isin(selected_sites)
    ].copy()
    if selected.empty:
        raise ValueError(f"No PLATEAU context found for {story['plan_id']}")
    point_buffers = [
        Point(float(site["candidate_x"]), float(site["candidate_y"])).buffer(700)
        for site in selected.drop_duplicates("candidate_id").to_dict("records")
    ]
    clipping_area = unary_union(point_buffers)
    features: list[dict[str, Any]] = []

    for context_type, (_, layer_type) in CONTEXT_SOURCES.items():
        references = selected.loc[selected.context_type.eq(context_type)]
        if references.empty:
            continue
        frame = context_frames[context_type]
        indexed = frame.set_index("gml_id", drop=False)
        missing = sorted(set(references.gml_id) - set(indexed.index))
        if missing:
            raise ValueError(f"Missing {context_type} source features: {missing[:3]}")
        for gml_id in sorted(set(references.gml_id)):
            row = indexed.loc[gml_id]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            geometry = row.geometry.intersection(clipping_area)
            if geometry.is_empty:
                continue
            geometry = geometry.simplify(2, preserve_topology=True)
            wgs84 = gpd.GeoSeries([geometry], crs=frame.crs).to_crs(4326).iloc[0]
            site_orders = sorted(
                selected_sites[candidate_id]["site_order"]
                for candidate_id in references.loc[
                    references.gml_id.eq(gml_id), "candidate_id"
                ].unique()
            )
            features.append(
                _feature(
                    wgs84,
                    {
                        "layer_type": layer_type,
                        "context_type": context_type,
                        "story_id": story["story_id"],
                        "plan_id": story["plan_id"],
                        "plateau_gml_id": gml_id,
                        "label": _context_label(context_type, row),
                        "hazard_type": row.get("hazard_type"),
                        "source_member": row.get("source_gml"),
                        "source_member_crc32": row.get("source_member_crc32"),
                        "site_orders": ",".join(str(value) for value in site_orders),
                        "interpretation": "review context; not an automatic siting decision",
                    },
                    f"{story['story_id']}:{context_type}:{gml_id}",
                )
            )
    return features


def build() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    competition_story = json.loads(STORY_PATH.read_text(encoding="utf-8"))
    full_scenarios = json.loads(FULL_SCENARIOS_PATH.read_text(encoding="utf-8"))
    robust_plan = {
        key: value
        for key, value in full_scenarios["plans"]["robust"]["3"].items()
        if key != "mesh_results"
    }
    story_report = {
        **competition_story,
        "source": (
            "three selected static municipal alternatives from "
            "maizuru_network_scenarios.json; competition story remains A/B"
        ),
        "scenario_story": [
            *competition_story["scenario_story"],
            {"story_id": "scenario_c", **robust_plan},
        ],
    }
    WORKSPACE_STORY_PATH.write_text(
        json.dumps(story_report, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    stories = story_report["scenario_story"]
    if [story["story_id"] for story in stories] != [
        "scenario_a",
        "scenario_b",
        "scenario_c",
    ]:
        raise ValueError("The Workspace must contain the selected A/B/C alternatives")

    network = pd.read_parquet(NETWORK_PATH)
    demographics = pd.read_parquet(DEMOGRAPHICS_PATH)
    building_points = (
        demographics.sort_values(["gml_id", "allocation_fraction"], ascending=[True, False])
        .drop_duplicates("gml_id")[["gml_id", "longitude", "latitude"]]
    )
    gains = pd.read_parquet(GAINS_PATH)
    nodes = gpd.read_parquet(NODES_PATH).to_crs(4326)
    candidate_context = pd.read_parquet(CANDIDATE_CONTEXT_PATH)
    context_frames = {
        context_type: gpd.read_parquet(path)
        for context_type, (path, _) in CONTEXT_SOURCES.items()
    }
    for context_type, frame in context_frames.items():
        if frame.crs is None:
            raise ValueError(f"{context_type} context has no declared CRS")

    features: list[dict[str, Any]] = []
    for story in stories:
        features.extend(_affected_buildings(story, network, building_points, gains))
        features.extend(_scenario_sites(story))
        features.extend(_representative_routes(story, nodes))
        features.extend(_scenario_context(story, candidate_context, context_frames))

    affected = [
        feature for feature in features if feature["properties"]["layer_type"] == "affected_building"
    ]
    map_features = [
        feature for feature in features if feature["properties"]["layer_type"] != "affected_building"
    ]
    layer_counts = Counter(feature["properties"]["layer_type"] for feature in map_features)
    story_counts = Counter(feature["properties"]["story_id"] for feature in map_features)
    band_codes = {"under_250": 0, "250_499": 1, "500_plus": 2}
    building_points = {
        "schema_version": "municipal-workspace-building-points-1.0.0",
        "generated_at": story_report["generated_at"],
        "privacy": "locations and distance bands only; no IDs, exact distances or person estimates",
        "band_codes": {str(code): band for band, code in band_codes.items()},
        "stories": {
            story["story_id"]: [
                [
                    round(float(feature["geometry"]["coordinates"][0]), 7),
                    round(float(feature["geometry"]["coordinates"][1]), 7),
                    band_codes[feature["properties"]["distance_reduction_band"]],
                ]
                for feature in affected
                if feature["properties"]["story_id"] == story["story_id"]
            ]
            for story in stories
        },
    }
    collection = {
        "type": "FeatureCollection",
        "schema_version": "municipal-workspace-map-1.0.0",
        "generated_at": story_report["generated_at"],
        "source": "selected real Maizuru network scenarios and official PLATEAU context",
        "privacy": "building locations and distance bands only; no per-building person estimates",
        "layer_counts": dict(sorted(layer_counts.items())),
        "story_counts": dict(sorted(story_counts.items())),
        "features": map_features,
    }
    OUTPUT_PATH.write_text(
        json.dumps(collection, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    BUILDING_POINTS_PATH.write_text(
        json.dumps(building_points, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "municipal-workspace-manifest-1.0.0",
        "generated_at": story_report["generated_at"],
        "city_id": "26202",
        "story_plan_ids": [story["plan_id"] for story in stories],
        "public_workspace_story": {
            "path": str(WORKSPACE_STORY_PATH.relative_to(ROOT)),
            "sha256": _sha256(WORKSPACE_STORY_PATH),
            "bytes": WORKSPACE_STORY_PATH.stat().st_size,
            "scenario_count": len(stories),
        },
        "public_map": {
            "path": str(OUTPUT_PATH.relative_to(ROOT)),
            "sha256": _sha256(OUTPUT_PATH),
            "bytes": OUTPUT_PATH.stat().st_size,
            "feature_count": len(map_features),
            "layer_counts": dict(sorted(layer_counts.items())),
            "story_counts": dict(sorted(story_counts.items())),
        },
        "public_building_points": {
            "path": str(BUILDING_POINTS_PATH.relative_to(ROOT)),
            "sha256": _sha256(BUILDING_POINTS_PATH),
            "bytes": BUILDING_POINTS_PATH.stat().st_size,
            "point_count": len(affected),
            "story_counts": {
                key: len(value) for key, value in building_points["stories"].items()
            },
        },
        "privacy": collection["privacy"],
        "database_loaded": False,
        "database_note": "Static preview built from canonical artifacts; database load not executed here.",
        "source_files": {
            str(path.relative_to(ROOT)): _sha256(path)
            for path in (
                STORY_PATH,
                FULL_SCENARIOS_PATH,
                NETWORK_PATH,
                DEMOGRAPHICS_PATH,
                GAINS_PATH,
                NODES_PATH,
                CANDIDATE_CONTEXT_PATH,
                *(path for path, _ in CONTEXT_SOURCES.values()),
            )
        },
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return collection, building_points, manifest


if __name__ == "__main__":
    collection, building_points, manifest = build()
    print(
        f"wrote {manifest['public_map']['path']}: "
        f"{len(collection['features']):,} features; "
        f"{sum(len(points) for points in building_points['stories'].values()):,} building points; "
        f"{manifest['public_map']['bytes'] + manifest['public_building_points']['bytes']:,} bytes"
    )
