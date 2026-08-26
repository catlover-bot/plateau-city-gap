"""Normalize the verified network-scenario result into canonical Parquet tables."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.citygap_platform.ingestion.context import context_config_hash

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "analysis/outputs/real"
SCENARIOS = OUTPUT / "maizuru_network_scenarios.json"
PERFORMANCE = OUTPUT / "maizuru_network_scenario_performance.json"
CONTEXT = OUTPUT / "maizuru_plateau_context_summary.json"
INVENTORY = OUTPUT / "maizuru_plateau_inventory.json"
CANDIDATES = OUTPUT / "maizuru_scenario_candidate_context.csv"
MANIFEST = OUTPUT / "maizuru_scenario_canonical_manifest.json"
TABLE_NAMES = (
    "scenario_runs",
    "scenario_sites",
    "scenario_objectives",
    "scenario_constraints",
    "scenario_impacts",
    "scenario_context",
    "scenario_evidence",
)
NAMESPACE = uuid.UUID("1946ec85-8561-57af-93b6-aae882bea2b5")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def scenario_config_hash(report: dict[str, Any]) -> str:
    config = {
        "algorithm_version": report["algorithm_version"],
        "network": report["network"],
        "candidate_set": report["candidate_set"],
        "objectives": report["objectives"],
        "context_policy": report["context_policy"],
        "provenance": report["provenance"],
    }
    return hashlib.sha256(_canonical_json(config).encode()).hexdigest()


def _minimum_site_separation(plan: dict[str, Any], coordinates: pd.DataFrame) -> float | None:
    if len(plan["sites"]) < 2:
        return None
    positions = coordinates.loc[[site["candidate_id"] for site in plan["sites"]]].to_numpy(float)
    return min(
        float(np.linalg.norm(positions[left] - positions[right]))
        for left in range(len(positions))
        for right in range(left + 1, len(positions))
    )


def _objective_rows(run_id: str, plan: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = {
        "overall": (
            "total_building_distance_reduction_m",
            "building_m",
            "network-distance reduction summed across reachable buildings",
        ),
        "elderly": (
            "elderly_weighted_distance_reduction_person_m",
            "estimated_elderly_person_m",
            "500m-census elderly-estimate-weighted network-distance reduction",
        ),
        "worst_served": (
            "worst_decile_mean_reduction_m",
            "m",
            "mean reduction for buildings in the worst baseline distance decile",
        ),
        "robust": (
            "robust_top20_elderly_weighted_reduction_person_m",
            "estimated_elderly_person_m",
            "elderly-weighted reduction within Robust Top 20 meshes",
        ),
        "reachability": (
            "newly_network_connected_building_count",
            "building",
            "buildings newly connected within selected graph components",
        ),
    }
    rows = []
    for name, (metric, unit, definition) in metrics.items():
        rows.append(
            {
                "scenario_run_id": run_id,
                "objective_name": name,
                "objective_role": "selection" if plan["mode"] == name else "evaluation",
                "value": float(plan["impact"][metric]),
                "unit": unit,
                "definition": definition,
                "metadata_json": "{}",
            }
        )
    if plan["mode"] == "balanced":
        vector = plan["selection_trace"][-1]["normalized_maximin_vector"]
        rows.append(
            {
                "scenario_run_id": run_id,
                "objective_name": "balanced",
                "objective_role": "selection",
                "value": float(min(vector)),
                "unit": "normalized_ratio",
                "definition": (
                    "lexicographic max-min over separately normalized objective marginals; "
                    "not a weighted composite score"
                ),
                "metadata_json": _canonical_json({"normalized_maximin_vector": vector}),
            }
        )
    return rows


def build(output: Path = OUTPUT) -> dict[str, Any]:
    for path in (SCENARIOS, PERFORMANCE, CONTEXT, INVENTORY, CANDIDATES):
        if not path.exists():
            raise FileNotFoundError(path)
    report = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    performance = json.loads(PERFORMANCE.read_text(encoding="utf-8"))
    context = json.loads(CONTEXT.read_text(encoding="utf-8"))
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    candidate_frame = pd.read_csv(CANDIDATES)
    coordinates = candidate_frame.set_index("candidate_id")[["candidate_x", "candidate_y"]]
    config_hash = scenario_config_hash(report)
    dataset_version_key = (
        f"{report['city']['city_id']}:{inventory['dataset']['dataset_year']}:"
        f"{inventory['archive']['sha256']}"
    )

    tables: dict[str, list[dict[str, Any]]] = {name: [] for name in TABLE_NAMES}
    for mode, plans in report["plans"].items():
        for site_count_text, plan in plans.items():
            site_count = int(site_count_text)
            run_id = str(
                uuid.uuid5(NAMESPACE, f"{dataset_version_key}:{config_hash}:{plan['plan_id']}")
            )
            runtime = sum(
                float(stage["stage_runtime_seconds"])
                for stage in plan["selection_trace"][:site_count]
            )
            tables["scenario_runs"].append(
                {
                    "scenario_run_id": run_id,
                    "scenario_key": plan["plan_id"],
                    "city_id": report["city"]["city_id"],
                    "dataset_version_key": dataset_version_key,
                    "dataset_year": int(inventory["dataset"]["dataset_year"]),
                    "dataset_archive_sha256": inventory["archive"]["sha256"],
                    "plateau_product_specification_version": inventory["dataset"][
                        "product_specification_version"
                    ],
                    "network_version": report["network"]["graph_version"],
                    "context_version": context["algorithm_version"],
                    "context_config_hash": context_config_hash(context),
                    "algorithm_version": report["algorithm_version"],
                    "objective_mode": mode,
                    "objective_definition": plan["objective"],
                    "site_count": site_count,
                    "candidate_count": int(report["candidate_set"]["count"]),
                    "algorithm_kind": (
                        "exact" if site_count == 1 else "deterministic_greedy_approximation"
                    ),
                    "config_hash": config_hash,
                    "generated_at": report["generated_at"],
                    "runtime_seconds": runtime,
                    "lifecycle_status": "draft",
                    "metadata_json": _canonical_json(
                        {
                            "exactness": plan["exactness"],
                            "shared_pipeline_runtime_seconds": performance["total_runtime_seconds"],
                            "pedestrian_network": report["network"]["pedestrian_network"],
                            "land_availability_confirmed": report["candidate_set"][
                                "land_availability_confirmed"
                            ],
                        }
                    ),
                }
            )
            tables["scenario_objectives"].extend(_objective_rows(run_id, plan))
            for metric, value in plan["impact"].items():
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    continue
                unit = (
                    "building"
                    if "building_count" in metric
                    else ("m" if metric.endswith("_m") else "reported_metric")
                )
                tables["scenario_impacts"].append(
                    {
                        "scenario_run_id": run_id,
                        "metric_name": metric,
                        "value": float(value),
                        "unit": unit,
                        "interpretation": "model output; see source scenario limitations",
                    }
                )

            minimum_separation = _minimum_site_separation(plan, coordinates)
            tables["scenario_constraints"].extend(
                [
                    {
                        "scenario_run_id": run_id,
                        "site_order": None,
                        "constraint_name": "minimum_site_separation_m",
                        "threshold_json": _canonical_json(
                            {"minimum": report["candidate_set"]["minimum_site_separation_m"]}
                        ),
                        "observed_json": _canonical_json({"minimum": minimum_separation}),
                        "satisfied": minimum_separation is None
                        or minimum_separation
                        >= report["candidate_set"]["minimum_site_separation_m"] - 1e-9,
                        "interpretation": "optimizer spacing constraint",
                    },
                    {
                        "scenario_run_id": run_id,
                        "site_order": None,
                        "constraint_name": "land_availability_confirmed",
                        "threshold_json": "{}",
                        "observed_json": _canonical_json({"value": False}),
                        "satisfied": None,
                        "interpretation": "unknown; requires municipal confirmation",
                    },
                    {
                        "scenario_run_id": run_id,
                        "site_order": None,
                        "constraint_name": "validated_pedestrian_network",
                        "threshold_json": "{}",
                        "observed_json": _canonical_json({"value": False}),
                        "satisfied": None,
                        "interpretation": "road-surface adjacency is not a pedestrian network",
                    },
                ]
            )

            for site in plan["sites"]:
                order = int(site["site_order"])
                tables["scenario_sites"].append(
                    {
                        "scenario_run_id": run_id,
                        "site_order": order,
                        "candidate_id": site["candidate_id"],
                        "network_node_id": site["node_id"],
                        "road_gml_id": site["road_gml_id"],
                        "road_surface_id": site["road_surface_id"],
                        "road_name": site["road_name"],
                        "longitude": float(site["longitude"]),
                        "latitude": float(site["latitude"]),
                        "existing_transport_distance_m": float(
                            site["existing_transport_distance_m"]
                        ),
                        "component_id": site["component_id"],
                        "candidate_to_graph_connector_m": float(
                            site["candidate_to_graph_connector_m"]
                        ),
                        "siting_feasibility": site["siting_feasibility"],
                    }
                )
                for flag, observed in site["feasibility_flags"].items():
                    if not flag.endswith("_attention"):
                        continue
                    tables["scenario_constraints"].append(
                        {
                            "scenario_run_id": run_id,
                            "site_order": order,
                            "constraint_name": flag,
                            "threshold_json": "{}",
                            "observed_json": _canonical_json({"value": bool(observed)}),
                            "satisfied": None,
                            "interpretation": "review prompt only; not a siting decision",
                        }
                    )
                context_rows = (
                    (
                        "landuse",
                        site["landuse_context"],
                        site["landuse_feature_count"],
                        None,
                        {},
                    ),
                    (
                        "planning",
                        site["planning_context"],
                        site["planning_feature_count"],
                        None,
                        {},
                    ),
                    (
                        "hazard",
                        site["hazard_context"],
                        None,
                        site["hazard_review_status"],
                        {"overlap": site["hazard_overlap"]},
                    ),
                    ("terrain", None, None, None, site["terrain"]),
                    ("road", site["road_name"], 1, None, site["road_source"]),
                )
                for context_type, label, count, review_status, payload in context_rows:
                    tables["scenario_context"].append(
                        {
                            "scenario_run_id": run_id,
                            "site_order": order,
                            "context_type": context_type,
                            "label": label,
                            "feature_count": count,
                            "review_status": review_status,
                            "siting_feasibility": "not_determined",
                            "source_payload_json": _canonical_json(payload),
                        }
                    )

            evidence = plan["representative_evidence"]
            tables["scenario_evidence"].append(
                {
                    "scenario_run_id": run_id,
                    "representative_building_gml_id": evidence["building_gml_id"],
                    "virtual_candidate_id": evidence["after"]["virtual_scenario_candidate_id"],
                    "before_network_distance_m": evidence["before"]["network_distance_m"],
                    "after_network_distance_m": evidence["after"]["network_distance_m"],
                    "route_semantics": evidence["route_semantics"],
                    "evidence_json": _canonical_json(evidence),
                }
            )

    output.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for name, records in tables.items():
        path = output / f"{name}.parquet"
        pd.DataFrame.from_records(records).to_parquet(path, index=False)
        artifacts[name] = {
            "file": path.name,
            "row_count": len(records),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    manifest = {
        "schema_version": "1.0.0",
        "city": report["city"],
        "dataset_version_key": dataset_version_key,
        "network_version": report["network"]["graph_version"],
        "context_version": context["algorithm_version"],
        "context_config_hash": context_config_hash(context),
        "algorithm_version": report["algorithm_version"],
        "config_hash": config_hash,
        "canonical_tables": artifacts,
        "lifecycle_initial_status": "draft",
        "database_executed": False,
        "database_status": "canonical Parquet generated; PostGIS loader not executed",
    }
    manifest_path = output / MANIFEST.name
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    print(json.dumps(build(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
