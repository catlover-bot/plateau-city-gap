"""Independent shortest-path certificates for persisted network results.

The verifier does not run Dijkstra.  It checks the mathematical optimality
conditions on every undirected edge and proves that stored predecessor chains
realize the reported distances back to a declared destination seed.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd


def verify_shortest_path_certificate(
    edges: pd.DataFrame,
    seeds: pd.DataFrame,
    result: pd.DataFrame,
    *,
    destination_id_column: str,
    destination_name_column: str,
    sample_node_ids: list[str] | None = None,
    tolerance_m: float = 1e-7,
) -> dict[str, Any]:
    """Verify shortest-path labels without invoking the production solver."""

    labels = result.set_index("node_id", verify_integrity=True)
    edge_lookup: dict[str, tuple[str, str, float]] = {}
    maximum_edge_violation = 0.0
    finite_to_unreachable_edges = 0
    edge_conditions = 0
    for row in edges.itertuples(index=False):
        edge_id = str(row.edge_id)
        source = str(row.source_node_id)
        target = str(row.target_node_id)
        weight = float(row.length_m)
        edge_lookup[edge_id] = (source, target, weight)
        source_distance = float(labels.loc[source, "network_to_destination_distance_m"])
        target_distance = float(labels.loc[target, "network_to_destination_distance_m"])
        if math.isfinite(source_distance) != math.isfinite(target_distance):
            finite_to_unreachable_edges += 1
        if math.isfinite(source_distance) and math.isfinite(target_distance):
            maximum_edge_violation = max(
                maximum_edge_violation,
                source_distance - target_distance - weight,
                target_distance - source_distance - weight,
            )
            edge_conditions += 2

    seed_upper_bound_violation = 0.0
    seed_keys: set[tuple[str, str, str, float]] = set()
    for row in seeds.itertuples(index=False):
        node_id = str(row.node_id)
        destination_id = str(getattr(row, destination_id_column))
        destination_name = str(getattr(row, destination_name_column))
        connector = float(row.origin_to_node_distance_m)
        seed_keys.add((node_id, destination_id, destination_name, connector))
        distance = float(labels.loc[node_id, "network_to_destination_distance_m"])
        seed_upper_bound_violation = max(seed_upper_bound_violation, distance - connector)

    maximum_predecessor_residual = 0.0
    predecessor_checks = 0
    invalid_predecessors = 0
    terminal_seed_mismatches = 0
    for node_id, row in labels.iterrows():
        distance = float(row["network_to_destination_distance_m"])
        if not math.isfinite(distance):
            continue
        previous_node = row["predecessor_node_id"]
        previous_edge = row["predecessor_edge_id"]
        if pd.isna(previous_node) and pd.isna(previous_edge):
            target = (
                str(node_id),
                str(row["destination_id"]),
                str(row["destination_name"]),
                distance,
            )
            if not any(
                target[:3] == seed[:3] and abs(target[3] - seed[3]) <= tolerance_m
                for seed in seed_keys
            ):
                terminal_seed_mismatches += 1
            continue
        if pd.isna(previous_node) or pd.isna(previous_edge) or str(previous_edge) not in edge_lookup:
            invalid_predecessors += 1
            continue
        previous_node = str(previous_node)
        previous_edge = str(previous_edge)
        source, target, weight = edge_lookup[previous_edge]
        if {str(node_id), previous_node} != {source, target}:
            invalid_predecessors += 1
            continue
        previous_distance = float(
            labels.loc[previous_node, "network_to_destination_distance_m"]
        )
        maximum_predecessor_residual = max(
            maximum_predecessor_residual, abs(distance - previous_distance - weight)
        )
        predecessor_checks += 1

    samples = []
    for origin_node in sample_node_ids or []:
        node_id = str(origin_node)
        start_distance = float(labels.loc[node_id, "network_to_destination_distance_m"])
        current = node_id
        edge_ids: list[str] = []
        graph_length = 0.0
        visited = {current}
        while True:
            row = labels.loc[current]
            previous_node = row["predecessor_node_id"]
            previous_edge = row["predecessor_edge_id"]
            if pd.isna(previous_node) and pd.isna(previous_edge):
                terminal_connector = float(row["network_to_destination_distance_m"])
                break
            previous_node = str(previous_node)
            previous_edge = str(previous_edge)
            graph_length += edge_lookup[previous_edge][2]
            edge_ids.append(previous_edge)
            if previous_node in visited:
                raise ValueError(f"Predecessor cycle in verifier sample {node_id}")
            visited.add(previous_node)
            current = previous_node
        samples.append(
            {
                "origin_node_id": node_id,
                "destination_id": labels.loc[node_id, "destination_id"],
                "reported_node_distance_m": start_distance,
                "summed_graph_length_m": graph_length,
                "terminal_connector_m": terminal_connector,
                "route_edge_count": len(edge_ids),
                "realization_residual_m": abs(
                    start_distance - graph_length - terminal_connector
                ),
            }
        )

    maximum_sample_residual = max(
        (sample["realization_residual_m"] for sample in samples), default=0.0
    )
    certified = all(
        (
            maximum_edge_violation <= tolerance_m,
            seed_upper_bound_violation <= tolerance_m,
            maximum_predecessor_residual <= tolerance_m,
            maximum_sample_residual <= tolerance_m,
            finite_to_unreachable_edges == 0,
            invalid_predecessors == 0,
            terminal_seed_mismatches == 0,
        )
    )
    return {
        "method": "edge_optimality_and_predecessor_realization_certificate",
        "production_solver_reused": False,
        "certified": certified,
        "tolerance_m": tolerance_m,
        "edge_optimality_conditions_checked": edge_conditions,
        "maximum_edge_optimality_violation_m": maximum_edge_violation,
        "finite_to_unreachable_edges": finite_to_unreachable_edges,
        "seed_upper_bound_violation_m": seed_upper_bound_violation,
        "predecessor_equations_checked": predecessor_checks,
        "maximum_predecessor_residual_m": maximum_predecessor_residual,
        "invalid_predecessors": invalid_predecessors,
        "terminal_seed_mismatches": terminal_seed_mismatches,
        "samples": samples,
    }
