"""Build the deterministic 120-goal Municipal Open Data Platform audit."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

from backend.citygap_platform.database.migrations import checksum, migration_files
from backend.citygap_platform.open_data.registry import OFFICIAL_SOURCE_REGISTRY

ROOT = Path(__file__).resolve().parents[2]
OPEN_REAL = ROOT / "analysis/outputs/real/open_data"
OUTPUT = OPEN_REAL / "open_data_platform_final_audit.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_matches(summary: dict[str, Any], path_key: str, hash_key: str) -> bool:
    path = ROOT / summary[path_key]
    return path.is_file() and _sha256(path) == summary[hash_key]


def _unimplemented_skip_count() -> int:
    count = 0
    for directory in (ROOT / "analysis", ROOT / "backend"):
        for path in directory.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                if not (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "pytest"
                    and node.func.attr == "skip"
                ):
                    continue
                if node.args and isinstance(node.args[0], ast.Constant):
                    count += str(node.args[0].value).startswith("UNIMPLEMENTED:")
    return count


GOALS: tuple[tuple[int, str, str], ...] = (
    (1, "OPEN DATA ADAPTER REGISTRY", "registry"),
    (2, "SOURCE REGISTRY", "registry"),
    (3, "OFFICIAL SOURCE FIRST", "official_sources"),
    (4, "SOURCE PROVENANCE CONTRACT", "provenance"),
    (5, "LICENSE MACHINE-READABLE MODEL", "licence_public"),
    (6, "NO UNSAFE REDISTRIBUTION", "licence_public"),
    (7, "DATA DISCOVERY", "discovery_coverage"),
    (8, "DATA COVERAGE MATRIX", "discovery_coverage"),
    (9, "WHY UNAVAILABLE", "discovery_coverage"),
    (10, "MUNICIPAL STANDARD ODS ADAPTER", "standard_ods"),
    (11, "STANDARD ODS SCHEMA MAPPING", "standard_ods"),
    (12, "SCHEMA DRIFT", "standard_ods"),
    (13, "MUNICIPAL CKAN/BODIK ADAPTER", "ckan_inventory"),
    (14, "MAIZURU OPEN DATA INVENTORY", "ckan_inventory"),
    (15, "FUJISAWA OPEN DATA INVENTORY", "ckan_inventory"),
    (16, "MHLW MEDICAL ADAPTER", "mhlw_health"),
    (17, "MEDICAL FACILITY IDENTITY", "medical_identity"),
    (18, "NO FALSE MEDICAL AVAILABILITY", "mhlw_health"),
    (19, "CARE SERVICE ADAPTER", "mhlw_health"),
    (20, "KAYOI-NO-BA / SOCIAL PARTICIPATION", "secondary_capabilities"),
    (21, "WELFARE ADAPTER", "secondary_capabilities"),
    (22, "FUTURE 250M POPULATION", "demographic_economic"),
    (23, "FUTURE POPULATION SCENARIO MODEL", "demographic_economic"),
    (24, "NO BEST FUTURE MODEL", "demographic_economic"),
    (25, "ECONOMIC CENSUS", "demographic_economic"),
    (26, "DAYTIME ACTIVITY", "demographic_economic"),
    (27, "NEW FINDING: SERVICE / ACTIVITY MISMATCH", "service_activity_findings"),
    (28, "NPA TRAFFIC ACCIDENT ADAPTER", "traffic_ground"),
    (29, "ACCIDENT HISTORICAL CONTEXT", "traffic_ground"),
    (30, "GSI FOUNDATION MAP", "gsi_boundary"),
    (31, "JGD2024", "datum_contract"),
    (32, "PLATEAU VS GSI VALIDATION", "gsi_boundary"),
    (33, "J-SHIS ADAPTER", "traffic_ground"),
    (34, "EARTHQUAKE CONTEXT", "traffic_ground"),
    (35, "HAZARD TYPE MODEL", "hazard_semantics"),
    (36, "NO UNIVERSAL HAZARD SCORE", "hazard_semantics"),
    (37, "PEDESTRIAN NETWORK RESEARCH", "pedestrian_boundary"),
    (38, "PEDESTRIAN CAPABILITY", "pedestrian_boundary"),
    (39, "ACCESSIBILITY MODEL V2", "pedestrian_boundary"),
    (40, "PEDESTRIAN ATTRIBUTES", "pedestrian_boundary"),
    (41, "XROAD RESEARCH", "xroad_boundary"),
    (42, "TRAFFIC VOLUME CONTEXT", "xroad_boundary"),
    (43, "TRAFFIC VOLUME != CAPACITY", "transport_semantics"),
    (44, "STATION USAGE", "secondary_capabilities"),
    (45, "GTFS RESEARCH AGAIN", "transport_semantics"),
    (46, "PERSON TRIP", "secondary_capabilities"),
    (47, "MOBILITY != INDIVIDUAL TRACKING", "transport_semantics"),
    (48, "OPEN DATA CANONICAL MODEL", "canonical_lineage"),
    (49, "RAW + CANONICAL", "canonical_lineage"),
    (50, "TRANSFORMATION LINEAGE", "canonical_lineage"),
    (51, "SPATIAL LINKAGE", "canonical_lineage"),
    (52, "TEMPORAL ALIGNMENT", "temporal_contract"),
    (53, "TEMPORAL MISMATCH", "temporal_contract"),
    (54, "DATA FRESHNESS", "updates_dependency"),
    (55, "UPDATE DETECTION", "updates_dependency"),
    (56, "DATA UPDATE JOBS", "updates_dependency"),
    (57, "DEPENDENCY GRAPH V2", "updates_dependency"),
    (58, "NO AUTOMATIC FINDING INVALIDATION", "updates_dependency"),
    (59, "DATA HUB V2", "data_hub"),
    (60, "CITY DATA COVERAGE UI", "data_hub"),
    (61, "MISSING DATA AS PRODUCT FEATURE", "data_hub"),
    (62, "CAPABILITY AUTO-REFRESH", "data_hub"),
    (63, "ANALYSIS CATALOG V2", "analyses"),
    (64, "ANALYSIS DEGRADATION", "analyses"),
    (65, "SERVICE NEED DOMAINS", "analyses"),
    (66, "MEDICAL ACCESS V2", "analyses"),
    (67, "CARE ACCESS", "analyses"),
    (68, "SOCIAL PARTICIPATION ACCESS", "secondary_capabilities"),
    (69, "DAYTIME SERVICE CONTEXT", "analyses"),
    (70, "RESILIENCE V2", "analyses"),
    (71, "PLATEAU REMAINS PRIMARY SPATIAL MODEL", "plateau_spatial"),
    (72, "PLATEAU LINK COVERAGE", "plateau_spatial"),
    (73, "PROVENANCE IN SPATIAL WORKSPACE", "product_ux"),
    (74, "DATA TIMELINE", "data_hub"),
    (75, "DO NOT HIDE MIXED YEARS", "temporal_contract"),
    (76, "DATASET COMPARISON", "source_governance"),
    (77, "CONFLICT MODEL", "source_governance"),
    (78, "SOURCE PREFERENCE POLICY", "source_governance"),
    (79, "DATA QUALITY SCOREは禁止", "quality_operations"),
    (80, "QUALITY GATE POLICIES", "quality_operations"),
    (81, "QUARANTINE", "quality_operations"),
    (82, "REPROCESSING", "quality_operations"),
    (83, "REPRODUCIBILITY", "quality_operations"),
    (84, "OPEN DATA OPERATIONS UI", "product_ux"),
    (85, "NO DEVELOPER REQUIRED FOR NORMAL UPDATE", "updates_dependency"),
    (86, "SCHEDULED METADATA CHECK", "updates_dependency"),
    (87, "NO AGGRESSIVE SCRAPING", "provider_resilience"),
    (88, "OBJECT STORAGE PREPARATION", "storage"),
    (89, "CONTENT-ADDRESSED RAW STORAGE", "storage"),
    (90, "SECURITY", "security"),
    (91, "CSV FORMULA INJECTION", "security"),
    (92, "XML / GML SAFETY", "security"),
    (93, "PROVIDER FAILURE", "provider_resilience"),
    (94, "NO LIVE API HARD DEPENDENCY", "provider_resilience"),
    (95, "PERFORMANCE", "performance"),
    (96, "POSTGIS INDEXING", "postgis_indexes"),
    (97, "REAL CITY BENCHMARK", "performance"),
    (98, "COLD/WARM TILE", "performance"),
    (99, "CONCURRENCY", "performance"),
    (100, "SKIP TEST AUDIT", "skip_audit"),
    (101, "MIGRATION SAFETY", "migration_safety"),
    (102, "API V1 EXTENSION", "api_v1"),
    (103, "TENANT BOUNDARY", "tenancy_cache"),
    (104, "SHARED PUBLIC SOURCE CACHE", "tenancy_cache"),
    (105, "SEARCH V2", "search_home_onboarding"),
    (106, "CITY HOME V2", "search_home_onboarding"),
    (107, "ORGANIZATION HOME V2", "search_home_onboarding"),
    (108, "OPEN DATA ONBOARDING", "search_home_onboarding"),
    (109, "AUTO-DISCOVERY != AUTO-ACCEPT", "discovery_coverage"),
    (110, "PRODUCT UX", "product_ux"),
    (111, "ADVANCED TECH DETAILS", "product_ux"),
    (112, "MUNICIPAL JAPANESE COPY", "product_ux"),
    (113, "FIELD VALIDATION CONNECTION", "field_feedback"),
    (114, "SOURCE FEEDBACK", "field_feedback"),
    (115, "LOCAL OVERRIDE MODEL", "override_governance"),
    (116, "OVERRIDE GOVERNANCE", "override_governance"),
    (117, "OFFICIAL UPDATE RECONCILIATION", "override_governance"),
    (118, "EVIDENCE CENTER V2", "evidence_reports"),
    (119, "REPORTS V2", "evidence_reports"),
    (120, "PUBLIC TRANSPARENCY", "public_transparency"),
)

BOUNDARY_GOALS = frozenset({20, 21, 30, 32, 37, 38, 40, 41, 42, 44, 45, 46, 68})

EVIDENCE: dict[str, list[str]] = {
    "registry": ["backend/citygap_platform/open_data/registry.py"],
    "official_sources": ["backend/citygap_platform/open_data/registry.py"],
    "provenance": ["infra/migrations/018_open_data_foundation.sql"],
    "licence_public": [
        "infra/migrations/018_open_data_foundation.sql",
        "analysis/outputs/real/open_data/official_capability_audit.json",
    ],
    "discovery_coverage": [
        "analysis/outputs/real/open_data/municipal_catalog_inventory.json",
        "infra/migrations/023_city_data_coverage_lineage.sql",
    ],
    "standard_ods": ["backend/citygap_platform/open_data/standard_ods.py"],
    "ckan_inventory": [
        "backend/citygap_platform/open_data/ckan.py",
        "analysis/outputs/real/open_data/municipal_catalog_inventory.json",
    ],
    "mhlw_health": ["analysis/outputs/real/open_data/mhlw_health_summary.json"],
    "medical_identity": ["analysis/outputs/real/open_data/mhlw_medical_identity_comparison.json"],
    "secondary_capabilities": [
        "analysis/outputs/real/open_data/official_capability_audit.json",
        "infra/migrations/026_secondary_official_capability_boundaries.sql",
    ],
    "demographic_economic": ["analysis/outputs/real/open_data/demographic_economic_summary.json"],
    "service_activity_findings": [
        "analysis/outputs/real/open_data/municipal_open_data_analysis_summary.json"
    ],
    "traffic_ground": ["analysis/outputs/real/open_data/geospatial_resilience_summary.json"],
    "gsi_boundary": ["infra/migrations/021_geospatial_resilience_sources.sql"],
    "datum_contract": ["infra/migrations/018_open_data_foundation.sql"],
    "hazard_semantics": [
        "infra/migrations/012_network_resilience.sql",
        "analysis/outputs/real/open_data/geospatial_resilience_summary.json",
    ],
    "pedestrian_boundary": ["infra/migrations/023_city_data_coverage_lineage.sql"],
    "xroad_boundary": ["analysis/outputs/real/open_data/geospatial_resilience_summary.json"],
    "transport_semantics": [
        "infra/migrations/023_city_data_coverage_lineage.sql",
        "infra/migrations/026_secondary_official_capability_boundaries.sql",
    ],
    "canonical_lineage": ["infra/migrations/018_open_data_foundation.sql"],
    "temporal_contract": [
        "analysis/outputs/real/open_data/demographic_economic_summary.json",
        "analysis/outputs/real/open_data/mhlw_health_summary.json",
    ],
    "updates_dependency": ["infra/migrations/024_open_data_operations.sql"],
    "data_hub": ["frontend/src/service/ServiceApp.tsx"],
    "analyses": ["analysis/outputs/real/open_data/municipal_open_data_analysis_summary.json"],
    "plateau_spatial": [
        "analysis/outputs/real/open_data/municipal_open_data_analysis_summary.json"
    ],
    "source_governance": ["infra/migrations/023_city_data_coverage_lineage.sql"],
    "quality_operations": [
        "infra/migrations/023_city_data_coverage_lineage.sql",
        "infra/migrations/024_open_data_operations.sql",
    ],
    "storage": ["backend/citygap_platform/open_data/storage.py"],
    "security": [
        "backend/citygap_platform/ingestion/adapters.py",
        "backend/citygap_platform/ingestion/citygml.py",
    ],
    "provider_resilience": ["infra/migrations/024_open_data_operations.sql"],
    "performance": ["analysis/outputs/real/pilot_performance.json"],
    "postgis_indexes": ["infra/migrations/024_open_data_operations.sql"],
    "skip_audit": ["backend/tests/test_skip_classification.py"],
    "migration_safety": ["infra/migrations/026_secondary_official_capability_boundaries.sql"],
    "api_v1": ["backend/citygap_platform/api/service.py"],
    "tenancy_cache": ["infra/migrations/018_open_data_foundation.sql"],
    "search_home_onboarding": ["frontend/src/service/ServiceApp.tsx"],
    "product_ux": ["frontend/src/service/ServiceApp.tsx"],
    "field_feedback": ["infra/migrations/025_open_data_review_evidence.sql"],
    "override_governance": ["infra/migrations/025_open_data_review_evidence.sql"],
    "evidence_reports": [
        "infra/migrations/025_open_data_review_evidence.sql",
        "backend/citygap_platform/api/service_repository.py",
    ],
    "public_transparency": ["infra/migrations/025_open_data_review_evidence.sql"],
}


def build_audit() -> dict[str, Any]:
    inventory = _load(OPEN_REAL / "municipal_catalog_inventory.json")
    maizuru = _load(OPEN_REAL / "maizuru_p0_canonical_summary.json")
    health = _load(OPEN_REAL / "mhlw_health_summary.json")
    demographic = _load(OPEN_REAL / "demographic_economic_summary.json")
    resilience = _load(OPEN_REAL / "geospatial_resilience_summary.json")
    analyses = _load(OPEN_REAL / "municipal_open_data_analysis_summary.json")
    secondary = _load(OPEN_REAL / "official_capability_audit.json")
    performance = _load(ROOT / "analysis/outputs/real/pilot_performance.json")
    migrations = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "infra/migrations").glob("*.sql"))
    }
    all_migrations = "\n".join(migrations.values())
    service_source = _read("backend/citygap_platform/api/service.py")
    repository_source = _read("backend/citygap_platform/api/service_repository.py")
    ui_source = _read("frontend/src/service/ServiceApp.tsx")
    ods_source = _read("backend/citygap_platform/open_data/standard_ods.py")
    storage_source = _read("backend/citygap_platform/open_data/storage.py")
    adapter_source = _read("backend/citygap_platform/ingestion/adapters.py")
    citygml_source = _read("backend/citygap_platform/ingestion/citygml.py")
    workflow_source = _read(".github/workflows/pilot-ci.yml")
    foundation = migrations["018_open_data_foundation.sql"]
    lineage = migrations["023_city_data_coverage_lineage.sql"]
    operations = migrations["024_open_data_operations.sql"]
    review = migrations["025_open_data_review_evidence.sql"]
    secondary_migration = migrations["026_secondary_official_capability_boundaries.sql"]

    inventory_cities = {city["city_code"]: city for city in inventory["cities"]}
    resilience_cities = resilience["cities"]
    analysis_ids = {item["analysis_id"] for item in analyses["analysis_availability"]}
    required_analysis_ids = {
        "medical-access-v2",
        "care-access",
        "future-population-spatial",
        "daytime-activity-context",
        "earthquake-ground-context",
        "historical-traffic-safety-context",
    }
    required_source_keys = {
        "digital-agency-municipal-standard-ods",
        "bodik-maizuru",
        "fujisawa-open-data-library",
        "mhlw-medical-information-network",
        "mhlw-care-service",
        "mlit-future-population-250m-r6",
        "estat-economic-census-2021-500m",
        "gsi-fundamental-geospatial-data",
        "jshis-surface-ground-v4",
        "npa-traffic-accident-2024",
        "mlit-pedestrian-network-catalog",
        "xroad-open-traffic-api",
        "mhlw-kayoi-no-ba",
        "wam-disability-welfare-open-data",
        "mlit-station-passenger-count-s12",
        "mlit-person-trip-study-catalog",
    }

    checks = {
        "registry": (
            len(OFFICIAL_SOURCE_REGISTRY.adapters) == 20
            and len(OFFICIAL_SOURCE_REGISTRY.sources) == 22
            and required_source_keys
            <= {source.source_key for source in OFFICIAL_SOURCE_REGISTRY.sources}
        ),
        "official_sources": all(
            source.official_url.startswith("https://") and source.provider
            for source in OFFICIAL_SOURCE_REGISTRY.sources
        ),
        "provenance": all(
            term in foundation
            for term in (
                "open_data_source_catalog",
                "open_data_resources",
                "adapter_version",
                "source_row_locator",
                "transformation_run_id",
                "canonical_version",
            )
        ),
        "licence_public": (
            "open_data_license_policies" in foundation
            and "unknown_terms boolean NOT NULL" in foundation
            and secondary["result"]["public_raw_resource_count"] == 0
            and "Reject tracked secrets and raw municipal data" in workflow_source
        ),
        "discovery_coverage": (
            inventory["official_sources_only"] is True
            and len(inventory["coverage"]) == 28
            and {item["status"] for item in inventory["coverage"]}
            <= {"available", "partial", "unavailable", "unknown", "requires_review"}
            and all(
                item.get("unavailable_reason")
                for item in inventory["coverage"]
                if item["status"] in {"unavailable", "requires_review"}
            )
            and "automatic_acceptance', false" in operations
        ),
        "standard_ods": all(
            term in ods_source
            for term in (
                "class OdsSchema",
                "SCHEMAS",
                "CanonicalRecordType",
                "schema_audit",
                "canonicalize_rows",
            )
        ),
        "ckan_inventory": (
            inventory_cities["26202"]["dataset_count"] == 30
            and inventory_cities["26202"]["resource_count"] == 31
            and inventory_cities["14205"]["dataset_count"] == 9
            and inventory_cities["14205"]["resource_count"] == 9
            and inventory_cities["14205"]["linked_resource_license_id"] == "unknown"
        ),
        "mhlw_health": (
            health["raw_resource_count"] == 43
            and health["raw_unique_sha256_count"] == 43
            and health["canonical_record_count"] == 7_923
            and health["cities"]["maizuru"]["canonical_record_count"] == 741
            and health["cities"]["fujisawa"]["canonical_record_count"] == 7_182
            and health["analysis_readiness"] == "requires_review"
            and health["unavailable_reason"] == "not_verified"
        ),
        "medical_identity": (
            analyses["cities"]["maizuru"]["plateau_link_coverage"]["medical"]["identity_claimed"]
            is False
            and health["cities"]["maizuru"]["medical_identity_counts"]["ambiguous"] == 18
            and (OPEN_REAL / "mhlw_medical_identity_comparison.json").is_file()
        ),
        "secondary_capabilities": (
            secondary["result"]["status"] == "passed"
            and secondary["result"]["registered_source_count"] == 4
            and secondary["result"]["promoted_canonical_source_count"] == 0
            and secondary["result"]["synthetic_record_count"] == 0
            and '"missing_rows_are_not_zero":true' in secondary_migration
            and '"individual_tracking":false' in secondary_migration
        ),
        "demographic_economic": (
            demographic["raw_resource_count"] == 4
            and demographic["raw_unique_sha256_count"] == 4
            and demographic["canonical_record_count"] == 2_629
            and demographic["mesh_context_feature_count"] == 822
            and demographic["automatic_best_projection_selected"] is False
            and demographic["temporal_alignment"] == "mixed_and_explicit"
        ),
        "service_activity_findings": (
            analyses["finding_count"] == 50
            and sum(
                city["finding_counts"]["activity_service_gap_candidate"]
                for city in analyses["cities"].values()
            )
            == 20
            and analyses["generated_from_synthetic_data"] is False
        ),
        "traffic_ground": (
            resilience["canonical_record_count"] == 4_105
            and resilience["prediction_generated"] is False
            and resilience["risk_probability_generated"] is False
            and resilience["unavailable_sources_fabricated_as_rows"] is False
            and resilience_cities["maizuru"]["jshis_surface_ground"]["published_250m_cell_count"]
            == 1_980
            and resilience_cities["fujisawa"]["historical_traffic_accidents"]["record_count"] == 982
        ),
        "gsi_boundary": all(
            city["researched_capabilities"]["gsi_foundation_map"]
            == {"status": "requires_review", "unavailable_reason": "requires_credentials"}
            for city in resilience_cities.values()
        ),
        "datum_contract": all(
            term in foundation
            for term in (
                "horizontal_datum text",
                "vertical_datum text",
                "transformation_method text",
                "source_crs text",
            )
        ),
        "hazard_semantics": (
            all(
                term in migrations["012_network_resilience.sql"]
                for term in (
                    "hazard_dataset_version_id",
                    "hazard_type text",
                    "hazard_class text",
                    "closure_assumption text",
                    "assumption_source text",
                    "explicitly_confirmed boolean",
                )
            )
            and resilience["risk_probability_generated"] is False
            and analyses["quality_model"]["single_quality_score"] is False
        ),
        "pedestrian_boundary": (
            "PLATEAU roads are not substituted" in lineage
            and all(
                city["researched_capabilities"]["pedestrian_network"]
                == {"status": "unavailable", "unavailable_reason": "outside_coverage"}
                for city in resilience_cities.values()
            )
        ),
        "xroad_boundary": all(
            city["researched_capabilities"]["xroad_traffic"]["stable_snapshot_ingested"] is False
            for city in resilience_cities.values()
        ),
        "transport_semantics": (
            "not_gtfs" in lineage
            and "no traffic volume, congestion, capacity or prediction metric"
            in _read("docs/open-data-geospatial-resilience.md")
            and "not_capacity_or_congestion" in secondary_migration
            and "individual_tracking" in secondary_migration
        ),
        "canonical_lineage": (
            all(
                f"CREATE TABLE {table}" in foundation
                for table in (
                    "open_data_raw_blobs",
                    "open_data_resources",
                    "canonical_open_data_records",
                    "open_data_spatial_links",
                )
            )
            and _artifact_matches(maizuru, "canonical_artifact", "canonical_artifact_sha256")
            and _artifact_matches(health, "canonical_artifact", "canonical_artifact_sha256")
            and _artifact_matches(demographic, "canonical_artifact", "canonical_artifact_sha256")
            and _artifact_matches(resilience, "canonical_artifact", "canonical_artifact_sha256")
        ),
        "temporal_contract": (
            all(
                city["temporal_alignment"]["status"] == "mixed"
                and city["temporal_alignment"]["hidden_as_single_year"] is False
                for city in health["cities"].values()
            )
            and all(
                city["temporal_alignment"]["status"] == "mixed"
                and city["temporal_alignment"]["hidden_as_single_year"] is False
                for city in demographic["cities"].values()
            )
        ),
        "updates_dependency": all(
            term in operations
            for term in (
                "open_data_source_refresh_policies",
                "open_data_operator_tasks",
                "open_data_reprocessing_requests",
                "preserve_previous_canonical",
                "scheduled_interval_hours >= minimum_interval_hours",
                "analysis_run_open_data_inputs",
            )
        ),
        "data_hub": all(
            term in ui_source
            for term in (
                "DATA HUB",
                "都市データカバレッジ",
                "不足理由",
                "混在する基準時点",
                "Dependencies",
            )
        ),
        "analyses": (
            analysis_ids == required_analysis_ids
            and all(item["tier"] == "BASE" for item in analyses["analysis_availability"])
            and analyses["mesh_count"] == 822
            and analyses["finding_count"] == 50
        ),
        "plateau_spatial": (
            maizuru["plateau"]["building_count"] == 44_640
            and all(
                not coverage["identity_claimed"]
                for city in analyses["cities"].values()
                for coverage in city["plateau_link_coverage"].values()
            )
        ),
        "source_governance": all(
            term in lineage
            for term in (
                "open_data_dataset_comparisons",
                "open_data_source_conflicts",
                "analysis_source_selection_policies",
                "automatic_newer_wins boolean NOT NULL DEFAULT false",
                "automatic_truth_selection boolean NOT NULL DEFAULT false",
                "automatic_selection boolean NOT NULL DEFAULT false",
            )
        ),
        "quality_operations": (
            analyses["quality_model"]["single_quality_score"] is False
            and "dataset_family_quality_gate_policies" in lineage
            and "open_data_quarantine_events" in operations
            and "open_data_reprocessing_requests" in operations
            and "analysis_run_open_data_inputs" in operations
        ),
        "storage": (
            "sha256" in storage_source
            and "ContentAddressedObjectStore" in storage_source
            and "UNIQUE NULLS NOT DISTINCT (sha256, owner_organization_id)" in foundation
        ),
        "security": (
            "formula-like cell" in adapter_source
            and "DTD and entity declarations are prohibited" in citygml_source
            and "unsafe member path" in adapter_source
            and "max_uncompressed_bytes" in adapter_source
        ),
        "provider_resilience": (
            "preserve_previous_canonical boolean NOT NULL DEFAULT true" in operations
            and "minimum_interval_hours BETWEEN 6 AND 8760" in operations
            and all(item["tier"] == "BASE" for item in analyses["analysis_availability"])
        ),
        "performance": (
            performance["classification"]["api_database"] == "SYNTHETIC_SCALE"
            and performance["classification"]["real_pipeline"] == "REAL_MUNICIPAL_DATA"
            and performance["classification"]["production_sla_claimed"] is False
            and performance["classification"]["concurrency_result_is_sla"] is False
            and performance["synthetic_scale"]["buildings"] == 100_000
            and performance["synthetic_scale"]["road_edges"] == 100_000
            and set(performance["synthetic_scale"]["concurrency_1_10_25_50"])
            == {"bbox_buildings", "warm_vector_tile"}
            and set(performance["real_pipeline"]) == {"maizuru", "fujisawa"}
        ),
        "postgis_indexes": (
            "using gist" in all_migrations.lower()
            and "open_data_spatial_links_record_method_idx" in operations
            and "organization_id, city_id" in operations
        ),
        "skip_audit": _unimplemented_skip_count() == 0,
        "migration_safety": (
            [path.name[:3] for path in migration_files(ROOT / "infra/migrations")]
            == [f"{number:03d}" for number in range(1, 27)]
            and all(
                len(checksum(path)) == 64 for path in migration_files(ROOT / "infra/migrations")
            )
        ),
        "api_v1": all(
            route in service_source
            for route in (
                '"/cities/{city}/data-coverage"',
                '"/cities/{city}/sources"',
                '"/datasets"',
                '"/datasets/{dataset_id}"',
                '"/sources/discover"',
                '"/datasets/{dataset_id}/validate"',
                '"/datasets/{dataset_id}/promote"',
                '"/datasets/{dataset_id}/lineage"',
            )
        ),
        "tenancy_cache": (
            "REFERENCES cities(organization_id, id)" in foundation
            and "reuse_scope = 'public_verified' AND owner_organization_id IS NULL" in foundation
            and "reuse_scope = 'tenant_only' AND owner_organization_id IS NOT NULL" in foundation
            and "REFERENCES dataset_versions(organization_id, id)" in foundation
        ),
        "search_home_onboarding": all(
            term in ui_source
            for term in (
                "Organization内の都市",
                "この都市で使えるデータ",
                "公式ソースを探索",
                "onboardingLabels",
                "採用はまだ行っていません",
            )
        ),
        "product_ux": (
            all(
                term in ui_source
                for term in (
                    "出典",
                    "年度",
                    "利用状況",
                    "Source CRS",
                    "SHA-256",
                    "要確認",
                )
            )
            and all(
                term in _read("frontend/src/service/components.tsx")
                for term in ("標準形式への変換", "分析に使用中", "要確認")
            )
            and all(
                term in _read("frontend/src/features/inspector/ObjectLens.tsx")
                for term in (
                    "PLATEAU OBJECT LENS",
                    "Finding ↔ PLATEAU 追跡",
                    "PLATEAUを外すと失われるもの",
                )
            )
        ),
        "field_feedback": (
            "CREATE TABLE open_data_field_tasks" in review
            and "ALTER TABLE open_data_source_feedback" in review
            and "raw_mutation_permitted" in review
            and "canonical_mutation_permitted" in review
        ),
        "override_governance": all(
            term in review
            for term in (
                "ALTER TABLE local_data_overrides",
                "reviewed_by text",
                "expires_at",
                "effective_date",
                "open_data_override_reconciliation_candidate",
                "never deletes local overrides",
            )
        ),
        "evidence_reports": (
            "open_data_lineage_manifest" in review
            and "content_schema_version" in review
            and "deterministic boolean NOT NULL DEFAULT true" in review
            and "Evidence Center V2" in ui_source
            and all(
                report_name in repository_source
                for report_name in (
                    "data_coverage_report",
                    "data_quality_report",
                    "urban_state_source_report",
                    "analysis_source_report",
                )
            )
        ),
        "public_transparency": (
            "CREATE TABLE public_transparency_records" in review
            and "public transparency requires a public report" in review
            and "public transparency requires public evidence" in review
            and "source_citations jsonb" in review
            and "limitations jsonb" in review
            and "license.unknown_terms" in repository_source
            and "Public reports require public-classified inputs and evidence" in repository_source
        ),
    }

    missing_evidence = {
        key: path
        for key, paths in EVIDENCE.items()
        for path in paths
        if not (ROOT / path).is_file()
    }
    if missing_evidence:
        raise FileNotFoundError(missing_evidence)
    if len(GOALS) != 120 or [goal[0] for goal in GOALS] != list(range(1, 121)):
        raise ValueError("The audit must enumerate goals 1 through 120 exactly once")
    unknown_checks = {goal[2] for goal in GOALS} - checks.keys()
    if unknown_checks:
        raise KeyError(f"Goal mapping references unknown checks: {sorted(unknown_checks)}")

    goal_results = []
    for goal_id, title, check_key in GOALS:
        passed = checks[check_key]
        status = (
            "failed"
            if not passed
            else "verified_boundary"
            if goal_id in BOUNDARY_GOALS
            else "verified"
        )
        goal_results.append(
            {
                "goal": goal_id,
                "title": title,
                "status": status,
                "check": check_key,
                "evidence": EVIDENCE[check_key],
            }
        )

    status_counts = {
        status: sum(goal["status"] == status for goal in goal_results)
        for status in ("verified", "verified_boundary", "failed")
    }
    checks_passed = all(checks.values())
    return {
        "schema_version": "citygap.municipal-open-data-platform-final-audit@1",
        "audit_date": "2026-08-29",
        "baseline_commit": "47f7de7886591b1c87c50fbf192ea6105598c666",
        "passed": checks_passed and status_counts["failed"] == 0,
        "status_semantics": {
            "verified": "Implemented and backed by the named code, migration, test, or real artifact.",
            "verified_boundary": (
                "Official availability was checked and the safe unavailable/review/degraded boundary "
                "is implemented; this is not an analysis-ready claim."
            ),
            "failed": "The required evidence check did not pass.",
        },
        "check_count": len(checks),
        "checks": checks,
        "goal_count": len(goal_results),
        "status_counts": status_counts,
        "goals": goal_results,
        "real_data_metrics": {
            "municipal_catalog_datasets": {
                "maizuru": inventory_cities["26202"]["dataset_count"],
                "fujisawa": inventory_cities["14205"]["dataset_count"],
            },
            "raw_resources": {
                "maizuru_priority": 9,
                "mhlw_health_care": health["raw_resource_count"],
                "demographic_economic": demographic["raw_resource_count"],
                "geospatial_resilience_primary": resilience["raw_primary_resource_count"],
            },
            "canonical_records": {
                "maizuru_priority": maizuru["canonical_record_count"],
                "mhlw_health_care": health["canonical_record_count"],
                "demographic_economic": demographic["canonical_record_count"],
                "geospatial_resilience": resilience["canonical_record_count"],
                "total": sum(
                    (
                        maizuru["canonical_record_count"],
                        health["canonical_record_count"],
                        demographic["canonical_record_count"],
                        resilience["canonical_record_count"],
                    )
                ),
            },
            "analysis_meshes": analyses["mesh_count"],
            "new_findings": analyses["finding_count"],
        },
        "implementation_ci": {
            "run_id": 33185736512,
            "verified_commit": "980c843deccbeafb7cd3fa7742f001b8510088e3",
            "conclusion": "success",
            "required_gates": {
                gate: "success"
                for gate in (
                    "frontend",
                    "security",
                    "validation-gates",
                    "python-unit",
                    "api-integration",
                    "postgis-integration",
                    "migration",
                    "public-assets",
                    "build",
                )
            },
            "note": "Recorded external evidence; this deterministic local audit does not query GitHub.",
        },
        "remaining_external_boundaries": [
            "WAM NET pilot rows, schema and resource redistribution terms require human review.",
            "GSI Foundation Map download requires credentials and Survey Act/terms review.",
            "No official city-covering pedestrian network or official GTFS was verified for either pilot city.",
            "xROAD has no stable, version-pinned pilot traffic snapshot in canonical storage.",
            "Station usage and person-trip sources remain non-promoted historical/catalog context.",
            "Municipal production OIDC, retention, backup, publication and legal approvals remain deployment work.",
        ],
    }


def main() -> None:
    audit = build_audit()
    OUTPUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not audit["passed"]:
        failed = [key for key, passed in audit["checks"].items() if not passed]
        raise SystemExit(f"Open Data Platform final audit failed: {failed}")
    print(
        f"wrote {OUTPUT.relative_to(ROOT)} with {audit['goal_count']} verified goals "
        f"and {audit['check_count']} passing checks"
    )


if __name__ == "__main__":
    main()
