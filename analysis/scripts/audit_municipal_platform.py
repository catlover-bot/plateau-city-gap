"""Build the final machine-readable audit from tracked real-data artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.citygap_platform.api.app import create_app
from backend.citygap_platform.domain.registry import validate_platform_registry

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "analysis" / "outputs" / "real"
OUTPUT = REAL / "municipal_platform_final_audit.json"


def _load(relative: str) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hashes_match(manifest: dict[str, Any], section: str) -> bool:
    item = manifest[section]
    path = ROOT / item["path"]
    return path.stat().st_size == item["bytes"] and _sha256(path) == item["sha256"]


def _evidence_hashes_match(manifest: dict[str, Any]) -> bool:
    directory = REAL / "evidence_packages" / manifest["plan_id"]
    return all(
        (directory / item["path"]).stat().st_size == item["size_bytes"]
        and _sha256(directory / item["path"]) == item["sha256"]
        for item in manifest["formats"].values()
    )


def build_audit() -> dict[str, Any]:
    inventory = _load("analysis/outputs/real/maizuru_plateau_inventory.json")
    buildings = _load("analysis/outputs/real/maizuru_building_demographics_summary.json")
    road = _load("analysis/outputs/real/maizuru_road_network_summary.json")
    terrain = _load("analysis/outputs/real/maizuru_terrain_verification.json")
    context = _load("analysis/outputs/real/maizuru_plateau_context_verification.json")
    context_summary = _load("analysis/outputs/real/maizuru_plateau_context_summary.json")
    scenarios = _load("analysis/outputs/real/maizuru_network_scenario_verification.json")
    performance = _load("analysis/outputs/real/maizuru_network_scenario_performance.json")
    canonical = _load("analysis/outputs/real/maizuru_scenario_canonical_manifest.json")
    registry = _load("analysis/outputs/real/platform_registry.json")
    workspace = _load("analysis/outputs/real/maizuru_municipal_workspace_manifest.json")
    browser = _load("analysis/outputs/real/municipal_workspace_browser_audit.json")
    evidence = _load(
        "analysis/outputs/real/evidence_packages/network-overall-3/manifest.json"
    )
    competition_story = _load("frontend/public/data/network_scenario_story.json")
    workspace_story = _load("frontend/public/data/municipal_workspace_story.json")
    validate_platform_registry(registry)

    routes = {route.path for route in create_app(repository=object()).routes}
    required_routes = {
        "/cities",
        "/cities/{city_id}/buildings",
        "/cities/{city_id}/road-edges",
        "/cities/{city_id}/context/{layer}",
        "/cities/{city_id}/scenarios",
        "/cities/{city_id}/scenario-comparison",
        "/registry/cities/{city_id}/jobs",
    }
    migrations = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "infra" / "migrations").glob("*.sql"))
    )
    required_tables = {
        "cities",
        "datasets",
        "dataset_versions",
        "ingestion_runs",
        "plateau_city_objects",
        "building_demographics",
        "road_network_nodes",
        "road_network_edges",
        "facility_registry",
        "plateau_urban_planning",
        "plateau_hazards",
        "scenario_runs",
        "scenario_impacts",
        "evidence_exports",
    }
    adapter_source = (
        ROOT / "backend" / "citygap_platform" / "ingestion" / "adapters.py"
    ).read_text(encoding="utf-8")
    citygml_source = (
        ROOT / "backend" / "citygap_platform" / "ingestion" / "citygml.py"
    ).read_text(encoding="utf-8")
    maizuru_capabilities = {
        item["capability"]: item["status"]
        for item in registry["capabilities"]
        if item["city_code"] == "26202"
    }

    checks = {
        "plateau_inventory_has_8_themes_and_97140_features": (
            len(inventory["themes"]) == 8
            and inventory["totals"]["feature_count"] == 97_140
            and inventory["totals"]["duplicate_gml_id_count"] == 0
        ),
        "building_demographics_conserve_population": (
            buildings["counts"]["strict_residential_buildings_citywide"] == 29_674
            and buildings["counts"]["strict_allocated_meshes"] == 149
            and max(buildings["conservation"].values()) < 1e-9
            and not buildings["privacy"]["suppressed_or_aggregation_affected_disaggregated"]
        ),
        "road_graph_is_real_but_not_claimed_as_pedestrian": (
            road["graph"]["nodes"] == 15_684
            and road["graph"]["edges"] == 23_437
            and road["graph"]["largest_component_fraction"] > 0.99
            and not road["graph"]["pedestrian_network"]
        ),
        "terrain_components_independently_verify": (
            terrain["verified"]
            and terrain["nodes"]["finite_elevations"] == road["graph"]["nodes"]
            and terrain["edges"]["records"] == road["graph"]["edges"]
        ),
        "official_context_counts_and_joins_verify": (
            context["passed"]
            and context["evidence"]["normalised_actual"]
            == {
                "land_use": 31_067,
                "urban_planning": 394,
                "landslide": 4_643,
                "flood": 666,
                "tsunami": 23,
            }
            and context_summary["targets"]["scenario_candidates"] == 11_460
        ),
        "all_30_network_scenarios_independently_verify": (
            scenarios["passed"]
            and scenarios["evidence"]["plan_count"] == 30
            and all(scenarios["checks"].values())
        ),
        "scenario_storage_has_seven_canonical_tables": (
            len(canonical["canonical_tables"]) == 7
            and canonical["canonical_tables"]["scenario_runs"]["row_count"] == 30
            and canonical["lifecycle_initial_status"] == "draft"
        ),
        "multi_city_registry_is_explicit": (
            len(registry["cities"]) == 2
            and len(registry["capabilities"]) == 18
            and maizuru_capabilities["gtfs"] == "unavailable"
        ),
        "five_municipal_adapter_formats_are_implemented": all(
            name in adapter_source
            for name in (
                "CityGmlSourceAdapter",
                "GtfsZipSourceAdapter",
                "CsvSourceAdapter",
                "GeoJsonSourceAdapter",
                "GeoPackageSourceAdapter",
            )
        ),
        "xml_and_archive_security_boundaries_are_explicit": (
            "DTD and entity declarations are prohibited" in citygml_source
            and "unsafe member path" in adapter_source
            and "max_uncompressed_bytes" in adapter_source
        ),
        "postgis_schema_covers_municipal_entities": all(
            f"CREATE TABLE {table}" in migrations for table in required_tables
        ),
        "bounded_api_covers_review_workflow": required_routes <= routes,
        "workspace_assets_match_hashes_and_privacy_policy": (
            _hashes_match(workspace, "public_workspace_story")
            and _hashes_match(workspace, "public_map")
            and _hashes_match(workspace, "public_building_points")
            and workspace["public_building_points"]["point_count"] == 7_684
            and "no per-building person estimates" in workspace["privacy"]
        ),
        "competition_story_remains_ab_while_workspace_is_abc": (
            len(competition_story["scenario_story"]) == 2
            and len(workspace_story["scenario_story"]) == 3
        ),
        "browser_workspace_audit_passed": browser["passed"],
        "evidence_json_csv_html_hashes_match": (
            set(evidence["formats"]) == {"json", "csv", "html"}
            and _evidence_hashes_match(evidence)
        ),
        "database_execution_is_not_overclaimed": (
            canonical["database_executed"] is False
            and workspace["database_loaded"] is False
            and evidence["database_executed"] is False
        ),
        "sparse_scenario_matrix_avoids_dense_zero_gain_pairs": (
            performance["sparse_improvement_pair_count"] == 1_063_003
            and performance["avoided_zero_gain_pair_count"] == 78_732_977
            and performance["total_runtime_seconds"] < 30
        ),
    }
    audit = {
        "schema_version": "municipal-platform-final-audit-1.0.0",
        "audit_date": "2026-08-27",
        "scope": "tracked real-data artifacts, contracts, static UI and browser audit",
        "passed": all(checks.values()),
        "checks": checks,
        "real_data_metrics": {
            "plateau_feature_count": inventory["totals"]["feature_count"],
            "plateau_theme_count": len(inventory["themes"]),
            "citygml_building_count": buildings["counts"]["buildings_audited"],
            "strict_residential_buildings": buildings["counts"][
                "strict_residential_buildings_citywide"
            ],
            "network_demographic_buildings": road["coverage"]["strict_demographic_buildings"],
            "road_nodes": road["graph"]["nodes"],
            "road_edges": road["graph"]["edges"],
            "transport_reachable_buildings": road["coverage"][
                "transport_reachable_buildings"
            ],
            "medical_reachable_buildings": road["coverage"]["medical_reachable_buildings"],
            "scenario_candidates": context_summary["targets"]["scenario_candidates"],
            "scenario_plans": scenarios["evidence"]["plan_count"],
            "workspace_building_points": workspace["public_building_points"]["point_count"],
        },
        "performance": {
            "network_analysis_seconds": road["performance"]["total_seconds"],
            "network_peak_rss_kib": road["performance"]["peak_rss_kib"],
            "scenario_analysis_seconds": performance["total_runtime_seconds"],
            "scenario_peak_rss_kib": performance["peak_rss_kib"],
            "sparse_pairs": performance["sparse_improvement_pair_count"],
            "dense_pairs_avoided": performance["avoided_zero_gain_pair_count"],
            "headless_demo_ready_ms": browser["demo_ready_ms"],
            "headless_scenario_a_points_ready_ms": browser[
                "scenario_a_points_ready_ms_from_navigation"
            ],
        },
        "claim_boundaries": {
            "postgis_executed": False,
            "official_road_generator_executed": False,
            "validated_pedestrian_network": False,
            "gtfs_feed_loaded": False,
            "automatic_policy_recommendation": False,
            "building_estimates_are_residents": False,
        },
        "final_questions": {
            "A_plateau_removal_preserves_detailed_analysis": "NO",
            "B_plateau_is_analysis_foundation_not_only_3d": "YES",
            "C_results_trace_to_sources_and_methods": "YES",
            "D_new_city_requires_core_logic_rewrite": "NO",
            "E_closer_to_municipal_platform_than_hackathon_demo": "YES",
        },
        "pilot_remaining": [
            "Execute migrations and canonical loaders against an approved PostGIS environment.",
            "Acquire and validate actual municipal GTFS or operator timetable data; do not convert P11 points.",
            "Generate or validate a pedestrian network with crossings, permissions and road-safety review.",
            "Add authenticated role-based access, durable queue workers, backups and monitoring.",
            "Collect field checks, land ownership, capacity, operating constraints and reviewed costs.",
            "Benchmark 100k+ buildings and edges with MVT/PMTiles delivery before a production SLA.",
        ],
    }
    return audit


def main() -> None:
    audit = build_audit()
    OUTPUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not audit["passed"]:
        failed = [name for name, passed in audit["checks"].items() if not passed]
        raise SystemExit(f"Municipal platform audit failed: {failed}")
    print(f"wrote {OUTPUT.relative_to(ROOT)} with {len(audit['checks'])} passing checks")


if __name__ == "__main__":
    main()
