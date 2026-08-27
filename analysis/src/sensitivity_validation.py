"""Transparent hazard and criticality sensitivity rule sets."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd


def hazard_assumption_edge_sets(
    hazards: pd.DataFrame,
    edges: pd.DataFrame,
    nodes: pd.DataFrame,
    critical_edge_ids: set[str],
) -> dict[str, dict[str, Any]]:
    """Build five bounded, reproducible closure models from real attributes."""

    hazard_edges = set(hazards["edge_id"].astype(str))
    edge_by_id = edges.set_index(edges["edge_id"].astype(str), drop=False)
    available = hazard_edges & set(edge_by_id.index)
    rank_numeric = pd.to_numeric(hazards["rank_code"], errors="coerce")
    if rank_numeric.notna().any():
        rank_threshold = float(rank_numeric.dropna().median())
        threshold_edges = set(
            hazards.loc[rank_numeric.ge(rank_threshold), "edge_id"].astype(str)
        ) & available
        rank_rule = f"published numeric rank_code >= median {rank_threshold:g}; no severity probability implied"
    else:
        labels = sorted(hazards["rank_label"].dropna().astype(str).unique())
        selected_labels = set(labels[len(labels) // 2 :])
        threshold_edges = set(
            hazards.loc[hazards["rank_label"].astype(str).isin(selected_labels), "edge_id"].astype(str)
        ) & available
        rank_rule = "lexicographic upper half of published rank labels; semantic severity unavailable"

    length_by_edge = edge_by_id["length_m"].astype(float)
    overlap = hazards.groupby(hazards["edge_id"].astype(str))["intersection_length_m"].sum()
    overlap_ratio = overlap / length_by_edge.reindex(overlap.index).replace(0, pd.NA)
    ratio_edges = set(overlap_ratio.loc[overlap_ratio.ge(0.50)].index) & available

    node_group = nodes.set_index(nodes["node_id"].astype(str))["gml_id"].astype(str)
    hazard_groups: set[str] = set()
    for row in edge_by_id.loc[sorted(available)].itertuples(index=False):
        hazard_groups.add(str(node_group.get(str(row.source_node_id), "")))
        hazard_groups.add(str(node_group.get(str(row.target_node_id), "")))
    hazard_groups.discard("")
    group_edges: set[str] = set()
    for row in edges.itertuples(index=False):
        if (
            str(node_group.get(str(row.source_node_id), "")) in hazard_groups
            or str(node_group.get(str(row.target_node_id), "")) in hazard_groups
        ):
            group_edges.add(str(row.edge_id))

    return {
        "S1_all_overlap_edges": {
            "closed_edges": frozenset(available),
            "rule": "all edges with positive published hazard geometry overlap are unavailable",
            "validated_parameter_range": "overlap > 0 m",
        },
        "S2_published_rank_threshold": {
            "closed_edges": frozenset(threshold_edges),
            "rule": rank_rule,
            "validated_parameter_range": "one deterministic median threshold",
        },
        "S3_overlap_ratio_threshold": {
            "closed_edges": frozenset(ratio_edges),
            "rule": "summed hazard intersection length / edge length >= 0.50",
            "validated_parameter_range": "ratio threshold 0.50",
        },
        "S4_road_group_closure": {
            "closed_edges": frozenset(group_edges),
            "rule": "all edges incident to a PLATEAU Road feature group containing an overlapped edge",
            "validated_parameter_range": "feature-level road group",
        },
        "S5_critical_overlap_only": {
            "closed_edges": frozenset(available & critical_edge_ids),
            "rule": "only Tarjan bridge candidates that also overlap the published hazard geometry",
            "validated_parameter_range": "baseline criticality candidate intersection",
        },
    }


def criticality_robustness(
    models: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Aggregate exact edge candidates without inventing a combined score."""

    by_edge: dict[str, list[tuple[str, int, dict[str, Any]]]] = defaultdict(list)
    for model, records in models.items():
        ordered = sorted(
            records,
            key=lambda row: (
                -int(row["affected_buildings"]),
                -float(row["affected_estimated_elderly_population"]),
                str(row["edge_id"]),
            ),
        )
        for rank, record in enumerate(ordered, start=1):
            by_edge[str(record["edge_id"])].append((model, rank, record))
    result: list[dict[str, Any]] = []
    for edge_id, observations in by_edge.items():
        building_values = [int(item[2]["affected_buildings"]) for item in observations]
        elderly_values = [
            float(item[2]["affected_estimated_elderly_population"]) for item in observations
        ]
        ranks = [item[1] for item in observations]
        result.append(
            {
                "edge_id": edge_id,
                "present_in_n_models": len(observations),
                "model_count": len(models),
                "present_models": sorted(item[0] for item in observations),
                "affected_building_range": [min(building_values), max(building_values)],
                "affected_elderly_range": [min(elderly_values), max(elderly_values)],
                "rank_range": [min(ranks), max(ranks)],
            }
        )
    return sorted(
        result,
        key=lambda row: (
            -row["present_in_n_models"],
            -row["affected_building_range"][1],
            row["rank_range"][0],
            row["edge_id"],
        ),
    )

