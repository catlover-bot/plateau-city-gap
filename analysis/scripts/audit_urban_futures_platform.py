"""Build a deterministic final audit for the Urban Futures & Resilience extension."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.citygap_platform.api.app import create_app
from backend.citygap_platform.domain.jobs import JOB_STAGES
from backend.citygap_platform.domain.registry import CAPABILITIES, validate_platform_registry
from backend.citygap_platform.security.auth import ROLE_PERMISSIONS

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "analysis/outputs/real"
EVIDENCE = ROOT / "analysis/outputs/evidence-v3"
OUTPUT = REAL / "urban_futures_platform_final_audit.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_audit() -> dict[str, Any]:
    validation = _load(REAL / "urban_futures_validation.json")
    registry = _load(REAL / "platform_registry.json")
    benchmark = _load(ROOT / "analysis/outputs/benchmarks/urban_resilience_scale.json")
    browser = _load(REAL / "urban_futures_browser_audit.json")
    municipal = _load(REAL / "municipal_platform_final_audit.json")
    public = _load(ROOT / "frontend/public/data/urban_futures_resilience.json")
    evidence = _load(EVIDENCE / "maizuru-2025-flood-evidence-v3.json")
    migrations = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "infra/migrations").glob("*.sql"))
    )
    routes = {route.path for route in create_app(repository=object()).routes}
    validate_platform_registry(registry)

    cities = validation["cities"]
    maizuru = cities["maizuru"]
    fujisawa = cities["fujisawa"]
    future_rows = [
        row
        for city in cities.values()
        for series in city["official_future_population"]["series"].values()
        for row in series
    ]
    explicit_stress_tests = [
        stress
        for city in cities.values()
        for stress in city["stress_tests"].values()
    ]
    capability_rows = {
        (row["city_code"], row["capability"]): row["status"]
        for row in registry["capabilities"]
    }
    required_tables = {
        "urban_states",
        "state_dataset_versions",
        "state_network_versions",
        "state_analysis_runs",
        "urban_state_change_sets",
        "recomputation_plans",
        "incremental_recompute_validations",
        "stress_test_runs",
        "stress_test_assumptions",
        "stress_test_edge_impacts",
        "stress_test_building_impacts",
        "stress_test_facility_impacts",
        "stress_test_metrics",
        "future_population_states",
        "policy_portfolios",
        "implementation_records",
        "outcome_evaluations",
        "field_offline_packages",
        "field_sync_conflicts",
        "temporal_evidence_packages",
        "municipal_annual_reports",
    }
    required_routes = {
        "/cities/{city_id}/states",
        "/cities/{city_id}/states/{state_id}",
        "/cities/{city_id}/state-comparison",
        "/cities/{city_id}/changes",
        "/cities/{city_id}/stress-tests",
        "/stress-tests/{stress_test_id}",
        "/stress-tests/{stress_test_id}/impacts",
        "/cities/{city_id}/network/criticality",
        "/cities/{city_id}/future-states",
        "/cities/{city_id}/outcomes",
        "/cities/{city_id}/field/offline-packages",
        "/cities/{city_id}/field/sync",
    }
    new_jobs = {
        "dataset_diff",
        "incremental_recompute",
        "future_population",
        "stress_test",
        "criticality_analysis",
        "outcome_evaluation",
    }
    expected_capability_statuses = {
        "temporal_diff": "partial",
        "future_population": "available",
        "hazard_stress_test": "available",
        "criticality": "available",
        "evacuation_reachability": "available",
        "planning_monitoring": "available",
        "field_mode": "partial",
        "outcome_monitoring": "partial",
    }

    checks = {
        "existing_municipal_platform_remains_valid": municipal["passed"],
        "two_real_cities_use_non_synthetic_validation": (
            set(cities) == {"maizuru", "fujisawa"}
            and validation["generated_from_synthetic_data"] is False
        ),
        "urban_state_identity_diff_is_correctly_bounded": (
            maizuru["state_diff_identity_validation"]["correctness_check"]
            and fujisawa["state_diff_identity_validation"]["correctness_check"]
            and maizuru["state_diff_identity_validation"]["result"]["unchanged"] == 23_437
            and fujisawa["state_diff_identity_validation"]["result"]["unchanged"] == 71_487
            and "second official PLATEAU version"
            in maizuru["state_diff_identity_validation"]["annual_change_detection"]
        ),
        "future_population_is_official_verified_and_not_prediction": (
            len(future_rows) >= 21
            and all(row["source_verified"] for row in future_rows)
            and all(row["fixed_service_assumption"] for row in future_rows)
            and all("official population scenario" in row["limitation"] for row in future_rows)
        ),
        "maizuru_runs_three_explicit_hazard_stress_tests": (
            set(maizuru["stress_tests"]) == {"flood", "landslide", "tsunami"}
            and all(stress["assumption"]["explicitly_confirmed"] for stress in explicit_stress_tests)
            and all("not a prediction" in stress["assumption"]["limitation"] for stress in explicit_stress_tests)
        ),
        "fujisawa_missing_hazard_types_are_not_fabricated": set(fujisawa["stress_tests"]) == {"flood"},
        "criticality_is_linear_and_independently_verified": all(
            city["criticality"]["algorithm"].endswith("O(V+E)")
            and city["criticality"]["candidate_count"] > 0
            and all(
                row["independent_removal_verifier"]
                for row in city["criticality"]["independent_verification"]
            )
            for city in cities.values()
        ),
        "official_shelters_are_network_reachability_only": all(
            city["official_shelters"]["feature_count"] > 0
            and "not evacuation" in city["official_shelters"]["reachability_semantics"]
            for city in cities.values()
        ),
        "planning_comparison_makes_no_legal_claim": all(
            not city["planning_context"]["legal_compliance_claimed"]
            and city["planning_context"]["label"] == "planning-context mismatch candidate"
            for city in cities.values()
        ),
        "capability_matrix_is_complete_and_evidence_backed": (
            len(registry["capabilities"]) == 2 * len(CAPABILITIES)
            and all(
                capability_rows[(city_code, name)] == status
                for city_code in ("26202", "14205")
                for name, status in expected_capability_statuses.items()
            )
        ),
        "postgis_schema_covers_temporal_resilience_cycle": all(
            f"CREATE TABLE {table}" in migrations for table in required_tables
        ),
        "api_is_bounded_and_covers_temporal_cycle": required_routes <= routes,
        "jobs_cover_detect_through_reevaluate": new_jobs <= set(JOB_STAGES),
        "rbac_separates_analysis_planning_and_admin": (
            "stress_test:create" in ROLE_PERMISSIONS["analyst"]
            and {"outcome:review", "field:sync"} <= ROLE_PERMISSIONS["planner"]
            and ROLE_PERMISSIONS["administrator"] == frozenset({"*"})
        ),
        "evidence_v3_has_three_nonempty_formats": (
            evidence["schema_version"] == "evidence-v3.0.0"
            and all(
                (EVIDENCE / f"maizuru-2025-flood-evidence-v3.{suffix}").stat().st_size > 0
                for suffix in ("json", "csv", "html")
            )
            and evidence["field_verification"]["automatic_approval"] is False
        ),
        "public_asset_is_aggregated_and_not_predictive": (
            public["building_level_demographics_included"] is False
            and public["analysis_status"] == "reviewed_aggregated_real_data"
            and public["story"]["prediction_claimed"] is False
        ),
        "public_resilience_maps_are_aggregated_and_bounded": all(
            city["resilience_map"]["features"]
            and all(
                feature["properties"]["layer_type"]
                in {
                    "normal_route",
                    "disrupted_route",
                    "critical_edge",
                    "disconnected_area",
                    "affected_facility",
                }
                and "gml_id" not in feature["properties"]
                and "building_id" not in feature["properties"]
                and "estimated_population" not in feature["properties"]
                for feature in city["resilience_map"]["features"]
            )
            for city in public["cities"].values()
        ),
        "public_browser_audit_passes_seven_boundaries": (
            browser["passed"]
            and len(browser["checks"]) == 7
            and all(browser["checks"].values())
            and not browser["console_errors"]
        ),
        "all_requested_synthetic_scales_are_separate": (
            benchmark["all_requested_scales_executed"]
            and [row["road_edges"] for row in benchmark["benchmarks"]]
            == [100_000, 250_000, 500_000]
            and all(row["generated_from_synthetic_data"] for row in benchmark["benchmarks"])
        ),
        "golden_maizuru_has_at_least_five_real_cases": (
            len(validation["golden_maizuru_cases"]) >= 5
            and all(row["status"] == "pass" and row["real_data"] for row in validation["golden_maizuru_cases"])
        ),
    }
    return {
        "schema_version": "urban-futures-platform-final-audit-1.0.0",
        "audit_date": "2026-08-27",
        "baseline_commit": "a8d382a3f007e9d8146e98d83704e82983530736",
        "passed": all(checks.values()),
        "checks": checks,
        "check_count": len(checks),
        "external_verification": {
            "municipal_pilot_ci_run": 33066544364,
            "pages_deploy_run": 33066544350,
            "verified_commit": "b724ee736751b0f4ef86daf68b519d6ddb48d323",
            "note": "External run IDs are recorded facts; this local audit does not query GitHub.",
        },
        "remaining_municipal_validation": [
            "Register a second official PLATEAU version before claiming annual change counts.",
            "Approve a full municipal PostGIS load, network source and shelter snap tolerances.",
            "Configure production OIDC, audit retention, backups and field-device policy.",
            "Register a real implemented intervention and later observed state before outcome use.",
            "Complete municipal legal, licensing, accessibility, privacy and publication review.",
        ],
    }


def main() -> None:
    audit = build_audit()
    OUTPUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not audit["passed"]:
        failed = [name for name, passed in audit["checks"].items() if not passed]
        raise SystemExit(f"Urban Futures final audit failed: {failed}")
    print(f"wrote {OUTPUT.relative_to(ROOT)} with {audit['check_count']} passing checks")


if __name__ == "__main__":
    main()
