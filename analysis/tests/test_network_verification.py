import geopandas as gpd
import pandas as pd

from analysis.src.network_verification import verify_shortest_path_certificate
from analysis.src.plateau_road_network import ANALYSIS_CRS, multi_source_shortest_paths


def _fixture() -> tuple[gpd.GeoDataFrame, pd.DataFrame, pd.DataFrame]:
    nodes = gpd.GeoDataFrame(
        {"node_id": ["a", "b", "c"]},
        geometry=gpd.points_from_xy([0, 1, 2], [0, 0, 0]),
        crs=ANALYSIS_CRS,
    )
    edges = pd.DataFrame(
        {
            "edge_id": ["ab", "bc"],
            "source_node_id": ["a", "b"],
            "target_node_id": ["b", "c"],
            "length_m": [2.0, 3.0],
        }
    )
    seeds = pd.DataFrame(
        {
            "node_id": ["c"],
            "origin_to_node_distance_m": [1.0],
            "facility_id": ["facility"],
            "facility_name": ["Facility"],
        }
    )
    result = multi_source_shortest_paths(
        nodes,
        edges,
        seeds,
        destination_id_column="facility_id",
        destination_name_column="facility_name",
    )
    return edges, seeds, result


def test_independent_certificate_accepts_valid_shortest_path_labels() -> None:
    edges, seeds, result = _fixture()
    report = verify_shortest_path_certificate(
        edges,
        seeds,
        result,
        destination_id_column="facility_id",
        destination_name_column="facility_name",
        sample_node_ids=["a", "b"],
    )
    assert report["production_solver_reused"] is False
    assert report["certified"] is True
    assert report["edge_optimality_conditions_checked"] == 4
    assert report["samples"][0]["reported_node_distance_m"] == 6
    assert report["samples"][0]["summed_graph_length_m"] == 5
    assert report["samples"][0]["terminal_connector_m"] == 1


def test_independent_certificate_rejects_tampered_label() -> None:
    edges, seeds, result = _fixture()
    result.loc[result["node_id"].eq("a"), "network_to_destination_distance_m"] = 9.0
    report = verify_shortest_path_certificate(
        edges,
        seeds,
        result,
        destination_id_column="facility_id",
        destination_name_column="facility_name",
    )
    assert report["certified"] is False
    assert report["maximum_edge_optimality_violation_m"] == 3
