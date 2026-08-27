"""Municipal pilot readiness checks with explicit blockers and limitations."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any

from backend.citygap_platform.api.repository import PostGISRepository
from backend.citygap_platform.security.auth import AuthSettings


@dataclass(frozen=True, slots=True)
class PilotCheck:
    name: str
    passed: bool
    required: bool
    detail: str
    remediation: str | None = None


def classify_readiness(checks: list[PilotCheck]) -> dict[str, Any]:
    blockers = [check for check in checks if check.required and not check.passed]
    limitations = [check for check in checks if not check.required and not check.passed]
    status = "NOT_READY" if blockers else "READY_WITH_LIMITATIONS" if limitations else "READY"
    return {
        "status": status,
        "checks": [asdict(check) for check in checks],
        "blockers": [check.name for check in blockers],
        "limitations": [check.name for check in limitations],
    }


class PilotReadinessService:
    def __init__(self, repository: PostGISRepository):
        self.repository = repository

    def check(self, city_id: str) -> dict[str, Any]:
        process = self.repository.readiness(city_id)
        checks = [
            PilotCheck(
                "postgis",
                bool(process["checks"].get("database") and process["checks"].get("extensions")),
                True,
                "PostgreSQL, PostGIS and pgRouting must answer real queries.",
                "Start the pinned PostGIS/pgRouting service and verify credentials.",
            ),
            PilotCheck(
                "migrations",
                bool(process["checks"].get("migrations")),
                True,
                str(process.get("details", {}).get("migration_count", "migration status unavailable")),
                "Run the checksum migration runner before accepting pilot traffic.",
            ),
        ]
        facts = self._database_facts(city_id) if process["checks"].get("database") else {}
        checks.extend(
            [
                PilotCheck(
                    "plateau_registered",
                    bool(facts.get("plateau_registered")),
                    True,
                    "A current, exact PLATEAU dataset version is required.",
                    "Register and ingest a checksum-verified PLATEAU version.",
                ),
                PilotCheck(
                    "population_registered",
                    bool(facts.get("population_registered")),
                    True,
                    "A versioned population source is required for demographic analysis.",
                    "Register the census dataset version used by the city analysis.",
                ),
                PilotCheck(
                    "facility_registered",
                    bool(facts.get("facility_registered")),
                    True,
                    "At least one facility source must be registered and loaded.",
                    "Register transport/medical facilities and record their inclusion policy.",
                ),
                PilotCheck(
                    "quality_gate",
                    bool(facts.get("quality_gate")),
                    True,
                    "The selected dataset must pass quality checks before analysis_ready.",
                    "Resolve geometry/CRS/coverage/codelist failures and rerun validation.",
                ),
                PilotCheck(
                    "network_status",
                    bool(facts.get("network_count")),
                    True,
                    f"Registered network versions: {facts.get('network_count', 0)}.",
                    "Generate or import a versioned network without relabelling experimental output.",
                ),
                PilotCheck(
                    "scenario_engine",
                    bool(facts.get("scenario_count")),
                    True,
                    f"Persisted scenario runs: {facts.get('scenario_count', 0)}.",
                    "Run and persist at least one evidence-backed scenario for review.",
                ),
                PilotCheck(
                    "evidence_package",
                    bool(facts.get("evidence_count")),
                    False,
                    f"Persisted evidence exports: {facts.get('evidence_count', 0)}.",
                    "Generate Evidence Package V2 before the first review meeting.",
                ),
                PilotCheck(
                    "gtfs",
                    bool(facts.get("gtfs_count")),
                    False,
                    "GTFS is optional and must remain unavailable when no official feed is registered.",
                    "Record unavailable/partial status; never substitute P11 for GTFS.",
                ),
                PilotCheck(
                    "coverage",
                    bool(facts.get("demographic_count")),
                    True,
                    f"Building demographic records: {facts.get('demographic_count', 0)}.",
                    "Complete building population allocation and verify conservation/coverage.",
                ),
            ]
        )
        auth_safe = False
        auth_detail = "Pilot readiness requires production OIDC verification."
        try:
            auth = AuthSettings.from_environment()
            auth_safe = bool(
                auth.environment in {"pilot", "production"}
                and auth.mode == "oidc"
                and os.getenv("CITYGAP_OIDC_VERIFIER_CONFIGURED") == "true"
            )
            if auth_safe:
                auth_detail = "Pilot OIDC mode and an externally verified adapter are declared."
            elif auth.mode == "development":
                auth_detail = "Development identity headers are not acceptable for a pilot."
            elif os.getenv("CITYGAP_OIDC_VERIFIER_CONFIGURED") != "true":
                auth_detail = "OIDC issuer/audience exist, but the verifier integration is not confirmed."
        except RuntimeError as error:
            auth_detail = str(error)
        checks.append(
            PilotCheck(
                "auth_mode",
                auth_safe,
                True,
                auth_detail,
                "Configure a verified OIDC provider in pilot/production mode.",
            )
        )
        backup_configured = bool(
            os.getenv("CITYGAP_BACKUP_DIRECTORY")
            or os.getenv("CITYGAP_BACKUP_COMMAND_VERIFIED") == "true"
        )
        checks.append(
            PilotCheck(
                "backup_config",
                backup_configured,
                True,
                "Backup destination/verified operation must be explicit for a pilot.",
                "Set CITYGAP_BACKUP_DIRECTORY and execute the documented restore drill.",
            )
        )
        result = classify_readiness(checks)
        result["city_id"] = city_id
        result["process_readiness"] = process
        result["facts"] = facts
        return result

    def _database_facts(self, city_id: str) -> dict[str, int | bool]:
        with self.repository._connect() as connection:
            row = connection.execute(
                """WITH selected_version AS (
                    SELECT version.id, version.registry_version_id
                    FROM city_dataset_versions AS version
                    WHERE version.city_id=%s AND version.is_current
                      AND EXISTS (
                          SELECT 1 FROM ingestion_runs AS ingestion
                          WHERE ingestion.dataset_version_id=version.id
                            AND ingestion.status='completed'
                      )
                )
                SELECT
                    EXISTS(SELECT 1 FROM selected_version) AS plateau_registered,
                    EXISTS(SELECT 1 FROM dataset_registry_provenance
                           WHERE city_code=%s AND dataset_key ILIKE '%%population%%') AS population_registered,
                    EXISTS(SELECT 1 FROM facility_registry AS facility
                           WHERE facility.dataset_version_id IN (
                               SELECT id FROM selected_version
                           )) AS facility_registered,
                    EXISTS(SELECT 1 FROM selected_version AS selected
                           JOIN dataset_versions AS version
                             ON version.id=selected.registry_version_id
                           WHERE version.quality_status='passed'
                             AND version.analysis_ready) AS quality_gate,
                    (SELECT count(*) FROM road_network_versions AS network
                     WHERE network.dataset_version_id IN (SELECT id FROM selected_version)),
                    (SELECT count(*) FROM scenario_runs AS scenario
                     WHERE scenario.dataset_version_id IN (SELECT id FROM selected_version)),
                    (SELECT count(*) FROM evidence_exports AS evidence
                     JOIN scenario_runs AS scenario ON scenario.id=evidence.scenario_run_id
                     WHERE scenario.dataset_version_id IN (SELECT id FROM selected_version)),
                    (SELECT count(*) FROM gtfs_feeds AS feed
                     JOIN dataset_versions AS registry ON registry.id=feed.dataset_version_id
                     JOIN datasets AS dataset ON dataset.id=registry.dataset_id
                     JOIN cities AS city ON city.id=dataset.city_id WHERE city.city_code=%s),
                    (SELECT count(*) FROM building_demographics AS demographics
                     WHERE demographics.dataset_version_id IN (SELECT id FROM selected_version))
                """,
                (city_id, city_id, city_id),
            ).fetchone()
        keys = (
            "plateau_registered",
            "population_registered",
            "facility_registered",
            "quality_gate",
            "network_count",
            "scenario_count",
            "evidence_count",
            "gtfs_count",
            "demographic_count",
        )
        return dict(zip(keys, row, strict=True))
