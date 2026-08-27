from __future__ import annotations

import hashlib
import json

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from analysis.src.model_validation import (
    OSM_ATTRIBUTION,
    REFERENCE_SEMANTICS,
    classify_disagreement_cause,
    comparison_statistics,
    read_osm_overpass_reference,
    reference_agreement,
    shortest_path,
    snap_points_to_reference_nodes,
)


def test_osm_reference_is_versioned_attributed_and_not_ground_truth(tmp_path) -> None:
    payload = {
        "elements": [
            {
                "type": "way",
                "id": 12,
                "tags": {"highway": "residential", "sidewalk": "both"},
                "geometry": [
                    {"lon": 135.0, "lat": 35.0},
                    {"lon": 135.001, "lat": 35.0},
                    {"lon": 135.002, "lat": 35.0},
                ],
            }
        ]
    }
    source = tmp_path / "osm.json"
    serialized = json.dumps(payload)
    source.write_text(serialized, encoding="utf-8")
    digest = hashlib.sha256(serialized.encode()).hexdigest()
    graph = read_osm_overpass_reference(
        source,
        analysis_crs="EPSG:6674",
        retrieval_date="2026-08-27",
        extract_source="pinned Overpass query",
        source_sha256=digest,
    )
    assert graph.report["reference_semantics"] == REFERENCE_SEMANTICS
    assert graph.report["attribution"] == OSM_ATTRIBUTION
    assert graph.report["replacement_for_production_network"] is False
    assert graph.report["nodes"] == 3
    assert graph.report["edges"] == 2
    nodes = graph.nodes.assign(_x=graph.nodes.geometry.x).sort_values("_x")
    route = shortest_path(graph, nodes.iloc[0].node_id, nodes.iloc[-1].node_id)
    assert route["reachable"] is True
    assert route["distance_m"] == pytest.approx(route["graph_distance_m"])


def test_snap_comparison_metrics_and_transparent_categories() -> None:
    nodes = gpd.GeoDataFrame(
        {"node_id": ["a", "b"]},
        geometry=[Point(0, 0), Point(100, 0)],
        crs="EPSG:6674",
    )
    points = gpd.GeoDataFrame(
        {"sample_id": ["one"]}, geometry=[Point(2, 0)], crs="EPSG:6674"
    )
    snapped = snap_points_to_reference_nodes(points, nodes, id_column="sample_id")
    assert snapped.iloc[0].node_id == "a"
    assert snapped.iloc[0].snap_distance_m == pytest.approx(2)
    assert reference_agreement(100, 110, True, True) == "distance_similar"
    assert reference_agreement(100, 220, True, True) == "large_difference"
    assert reference_agreement(None, 200, False, True) == "connectivity_disagreement"

    samples = pd.DataFrame(
        {
            "primary_reachable": [True, True, False],
            "reference_reachable": [True, True, True],
            "primary_distance_m": [100.0, 300.0, None],
            "reference_distance_m": [110.0, 200.0, 500.0],
            "destination_agreement": [True, False, False],
            "primary_origin_snap_m": [2.0, 4.0, 3.0],
            "reference_origin_snap_m": [5.0, 6.0, 7.0],
            "route_overlap_fraction": [0.8, 0.1, None],
            "reference_agreement": [
                "distance_similar",
                "moderate_difference",
                "connectivity_disagreement",
            ],
        }
    )
    summary = comparison_statistics(samples)
    assert summary["sample_count"] == 3
    assert summary["comparable_distance_count"] == 2
    assert summary["connectivity_disagreement_count"] == 1
    assert "confidence" not in summary


def test_disagreement_causes_are_rules_not_predictions() -> None:
    assert classify_disagreement_cause(
        {"primary_reachable": False, "reference_reachable": True}
    )[0] == "topology"
    assert classify_disagreement_cause(
        {
            "primary_reachable": True,
            "reference_reachable": True,
            "primary_origin_snap_m": 151,
            "reference_origin_snap_m": 1,
        }
    )[0] == "snap"
