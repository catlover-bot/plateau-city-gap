"""Cross-validate experimental PLATEAU routes against pinned OSM references.

The comparison uses identical building origins and medical destinations.  OSM
is an independent ``reference_network`` and never a ground truth or a silent
replacement for the production model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml
from shapely.geometry import mapping
from shapely.ops import unary_union

import analysis.scripts.build_building_demographics as demographics_builder
from analysis.src.model_validation import (
    ALGORITHM_VERSION,
    REFERENCE_SEMANTICS,
    classify_disagreement_cause,
    comparison_statistics,
    multi_source_reference_destinations,
    read_osm_overpass_reference,
    reference_agreement,
    route_geometry,
    shortest_path,
    snap_points_to_reference_nodes,
)
from analysis.src.plateau_road_network import reconstruct_route
from analysis.src.spatial import boundary_from_plateau

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "analysis/outputs/real/validation/network_cross_validation.json"
PUBLIC_OUTPUT = ROOT / "frontend/public/data/validation/network_cross_validation.json"
PUBLIC_ROUTES = ROOT / "frontend/public/data/validation/network_disagreement_routes.geojson"
INTERNAL_DIR = ROOT / "analysis/outputs/real/validation/internal"

CITY_CONFIG: dict[str, dict[str, Any]] = {
    "maizuru": {
        "city_code": "26202",
        "city_name": "舞鶴市",
        "analysis_crs": "EPSG:6674",
        "config": ROOT / "analysis/config/maizuru.yaml",
        "osm": ROOT / "data/raw/osm_reference/maizuru-20260827-overpass.json",
        "osm_sha256": "1308277a253ca2cc4fb7b8d5883a78b7430be66a385210307092f0ee6401d71e",
        "bbox": [135.159264, 35.380036, 135.486869, 35.714472],
    },
    "fujisawa": {
        "city_code": "14205",
        "city_name": "藤沢市",
        "analysis_crs": "EPSG:6677",
        "config": ROOT / "analysis/config/fujisawa.yaml",
        "osm": ROOT / "data/raw/osm_reference/fujisawa-20260827-overpass.json",
        "osm_sha256": "1e5b637e583ca340cc1d29d5a382b4f594b5e42b68db7b6ddf873cd94031f9e2",
        "bbox": [139.393991, 35.296481, 139.516842, 35.429103],
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if pd.isna(value) or not np.isfinite(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any], *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    options = {"separators": (",", ":")} if compact else {"indent": 2, "sort_keys": True}
    path.write_text(json.dumps(_json_value(payload), ensure_ascii=False, **options) + "\n", encoding="utf-8")


def _load_facilities(city: str) -> gpd.GeoDataFrame:
    meta = CITY_CONFIG[city]
    config = yaml.safe_load(Path(meta["config"]).read_text(encoding="utf-8"))
    datasets = config["datasets"]
    demographics_builder.STATIONS = ROOT / datasets["stations"]["path"]
    demographics_builder.BUS_STOPS = ROOT / datasets["bus_stops"]["path"]
    demographics_builder.MEDICAL = ROOT / datasets["medical"]["path"]
    demographics_builder.ANALYSIS_CRS = meta["analysis_crs"]
    boundary_path = ROOT / datasets["boundary"]["path"]
    boundary = boundary_from_plateau(
        gpd.read_file(boundary_path).to_crs("EPSG:4326"),
        city_code=meta["city_code"],
        city_name=meta["city_name"],
    )
    source = demographics_builder._facilities(boundary)["medical"].to_crs(meta["analysis_crs"])
    source = source.reset_index(drop=True).copy()
    source["facility_name"] = source["name"].astype(str)
    source["facility_id"] = [
        f"medical::{index:04d}::{name}"
        for index, name in enumerate(source["facility_name"])
    ]
    return gpd.GeoDataFrame(
        source[["facility_id", "facility_name", "geometry"]],
        geometry="geometry",
        crs=meta["analysis_crs"],
    )


def _stable_sample_order(city: str, stratum: str, value: str) -> str:
    return hashlib.sha256(f"{city}|{stratum}|{value}".encode()).hexdigest()


def _sample_candidates(
    city: str,
    demographics: pd.DataFrame,
    access: pd.DataFrame,
    terrain: pd.DataFrame,
    facilities: gpd.GeoDataFrame,
) -> pd.DataFrame:
    meta = CITY_CONFIG[city]
    unique = demographics.sort_values(["gml_id", "mesh_code"]).drop_duplicates("gml_id")
    columns = [
        "gml_id",
        "longitude",
        "latitude",
        "estimated_elderly_population",
        "nearest_public_transport_distance_m",
        "nearest_medical_name",
    ]
    candidates = unique[columns].merge(access, on="gml_id", how="left", validate="one_to_one")
    candidates = candidates.merge(
        terrain[["gml_id", "medical_maximum_observed_absolute_grade_percent"]],
        on="gml_id",
        how="left",
        validate="one_to_one",
    )
    name_to_id = (
        facilities.sort_values("facility_id")
        .drop_duplicates("facility_name")
        .set_index("facility_name")["facility_id"]
    )
    candidates["destination_id"] = candidates["nearest_network_medical_id"]
    missing_destination = candidates["destination_id"].isna()
    candidates.loc[missing_destination, "destination_id"] = candidates.loc[
        missing_destination, "nearest_medical_name"
    ].map(name_to_id)
    projected = gpd.GeoDataFrame(
        candidates[["gml_id"]],
        geometry=gpd.points_from_xy(candidates["longitude"], candidates["latitude"]),
        crs="EPSG:4326",
    ).to_crs(meta["analysis_crs"])
    facility_geometry = facilities.set_index("facility_id").geometry
    candidates["euclidean_distance_m"] = [
        float(point.distance(facility_geometry.loc[destination])) if destination in facility_geometry.index else np.nan
        for point, destination in zip(projected.geometry, candidates["destination_id"], strict=True)
    ]
    candidates["detour_factor"] = (
        candidates["nearest_network_medical_distance_m"]
        / candidates["euclidean_distance_m"].replace(0, np.nan)
    )
    tsunami = gpd.read_parquet(
        ROOT / f"analysis/outputs/real/{city}_plateau_hazards.parquet"
    )
    tsunami = tsunami.loc[tsunami["hazard_type"].eq("tsunami")].to_crs(meta["analysis_crs"])
    tsunami_union = tsunami.geometry.union_all() if not tsunami.empty else None
    candidates["coastal_context_distance_m"] = (
        [float(point.distance(tsunami_union)) for point in projected.geometry]
        if tsunami_union is not None
        else np.nan
    )
    candidates = candidates.loc[candidates["destination_id"].notna()].copy()
    reachable = candidates["nearest_network_medical_distance_m"].dropna()
    q33, q67 = reachable.quantile([0.33, 0.67])
    pools: dict[str, pd.Series] = {
        "short_distance": candidates["nearest_network_medical_distance_m"].le(q33),
        "medium_distance": candidates["nearest_network_medical_distance_m"].between(q33, q67),
        "long_distance": candidates["nearest_network_medical_distance_m"].ge(q67),
        "coastal": candidates["coastal_context_distance_m"].le(
            max(500.0, float(candidates["coastal_context_distance_m"].quantile(0.10)))
        ),
        "mountainous": candidates["medical_maximum_observed_absolute_grade_percent"].ge(
            candidates["medical_maximum_observed_absolute_grade_percent"].quantile(0.90)
        ),
        "urban_center": candidates["nearest_public_transport_distance_m"].le(
            candidates["nearest_public_transport_distance_m"].quantile(0.10)
        ),
        "network_detour_high": candidates["detour_factor"].ge(candidates["detour_factor"].quantile(0.90)),
        "disconnected": candidates["nearest_network_medical_distance_m"].isna(),
        "high_elderly_weighted_area": candidates["estimated_elderly_population"].ge(
            candidates["estimated_elderly_population"].quantile(0.90)
        ),
    }
    selected_strata: dict[str, set[str]] = {}
    quota = 14
    for stratum, mask in pools.items():
        pool = candidates.loc[mask, "gml_id"].astype(str).tolist()
        ordered = sorted(pool, key=lambda value: _stable_sample_order(city, stratum, value))
        for gml_id in ordered[:quota]:
            selected_strata.setdefault(gml_id, set()).add(stratum)
    all_ordered = sorted(
        candidates["gml_id"].astype(str),
        key=lambda value: _stable_sample_order(city, "deterministic_fill", value),
    )
    for gml_id in all_ordered:
        if len(selected_strata) >= 120:
            break
        selected_strata.setdefault(gml_id, set()).add("deterministic_fill")
    if len(selected_strata) < 100:
        raise ValueError(f"{city}: deterministic sampling produced fewer than 100 routes")
    sample = candidates.loc[candidates["gml_id"].isin(selected_strata)].copy()
    sample["strata"] = sample["gml_id"].map(lambda value: sorted(selected_strata[str(value)]))
    sample["sample_id"] = sample["gml_id"].map(
        lambda value: f"route-{city}-{hashlib.sha256(str(value).encode()).hexdigest()[:16]}"
    )
    sample["sampling_rank"] = sample["gml_id"].map(
        lambda value: _stable_sample_order(city, "final", str(value))
    )
    return sample.sort_values("sampling_rank").reset_index(drop=True)


def _experimental_geometry(
    edge_ids: list[str], edge_lookup: gpd.GeoDataFrame
) -> Any | None:
    if not edge_ids:
        return None
    lines = [edge_lookup.loc[edge_id] for edge_id in edge_ids if edge_id in edge_lookup.index]
    return unary_union(lines) if lines else None


def _public_route_feature(record: dict[str, Any], route_model: str) -> dict[str, Any]:
    properties = {
        "sample_id": record["sample_id"],
        "city_id": record["city_id"],
        "reference_agreement": record["reference_agreement"],
        "cause_candidate": record["cause_candidate"],
        "primary_distance_m": record["primary_distance_m"],
        "reference_distance_m": record["reference_distance_m"],
        "euclidean_distance_m": record["euclidean_distance_m"],
        "primary_reachable": record["primary_reachable"],
        "reference_reachable": record["reference_reachable"],
        "review_status": "not_reviewed",
        "route_model": route_model,
        "route_semantics": (
            "experimental PLATEAU road-surface adjacency"
            if route_model == "primary_model"
            else "OpenStreetMap reference network"
        ),
    }
    geometry = record.get(f"public_{route_model}_geometry")
    return {"type": "Feature", "properties": properties, "geometry": mapping(geometry) if geometry else None}


def validate_city(city: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    started = time.perf_counter()
    meta = CITY_CONFIG[city]
    if _sha256(meta["osm"]) != meta["osm_sha256"]:
        raise ValueError(f"{city}: pinned OSM extract checksum mismatch")
    reference = read_osm_overpass_reference(
        meta["osm"],
        analysis_crs=meta["analysis_crs"],
        retrieval_date="2026-08-27",
        extract_source=(
            "Overpass API pinned historical query [date:2026-08-27T00:00:00Z] "
            f"bbox={','.join(map(str, meta['bbox']))}"
        ),
        source_sha256=meta["osm_sha256"],
    )
    demographics = pd.read_parquet(ROOT / f"analysis/outputs/real/{city}_building_demographics.parquet")
    access = pd.read_parquet(ROOT / f"analysis/outputs/real/{city}_building_network_accessibility.parquet")
    terrain = pd.read_parquet(ROOT / f"analysis/outputs/real/{city}_building_terrain_accessibility.parquet")
    facilities = _load_facilities(city)
    samples = _sample_candidates(city, demographics, access, terrain, facilities)
    origins = gpd.GeoDataFrame(
        samples[["sample_id"]],
        geometry=gpd.points_from_xy(samples["longitude"], samples["latitude"]),
        crs="EPSG:4326",
    ).to_crs(meta["analysis_crs"])
    origin_snaps = snap_points_to_reference_nodes(origins, reference.nodes, id_column="sample_id")
    facility_snaps = snap_points_to_reference_nodes(
        facilities, reference.nodes, id_column="facility_id"
    ).merge(
        pd.DataFrame(facilities.drop(columns="geometry")),
        on="facility_id",
        how="left",
        validate="one_to_one",
    )
    nearest_reference = multi_source_reference_destinations(
        reference, facility_snaps, destination_id_column="facility_id"
    ).set_index("node_id")
    origin_snap_lookup = origin_snaps.set_index("sample_id")
    facility_snap_lookup = facility_snaps.set_index("facility_id")
    medical_labels = pd.read_parquet(ROOT / f"analysis/outputs/real/{city}_medical_network_labels.parquet")
    experimental_edges = gpd.read_parquet(
        ROOT / f"analysis/outputs/real/{city}_road_graph_edges.parquet"
    )
    experimental_edge_geometry = experimental_edges.set_index("edge_id").geometry
    experimental_edge_length = experimental_edges.set_index("edge_id")["length_m"]
    reference_edge_lookup = reference.edges.set_index("edge_id")
    records: list[dict[str, Any]] = []
    for row in samples.itertuples(index=False):
        origin_snap = origin_snap_lookup.loc[row.sample_id]
        destination_snap = facility_snap_lookup.loc[row.destination_id]
        reference_route = shortest_path(
            reference,
            str(origin_snap.node_id),
            str(destination_snap.node_id),
            origin_connector_m=float(origin_snap.snap_distance_m),
            destination_connector_m=float(destination_snap.snap_distance_m),
        )
        primary_reachable = bool(pd.notna(row.nearest_network_medical_distance_m))
        primary_distance = float(row.nearest_network_medical_distance_m) if primary_reachable else None
        experimental_route_edges: list[str] = []
        experimental_geometry = None
        primary_destination_snap = None
        if primary_reachable:
            _, experimental_route_edges = reconstruct_route(medical_labels, str(row.node_id))
            graph_length = float(experimental_edge_length.reindex(experimental_route_edges).sum())
            primary_destination_snap = max(
                0.0,
                primary_distance - float(row.origin_to_node_distance_m) - graph_length,
            )
            experimental_geometry = _experimental_geometry(
                experimental_route_edges, experimental_edge_geometry
            )
        reference_geometry = route_geometry(reference, reference_route["edges"])
        overlap = None
        if experimental_geometry is not None and reference_geometry is not None and experimental_geometry.length > 0:
            overlap = float(
                experimental_geometry.intersection(reference_geometry.buffer(20)).length
                / experimental_geometry.length
            )
        nearest = nearest_reference.loc[str(origin_snap.node_id)]
        reference_route_rows = reference_edge_lookup.reindex(reference_route["edges"])
        agreement = reference_agreement(
            primary_distance,
            reference_route["distance_m"],
            primary_reachable,
            bool(reference_route["reachable"]),
        )
        record: dict[str, Any] = {
            "sample_id": row.sample_id,
            "city_id": city,
            "gml_id": row.gml_id,
            "strata": row.strata,
            "destination_id": row.destination_id,
            "euclidean_distance_m": float(row.euclidean_distance_m),
            "primary_model": "experimental_citygml_lod1_surface_adjacency",
            "reference_model": "openstreetmap_pinned_reference_network",
            "reference_semantics": REFERENCE_SEMANTICS,
            "primary_reachable": primary_reachable,
            "reference_reachable": bool(reference_route["reachable"]),
            "primary_distance_m": primary_distance,
            "reference_distance_m": reference_route["distance_m"],
            "primary_detour_factor": primary_distance / row.euclidean_distance_m if primary_distance else None,
            "reference_detour_factor": reference_route["distance_m"] / row.euclidean_distance_m if reference_route["distance_m"] else None,
            "primary_origin_snap_m": float(row.origin_to_node_distance_m) if pd.notna(row.origin_to_node_distance_m) else None,
            "primary_road_surface_snap_m": float(row.road_surface_distance_m) if pd.notna(row.road_surface_distance_m) else None,
            "primary_destination_snap_m": primary_destination_snap,
            "reference_origin_snap_m": float(origin_snap.snap_distance_m),
            "reference_destination_snap_m": float(destination_snap.snap_distance_m),
            "reference_nearest_destination_id": nearest.reference_nearest_destination_id,
            "destination_agreement": bool(nearest.reference_nearest_destination_id == row.destination_id),
            "route_overlap_fraction": overlap,
            "reference_agreement": agreement,
            "reference_route_has_bridge": bool(reference_route_rows["bridge"].fillna(False).any()),
            "reference_route_has_tunnel": bool(reference_route_rows["tunnel"].fillna(False).any()),
            "reference_route_has_oneway": bool(reference_route_rows["oneway"].fillna(False).any()),
            "limitations": [
                "Neither model is a field-observed ground truth.",
                "PLATEAU graph is experimental surface adjacency, not a validated pedestrian graph.",
                "OSM completeness, tagging, crossings, entrances and current passability are not guaranteed.",
            ],
        }
        cause, cause_rule = classify_disagreement_cause(record)
        record["cause_candidate"] = cause
        record["cause_rule"] = cause_rule
        if agreement in {"large_difference", "connectivity_disagreement", "moderate_difference"}:
            for route_model, geometry in (
                ("primary_model", experimental_geometry),
                ("reference_model", reference_geometry),
            ):
                record[f"public_{route_model}_geometry"] = (
                    gpd.GeoSeries([geometry], crs=meta["analysis_crs"])
                    .to_crs("EPSG:4326")
                    .iloc[0]
                    if geometry is not None
                    else None
                )
        records.append(record)
    internal = pd.DataFrame([
        {key: value for key, value in record.items() if not key.startswith("public_")}
        for record in records
    ])
    INTERNAL_DIR.mkdir(parents=True, exist_ok=True)
    internal.to_parquet(INTERNAL_DIR / f"{city}_network_validation_samples.parquet", index=False)
    stats = comparison_statistics(internal)
    stratum_counts: dict[str, int] = {}
    for strata in internal["strata"]:
        for stratum in strata:
            stratum_counts[stratum] = stratum_counts.get(stratum, 0) + 1
    disagreements = internal.loc[
        internal["reference_agreement"].isin(
            ["large_difference", "connectivity_disagreement", "moderate_difference"]
        )
    ].copy()
    disagreements["absolute_difference_m"] = (
        disagreements["primary_distance_m"] - disagreements["reference_distance_m"]
    ).abs()
    disagreements = disagreements.sort_values(
        ["reference_agreement", "absolute_difference_m", "sample_id"],
        ascending=[True, False, True],
    )
    record_by_sample = {record["sample_id"]: record for record in records}
    route_features = [
        _public_route_feature(record_by_sample[sample_id], route_model)
        for sample_id in disagreements.head(30)["sample_id"]
        for route_model in ("primary_model", "reference_model")
        if record_by_sample[sample_id].get(f"public_{route_model}_geometry") is not None
    ]
    public_disagreements = [
        {
            "sample_id": item.sample_id,
            "reference_agreement": item.reference_agreement,
            "primary_distance_m": _json_value(item.primary_distance_m),
            "reference_distance_m": _json_value(item.reference_distance_m),
            "absolute_difference_m": _json_value(item.absolute_difference_m),
            "cause_candidate": item.cause_candidate,
            "cause_rule": item.cause_rule,
        }
        for item in disagreements.head(20).itertuples(index=False)
    ]
    return (
        {
            "city_id": city,
            "city_name": meta["city_name"],
            "algorithm_version": ALGORITHM_VERSION,
            "sample_rule": {
                "method": "deterministic stratified hash-order selection without manual cherry-picking",
                "minimum_routes": 100,
                "selected_routes": len(internal),
                "stratum_counts": dict(sorted(stratum_counts.items())),
            },
            "primary_network": {
                "method": "experimental_citygml_lod1_surface_adjacency",
                "pedestrian_network": False,
                "route_semantics": "experimental road-surface adjacency path; not a walking route",
                "graph_version": str(access["graph_version"].iloc[0]),
            },
            "reference_network": reference.report,
            "metrics": stats,
            "major_disagreements": public_disagreements,
            "coverage": {
                "reference_bbox": meta["bbox"],
                "sample_reference_reachable_fraction": float(internal["reference_reachable"].mean()),
                "sample_primary_reachable_fraction": float(internal["primary_reachable"].mean()),
            },
            "validation_status": "cross_validated",
            "municipal_review": "not_reviewed",
            "field_validation": "awaiting_field_validation",
            "runtime_seconds": time.perf_counter() - started,
            "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            "known_limitations": [
                "Reference agreement is not real-world correctness.",
                "The OSM reference is a fixed historical Overpass extract and may be incomplete.",
                "Official PLATEAU generator output was unavailable for these cities.",
                "No municipal road network or field observation was supplied.",
            ],
        },
        route_features,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", choices=["maizuru", "fujisawa", "all"], default="all")
    args = parser.parse_args()
    selected = list(CITY_CONFIG) if args.city == "all" else [args.city]
    city_results: list[dict[str, Any]] = []
    route_features: list[dict[str, Any]] = []
    for city in selected:
        city_result, city_routes = validate_city(city)
        city_results.append(city_result)
        route_features.extend(city_routes)
    payload = {
        "schema_version": "validation-evidence-v1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "claim": "experimental_network_accessibility",
        "validation_method": "independent_reference_network_comparison",
        "validation_status": "cross_validated",
        "official_plateau_network": {
            "repository": "https://github.com/Project-PLATEAU/PLATEAU-RoadNetwork-Generator",
            "reviewed_at": "2026-08-27",
            "status": "NOT_AVAILABLE",
            "reason": "Published generated walk/drive outputs for Maizuru or Fujisawa were not found; the current generator is a Windows GUI workflow.",
            "manual_export_adapter_preserved": True,
            "comparison_performed": False,
        },
        "reference_warning": "OSM is a reference_network, not ground truth and not a production replacement.",
        "cities": city_results,
    }
    _write_json(OUTPUT, payload)
    public_payload = json.loads(json.dumps(_json_value(payload)))
    _write_json(PUBLIC_OUTPUT, public_payload, compact=True)
    PUBLIC_ROUTES.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_ROUTES.write_text(
        json.dumps(_json_value({"type": "FeatureCollection", "features": route_features}), ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(OUTPUT), "cities": {row["city_id"]: row["metrics"] for row in city_results}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
