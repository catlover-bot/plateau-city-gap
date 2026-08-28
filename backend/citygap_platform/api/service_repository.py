"""Tenant-scoped persistence for the municipal urban intelligence service.

Every public method takes ``organization_id`` first.  This is intentional: a new
query cannot accidentally become tenant-global, and object identifiers are never
treated as authorization by themselves.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

from backend.citygap_platform.domain.municipal_service import (
    DatasetReleaseStatus,
    FindingStatus,
    InvestigationStatus,
    ReviewStatus,
    decode_cursor,
    encode_cursor,
    validate_dataset_transition,
    validate_finding_transition,
    validate_investigation_transition,
    validate_review_transition,
)
from backend.citygap_platform.observability import current_request_context

from .repository import PostGISRepository


class MunicipalServiceRepository(PostGISRepository):
    """PostGIS repository for stable ``/api/v1`` municipal workflows."""

    @staticmethod
    def _dicts(cursor) -> list[dict[str, Any]]:
        return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def _one(cursor) -> dict[str, Any] | None:
        row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def _city(connection, organization_id: str, city_reference: str) -> dict[str, Any] | None:
        return MunicipalServiceRepository._one(
            connection.execute(
                """SELECT id, city_code, city_key, name, prefecture_name, analysis_crs,
                          service_status, organization_id
                   FROM cities
                   WHERE organization_id = %s
                     AND (id::text = %s OR city_code = %s OR city_key = %s)""",
                (organization_id, city_reference, city_reference, city_reference),
            )
        )

    @staticmethod
    def _service_audit(
        connection,
        organization_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        city_id: str | None,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None:
        context = current_request_context()
        connection.execute(
            """INSERT INTO audit_log (
                   organization_id, actor, action, resource_type, resource_id,
                   city_id, request_id, before_state, after_state
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                organization_id,
                context.actor,
                action,
                resource_type,
                resource_id,
                city_id,
                context.request_id,
                json.dumps(before, ensure_ascii=False, default=str) if before else None,
                json.dumps(after, ensure_ascii=False, default=str) if after else None,
            ),
        )

    @staticmethod
    def _activity(
        connection,
        organization_id: str,
        city_id: str | None,
        event_type: str,
        resource_type: str,
        resource_id: str,
        summary: str,
    ) -> None:
        context = current_request_context()
        stored_event_type = {
            "finding.created": "finding_created",
            "finding.status_changed": "finding_status_changed",
            "investigation.created": "investigation_started",
            "review.requested": "review_submitted",
            "review.status_changed": "review_status_changed",
            "field_observation.created": "field_check_added",
            "decision.recorded": "decision_recorded",
        }.get(event_type, event_type.replace(".", "_"))
        connection.execute(
            """INSERT INTO activity_events (
                   organization_id, city_id, event_type, resource_type, resource_id,
                   title, description, actor_label
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                organization_id,
                city_id,
                stored_event_type,
                resource_type,
                resource_id,
                summary,
                summary,
                context.actor,
            ),
        )

    def authorize_identity(
        self,
        organization_id: str,
        actor: str,
        issuer: str,
        claimed_roles: frozenset[str],
    ) -> bool:
        """Verify that token roles are backed by active tenant membership records."""

        if not claimed_roles:
            return False
        with self._connect() as connection:
            row = connection.execute(
                """SELECT array_agg(DISTINCT membership.role)
                   FROM platform_users AS platform_user
                   JOIN organization_memberships AS membership
                     ON membership.user_id = platform_user.id
                   WHERE platform_user.issuer = %s
                     AND (platform_user.subject = %s OR platform_user.email = %s)
                     AND platform_user.active AND membership.active
                     AND membership.organization_id = %s""",
                (issuer, actor, actor, organization_id),
            ).fetchone()
        granted_roles = frozenset(row[0] or ()) if row else frozenset()
        return claimed_roles <= granted_roles

    def service_profile(
        self, organization_id: str, actor: str, issuer: str
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            organization = self._one(
                connection.execute(
                    """SELECT id, organization_key, name, organization_type, status,
                              default_data_classification
                       FROM organizations WHERE id = %s AND status = 'active'""",
                    (organization_id,),
                )
            )
            if organization is None:
                return None
            user = self._one(
                connection.execute(
                    """SELECT id, display_name, email
                       FROM platform_users
                       WHERE issuer = %s AND (subject = %s OR email = %s) AND active
                       ORDER BY updated_at DESC LIMIT 1""",
                    (issuer, actor, actor),
                )
            )
            memberships: list[dict[str, Any]] = []
            if user:
                memberships = self._dicts(
                    connection.execute(
                        """SELECT membership.role, membership.granted_at
                           FROM organization_memberships AS membership
                           WHERE membership.organization_id = %s
                             AND membership.user_id = %s AND membership.active
                           ORDER BY membership.role""",
                        (organization_id, user["id"]),
                    )
                )
            return {"organization": organization, "user": user, "memberships": memberships}

    def organization_members(self, organization_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            connection.row_factory = dict_row
            return self._dicts(
                connection.execute(
                    """SELECT platform_user.id AS user_id, platform_user.issuer,
                              platform_user.subject, platform_user.display_name,
                              platform_user.email, platform_user.active AS user_active,
                              membership.role, membership.active, membership.granted_at
                       FROM organization_memberships AS membership
                       JOIN platform_users AS platform_user ON platform_user.id = membership.user_id
                       WHERE membership.organization_id = %s
                       ORDER BY platform_user.display_name, membership.role""",
                    (organization_id,),
                )
            )

    def create_organization_membership(
        self, organization_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        with self._connect() as connection:
            connection.row_factory = dict_row
            user = self._one(
                connection.execute(
                    """INSERT INTO platform_users (
                           issuer, subject, display_name, email, active
                       ) VALUES (%s, %s, %s, %s, true)
                       ON CONFLICT (issuer, subject) DO UPDATE SET
                           display_name = EXCLUDED.display_name,
                           email = EXCLUDED.email,
                           updated_at = now()
                       RETURNING id, issuer, subject, display_name, email, active AS user_active""",
                    (
                        payload["issuer"],
                        payload["subject"],
                        payload["display_name"],
                        payload.get("email"),
                    ),
                )
            )
            assert user is not None
            before = self._one(
                connection.execute(
                    """SELECT role, active, granted_at
                       FROM organization_memberships
                       WHERE organization_id = %s AND user_id = %s AND role = %s""",
                    (organization_id, user["id"], payload["role"]),
                )
            )
            result = self._one(
                connection.execute(
                    """INSERT INTO organization_memberships (
                           organization_id, user_id, role, active
                       ) VALUES (%s, %s, %s, true)
                       ON CONFLICT (organization_id, user_id, role) DO UPDATE SET
                           active = true, granted_at = now()
                       RETURNING user_id, role, active, granted_at""",
                    (organization_id, user["id"], payload["role"]),
                )
            )
            assert result is not None
            after = {**user, **result}
            self._service_audit(
                connection,
                organization_id,
                "membership.grant",
                "organization_membership",
                f"{user['id']}:{payload['role']}",
                None,
                before,
                after,
            )
            return after

    def transition_organization_membership(
        self,
        organization_id: str,
        user_id: str,
        role: str,
        expected_active: bool,
        proposed_active: bool,
        note: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            before = self._one(
                connection.execute(
                    """SELECT membership.user_id, membership.role, membership.active,
                              platform_user.display_name, platform_user.issuer,
                              platform_user.subject
                       FROM organization_memberships AS membership
                       JOIN platform_users AS platform_user
                         ON platform_user.id = membership.user_id
                       WHERE membership.organization_id = %s
                         AND membership.user_id = %s AND membership.role = %s
                       FOR UPDATE OF membership""",
                    (organization_id, user_id, role),
                )
            )
            if before is None:
                return None
            if before["active"] != expected_active:
                raise ValueError("Membership changed; reload before updating it")
            if role == "administrator" and expected_active and not proposed_active:
                active_administrators = connection.execute(
                    """SELECT count(*) FROM organization_memberships
                       WHERE organization_id = %s AND role = 'administrator' AND active""",
                    (organization_id,),
                ).fetchone()[0]
                if active_administrators <= 1:
                    raise ValueError(
                        "The last active organization administrator cannot be disabled"
                    )
            after = self._one(
                connection.execute(
                    """UPDATE organization_memberships SET active = %s
                       WHERE organization_id = %s AND user_id = %s AND role = %s
                       RETURNING user_id, role, active, granted_at""",
                    (proposed_active, organization_id, user_id, role),
                )
            )
            assert after is not None
            self._service_audit(
                connection,
                organization_id,
                "membership.status",
                "organization_membership",
                f"{user_id}:{role}",
                None,
                {**before, "note": None},
                {**after, "note": note},
            )
            return {**before, **after}

    def service_cities(self, organization_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            connection.row_factory = dict_row
            return self._dicts(
                connection.execute(
                    """SELECT home.*,
                              COALESCE(capabilities.available, 0) AS available_capabilities,
                              COALESCE(capabilities.total, 0) AS capability_count
                       FROM city_service_home AS home
                       LEFT JOIN LATERAL (
                           SELECT count(*) FILTER (WHERE status = 'available') AS available,
                                  count(*) AS total
                           FROM city_capabilities WHERE city_id = home.city_id
                       ) AS capabilities ON true
                       WHERE home.organization_id = %s
                       ORDER BY home.name""",
                    (organization_id,),
                )
            )

    def create_service_city(self, organization_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        capabilities = (
            "screening",
            "building_detail",
            "road_network",
            "terrain",
            "land_use",
            "urban_planning",
            "hazard",
            "gtfs",
            "scenario",
            "temporal_diff",
            "future_population",
            "hazard_stress_test",
            "criticality",
            "field_mode",
            "outcome_monitoring",
            "evacuation_reachability",
            "planning_monitoring",
        )
        with self._connect() as connection:
            connection.row_factory = dict_row
            duplicate = connection.execute(
                """SELECT 1 FROM cities
                   WHERE city_code = %s OR city_key = %s""",
                (payload["city_code"], payload["city_key"]),
            ).fetchone()
            if duplicate:
                raise ValueError("City code or key is already registered")
            city = self._one(
                connection.execute(
                    """INSERT INTO cities (
                           city_code, city_key, name, prefecture_code,
                           prefecture_name, analysis_crs, organization_id,
                           service_status
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'onboarding')
                       RETURNING *""",
                    (
                        payload["city_code"],
                        payload["city_key"],
                        payload["name"],
                        payload["prefecture_code"],
                        payload["prefecture_name"],
                        payload["analysis_crs"],
                        organization_id,
                    ),
                )
            )
            assert city is not None
            connection.executemany(
                """INSERT INTO city_capabilities (
                       city_id, capability, status, note, evidence, updated_at
                   ) VALUES (%s, %s, 'unavailable', %s, '[]', now())""",
                [
                    (
                        city["id"],
                        capability,
                        "必要な実データと検証済み成果がまだ登録されていません",
                    )
                    for capability in capabilities
                ],
            )
            self._service_audit(
                connection,
                organization_id,
                "city.create",
                "city",
                str(city["id"]),
                str(city["id"]),
                None,
                city,
            )
            return city

    def city_onboarding(self, organization_id: str, city_reference: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            categories = self._dicts(
                connection.execute(
                    """SELECT dataset.dataset_category,
                              count(version.id) AS registered_versions,
                              count(version.id) FILTER (
                                  WHERE version.service_status = 'promoted'
                              ) AS promoted_versions
                       FROM datasets AS dataset
                       LEFT JOIN dataset_versions AS version
                         ON version.organization_id = dataset.organization_id
                        AND version.dataset_id = dataset.id
                       WHERE dataset.organization_id = %s AND dataset.city_id = %s
                       GROUP BY dataset.dataset_category""",
                    (organization_id, city["id"]),
                )
            )
            by_category = {row["dataset_category"]: row for row in categories}
            state_count = connection.execute(
                """SELECT count(*) FROM urban_states
                   WHERE organization_id = %s AND city_id = %s
                     AND lifecycle_status IN ('validated', 'current')""",
                (organization_id, city["id"]),
            ).fetchone()[0]
            analysis_count = connection.execute(
                """SELECT count(*) FROM analysis_runs
                   WHERE organization_id = %s AND city_id = %s""",
                (organization_id, city["id"]),
            ).fetchone()[0]
            capability_rows = self._dicts(
                connection.execute(
                    """SELECT capability, status, note
                       FROM city_capabilities WHERE city_id = %s ORDER BY capability""",
                    (city["id"],),
                )
            )

            def dataset_step(category: str) -> dict[str, Any]:
                row = by_category.get(category, {})
                promoted = int(row.get("promoted_versions", 0))
                registered = int(row.get("registered_versions", 0))
                return {
                    "key": category,
                    "status": "complete"
                    if promoted
                    else "in_progress"
                    if registered
                    else "missing",
                    "registered_versions": registered,
                    "promoted_versions": promoted,
                }

            steps = [dataset_step(key) for key in ("plateau", "population", "facilities")]
            steps.extend(
                [
                    {
                        "key": "first_urban_state",
                        "status": "complete" if state_count else "missing",
                        "count": state_count,
                    },
                    {
                        "key": "first_analysis",
                        "status": "complete" if analysis_count else "missing",
                        "count": analysis_count,
                    },
                ]
            )
            return {"city": city, "steps": steps, "capabilities": capability_rows}

    def register_service_dataset(
        self, organization_id: str, city_reference: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        context = current_request_context()
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            if connection.execute(
                """SELECT 1 FROM datasets
                   WHERE organization_id = %s AND city_id = %s AND dataset_key = %s""",
                (organization_id, city["id"], payload["dataset_key"]),
            ).fetchone():
                raise ValueError("Dataset key is already registered for this city")
            dataset_id = str(uuid.uuid4())
            version_id = str(uuid.uuid4())
            dataset = self._one(
                connection.execute(
                    """INSERT INTO datasets (
                           id, city_id, dataset_key, title, provider,
                           organization_id, data_classification, dataset_category
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING *""",
                    (
                        dataset_id,
                        city["id"],
                        payload["dataset_key"],
                        payload["title"],
                        payload["provider"],
                        organization_id,
                        payload.get("data_classification", "internal"),
                        payload["dataset_category"],
                    ),
                )
            )
            version = self._one(
                connection.execute(
                    """INSERT INTO dataset_versions (
                           id, dataset_id, version_key, dataset_year, data_format,
                           source_url, license, declared_source_crs,
                           verification_status, registered_at, organization_id,
                           data_classification, service_status
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                                 'metadata_registered', now(), %s, %s, 'registered')
                       RETURNING *""",
                    (
                        version_id,
                        dataset_id,
                        payload["version_key"],
                        payload["dataset_year"],
                        payload["data_format"],
                        payload.get("source_url"),
                        payload.get("license"),
                        payload.get("declared_source_crs"),
                        organization_id,
                        payload.get("data_classification", "internal"),
                    ),
                )
            )
            assert dataset is not None and version is not None
            connection.execute(
                """INSERT INTO dataset_onboarding_events (
                       organization_id, dataset_version_id, to_status, note, actor
                   ) VALUES (%s, %s, 'registered', %s, %s)""",
                (
                    organization_id,
                    version_id,
                    "source metadata registered; validation has not run",
                    context.actor,
                ),
            )
            self._service_audit(
                connection,
                organization_id,
                "dataset.register",
                "dataset_version",
                version_id,
                str(city["id"]),
                None,
                {"dataset": dataset, "version": version},
            )
            return {"dataset": dataset, "version": version}

    def service_urban_states(
        self, organization_id: str, city_reference: str, limit: int
    ) -> list[dict[str, Any]] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            return self._dicts(
                connection.execute(
                    """SELECT state.id, state.state_key, state.label, state.effective_date,
                              state.state_type, state.lifecycle_status, state.base_state_id,
                              state.primary_dataset_version_id,
                              state.primary_plateau_dataset_version_id,
                              state.source_verified, state.population_model,
                              state.fixed_service_assumption, state.validation_report,
                              state.created_by, state.created_at, state.validated_at
                       FROM urban_states AS state
                       WHERE state.organization_id = %s AND state.city_id = %s
                       ORDER BY state.effective_date DESC, state.created_at DESC LIMIT %s""",
                    (organization_id, city["id"], limit),
                )
            )

    def create_service_urban_state(
        self, organization_id: str, city_reference: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        context = current_request_context()
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            primary = self._one(
                connection.execute(
                    """SELECT version.id, version.service_status, version.quality_status,
                              version.analysis_ready, dataset.dataset_category
                       FROM dataset_versions AS version
                       JOIN datasets AS dataset ON dataset.id = version.dataset_id
                       WHERE version.organization_id = %s AND dataset.city_id = %s
                         AND version.id = %s""",
                    (organization_id, city["id"], payload["primary_dataset_version_id"]),
                )
            )
            if primary is None:
                raise ValueError("Primary dataset version does not belong to this city")
            if not (
                primary["service_status"] == "promoted"
                and primary["quality_status"] == "passed"
                and primary["analysis_ready"]
            ):
                raise ValueError("Urban State requires a promoted, quality-passed dataset version")
            base_state_id = payload.get("base_state_id")
            if (
                base_state_id
                and not connection.execute(
                    """SELECT 1 FROM urban_states
                   WHERE organization_id = %s AND city_id = %s AND id = %s
                     AND lifecycle_status IN ('validated', 'current')""",
                    (organization_id, city["id"], base_state_id),
                ).fetchone()
            ):
                raise ValueError("Base Urban State must be validated in the same city")
            result = self._one(
                connection.execute(
                    """INSERT INTO urban_states (
                           organization_id, city_id, state_key, label, effective_date,
                           state_type, lifecycle_status, base_state_id,
                           primary_dataset_version_id, source_verified, population_model,
                           fixed_service_assumption, validation_report, created_by
                       ) VALUES (%s, %s, %s, %s, %s, %s, 'draft', %s, %s, %s, %s, %s,
                                 '{"service":"municipal-v1","validation":"pending"}', %s)
                       RETURNING *""",
                    (
                        organization_id,
                        city["id"],
                        payload["state_key"],
                        payload["label"],
                        payload["effective_date"],
                        payload["state_type"],
                        base_state_id,
                        payload["primary_dataset_version_id"],
                        payload["source_verified"],
                        payload.get("population_model"),
                        payload.get("fixed_service_assumption", False),
                        context.actor,
                    ),
                )
            )
            assert result is not None
            dataset_role = {
                "plateau": "plateau",
                "population": "population",
                "facilities": "facility",
                "transport": "transport",
                "hazard": "hazard",
                "planning": "planning",
            }.get(primary["dataset_category"], "other")
            connection.execute(
                """INSERT INTO state_dataset_versions (
                       organization_id, urban_state_id, dataset_role, dataset_version_id,
                       source_verified, metadata
                   ) VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    organization_id,
                    result["id"],
                    dataset_role,
                    payload["primary_dataset_version_id"],
                    payload["source_verified"],
                    json.dumps({"registered_by": "municipal-v1"}),
                ),
            )
            self._service_audit(
                connection,
                organization_id,
                "urban_state.create",
                "urban_state",
                str(result["id"]),
                str(city["id"]),
                None,
                result,
            )
            return result

    def transition_service_urban_state(
        self,
        organization_id: str,
        state_id: str,
        expected_status: str,
        proposed_status: str,
        note: str,
    ) -> dict[str, Any] | None:
        allowed = {
            "draft": {"validated", "archived"},
            "validated": {"current", "archived"},
            "current": {"superseded"},
            "superseded": {"archived"},
            "archived": set(),
        }
        if proposed_status not in allowed.get(expected_status, set()):
            raise ValueError(
                f"Invalid Urban State transition: {expected_status} -> {proposed_status}"
            )
        context = current_request_context()
        with self._connect() as connection:
            connection.row_factory = dict_row
            before = self._one(
                connection.execute(
                    """SELECT * FROM urban_states
                       WHERE organization_id = %s AND id = %s FOR UPDATE""",
                    (organization_id, state_id),
                )
            )
            if before is None:
                return None
            if before["lifecycle_status"] != expected_status:
                raise ValueError(f"Urban State status changed: expected {expected_status}")
            if proposed_status in {"validated", "current"} and not before["source_verified"]:
                raise ValueError("Source verification is required before validation")
            if proposed_status == "current":
                connection.execute(
                    """UPDATE urban_states
                       SET lifecycle_status = 'superseded', updated_at = now()
                       WHERE organization_id = %s AND city_id = %s
                         AND state_type = %s AND lifecycle_status = 'current'""",
                    (organization_id, before["city_id"], before["state_type"]),
                )
            after = self._one(
                connection.execute(
                    """UPDATE urban_states
                       SET lifecycle_status = %s,
                           validated_at = CASE WHEN %s = 'validated' THEN now()
                                               ELSE validated_at END,
                           validation_report = validation_report || %s::jsonb,
                           updated_at = now()
                       WHERE organization_id = %s AND id = %s RETURNING *""",
                    (
                        proposed_status,
                        proposed_status,
                        json.dumps(
                            {"lifecycle_note": note, "lifecycle_actor": context.actor},
                            ensure_ascii=False,
                        ),
                        organization_id,
                        state_id,
                    ),
                )
            )
            assert after is not None
            self._service_audit(
                connection,
                organization_id,
                "urban_state.transition",
                "urban_state",
                state_id,
                str(before["city_id"]),
                before,
                after,
            )
            return after

    def annual_updates(
        self, organization_id: str, city_reference: str, limit: int
    ) -> list[dict[str, Any]] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            return self._dicts(
                connection.execute(
                    """SELECT change.id, change.status, change.algorithm_version,
                              change.summary, change.created_at, change.started_at,
                              change.completed_at,
                              before_state.id AS from_urban_state_id,
                              before_state.label AS from_label,
                              before_state.effective_date AS from_effective_date,
                              after_state.id AS to_urban_state_id,
                              after_state.label AS to_label,
                              after_state.effective_date AS to_effective_date,
                              job.id AS job_id, job.state AS job_state,
                              job.current_stage AS job_stage, job.error_message
                       FROM urban_state_change_sets AS change
                       JOIN urban_states AS before_state
                         ON before_state.organization_id = change.organization_id
                        AND before_state.id = change.from_urban_state_id
                       JOIN urban_states AS after_state
                         ON after_state.organization_id = change.organization_id
                        AND after_state.id = change.to_urban_state_id
                       LEFT JOIN job_runs AS job
                         ON job.organization_id = change.organization_id
                        AND job.parameters ->> 'change_set_id' = change.id::text
                       WHERE change.organization_id = %s AND change.city_id = %s
                       ORDER BY change.created_at DESC, change.id DESC LIMIT %s""",
                    (organization_id, city["id"], limit),
                )
            )

    def create_annual_update(
        self, organization_id: str, city_reference: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        from_state_id = payload["from_urban_state_id"]
        to_state_id = payload["to_urban_state_id"]
        algorithm_version = payload["algorithm_version"]
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            states = self._dicts(
                connection.execute(
                    """SELECT id, state_key, label, effective_date, state_type,
                              lifecycle_status, source_verified
                       FROM urban_states
                       WHERE organization_id = %s AND city_id = %s
                         AND id = ANY(%s::uuid[])
                       ORDER BY effective_date, id""",
                    (organization_id, city["id"], [from_state_id, to_state_id]),
                )
            )
            by_id = {str(state["id"]): state for state in states}
            before_state = by_id.get(str(from_state_id))
            after_state = by_id.get(str(to_state_id))
            if before_state is None or after_state is None:
                raise ValueError("Annual update states must belong to the selected city")
            if before_state["state_type"] != "observed" or after_state["state_type"] != "observed":
                raise ValueError("Annual updates compare observed Urban States only")
            if before_state["lifecycle_status"] not in {"validated", "current", "superseded"}:
                raise ValueError("Previous Urban State must be validated")
            if after_state["lifecycle_status"] not in {"validated", "current"}:
                raise ValueError("New Urban State must be validated before change detection")
            if not before_state["source_verified"] or not after_state["source_verified"]:
                raise ValueError("Annual update states require verified sources")
            if after_state["effective_date"] <= before_state["effective_date"]:
                raise ValueError("New Urban State must have a later effective date")

            version_rows = self._dicts(
                connection.execute(
                    """SELECT DISTINCT dataset_version_id
                       FROM state_dataset_versions
                       WHERE organization_id = %s
                         AND urban_state_id = ANY(%s::uuid[])
                       ORDER BY dataset_version_id""",
                    (organization_id, [from_state_id, to_state_id]),
                )
            )
            version_ids = [str(row["dataset_version_id"]) for row in version_rows]
            if not version_ids:
                raise ValueError("Annual update states have no versioned dataset inputs")

            preserved = self._one(
                connection.execute(
                    """SELECT
                           (SELECT count(*) FROM investigations
                            WHERE organization_id = %s AND urban_state_id = %s)
                               AS investigations,
                           (SELECT count(*) FROM state_analysis_runs
                            WHERE organization_id = %s AND urban_state_id = %s)
                               AS analysis_runs,
                           (SELECT count(*) FROM report_records AS report
                            JOIN investigations AS investigation
                              ON investigation.organization_id = report.organization_id
                             AND investigation.id = report.investigation_id
                            WHERE report.organization_id = %s
                              AND investigation.urban_state_id = %s)
                               AS reports""",
                    (
                        organization_id,
                        from_state_id,
                        organization_id,
                        from_state_id,
                        organization_id,
                        from_state_id,
                    ),
                )
            ) or {"investigations": 0, "analysis_runs": 0, "reports": 0}
            contract = {
                "organization_id": organization_id,
                "city_id": str(city["id"]),
                "from_urban_state_id": str(from_state_id),
                "to_urban_state_id": str(to_state_id),
                "dataset_version_ids": version_ids,
                "algorithm_version": algorithm_version,
            }
            config_hash = hashlib.sha256(
                json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            change_set = self._one(
                connection.execute(
                    """INSERT INTO urban_state_change_sets (
                           organization_id, city_id, from_urban_state_id,
                           to_urban_state_id, algorithm_version, summary
                       ) VALUES (%s, %s, %s, %s, %s, %s)
                       ON CONFLICT (from_urban_state_id, to_urban_state_id, algorithm_version)
                       DO NOTHING RETURNING *""",
                    (
                        organization_id,
                        city["id"],
                        from_state_id,
                        to_state_id,
                        algorithm_version,
                        json.dumps(
                            {
                                "contract": contract,
                                "status_boundary": "queued_for_version_diff",
                            }
                        ),
                    ),
                )
            )
            created = change_set is not None
            if change_set is None:
                change_set = self._one(
                    connection.execute(
                        """SELECT * FROM urban_state_change_sets
                           WHERE organization_id = %s AND city_id = %s
                             AND from_urban_state_id = %s AND to_urban_state_id = %s
                             AND algorithm_version = %s""",
                        (
                            organization_id,
                            city["id"],
                            from_state_id,
                            to_state_id,
                            algorithm_version,
                        ),
                    )
                )
            assert change_set is not None
            idempotency_key = hashlib.sha256(
                f"{organization_id}:annual-update:{change_set['id']}:{config_hash}".encode()
            ).hexdigest()
            job = self._one(
                connection.execute(
                    """INSERT INTO job_runs (
                           organization_id, city_id, job_type, state, config_hash,
                           algorithm_version, idempotency_key, parameters
                       ) VALUES (%s, %s, 'dataset_diff', 'queued', %s, %s, %s, %s)
                       ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL
                       DO UPDATE SET idempotency_key = EXCLUDED.idempotency_key
                       RETURNING id, state, current_stage, queued_at, config_hash,
                                 algorithm_version""",
                    (
                        organization_id,
                        city["id"],
                        config_hash,
                        algorithm_version,
                        idempotency_key,
                        json.dumps({**contract, "change_set_id": str(change_set["id"])}),
                    ),
                )
            )
            assert job is not None
            for version_id in version_ids:
                connection.execute(
                    """INSERT INTO job_dataset_versions (
                           organization_id, job_run_id, dataset_version_id
                       ) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
                    (organization_id, job["id"], version_id),
                )
            connection.execute(
                """INSERT INTO job_events (job_run_id, state, message)
                   SELECT %s, 'queued', 'annual Urban State difference contract accepted'
                   WHERE NOT EXISTS (
                       SELECT 1 FROM job_events
                       WHERE job_run_id = %s AND state = 'queued'
                         AND message = 'annual Urban State difference contract accepted'
                   )""",
                (job["id"], job["id"]),
            )
            if created:
                self._activity(
                    connection,
                    organization_id,
                    str(city["id"]),
                    "annual_update.queued",
                    "urban_state_change_set",
                    str(change_set["id"]),
                    f"年次更新「{before_state['label']} → {after_state['label']}」を登録",
                )
                self._service_audit(
                    connection,
                    organization_id,
                    "annual_update.create",
                    "urban_state_change_set",
                    str(change_set["id"]),
                    str(city["id"]),
                    None,
                    {"change_set": change_set, "job": job, "contract": contract},
                )
            return {
                "change_set": change_set,
                "job": job,
                "contract": contract,
                "previous_records": {
                    **preserved,
                    "mutation_policy": "immutable_version_references",
                    "changed_by_this_request": False,
                },
                "created": created,
            }

    def city_service_home(self, organization_id: str, city_reference: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            home = self._one(
                connection.execute(
                    "SELECT * FROM city_service_home WHERE organization_id = %s AND city_id = %s",
                    (organization_id, city["id"]),
                )
            )
            capabilities = self._dicts(
                connection.execute(
                    """SELECT capability, status, note, evidence, updated_at
                       FROM city_capabilities WHERE city_id = %s ORDER BY capability""",
                    (city["id"],),
                )
            )
            datasets = self._dicts(
                connection.execute(
                    """SELECT dataset.dataset_key, dataset.dataset_category,
                              dataset.title, version.id AS version_id,
                              version.version_key, version.dataset_year, version.service_status,
                              version.data_classification, version.quality_status,
                              version.analysis_ready
                       FROM datasets AS dataset
                       JOIN dataset_versions AS version ON version.dataset_id = dataset.id
                       WHERE dataset.organization_id = %s AND dataset.city_id = %s
                       ORDER BY version.dataset_year DESC, version.registered_at DESC
                       LIMIT 20""",
                    (organization_id, city["id"]),
                )
            )
            recent_activity = self._dicts(
                connection.execute(
                    """SELECT event_type, resource_type, resource_id, title,
                              description AS summary, actor_label, occurred_at
                       FROM activity_events
                       WHERE organization_id = %s AND city_id = %s
                       ORDER BY occurred_at DESC, id DESC LIMIT 20""",
                    (organization_id, city["id"]),
                )
            )
            return {
                "city": city,
                "summary": home,
                "capabilities": capabilities,
                "datasets": datasets,
                "recent_activity": recent_activity,
            }

    def findings(
        self,
        organization_id: str,
        city_reference: str,
        status: str | None,
        finding_type: str | None,
        search: str | None,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any] | None:
        cursor_values = decode_cursor(cursor)
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            rows = self._dicts(
                connection.execute(
                    """SELECT id, city_id, urban_state_id, finding_type, title, summary,
                              status, source_analysis_run_id, validation_status, assigned_to,
                              dismissal_reason, created_by, created_at, updated_at,
                              ST_AsGeoJSON(geometry)::jsonb AS geometry
                       FROM findings
                       WHERE organization_id = %s AND city_id = %s
                         AND (%s::text IS NULL OR status = %s)
                         AND (%s::text IS NULL OR finding_type = %s)
                         AND (%s::text IS NULL OR title ILIKE '%%' || %s || '%%'
                              OR summary ILIKE '%%' || %s || '%%')
                         AND (
                           %s::timestamptz IS NULL OR (created_at, id) < (%s, %s::uuid)
                         )
                       ORDER BY created_at DESC, id DESC LIMIT %s""",
                    (
                        organization_id,
                        city["id"],
                        status,
                        status,
                        finding_type,
                        finding_type,
                        search,
                        search,
                        search,
                        cursor_values.get("created_at") if cursor_values else None,
                        cursor_values.get("created_at") if cursor_values else None,
                        cursor_values.get("id") if cursor_values else None,
                        limit + 1,
                    ),
                )
            )
            more = len(rows) > limit
            items = rows[:limit]
            next_cursor = None
            if more:
                last = items[-1]
                next_cursor = encode_cursor(
                    {"created_at": last["created_at"].isoformat(), "id": str(last["id"])}
                )
            return {"city": city, "items": items, "next_cursor": next_cursor}

    def create_finding(
        self, organization_id: str, city_reference: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            context = current_request_context()
            result = self._one(
                connection.execute(
                    """INSERT INTO findings (
                           organization_id, city_id, urban_state_id, finding_type, title,
                           summary, geometry, source_analysis_run_id, validation_status,
                           created_by
                       ) VALUES (
                           %s, %s, %s, %s, %s, %s,
                           CASE WHEN %s::jsonb IS NULL THEN NULL
                                ELSE ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) END,
                           %s, %s, %s
                       )
                       RETURNING id, city_id, finding_type, title, summary, status,
                                 validation_status, created_by, created_at""",
                    (
                        organization_id,
                        city["id"],
                        payload.get("urban_state_id"),
                        payload["finding_type"],
                        payload["title"],
                        payload["summary"],
                        json.dumps(payload.get("geometry")) if payload.get("geometry") else None,
                        json.dumps(payload.get("geometry")) if payload.get("geometry") else None,
                        payload.get("source_analysis_run_id"),
                        payload.get("validation_status", "unvalidated"),
                        context.actor,
                    ),
                )
            )
            assert result is not None
            self._activity(
                connection,
                organization_id,
                str(city["id"]),
                "finding.created",
                "finding",
                str(result["id"]),
                f"Finding「{payload['title']}」を登録",
            )
            self._service_audit(
                connection,
                organization_id,
                "finding.create",
                "finding",
                str(result["id"]),
                str(city["id"]),
                None,
                result,
            )
            return result

    def transition_finding(
        self,
        organization_id: str,
        finding_id: str,
        expected_status: str,
        proposed_status: str,
        dismissal_reason: str | None,
    ) -> dict[str, Any] | None:
        validate_finding_transition(FindingStatus(expected_status), FindingStatus(proposed_status))
        if proposed_status == "dismissed" and not (dismissal_reason or "").strip():
            raise ValueError("dismissal_reason is required when dismissing a finding")
        with self._connect() as connection:
            connection.row_factory = dict_row
            before = self._one(
                connection.execute(
                    """SELECT id, city_id, title, status, dismissal_reason
                       FROM findings WHERE organization_id = %s AND id = %s FOR UPDATE""",
                    (organization_id, finding_id),
                )
            )
            if before is None:
                return None
            if before["status"] != expected_status:
                raise ValueError(f"Finding status changed: expected {expected_status}")
            after = self._one(
                connection.execute(
                    """UPDATE findings SET status = %s, dismissal_reason = %s
                       WHERE organization_id = %s AND id = %s
                       RETURNING id, city_id, title, status, dismissal_reason, updated_at""",
                    (proposed_status, dismissal_reason, organization_id, finding_id),
                )
            )
            assert after is not None
            self._activity(
                connection,
                organization_id,
                str(before["city_id"]),
                "finding.status_changed",
                "finding",
                finding_id,
                f"Findingを {expected_status} から {proposed_status} へ変更",
            )
            self._service_audit(
                connection,
                organization_id,
                "finding.transition",
                "finding",
                finding_id,
                str(before["city_id"]),
                before,
                after,
            )
            return after

    def create_investigation(
        self, organization_id: str, city_reference: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            state_exists = connection.execute(
                """SELECT EXISTS(
                       SELECT 1 FROM urban_states
                       WHERE organization_id = %s AND id = %s AND city_id = %s
                   )""",
                (organization_id, payload["urban_state_id"], city["id"]),
            ).fetchone()["exists"]
            if not state_exists:
                raise ValueError("urban_state_id is not available in this city")
            context = current_request_context()
            result = self._one(
                connection.execute(
                    """INSERT INTO investigations (
                           organization_id, city_id, workspace_id, urban_state_id, title,
                           objective, assigned_to, due_date, spatial_state, notes, created_by
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING *""",
                    (
                        organization_id,
                        city["id"],
                        payload.get("workspace_id"),
                        payload["urban_state_id"],
                        payload["title"],
                        payload["objective"],
                        payload.get("assigned_to"),
                        payload.get("due_date"),
                        json.dumps(payload.get("spatial_state", {}), ensure_ascii=False),
                        payload.get("notes", ""),
                        context.actor,
                    ),
                )
            )
            assert result is not None
            for finding_id in payload.get("finding_ids", []):
                attached = connection.execute(
                    """INSERT INTO investigation_findings (
                           organization_id, investigation_id, finding_id, added_by
                       )
                       SELECT %s, %s, id, %s FROM findings
                       WHERE id = %s AND organization_id = %s AND city_id = %s
                       ON CONFLICT DO NOTHING""",
                    (
                        organization_id,
                        result["id"],
                        context.actor,
                        finding_id,
                        organization_id,
                        city["id"],
                    ),
                ).rowcount
                if attached != 1:
                    raise ValueError(f"finding is unavailable in this city: {finding_id}")
                connection.execute(
                    """UPDATE findings SET status = 'investigating'
                       WHERE id = %s AND status = 'triaged'""",
                    (finding_id,),
                )
            self._activity(
                connection,
                organization_id,
                str(city["id"]),
                "investigation.created",
                "investigation",
                str(result["id"]),
                f"Investigation「{payload['title']}」を開始",
            )
            self._service_audit(
                connection,
                organization_id,
                "investigation.create",
                "investigation",
                str(result["id"]),
                str(city["id"]),
                None,
                result,
            )
            return result

    def investigation_detail(
        self, organization_id: str, investigation_id: str
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            investigation = self._one(
                connection.execute(
                    """SELECT investigation.*, city.city_code, city.city_key, city.name AS city_name
                       FROM investigations AS investigation
                       JOIN cities AS city ON city.id = investigation.city_id
                       WHERE investigation.organization_id = %s AND investigation.id = %s""",
                    (organization_id, investigation_id),
                )
            )
            if investigation is None:
                return None
            findings = self._dicts(
                connection.execute(
                    """SELECT finding.id, finding.finding_type, finding.title, finding.summary,
                              finding.status, finding.validation_status
                       FROM investigation_findings AS link
                       JOIN findings AS finding ON finding.id = link.finding_id
                       WHERE link.organization_id = %s AND link.investigation_id = %s
                         AND finding.organization_id = %s
                       ORDER BY link.added_at""",
                    (organization_id, investigation_id, organization_id),
                )
            )
            entities = self._dicts(
                connection.execute(
                    """SELECT entity_type, entity_id, label, source, source_year, attributes,
                              evidence, ST_AsGeoJSON(geometry)::jsonb AS geometry
                       FROM investigation_entities
                       WHERE organization_id = %s AND investigation_id = %s
                       ORDER BY added_at""",
                    (organization_id, investigation_id),
                )
            )
            reviews = self._dicts(
                connection.execute(
                    """SELECT id, status, requested_by, reviewer_id, request_note, review_note,
                              requested_at, reviewed_at
                       FROM review_requests
                       WHERE organization_id = %s AND investigation_id = %s
                       ORDER BY requested_at DESC""",
                    (organization_id, investigation_id),
                )
            )
            field_observations = self._dicts(
                connection.execute(
                    """SELECT id, observation_type, status, notes, observed_at, actor_label,
                              attachment_ids, synced_at, ST_AsGeoJSON(gps)::jsonb AS gps
                       FROM field_observations
                       WHERE organization_id = %s AND investigation_id = %s
                       ORDER BY observed_at DESC""",
                    (organization_id, investigation_id),
                )
            )
            decisions = self._dicts(
                connection.execute(
                    """SELECT id, decision, reason, actor_label, decided_at,
                              related_scenario_run_id, related_evidence_ids,
                              official_approval_reference
                       FROM decision_records
                       WHERE organization_id = %s AND investigation_id = %s
                       ORDER BY decided_at DESC""",
                    (organization_id, investigation_id),
                )
            )
            saved_views = self._dicts(
                connection.execute(
                    """SELECT id, title, spatial_state, share_token,
                              data_classification, created_by, created_at, updated_at
                       FROM saved_views
                       WHERE organization_id = %s AND investigation_id = %s
                       ORDER BY updated_at DESC, id DESC""",
                    (organization_id, investigation_id),
                )
            )
            return {
                "investigation": investigation,
                "findings": findings,
                "entities": entities,
                "reviews": reviews,
                "field_observations": field_observations,
                "decisions": decisions,
                "saved_views": saved_views,
            }

    def investigations(
        self,
        organization_id: str,
        city_reference: str,
        status: str | None,
        search: str | None,
        limit: int,
    ) -> list[dict[str, Any]] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            return self._dicts(
                connection.execute(
                    """SELECT investigation.id, investigation.title,
                              investigation.objective, investigation.status,
                              investigation.urban_state_id, investigation.assigned_to,
                              investigation.due_date, investigation.updated_at,
                              count(link.finding_id) AS finding_count,
                              max(review.requested_at) AS latest_review_at
                       FROM investigations AS investigation
                       LEFT JOIN investigation_findings AS link
                         ON link.organization_id = investigation.organization_id
                        AND link.investigation_id = investigation.id
                       LEFT JOIN review_requests AS review
                         ON review.organization_id = investigation.organization_id
                        AND review.investigation_id = investigation.id
                       WHERE investigation.organization_id = %s
                         AND investigation.city_id = %s
                         AND (%s::text IS NULL OR investigation.status = %s)
                         AND (%s::text IS NULL OR investigation.title ILIKE '%%' || %s || '%%'
                              OR investigation.objective ILIKE '%%' || %s || '%%')
                       GROUP BY investigation.id
                       ORDER BY investigation.updated_at DESC LIMIT %s""",
                    (
                        organization_id,
                        city["id"],
                        status,
                        status,
                        search,
                        search,
                        search,
                        limit,
                    ),
                )
            )

    def transition_investigation(
        self,
        organization_id: str,
        investigation_id: str,
        expected_status: str,
        proposed_status: str,
        note: str,
    ) -> dict[str, Any] | None:
        validate_investigation_transition(
            InvestigationStatus(expected_status), InvestigationStatus(proposed_status)
        )
        with self._connect() as connection:
            connection.row_factory = dict_row
            before = self._one(
                connection.execute(
                    """SELECT id, city_id, title, status, notes FROM investigations
                       WHERE organization_id = %s AND id = %s FOR UPDATE""",
                    (organization_id, investigation_id),
                )
            )
            if before is None:
                return None
            if before["status"] != expected_status:
                raise ValueError(f"Investigation status changed: expected {expected_status}")
            after = self._one(
                connection.execute(
                    """UPDATE investigations
                       SET status = %s,
                           notes = CASE WHEN %s = '' THEN notes
                                       ELSE concat_ws(E'\\n', NULLIF(notes, ''), %s) END
                       WHERE organization_id = %s AND id = %s RETURNING *""",
                    (proposed_status, note, note, organization_id, investigation_id),
                )
            )
            assert after is not None
            self._activity(
                connection,
                organization_id,
                str(before["city_id"]),
                "investigation.status_changed",
                "investigation",
                investigation_id,
                f"Investigationを {expected_status} から {proposed_status} へ変更",
            )
            self._service_audit(
                connection,
                organization_id,
                "investigation.transition",
                "investigation",
                investigation_id,
                str(before["city_id"]),
                before,
                after,
            )
            return after

    def create_review_note(
        self,
        organization_id: str,
        resource_type: str,
        resource_id: str,
        body: str,
        parent_note_id: str | None,
    ) -> dict[str, Any] | None:
        table_by_resource = {
            "finding": "findings",
            "investigation": "investigations",
            "scenario": "scenario_runs",
            "review": "review_requests",
            "field_observation": "field_observations",
        }
        table = table_by_resource.get(resource_type)
        if table is None:
            raise ValueError("Unsupported comment resource type")
        with self._connect() as connection:
            connection.row_factory = dict_row
            exists = connection.execute(
                f"SELECT EXISTS(SELECT 1 FROM {table} WHERE organization_id = %s AND id = %s)",
                (organization_id, resource_id),
            ).fetchone()["exists"]
            if not exists:
                return None
            context = current_request_context()
            return self._one(
                connection.execute(
                    """INSERT INTO review_notes (
                           organization_id, resource_type, resource_id, parent_note_id,
                           body, author_label
                       ) VALUES (%s, %s, %s, %s, %s, %s)
                       RETURNING id, resource_type, resource_id, parent_note_id,
                                 body, author_label, created_at""",
                    (
                        organization_id,
                        resource_type,
                        resource_id,
                        parent_note_id,
                        body,
                        context.actor,
                    ),
                )
            )

    def create_assignment(
        self, organization_id: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        table_by_type = {
            "investigation": "investigations",
            "review": "review_requests",
            "field_check": "investigations",
        }
        table = table_by_type[payload["assignment_type"]]
        with self._connect() as connection:
            connection.row_factory = dict_row
            resource = self._one(
                connection.execute(
                    f"SELECT id FROM {table} WHERE organization_id = %s AND id = %s",
                    (organization_id, payload["resource_id"]),
                )
            )
            if resource is None:
                return None
            member = connection.execute(
                """SELECT EXISTS(
                       SELECT 1 FROM organization_memberships
                       WHERE organization_id = %s AND user_id = %s AND active
                   )""",
                (organization_id, payload["assigned_to"]),
            ).fetchone()["exists"]
            if not member:
                raise ValueError("Assignee is not an active organization member")
            result = self._one(
                connection.execute(
                    """INSERT INTO assignments (
                           organization_id, assignment_type, resource_id,
                           assigned_to, due_date
                       ) VALUES (%s, %s, %s, %s, %s) RETURNING *""",
                    (
                        organization_id,
                        payload["assignment_type"],
                        payload["resource_id"],
                        payload["assigned_to"],
                        payload.get("due_date"),
                    ),
                )
            )
            assert result is not None
            notification_type = (
                "field_check_assigned"
                if payload["assignment_type"] == "field_check"
                else (
                    "review_requested"
                    if payload["assignment_type"] == "review"
                    else "assignment_assigned"
                )
            )
            connection.execute(
                """INSERT INTO notifications (
                       organization_id, user_id, notification_type, title, body,
                       resource_type, resource_id
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    organization_id,
                    payload["assigned_to"],
                    notification_type,
                    "CITY GAPの担当依頼",
                    payload.get("note", "担当対象を確認してください"),
                    payload["assignment_type"],
                    payload["resource_id"],
                ),
            )
            return result

    def work_queue(self, organization_id: str, actor: str, issuer: str) -> dict[str, Any]:
        with self._connect() as connection:
            connection.row_factory = dict_row
            user = self._one(
                connection.execute(
                    """SELECT id, display_name FROM platform_users
                       WHERE issuer = %s AND (subject = %s OR email = %s) AND active
                       ORDER BY updated_at DESC LIMIT 1""",
                    (issuer, actor, actor),
                )
            )
            if user is None:
                return {
                    "user": None,
                    "assignments": [],
                    "notifications": [],
                    "unregistered_identity": True,
                }
            assignments = self._dicts(
                connection.execute(
                    """SELECT id, assignment_type, resource_id, status, due_date, created_at
                       FROM assignments
                       WHERE organization_id = %s AND assigned_to = %s
                         AND status IN ('assigned', 'in_progress')
                       ORDER BY due_date NULLS LAST, created_at DESC LIMIT 100""",
                    (organization_id, user["id"]),
                )
            )
            notifications = self._dicts(
                connection.execute(
                    """SELECT id, notification_type, title, body, resource_type,
                              resource_id, read_at, created_at
                       FROM notifications
                       WHERE organization_id = %s AND user_id = %s
                       ORDER BY read_at NULLS FIRST, created_at DESC LIMIT 100""",
                    (organization_id, user["id"]),
                )
            )
            return {
                "user": user,
                "assignments": assignments,
                "notifications": notifications,
                "unregistered_identity": False,
            }

    def save_investigation_view(
        self, organization_id: str, investigation_id: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            investigation = self._one(
                connection.execute(
                    """SELECT id, city_id FROM investigations
                       WHERE organization_id = %s AND id = %s""",
                    (organization_id, investigation_id),
                )
            )
            if investigation is None:
                return None
            context = current_request_context()
            result = self._one(
                connection.execute(
                    """INSERT INTO saved_views (
                           organization_id, city_id, investigation_id, title, spatial_state,
                           data_classification, created_by
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                       RETURNING id, investigation_id, title, spatial_state, share_token,
                                 data_classification, created_by, created_at""",
                    (
                        organization_id,
                        investigation["city_id"],
                        investigation_id,
                        payload["title"],
                        json.dumps(payload["spatial_state"], ensure_ascii=False),
                        payload.get("data_classification", "internal"),
                        context.actor,
                    ),
                )
            )
            assert result is not None
            self._activity(
                connection,
                organization_id,
                str(investigation["city_id"]),
                "saved_view.created",
                "saved_view",
                str(result["id"]),
                f"空間ビュー「{payload['title']}」を保存",
            )
            self._service_audit(
                connection,
                organization_id,
                "saved_view.create",
                "saved_view",
                str(result["id"]),
                str(investigation["city_id"]),
                None,
                result,
            )
            return result

    def saved_view(self, organization_id: str, share_token: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            return self._one(
                connection.execute(
                    """SELECT view.id, view.investigation_id, view.title,
                              view.spatial_state, view.data_classification,
                              view.created_by, view.created_at, view.updated_at,
                              investigation.title AS investigation_title,
                              investigation.urban_state_id, city.city_key, city.name AS city_name
                       FROM saved_views AS view
                       JOIN investigations AS investigation
                         ON investigation.organization_id = view.organization_id
                        AND investigation.id = view.investigation_id
                       JOIN cities AS city
                         ON city.organization_id = view.organization_id
                        AND city.id = view.city_id
                       WHERE view.organization_id = %s AND view.share_token = %s""",
                    (organization_id, share_token),
                )
            )

    def create_review(
        self, organization_id: str, investigation_id: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            investigation = self._one(
                connection.execute(
                    """SELECT id, city_id, status FROM investigations
                       WHERE organization_id = %s AND id = %s FOR UPDATE""",
                    (organization_id, investigation_id),
                )
            )
            if investigation is None:
                return None
            if investigation["status"] != "in_review":
                validate_investigation_transition(
                    InvestigationStatus(investigation["status"]),
                    InvestigationStatus.IN_REVIEW,
                )
            result = self._one(
                connection.execute(
                    """INSERT INTO review_requests (
                           organization_id, investigation_id, reviewer_id, request_note
                       ) VALUES (%s, %s, %s, %s)
                       RETURNING *""",
                    (
                        organization_id,
                        investigation_id,
                        payload.get("reviewer_id"),
                        payload.get("request_note", ""),
                    ),
                )
            )
            connection.execute(
                """UPDATE investigations SET status = 'in_review', updated_at = now()
                   WHERE organization_id = %s AND id = %s""",
                (organization_id, investigation_id),
            )
            assert result is not None
            self._activity(
                connection,
                organization_id,
                str(investigation["city_id"]),
                "review.requested",
                "review",
                str(result["id"]),
                "Investigationのレビューを依頼",
            )
            return result

    def transition_review(
        self,
        organization_id: str,
        review_id: str,
        expected_status: str,
        proposed_status: str,
        review_note: str,
    ) -> dict[str, Any] | None:
        validate_review_transition(ReviewStatus(expected_status), ReviewStatus(proposed_status))
        with self._connect() as connection:
            connection.row_factory = dict_row
            before = self._one(
                connection.execute(
                    """SELECT review.*, investigation.city_id
                       FROM review_requests AS review
                       LEFT JOIN investigations AS investigation
                         ON investigation.id = review.investigation_id
                       WHERE review.organization_id = %s AND review.id = %s FOR UPDATE""",
                    (organization_id, review_id),
                )
            )
            if before is None:
                return None
            if before["status"] != expected_status:
                raise ValueError(f"Review status changed: expected {expected_status}")
            if proposed_status in {"reviewed", "changes_requested"} and not review_note.strip():
                raise ValueError("review_note is required for a completed review action")
            after = self._one(
                connection.execute(
                    """UPDATE review_requests
                       SET status = %s, review_note = %s,
                           reviewed_at = CASE WHEN %s = 'reviewed' THEN now() ELSE NULL END
                       WHERE organization_id = %s AND id = %s RETURNING *""",
                    (
                        proposed_status,
                        review_note,
                        proposed_status,
                        organization_id,
                        review_id,
                    ),
                )
            )
            assert after is not None
            if before["investigation_id"]:
                next_investigation_status = {
                    "reviewed": "decision_pending",
                    "changes_requested": "open",
                }.get(proposed_status)
                if next_investigation_status:
                    connection.execute(
                        """UPDATE investigations SET status = %s, updated_at = now()
                           WHERE organization_id = %s AND id = %s""",
                        (
                            next_investigation_status,
                            organization_id,
                            before["investigation_id"],
                        ),
                    )
            self._activity(
                connection,
                organization_id,
                str(before["city_id"]) if before["city_id"] else None,
                "review.status_changed",
                "review",
                review_id,
                f"Reviewを {expected_status} から {proposed_status} へ変更",
            )
            return after

    def create_field_observation(
        self, organization_id: str, investigation_id: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            investigation = self._one(
                connection.execute(
                    """SELECT id, city_id, status FROM investigations
                       WHERE organization_id = %s AND id = %s""",
                    (organization_id, investigation_id),
                )
            )
            if investigation is None:
                return None
            if investigation["status"] in {"closed", "archived"}:
                raise ValueError("Closed investigations cannot receive new field observations")
            attachment_ids = payload.get("attachment_ids", [])
            if attachment_ids:
                matched_attachments = connection.execute(
                    """SELECT count(*) AS count FROM attachment_objects
                       WHERE organization_id = %s AND city_id = %s
                         AND id = ANY(%s::uuid[])""",
                    (organization_id, investigation["city_id"], attachment_ids),
                ).fetchone()["count"]
                if matched_attachments != len(set(attachment_ids)):
                    raise ValueError(
                        "Every attachment must belong to the investigation tenant and city"
                    )
            if investigation["status"] != "field_check":
                validate_investigation_transition(
                    InvestigationStatus(investigation["status"]),
                    InvestigationStatus.FIELD_CHECK,
                )
                connection.execute(
                    """UPDATE investigations SET status = 'field_check'
                       WHERE organization_id = %s AND id = %s""",
                    (organization_id, investigation_id),
                )
            context = current_request_context()
            longitude = payload.get("longitude")
            latitude = payload.get("latitude")
            result = self._one(
                connection.execute(
                    """INSERT INTO field_observations (
                           organization_id, city_id, investigation_id, related_finding_id,
                           related_scenario_run_id, observation_type, notes, gps, observed_at,
                           actor_label, attachment_ids, synced_at
                       ) VALUES (
                           %s, %s, %s, %s, %s, %s, %s,
                           CASE WHEN %s::double precision IS NULL THEN NULL
                                ELSE ST_SetSRID(ST_MakePoint(%s, %s), 4326) END,
                           %s, %s, %s, now()
                       )
                       RETURNING id, investigation_id, observation_type, status, notes,
                                 observed_at, actor_label, attachment_ids, synced_at""",
                    (
                        organization_id,
                        investigation["city_id"],
                        investigation_id,
                        payload.get("related_finding_id"),
                        payload.get("related_scenario_run_id"),
                        payload["observation_type"],
                        payload.get("notes", ""),
                        longitude,
                        longitude,
                        latitude,
                        payload["observed_at"],
                        context.actor,
                        attachment_ids,
                    ),
                )
            )
            assert result is not None
            self._activity(
                connection,
                organization_id,
                str(investigation["city_id"]),
                "field_observation.created",
                "field_observation",
                str(result["id"]),
                "現地観察記録を同期",
            )
            return result

    def create_attachment_metadata(
        self, organization_id: str, city_reference: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Register stored bytes only after resolving their tenant-owned city."""

        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            context = current_request_context()
            result = self._one(
                connection.execute(
                    """INSERT INTO attachment_objects (
                           organization_id, city_id, storage_provider, object_key,
                           original_file_name, content_type, size_bytes, sha256,
                           data_classification, created_by
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING id, city_id, storage_provider, object_key,
                                 original_file_name, content_type, size_bytes, sha256,
                                 data_classification, retention_class, created_by, created_at""",
                    (
                        organization_id,
                        city["id"],
                        payload["storage_provider"],
                        payload["object_key"],
                        payload["original_file_name"],
                        payload["content_type"],
                        payload["size_bytes"],
                        payload["sha256"],
                        payload["data_classification"],
                        context.actor,
                    ),
                )
            )
            assert result is not None
            self._service_audit(
                connection,
                organization_id,
                "attachment.create",
                "attachment",
                str(result["id"]),
                str(city["id"]),
                None,
                {
                    "content_type": result["content_type"],
                    "size_bytes": result["size_bytes"],
                    "sha256": result["sha256"],
                    "data_classification": result["data_classification"],
                },
            )
            return result

    def attachment_city(self, organization_id: str, city_reference: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            return self._city(connection, organization_id, city_reference)

    def attachment_metadata(
        self, organization_id: str, attachment_id: str
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            return self._one(
                connection.execute(
                    """SELECT id, city_id, storage_provider, object_key,
                              original_file_name, content_type, size_bytes, sha256,
                              data_classification, retention_class, created_by, created_at
                       FROM attachment_objects
                       WHERE organization_id = %s AND id = %s""",
                    (organization_id, attachment_id),
                )
            )

    def create_decision_record(
        self, organization_id: str, investigation_id: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            review = self._one(
                connection.execute(
                    """SELECT review.id, review.status, investigation.city_id
                       FROM review_requests AS review
                       JOIN investigations AS investigation
                         ON investigation.id = review.investigation_id
                       WHERE review.organization_id = %s AND review.id = %s
                         AND review.investigation_id = %s FOR UPDATE""",
                    (organization_id, payload["review_request_id"], investigation_id),
                )
            )
            if review is None:
                return None
            if review["status"] != "reviewed":
                raise ValueError("Decision Records require a completed review")
            investigation_status = connection.execute(
                """SELECT status FROM investigations
                   WHERE organization_id = %s AND id = %s FOR UPDATE""",
                (organization_id, investigation_id),
            ).fetchone()["status"]
            if investigation_status != "decision_pending":
                raise ValueError("Investigation must be decision_pending before a decision")
            evidence_ids = payload["related_evidence_ids"]
            matched_evidence = connection.execute(
                """SELECT count(*) AS count FROM evidence_centers
                   WHERE organization_id = %s AND city_id = %s
                     AND id = ANY(%s::uuid[])""",
                (organization_id, review["city_id"], evidence_ids),
            ).fetchone()["count"]
            if matched_evidence != len(set(evidence_ids)):
                raise ValueError(
                    "Every Decision Record evidence reference must belong to the tenant and city"
                )
            context = current_request_context()
            result = self._one(
                connection.execute(
                    """INSERT INTO decision_records (
                           organization_id, city_id, investigation_id, review_request_id,
                           decision, reason, actor_label, related_scenario_run_id,
                           related_evidence_ids, review_status, source,
                           optimizer_generated, official_approval_reference
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                                 'reviewed', 'human_entry', false, %s)
                       RETURNING *""",
                    (
                        organization_id,
                        review["city_id"],
                        investigation_id,
                        payload["review_request_id"],
                        payload["decision"],
                        payload["reason"],
                        context.actor,
                        payload.get("related_scenario_run_id"),
                        evidence_ids,
                        payload.get("official_approval_reference"),
                    ),
                )
            )
            assert result is not None
            connection.execute(
                """UPDATE investigations SET status = 'closed', updated_at = now()
                   WHERE organization_id = %s AND id = %s""",
                (organization_id, investigation_id),
            )
            self._activity(
                connection,
                organization_id,
                str(review["city_id"]),
                "decision.recorded",
                "decision_record",
                str(result["id"]),
                "人の操作によりDecision Recordを記録",
            )
            self._service_audit(
                connection,
                organization_id,
                "decision.create",
                "decision_record",
                str(result["id"]),
                str(review["city_id"]),
                None,
                result,
            )
            return result

    def data_hub(self, organization_id: str, city_reference: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            datasets = self._dicts(
                connection.execute(
                    """SELECT dataset.id AS dataset_id, dataset.dataset_key,
                              dataset.dataset_category, dataset.title,
                              dataset.provider, dataset.data_classification,
                              version.id AS version_id, version.version_key,
                              version.dataset_year, version.data_format, version.source_url,
                              version.license, version.verification_status,
                              version.lifecycle_status, version.quality_status,
                              version.service_status, version.analysis_ready,
                              version.registered_at
                       FROM datasets AS dataset
                       LEFT JOIN dataset_versions AS version ON version.dataset_id = dataset.id
                       WHERE dataset.organization_id = %s AND dataset.city_id = %s
                       ORDER BY dataset.title, version.dataset_year DESC""",
                    (organization_id, city["id"]),
                )
            )
            quality = self._dicts(
                connection.execute(
                    """SELECT quality.dataset_version_id, quality.check_key, quality.status,
                              quality.observed_value, quality.explanation, quality.checked_at
                       FROM dataset_quality_checks AS quality
                       JOIN dataset_versions AS version ON version.id = quality.dataset_version_id
                       JOIN datasets AS dataset ON dataset.id = version.dataset_id
                       WHERE quality.organization_id = %s AND dataset.city_id = %s
                       ORDER BY quality.checked_at DESC""",
                    (organization_id, city["id"]),
                )
            )
            plateau_model = self._dicts(
                connection.execute(
                    """SELECT * FROM plateau_model_inventory
                       WHERE organization_id = %s AND city_id = %s ORDER BY theme""",
                    (organization_id, city["id"]),
                )
            )
            urban_states = self._dicts(
                connection.execute(
                    """SELECT id, state_key, label, effective_date, state_type,
                              lifecycle_status, source_verified, created_at
                       FROM urban_states
                       WHERE organization_id = %s AND city_id = %s
                       ORDER BY effective_date DESC, created_at DESC""",
                    (organization_id, city["id"]),
                )
            )
            annual_updates = self._dicts(
                connection.execute(
                    """SELECT change.id, change.status, change.algorithm_version,
                              before_state.label AS from_label,
                              before_state.effective_date AS from_effective_date,
                              after_state.label AS to_label,
                              after_state.effective_date AS to_effective_date,
                              job.id AS job_id, job.state AS job_state,
                              job.current_stage AS job_stage, change.created_at
                       FROM urban_state_change_sets AS change
                       JOIN urban_states AS before_state
                         ON before_state.organization_id = change.organization_id
                        AND before_state.id = change.from_urban_state_id
                       JOIN urban_states AS after_state
                         ON after_state.organization_id = change.organization_id
                        AND after_state.id = change.to_urban_state_id
                       LEFT JOIN job_runs AS job
                         ON job.organization_id = change.organization_id
                        AND job.parameters ->> 'change_set_id' = change.id::text
                       WHERE change.organization_id = %s AND change.city_id = %s
                       ORDER BY change.created_at DESC, change.id DESC LIMIT 30""",
                    (organization_id, city["id"]),
                )
            )
            return {
                "city": city,
                "datasets": datasets,
                "quality_checks": quality,
                "plateau_model": plateau_model,
                "urban_states": urban_states,
                "annual_updates": annual_updates,
            }

    def transition_dataset_version(
        self,
        organization_id: str,
        version_id: str,
        expected_status: str,
        proposed_status: str,
        note: str,
    ) -> dict[str, Any] | None:
        validate_dataset_transition(
            DatasetReleaseStatus(expected_status), DatasetReleaseStatus(proposed_status)
        )
        context = current_request_context()
        with self._connect() as connection:
            connection.row_factory = dict_row
            before = self._one(
                connection.execute(
                    """SELECT version.*, dataset.city_id
                       FROM dataset_versions AS version
                       JOIN datasets AS dataset ON dataset.id = version.dataset_id
                       WHERE version.organization_id = %s AND version.id = %s FOR UPDATE""",
                    (organization_id, version_id),
                )
            )
            if before is None:
                return None
            if before["service_status"] != expected_status:
                raise ValueError(f"Dataset status changed: expected {expected_status}")
            if proposed_status == "promoted" and not (
                before["analysis_ready"]
                and before["quality_status"] == "passed"
                and before["lifecycle_status"] == "available"
            ):
                raise ValueError(
                    "Dataset cannot be promoted before quality and ingestion gates pass"
                )
            after = self._one(
                connection.execute(
                    """UPDATE dataset_versions
                       SET service_status = %s,
                           accepted_by = CASE WHEN %s = 'accepted' THEN %s ELSE accepted_by END,
                           accepted_at = CASE WHEN %s = 'accepted' THEN now() ELSE accepted_at END,
                           promoted_by = CASE WHEN %s = 'promoted' THEN %s ELSE promoted_by END,
                           promoted_at = CASE WHEN %s = 'promoted' THEN now() ELSE promoted_at END
                       WHERE organization_id = %s AND id = %s RETURNING *""",
                    (
                        proposed_status,
                        proposed_status,
                        context.actor,
                        proposed_status,
                        proposed_status,
                        context.actor,
                        proposed_status,
                        organization_id,
                        version_id,
                    ),
                )
            )
            connection.execute(
                """INSERT INTO dataset_onboarding_events (
                       organization_id, dataset_version_id, from_status, to_status, note, actor
                   ) VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    organization_id,
                    version_id,
                    expected_status,
                    proposed_status,
                    note,
                    context.actor,
                ),
            )
            assert after is not None
            self._service_audit(
                connection,
                organization_id,
                "dataset.transition",
                "dataset_version",
                version_id,
                str(before["city_id"]),
                before,
                after,
            )
            return after

    def analysis_catalog(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            connection.row_factory = dict_row
            definitions = self._dicts(
                connection.execute(
                    """SELECT id, version, name, purpose, required_capabilities,
                              input_contract, output_contract, algorithm_description,
                              claim_boundary
                       FROM analysis_definitions WHERE active ORDER BY name, version DESC"""
                )
            )
            parameters = self._dicts(
                connection.execute(
                    """SELECT analysis_id, analysis_version, parameter_key, value_type,
                              description, default_value, minimum, maximum, allowed_values
                       FROM analysis_parameter_definitions
                       ORDER BY analysis_id, analysis_version, parameter_key"""
                )
            )
            by_definition: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for parameter in parameters:
                key = (parameter.pop("analysis_id"), parameter.pop("analysis_version"))
                by_definition.setdefault(key, []).append(parameter)
            for definition in definitions:
                definition["parameters"] = by_definition.get(
                    (definition["id"], definition["version"]), []
                )
            return definitions

    def service_analysis_runs(
        self, organization_id: str, city_reference: str, limit: int
    ) -> list[dict[str, Any]] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            return self._dicts(
                connection.execute(
                    """SELECT run.id, run.analysis_type, run.status, run.algorithm_version,
                              run.config_hash, run.parameters, run.result_hash,
                              run.output_artifact, run.started_at, run.completed_at,
                              run.created_by,
                              array_remove(array_agg(input.dataset_version_id), NULL)
                                  AS dataset_version_ids,
                              job.id AS job_id, job.state AS job_state,
                              job.current_stage AS job_stage
                       FROM analysis_runs AS run
                       LEFT JOIN analysis_run_dataset_versions AS input
                         ON input.analysis_run_id = run.id
                       LEFT JOIN job_runs AS job
                         ON job.organization_id = run.organization_id
                        AND job.parameters ->> 'analysis_run_id' = run.id::text
                       WHERE run.organization_id = %s AND run.city_id = %s
                       GROUP BY run.id, job.id
                       ORDER BY run.started_at DESC, run.id DESC LIMIT %s""",
                    (organization_id, city["id"], limit),
                )
            )

    @staticmethod
    def _validated_analysis_parameters(
        definitions: list[dict[str, Any]], supplied: dict[str, Any]
    ) -> dict[str, Any]:
        known = {definition["parameter_key"]: definition for definition in definitions}
        unknown = set(supplied) - set(known)
        if unknown:
            raise ValueError(f"Unknown analysis parameters: {', '.join(sorted(unknown))}")
        values: dict[str, Any] = {}
        for key, definition in known.items():
            value = supplied.get(key, definition["default_value"])
            value_type = definition["value_type"]
            valid_type = {
                "integer": type(value) is int,
                "number": type(value) in {int, float},
                "string": isinstance(value, str),
                "boolean": type(value) is bool,
                "enum": isinstance(value, str),
            }[value_type]
            if not valid_type:
                raise ValueError(f"Analysis parameter {key} must be {value_type}")
            if definition["minimum"] is not None and value < definition["minimum"]:
                raise ValueError(f"Analysis parameter {key} is below its minimum")
            if definition["maximum"] is not None and value > definition["maximum"]:
                raise ValueError(f"Analysis parameter {key} exceeds its maximum")
            allowed = definition["allowed_values"]
            if allowed is not None and value not in allowed:
                raise ValueError(f"Analysis parameter {key} is not an allowed value")
            values[key] = value
        return values

    def create_service_analysis_run(
        self, organization_id: str, city_reference: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        context = current_request_context()
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            definition = self._one(
                connection.execute(
                    """SELECT id, version, name, required_capabilities,
                              input_contract, output_contract, claim_boundary
                       FROM analysis_definitions
                       WHERE id = %s AND version = %s AND active""",
                    (payload["analysis_id"], payload["analysis_version"]),
                )
            )
            if definition is None:
                raise ValueError("Analysis definition or version is not active")
            parameter_definitions = self._dicts(
                connection.execute(
                    """SELECT parameter_key, value_type, default_value, minimum,
                              maximum, allowed_values
                       FROM analysis_parameter_definitions
                       WHERE analysis_id = %s AND analysis_version = %s
                       ORDER BY parameter_key""",
                    (payload["analysis_id"], payload["analysis_version"]),
                )
            )
            parameters = self._validated_analysis_parameters(
                parameter_definitions, payload.get("parameters", {})
            )
            unavailable = self._dicts(
                connection.execute(
                    """SELECT required.capability,
                              COALESCE(capability.status, 'unavailable') AS status
                       FROM unnest(%s::text[]) AS required(capability)
                       LEFT JOIN city_capabilities AS capability
                         ON capability.city_id = %s
                        AND capability.capability = required.capability
                       WHERE capability.status IS DISTINCT FROM 'available'""",
                    (definition["required_capabilities"], city["id"]),
                )
            )
            if unavailable:
                missing = ", ".join(f"{row['capability']}={row['status']}" for row in unavailable)
                raise ValueError(f"Required city capabilities are unavailable: {missing}")
            state = self._one(
                connection.execute(
                    """SELECT id, state_key, lifecycle_status FROM urban_states
                       WHERE organization_id = %s AND city_id = %s AND id = %s""",
                    (organization_id, city["id"], payload["urban_state_id"]),
                )
            )
            if state is None:
                raise ValueError(
                    "Urban State does not belong to the selected organization and city"
                )
            if state["lifecycle_status"] not in {"validated", "current"}:
                raise ValueError("Analysis requires a validated or current Urban State")
            input_versions = payload["dataset_versions"]
            if not input_versions:
                raise ValueError("At least one explicit dataset version is required")
            required_dataset_roles = set(definition["input_contract"].get("dataset_roles", []))
            supplied_dataset_roles = set(input_versions)
            if supplied_dataset_roles != required_dataset_roles:
                missing_roles = sorted(required_dataset_roles - supplied_dataset_roles)
                unexpected_roles = sorted(supplied_dataset_roles - required_dataset_roles)
                details = []
                if missing_roles:
                    details.append("missing=" + ",".join(missing_roles))
                if unexpected_roles:
                    details.append("unexpected=" + ",".join(unexpected_roles))
                raise ValueError(
                    "Dataset input roles must exactly match the analysis contract: "
                    + "; ".join(details)
                )
            version_ids = list(dict.fromkeys(input_versions.values()))
            versions = self._dicts(
                connection.execute(
                    """SELECT version.id, dataset.dataset_key, version.service_status
                       FROM dataset_versions AS version
                       JOIN datasets AS dataset ON dataset.id = version.dataset_id
                       WHERE version.organization_id = %s AND dataset.city_id = %s
                         AND version.id = ANY(%s::uuid[])""",
                    (organization_id, city["id"], version_ids),
                )
            )
            if {str(row["id"]) for row in versions} != set(version_ids):
                raise ValueError("Every dataset version must belong to the selected city")
            unpromoted = [str(row["id"]) for row in versions if row["service_status"] != "promoted"]
            if unpromoted:
                raise ValueError(
                    "Analysis inputs must be promoted dataset versions: " + ", ".join(unpromoted)
                )
            algorithm_version = f"{definition['id']}@{definition['version']}"
            reproducibility = {
                "organization_id": organization_id,
                "city_id": str(city["id"]),
                "urban_state_id": payload["urban_state_id"],
                "analysis_id": definition["id"],
                "analysis_version": definition["version"],
                "dataset_versions": input_versions,
                "parameters": parameters,
            }
            config_hash = hashlib.sha256(
                json.dumps(
                    reproducibility,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            run = self._one(
                connection.execute(
                    """INSERT INTO analysis_runs (
                           id, organization_id, city_id, analysis_type, status,
                           config_hash, started_at, metadata, created_by,
                           algorithm_version, parameters
                       ) VALUES (
                           gen_random_uuid(), %s, %s, %s, 'queued', %s, now(),
                           %s, %s, %s, %s
                       ) RETURNING *""",
                    (
                        organization_id,
                        city["id"],
                        definition["id"],
                        config_hash,
                        json.dumps(
                            {
                                "urban_state_id": payload["urban_state_id"],
                                "dataset_roles": input_versions,
                                "input_contract": definition["input_contract"],
                                "output_contract": definition["output_contract"],
                                "claim_boundary": definition["claim_boundary"],
                            },
                            ensure_ascii=False,
                        ),
                        context.actor,
                        algorithm_version,
                        json.dumps(parameters, ensure_ascii=False),
                    ),
                )
            )
            assert run is not None
            for role, version_id in sorted(input_versions.items()):
                connection.execute(
                    """INSERT INTO analysis_run_dataset_versions (
                           organization_id, analysis_run_id, dataset_version_id, input_role
                       ) VALUES (%s, %s, %s, %s)""",
                    (organization_id, run["id"], version_id, role),
                )
            connection.execute(
                """INSERT INTO state_analysis_runs (
                       organization_id, urban_state_id, analysis_run_id, result_role
                   ) VALUES (%s, %s, %s, 'derived')""",
                (organization_id, payload["urban_state_id"], run["id"]),
            )
            idempotency_key = hashlib.sha256(
                f"{organization_id}:analysis_run:{run['id']}:{config_hash}".encode()
            ).hexdigest()
            job = self._one(
                connection.execute(
                    """INSERT INTO job_runs (
                           organization_id, city_id, job_type, state, config_hash,
                           algorithm_version, idempotency_key, parameters
                       ) VALUES (%s, %s, 'analysis_run', 'queued', %s, %s, %s, %s)
                       ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL
                       DO UPDATE SET idempotency_key = EXCLUDED.idempotency_key
                       RETURNING id, state, current_stage, queued_at""",
                    (
                        organization_id,
                        city["id"],
                        config_hash,
                        algorithm_version,
                        idempotency_key,
                        json.dumps(
                            {
                                "analysis_run_id": str(run["id"]),
                                "analysis_id": definition["id"],
                                "analysis_version": definition["version"],
                            }
                        ),
                    ),
                )
            )
            assert job is not None
            for version_id in sorted(set(version_ids)):
                connection.execute(
                    """INSERT INTO job_dataset_versions (
                           organization_id, job_run_id, dataset_version_id
                       ) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
                    (organization_id, job["id"], version_id),
                )
            connection.execute(
                """INSERT INTO job_events (job_run_id, state, message)
                   VALUES (%s, 'queued', 'versioned analysis contract accepted')
                   ON CONFLICT DO NOTHING""",
                (job["id"],),
            )
            self._activity(
                connection,
                organization_id,
                str(city["id"]),
                "analysis_started",
                "analysis_run",
                str(run["id"]),
                f"分析「{definition['name']}」をversion付き入力で登録",
            )
            self._service_audit(
                connection,
                organization_id,
                "analysis.create",
                "analysis_run",
                str(run["id"]),
                str(city["id"]),
                None,
                {**run, "job_id": job["id"], "reproducibility": reproducibility},
            )
            return {"analysis_run": run, "job": job, "reproducibility": reproducibility}

    def scenario_library(
        self, organization_id: str, city_reference: str, limit: int
    ) -> list[dict[str, Any]] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            return self._dicts(
                connection.execute(
                    """SELECT scenario.id, scenario.scenario_key, scenario.title,
                              scenario.objective_mode, scenario.objective_definition,
                              scenario.site_count, scenario.algorithm_version,
                              scenario.lifecycle_status, scenario.review_status,
                              scenario.assumptions, scenario.generated_at,
                              scenario.base_urban_state_id, scenario.parent_scenario_run_id
                       FROM scenario_runs AS scenario
                       JOIN city_dataset_versions AS version
                         ON version.id = scenario.dataset_version_id
                       WHERE scenario.organization_id = %s AND version.city_id = %s
                       ORDER BY scenario.generated_at DESC LIMIT %s""",
                    (organization_id, city["city_code"], limit),
                )
            )

    def clone_scenario(
        self, organization_id: str, scenario_id: str, title: str
    ) -> dict[str, Any] | None:
        context = current_request_context()
        new_id = str(uuid.uuid4())
        scenario_key = f"clone-{new_id}"
        with self._connect() as connection:
            connection.row_factory = dict_row
            result = self._one(
                connection.execute(
                    """INSERT INTO scenario_runs (
                           id, scenario_key, dataset_version_id, network_version_id,
                           context_run_id, plateau_product_specification_version,
                           algorithm_version, objective_mode, objective_definition,
                           site_count, candidate_count, algorithm_kind, config_hash,
                           generated_at, runtime_seconds, lifecycle_status, reviewed_at,
                           metadata, base_urban_state_id, organization_id, title,
                           parent_scenario_run_id, assumptions, review_status
                       )
                       SELECT %s, %s, scenario.dataset_version_id,
                              scenario.network_version_id, scenario.context_run_id,
                              scenario.plateau_product_specification_version,
                              scenario.algorithm_version, scenario.objective_mode,
                              scenario.objective_definition, scenario.site_count,
                              scenario.candidate_count, scenario.algorithm_kind,
                              scenario.config_hash, scenario.generated_at,
                              scenario.runtime_seconds, 'draft', NULL,
                              scenario.metadata || %s::jsonb,
                              scenario.base_urban_state_id, scenario.organization_id,
                              %s, scenario.id, scenario.assumptions, 'not_requested'
                       FROM scenario_runs AS scenario
                       WHERE scenario.organization_id = %s AND scenario.id = %s
                       RETURNING *""",
                    (
                        new_id,
                        scenario_key,
                        json.dumps(
                            {
                                "clone_boundary": "identical immutable computed result",
                                "cloned_from": scenario_id,
                                "cloned_by": context.actor,
                            },
                            ensure_ascii=False,
                        ),
                        title,
                        organization_id,
                        scenario_id,
                    ),
                )
            )
            if result is None:
                return None
            connection.execute(
                """INSERT INTO scenario_sites (
                       scenario_run_id, site_order, candidate_id, network_node_id,
                       road_gml_id, road_surface_id, road_name,
                       existing_transport_distance_m, component_id,
                       candidate_to_graph_connector_m, siting_feasibility, geom
                   )
                   SELECT %s, site_order, candidate_id, network_node_id,
                          road_gml_id, road_surface_id, road_name,
                          existing_transport_distance_m, component_id,
                          candidate_to_graph_connector_m, siting_feasibility, geom
                   FROM scenario_sites WHERE scenario_run_id = %s""",
                (new_id, scenario_id),
            )
            connection.execute(
                """INSERT INTO scenario_objectives (
                       scenario_run_id, objective_name, objective_role, value,
                       unit, definition, metadata
                   )
                   SELECT %s, objective_name, objective_role, value,
                          unit, definition, metadata
                   FROM scenario_objectives WHERE scenario_run_id = %s""",
                (new_id, scenario_id),
            )
            connection.execute(
                """INSERT INTO scenario_constraints (
                       scenario_run_id, site_order, constraint_name, threshold,
                       observed, satisfied, interpretation
                   )
                   SELECT %s, site_order, constraint_name, threshold,
                          observed, satisfied, interpretation
                   FROM scenario_constraints WHERE scenario_run_id = %s""",
                (new_id, scenario_id),
            )
            connection.execute(
                """INSERT INTO scenario_impacts (
                       scenario_run_id, metric_name, value, unit, interpretation
                   )
                   SELECT %s, metric_name, value, unit, interpretation
                   FROM scenario_impacts WHERE scenario_run_id = %s""",
                (new_id, scenario_id),
            )
            connection.execute(
                """INSERT INTO scenario_context (
                       scenario_run_id, site_order, context_type, label,
                       feature_count, review_status, siting_feasibility, source_payload
                   )
                   SELECT %s, site_order, context_type, label, feature_count,
                          review_status, siting_feasibility, source_payload
                   FROM scenario_context WHERE scenario_run_id = %s""",
                (new_id, scenario_id),
            )
            connection.execute(
                """INSERT INTO scenario_evidence (
                       scenario_run_id, representative_building_gml_id,
                       virtual_candidate_id, route_semantics, evidence, created_at
                   )
                   SELECT %s, representative_building_gml_id, virtual_candidate_id,
                          route_semantics, evidence, created_at
                   FROM scenario_evidence WHERE scenario_run_id = %s""",
                (new_id, scenario_id),
            )
            connection.execute(
                """INSERT INTO scenario_field_checks (scenario_run_id, site_order)
                   SELECT %s, site_order FROM scenario_sites WHERE scenario_run_id = %s""",
                (new_id, new_id),
            )
            connection.execute(
                """INSERT INTO scenario_lifecycle_events (
                       scenario_run_id, from_status, to_status, note
                   ) VALUES (%s, NULL, 'draft', %s)""",
                (new_id, f"cloned from {scenario_id}; field checks reset"),
            )
            city = self._one(
                connection.execute(
                    """SELECT city.id FROM cities AS city
                       JOIN city_dataset_versions AS version
                         ON version.city_id = city.city_code
                       WHERE city.organization_id = %s AND version.id = %s""",
                    (organization_id, result["dataset_version_id"]),
                )
            )
            self._service_audit(
                connection,
                organization_id,
                "scenario.clone",
                "scenario",
                new_id,
                str(city["id"]) if city else None,
                {"parent_scenario_run_id": scenario_id},
                result,
            )
            return result

    def scenario_comparisons(
        self, organization_id: str, city_reference: str, limit: int
    ) -> list[dict[str, Any]] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            return self._dicts(
                connection.execute(
                    """SELECT id, investigation_id, title, scenario_run_ids,
                              comparison_dimensions, created_by, created_at
                       FROM scenario_comparisons
                       WHERE organization_id = %s AND city_id = %s
                       ORDER BY created_at DESC, id DESC LIMIT %s""",
                    (organization_id, city["id"], limit),
                )
            )

    def create_scenario_comparison(
        self, organization_id: str, city_reference: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            matched = connection.execute(
                """SELECT count(*) AS count
                   FROM scenario_runs AS scenario
                   JOIN city_dataset_versions AS version ON version.id = scenario.dataset_version_id
                   WHERE scenario.organization_id = %s AND version.city_id = %s
                     AND scenario.id = ANY(%s::uuid[])""",
                (organization_id, city["city_code"], payload["scenario_run_ids"]),
            ).fetchone()["count"]
            if matched != len(payload["scenario_run_ids"]):
                raise ValueError("All scenarios must belong to the selected city and organization")
            context = current_request_context()
            return self._one(
                connection.execute(
                    """INSERT INTO scenario_comparisons (
                           organization_id, city_id, investigation_id, title,
                           scenario_run_ids, comparison_dimensions, created_by
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *""",
                    (
                        organization_id,
                        city["id"],
                        payload.get("investigation_id"),
                        payload["title"],
                        payload["scenario_run_ids"],
                        json.dumps(payload["comparison_dimensions"], ensure_ascii=False),
                        context.actor,
                    ),
                )
            )

    def create_evidence_center(
        self, organization_id: str, city_reference: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        if payload.get("data_classification", "internal") == "public":
            sources = payload["source_manifest"].get("sources", [])
            if (
                not sources
                or any(
                    not isinstance(source, dict) or source.get("data_classification") != "public"
                    for source in sources
                )
                or payload.get("field_evidence_manifest")
                or payload.get("decision_manifest")
            ):
                raise ValueError(
                    "Public Evidence requires public-classified sources and excludes field/decision records"
                )
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            investigation_id = payload.get("investigation_id")
            scenario_run_id = payload.get("scenario_run_id")
            if (
                investigation_id
                and not connection.execute(
                    """SELECT 1 FROM investigations
                   WHERE organization_id = %s AND city_id = %s AND id = %s""",
                    (organization_id, city["id"], investigation_id),
                ).fetchone()
            ):
                raise ValueError("Evidence investigation does not belong to the tenant and city")
            if (
                scenario_run_id
                and not connection.execute(
                    """SELECT 1 FROM scenario_runs AS scenario
                   JOIN city_dataset_versions AS version
                     ON version.id = scenario.dataset_version_id
                   WHERE scenario.organization_id = %s AND version.city_id = %s
                     AND scenario.id = %s""",
                    (organization_id, city["city_code"], scenario_run_id),
                ).fetchone()
            ):
                raise ValueError("Evidence scenario does not belong to the tenant and city")
            manifest = {
                "source_manifest": payload["source_manifest"],
                "algorithm_manifest": payload["algorithm_manifest"],
                "validation_manifest": payload["validation_manifest"],
                "field_evidence_manifest": payload.get("field_evidence_manifest", []),
                "decision_manifest": payload.get("decision_manifest", []),
            }
            digest = hashlib.sha256(
                json.dumps(
                    manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True
                ).encode()
            ).hexdigest()
            context = current_request_context()
            return self._one(
                connection.execute(
                    """INSERT INTO evidence_centers (
                           organization_id, city_id, investigation_id, scenario_run_id,
                           source_manifest, algorithm_manifest, validation_manifest,
                           field_evidence_manifest, decision_manifest, manifest_sha256,
                           data_classification, created_by
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING *""",
                    (
                        organization_id,
                        city["id"],
                        investigation_id,
                        scenario_run_id,
                        json.dumps(manifest["source_manifest"], ensure_ascii=False),
                        json.dumps(manifest["algorithm_manifest"], ensure_ascii=False),
                        json.dumps(manifest["validation_manifest"], ensure_ascii=False),
                        json.dumps(manifest["field_evidence_manifest"], ensure_ascii=False),
                        json.dumps(manifest["decision_manifest"], ensure_ascii=False),
                        digest,
                        payload.get("data_classification", "internal"),
                        context.actor,
                    ),
                )
            )

    def evidence_library(
        self, organization_id: str, city_reference: str, limit: int
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            evidence = self._dicts(
                connection.execute(
                    """SELECT id, investigation_id, scenario_run_id, manifest_sha256,
                              data_classification, created_by, created_at,
                              jsonb_array_length(field_evidence_manifest) AS field_evidence_count,
                              jsonb_array_length(decision_manifest) AS decision_count
                       FROM evidence_centers
                       WHERE organization_id = %s AND city_id = %s
                       ORDER BY created_at DESC, id DESC LIMIT %s""",
                    (organization_id, city["id"], limit),
                )
            )
            reports = self._dicts(
                connection.execute(
                    """SELECT id, report_type, title, investigation_id,
                              scenario_comparison_id, generator_version,
                              artifact_uri, artifact_sha256, data_classification,
                              created_by, created_at
                       FROM report_records
                       WHERE organization_id = %s AND city_id = %s
                       ORDER BY created_at DESC, id DESC LIMIT %s""",
                    (organization_id, city["id"], limit),
                )
            )
            validations = self._dicts(
                connection.execute(
                    """SELECT id, claim_key, method_key, validation_status,
                              run_status, algorithm_version, generated_at
                       FROM validation_runs
                       WHERE organization_id = %s AND city_id = %s
                       ORDER BY generated_at DESC, id DESC LIMIT %s""",
                    (organization_id, city["id"], limit),
                )
            )
            return {
                "city": city,
                "evidence_centers": evidence,
                "reports": reports,
                "validation_runs": validations,
            }

    @staticmethod
    def _report_digest(content: dict[str, Any]) -> tuple[str, str]:
        serialized = json.dumps(
            content,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return serialized, hashlib.sha256(serialized.encode()).hexdigest()

    def create_report_record(
        self, organization_id: str, city_reference: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        context = current_request_context()
        generator_version = "municipal-report-v1.0.0"
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
            organization = self._one(
                connection.execute(
                    "SELECT id, name FROM organizations WHERE id = %s",
                    (organization_id,),
                )
            )
            assert organization is not None
            report_type = payload["report_type"]
            subject: dict[str, Any]
            investigation_id = payload.get("investigation_id")
            comparison_id = payload.get("scenario_comparison_id")
            if report_type == "investigation":
                if not investigation_id or comparison_id:
                    raise ValueError("Investigation reports require one investigation_id")
                investigation = self.investigation_detail(organization_id, investigation_id)
                if investigation is None or str(investigation["investigation"]["city_id"]) != str(
                    city["id"]
                ):
                    raise ValueError("Investigation does not belong to the selected city")
                subject = investigation
            elif report_type == "scenario_comparison":
                if not comparison_id or investigation_id:
                    raise ValueError(
                        "Scenario comparison reports require one scenario_comparison_id"
                    )
                comparison = self._one(
                    connection.execute(
                        """SELECT * FROM scenario_comparisons
                           WHERE organization_id = %s AND city_id = %s AND id = %s""",
                        (organization_id, city["id"], comparison_id),
                    )
                )
                if comparison is None:
                    raise ValueError("Scenario comparison does not belong to the selected city")
                subject = {"scenario_comparison": comparison}
            elif report_type == "data_quality":
                if investigation_id or comparison_id:
                    raise ValueError("Data quality reports are city-scoped")
                subject = self.data_hub(organization_id, city_reference) or {}
            elif report_type in {"annual_change", "resilience_review"}:
                if investigation_id or comparison_id:
                    raise ValueError(f"{report_type} reports are city-scoped")
                subject = {
                    "urban_states": self._dicts(
                        connection.execute(
                            """SELECT id, state_key, label, effective_date, state_type,
                                      lifecycle_status, source_verified, validation_report
                               FROM urban_states
                               WHERE organization_id = %s AND city_id = %s
                               ORDER BY effective_date, id""",
                            (organization_id, city["id"]),
                        )
                    ),
                    "stress_tests": self._dicts(
                        connection.execute(
                            """SELECT id, title, stress_test_type, status, assumption_hash,
                                      algorithm_version, route_semantics, limitation, created_at
                               FROM stress_test_runs
                               WHERE organization_id = %s AND city_id = %s
                               ORDER BY created_at, id""",
                            (organization_id, city["id"]),
                        )
                    ),
                }
            else:
                raise ValueError("Unsupported report type")
            evidence = self._dicts(
                connection.execute(
                    """SELECT id, manifest_sha256, data_classification, created_at
                       FROM evidence_centers
                       WHERE organization_id = %s AND city_id = %s
                         AND (%s::uuid IS NULL OR investigation_id = %s)
                       ORDER BY created_at, id""",
                    (organization_id, city["id"], investigation_id, investigation_id),
                )
            )
            requested_classification = payload.get("data_classification", "internal")
            if requested_classification == "public":
                if report_type != "data_quality":
                    raise ValueError(
                        "This deterministic generator only supports public data_quality reports"
                    )
                dataset_classifications = {
                    row.get("data_classification")
                    for row in subject.get("datasets", [])
                    if row.get("version_id")
                }
                if dataset_classifications - {"public"} or any(
                    row["data_classification"] != "public" for row in evidence
                ):
                    raise ValueError("Public reports require public-classified inputs and evidence")
            structured_content = {
                "schema_version": "citygap-municipal-report-1.0.0",
                "generator_version": generator_version,
                "organization": {
                    "id": organization_id,
                    "name": organization["name"],
                },
                "city": {
                    "id": str(city["id"]),
                    "city_code": city["city_code"],
                    "city_key": city["city_key"],
                    "name": city["name"],
                },
                "report_type": report_type,
                "title": payload["title"],
                "subject": subject,
                "evidence": evidence,
                "claim_boundary": (
                    "This report records versioned model outputs, reviews and human decisions; "
                    "it does not create an administrative approval or policy recommendation."
                ),
            }
            _, digest = self._report_digest(structured_content)
            report_id = str(uuid.uuid4())
            artifact_uri = f"citygap-report://{report_id}/report.json"
            result = self._one(
                connection.execute(
                    """INSERT INTO report_records (
                           id, organization_id, city_id, investigation_id,
                           scenario_comparison_id, report_type, title, structured_content,
                           generator_version, artifact_uri, artifact_sha256,
                           data_classification, created_by
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING id, report_type, title, generator_version, artifact_uri,
                                 artifact_sha256, data_classification, created_by, created_at""",
                    (
                        report_id,
                        organization_id,
                        city["id"],
                        investigation_id,
                        comparison_id,
                        report_type,
                        payload["title"],
                        json.dumps(structured_content, ensure_ascii=False, default=str),
                        generator_version,
                        artifact_uri,
                        digest,
                        requested_classification,
                        context.actor,
                    ),
                )
            )
            assert result is not None
            self._service_audit(
                connection,
                organization_id,
                "report.create",
                "report",
                report_id,
                str(city["id"]),
                None,
                result,
            )
            return result

    def report_artifact(self, organization_id: str, report_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            report = self._one(
                connection.execute(
                    """SELECT id, title, structured_content, artifact_sha256,
                              data_classification, generator_version, created_at
                       FROM report_records WHERE organization_id = %s AND id = %s""",
                    (organization_id, report_id),
                )
            )
            if report is None:
                return None
            _, calculated = self._report_digest(report["structured_content"])
            if calculated != report["artifact_sha256"]:
                raise ValueError("Stored report content does not match its artifact hash")
            return report

    def export_report(
        self, organization_id: str, report_id: str, export_scope: str
    ) -> dict[str, Any] | None:
        report = self.report_artifact(organization_id, report_id)
        if report is None:
            return None
        if export_scope == "public" and report["data_classification"] != "public":
            raise ValueError("Only public-classified reports can be exported publicly")
        context = current_request_context()
        with self._connect() as connection:
            connection.row_factory = dict_row
            return self._one(
                connection.execute(
                    """INSERT INTO report_exports (
                           organization_id, report_id, export_scope, data_classification,
                           artifact_uri, artifact_sha256, exported_by
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                       RETURNING *""",
                    (
                        organization_id,
                        report_id,
                        export_scope,
                        report["data_classification"],
                        f"citygap-report://{report_id}/{export_scope}.json",
                        report["artifact_sha256"],
                        context.actor,
                    ),
                )
            )

    def service_search(
        self, organization_id: str, query: str, city_reference: str | None, limit: int
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            connection.row_factory = dict_row
            city_id = None
            if city_reference:
                city = self._city(connection, organization_id, city_reference)
                if city is None:
                    return []
                city_id = city["id"]
            return self._dicts(
                connection.execute(
                    """SELECT city_id, entity_type, entity_id, title, subtitle, updated_at
                       FROM service_search_documents
                       WHERE organization_id = %s
                         AND (%s::uuid IS NULL OR city_id = %s)
                         AND (title ILIKE '%%' || %s || '%%'
                              OR subtitle ILIKE '%%' || %s || '%%'
                              OR entity_id = %s)
                       ORDER BY updated_at DESC LIMIT %s""",
                    (organization_id, city_id, city_id, query, query, query, limit),
                )
            )

    def activity_feed(
        self, organization_id: str, city_reference: str | None, limit: int
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            connection.row_factory = dict_row
            city_id = None
            if city_reference:
                city = self._city(connection, organization_id, city_reference)
                if city is None:
                    return []
                city_id = city["id"]
            return self._dicts(
                connection.execute(
                    """SELECT id, city_id, event_type, resource_type, resource_id, title,
                              description AS summary, actor_label, occurred_at
                       FROM activity_events
                       WHERE organization_id = %s AND (%s::uuid IS NULL OR city_id = %s)
                       ORDER BY occurred_at DESC, id DESC LIMIT %s""",
                    (organization_id, city_id, city_id, limit),
                )
            )

    def service_audit_events(
        self,
        organization_id: str,
        city_reference: str | None,
        action: str | None,
        actor: str | None,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        cursor_values = decode_cursor(cursor)
        cursor_id: int | None = None
        if cursor_values is not None:
            try:
                cursor_id = int(cursor_values["id"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("Invalid pagination cursor") from error
        with self._connect() as connection:
            connection.row_factory = dict_row
            city_id = None
            city_code = None
            if city_reference:
                city = self._city(connection, organization_id, city_reference)
                if city is None:
                    return {"items": [], "next_cursor": None}
                city_id = str(city["id"])
                city_code = city["city_code"]
            rows = self._dicts(
                connection.execute(
                    """SELECT id, actor, action, resource_type, resource_id, city_id,
                              request_id, before_state AS before, after_state AS after,
                              data_classification, occurred_at
                       FROM audit_log
                       WHERE organization_id = %s
                         AND (%s::text IS NULL OR city_id IN (%s, %s))
                         AND (%s::text IS NULL OR action = %s)
                         AND (%s::text IS NULL OR actor = %s)
                         AND (%s::timestamptz IS NULL OR occurred_at >= %s)
                         AND (%s::timestamptz IS NULL OR occurred_at <= %s)
                         AND (%s::bigint IS NULL OR id < %s)
                       ORDER BY id DESC LIMIT %s""",
                    (
                        organization_id,
                        city_id,
                        city_id,
                        city_code,
                        action,
                        action,
                        actor,
                        actor,
                        occurred_from,
                        occurred_from,
                        occurred_to,
                        occurred_to,
                        cursor_id,
                        cursor_id,
                        limit + 1,
                    ),
                )
            )
        has_more = len(rows) > limit
        items = rows[:limit]
        return {
            "items": items,
            "next_cursor": encode_cursor({"id": items[-1]["id"]}) if has_more and items else None,
        }

    def record_usage(
        self,
        organization_id: str,
        city_reference: str | None,
        event_name: str,
        feature_key: str,
    ) -> None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            city_id = None
            if city_reference:
                city = self._city(connection, organization_id, city_reference)
                if city is None:
                    raise ValueError("City not found")
                city_id = city["id"]
            connection.execute(
                """INSERT INTO product_usage_events (
                       organization_id, city_id, event_name, feature_key, metadata
                   ) VALUES (%s, %s, %s, %s, '{}')""",
                (organization_id, city_id, event_name, feature_key),
            )

    def operations_overview(self, organization_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            connection.row_factory = dict_row
            jobs = (
                self._one(
                    connection.execute(
                        """SELECT
                           count(*) FILTER (
                               WHERE job.state = 'queued' AND cancellation.job_run_id IS NULL
                           ) AS queued,
                           count(*) FILTER (WHERE job.state = 'running') AS running,
                           count(*) FILTER (WHERE job.state = 'failed') AS failed,
                           count(*) FILTER (
                               WHERE cancellation.job_run_id IS NOT NULL
                           ) AS cancelled,
                           max(job.last_heartbeat_at) FILTER (
                               WHERE job.state = 'running'
                           ) AS latest_worker_heartbeat
                       FROM job_runs AS job
                       LEFT JOIN job_cancellation_requests AS cancellation
                         ON cancellation.organization_id = job.organization_id
                        AND cancellation.job_run_id = job.id
                       WHERE job.organization_id = %s""",
                        (organization_id,),
                    )
                )
                or {}
            )
            datasets = (
                self._one(
                    connection.execute(
                        """SELECT
                           count(*) FILTER (WHERE version.service_status = 'failed') AS failed,
                           count(*) FILTER (WHERE version.service_status = 'validating') AS validating,
                           count(*) FILTER (WHERE version.service_status = 'analysis_ready')
                               AS awaiting_promotion
                       FROM dataset_versions AS version
                       WHERE version.organization_id = %s""",
                        (organization_id,),
                    )
                )
                or {}
            )
            backups = self._dicts(
                connection.execute(
                    """SELECT id, backup_type, status, artifact_sha256,
                              started_at, completed_at, initiated_by, error_message
                       FROM backup_runs
                       WHERE organization_id = %s
                       ORDER BY started_at DESC LIMIT 10""",
                    (organization_id,),
                )
            )
            releases = self._dicts(
                connection.execute(
                    """SELECT version, application_commit, migration_version,
                              frontend_asset_version, analysis_versions,
                              release_status, migration_plan_uri, rollback_plan_uri,
                              released_at, created_at
                       FROM service_releases
                       ORDER BY created_at DESC"""
                )
            )
            return {
                "jobs": jobs,
                "datasets": datasets,
                "backups": backups,
                "releases": releases,
                "boundaries": {
                    "running_job_cancel": "operator intervention; API only cancels queued jobs",
                    "backup_execution": "deployment operator command; records are shown here",
                    "slo": "measurement foundation; no contractual SLA is asserted",
                },
            }

    def service_jobs(
        self,
        organization_id: str,
        state: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            connection.row_factory = dict_row
            return self._dicts(
                connection.execute(
                    """SELECT job.id, city.city_key, city.name AS city_name,
                              job.job_type,
                              CASE WHEN cancellation.job_run_id IS NOT NULL
                                   THEN 'cancelled' ELSE job.state END AS state,
                              job.current_stage, job.algorithm_version, job.config_hash,
                              job.retry_count, job.max_retries, job.queued_at,
                              job.started_at, job.finished_at, job.last_heartbeat_at,
                              job.error_message, cancellation.reason AS cancellation_reason,
                              cancellation.requested_by AS cancelled_by,
                              cancellation.requested_at AS cancelled_at
                       FROM job_runs AS job
                       JOIN cities AS city
                         ON city.organization_id = job.organization_id
                        AND city.id = job.city_id
                       LEFT JOIN job_cancellation_requests AS cancellation
                         ON cancellation.organization_id = job.organization_id
                        AND cancellation.job_run_id = job.id
                       WHERE job.organization_id = %s
                         AND (%s::text IS NULL OR
                              CASE WHEN cancellation.job_run_id IS NOT NULL
                                   THEN 'cancelled' ELSE job.state END = %s)
                       ORDER BY job.queued_at DESC, job.id DESC LIMIT %s""",
                    (organization_id, state, state, limit),
                )
            )

    def service_job_detail(self, organization_id: str, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = dict_row
            job = self._one(
                connection.execute(
                    """SELECT job.*,
                              CASE WHEN cancellation.job_run_id IS NOT NULL
                                   THEN 'cancelled' ELSE job.state END AS effective_state,
                              cancellation.reason AS cancellation_reason,
                              cancellation.requested_by AS cancelled_by,
                              cancellation.requested_at AS cancelled_at
                       FROM job_runs AS job
                       LEFT JOIN job_cancellation_requests AS cancellation
                         ON cancellation.organization_id = job.organization_id
                        AND cancellation.job_run_id = job.id
                       WHERE job.organization_id = %s AND job.id = %s""",
                    (organization_id, job_id),
                )
            )
            if job is None:
                return None
            inputs = self._dicts(
                connection.execute(
                    """SELECT link.dataset_version_id, version.version_key,
                              version.dataset_year, dataset.dataset_key, dataset.title
                       FROM job_dataset_versions AS link
                       JOIN dataset_versions AS version ON version.id = link.dataset_version_id
                       JOIN datasets AS dataset ON dataset.id = version.dataset_id
                       WHERE link.job_run_id = %s
                         AND version.organization_id = %s
                       ORDER BY dataset.dataset_key, version.version_key""",
                    (job_id, organization_id),
                )
            )
            events = self._dicts(
                connection.execute(
                    """SELECT state, stage, message, recorded_at
                       FROM job_events WHERE job_run_id = %s
                       ORDER BY recorded_at, id""",
                    (job_id,),
                )
            )
            attempts = self._dicts(
                connection.execute(
                    """SELECT attempt_number, worker_id, started_at, finished_at,
                              result, error_message
                       FROM job_attempts WHERE job_run_id = %s
                       ORDER BY attempt_number""",
                    (job_id,),
                )
            )
            return {"job": job, "inputs": inputs, "events": events, "attempts": attempts}

    def operate_service_job(
        self,
        organization_id: str,
        job_id: str,
        action: str,
        expected_state: str,
        reason: str,
        cancel_confirmation: str | None,
    ) -> dict[str, Any] | None:
        context = current_request_context()
        with self._connect() as connection:
            connection.row_factory = dict_row
            before = self._one(
                connection.execute(
                    """SELECT job.*, cancellation.job_run_id AS cancellation_id,
                              COALESCE(
                                  (SELECT max(attempt_number) FROM job_attempts
                                   WHERE job_run_id = job.id), 0
                              ) AS attempt_count
                       FROM job_runs AS job
                       LEFT JOIN job_cancellation_requests AS cancellation
                         ON cancellation.organization_id = job.organization_id
                        AND cancellation.job_run_id = job.id
                       WHERE job.organization_id = %s AND job.id = %s
                       FOR UPDATE OF job""",
                    (organization_id, job_id),
                )
            )
            if before is None:
                return None
            effective_state = "cancelled" if before["cancellation_id"] else before["state"]
            if effective_state != expected_state:
                raise ValueError(
                    f"Job state changed: expected {expected_state}, current {effective_state}"
                )
            if action == "cancel":
                if expected_state != "queued" or cancel_confirmation != "cancel":
                    raise ValueError(
                        "Only queued jobs can be cancelled and cancel_confirmation must be 'cancel'"
                    )
                connection.execute(
                    """INSERT INTO job_cancellation_requests (
                           organization_id, job_run_id, reason, requested_by
                       ) VALUES (%s, %s, %s, %s)""",
                    (organization_id, job_id, reason, context.actor),
                )
                after = {**before, "effective_state": "cancelled", "cancellation_reason": reason}
            elif action == "retry":
                if expected_state != "failed" or before["cancellation_id"]:
                    raise ValueError("Only failed, non-cancelled jobs can be retried")
                attempt_count = int(before["attempt_count"])
                if attempt_count >= 10:
                    raise ValueError("Manual retry limit reached")
                after = self._one(
                    connection.execute(
                        """UPDATE job_runs
                           SET state = 'queued', current_stage = NULL,
                               started_at = NULL, completed_at = NULL, finished_at = NULL,
                               last_heartbeat_at = NULL, locked_by = NULL,
                               error_message = NULL, retry_count = %s,
                               max_retries = GREATEST(max_retries, %s)
                           WHERE organization_id = %s AND id = %s
                           RETURNING *""",
                        (attempt_count, attempt_count + 1, organization_id, job_id),
                    )
                )
                connection.execute(
                    """INSERT INTO job_events (job_run_id, state, message)
                       VALUES (%s, 'queued', %s)""",
                    (job_id, f"manual retry requested: {reason}"),
                )
                assert after is not None
                after["effective_state"] = "queued"
            else:
                raise ValueError("Unsupported job operation")
            self._service_audit(
                connection,
                organization_id,
                f"job.{action}",
                "job",
                job_id,
                str(before["city_id"]),
                before,
                after,
            )
            return after

    def prometheus_metrics(self, organization_id: str) -> str:
        with self._connect() as connection:
            connection.row_factory = dict_row
            rows = self._dicts(
                connection.execute(
                    """SELECT
                           CASE WHEN cancellation.job_run_id IS NOT NULL
                                THEN 'cancelled' ELSE job.state END AS state,
                           count(*) AS count
                       FROM job_runs AS job
                       LEFT JOIN job_cancellation_requests AS cancellation
                         ON cancellation.organization_id = job.organization_id
                        AND cancellation.job_run_id = job.id
                       WHERE job.organization_id = %s
                       GROUP BY 1 ORDER BY 1""",
                    (organization_id,),
                )
            )
            runtime = self._one(
                connection.execute(
                    """SELECT count(*) FILTER (
                               WHERE started_at IS NOT NULL AND finished_at IS NOT NULL
                           ) AS completed_count,
                           COALESCE(sum(EXTRACT(EPOCH FROM (finished_at - started_at)))
                               FILTER (WHERE started_at IS NOT NULL AND finished_at IS NOT NULL), 0)
                               AS runtime_seconds_sum
                       FROM job_runs WHERE organization_id = %s""",
                    (organization_id,),
                )
            ) or {"completed_count": 0, "runtime_seconds_sum": 0}
            datasets = self._dicts(
                connection.execute(
                    """SELECT service_status AS state, count(*) AS count
                       FROM dataset_versions WHERE organization_id = %s
                       GROUP BY service_status ORDER BY service_status""",
                    (organization_id,),
                )
            )
        lines = [
            "# HELP citygap_jobs Tenant-scoped durable jobs by effective state.",
            "# TYPE citygap_jobs gauge",
        ]
        lines.extend(f'citygap_jobs{{state="{row["state"]}"}} {row["count"]}' for row in rows)
        lines.extend(
            [
                "# HELP citygap_job_runtime_seconds Completed durable job runtime.",
                "# TYPE citygap_job_runtime_seconds summary",
                "citygap_job_runtime_seconds_count " + str(runtime["completed_count"]),
                "citygap_job_runtime_seconds_sum " + str(runtime["runtime_seconds_sum"]),
                "# HELP citygap_dataset_versions Tenant dataset versions by lifecycle state.",
                "# TYPE citygap_dataset_versions gauge",
            ]
        )
        lines.extend(
            f'citygap_dataset_versions{{state="{row["state"]}"}} {row["count"]}' for row in datasets
        )
        return "\n".join(lines) + "\n"

    def service_health(self, organization_id: str) -> dict[str, Any]:
        process = self.readiness(None)
        database_ready = bool(process.get("ready"))
        worker = {"status": "unavailable", "last_seen_at": None, "worker_count": 0}
        required_datasets = {"status": "unavailable", "promoted_versions": 0}
        tile = {
            "status": "ready" if process.get("checks", {}).get("extensions") else "unavailable",
            "detail": "PostGIS and pgRouting query boundary",
        }
        if database_ready:
            with self._connect() as connection:
                connection.row_factory = dict_row
                heartbeat = (
                    self._one(
                        connection.execute(
                            """SELECT count(*) AS worker_count, max(last_seen_at) AS last_seen_at,
                                  COALESCE(EXTRACT(EPOCH FROM (now() - max(last_seen_at))), 1e12)
                                      AS age_seconds
                           FROM service_worker_heartbeats"""
                        )
                    )
                    or {}
                )
                threshold = int(os.getenv("CITYGAP_WORKER_HEALTH_SECONDS", "30"))
                worker = {
                    "status": (
                        "ready"
                        if heartbeat.get("last_seen_at")
                        and float(heartbeat["age_seconds"]) <= threshold
                        else "unavailable"
                    ),
                    "last_seen_at": heartbeat.get("last_seen_at"),
                    "worker_count": heartbeat.get("worker_count", 0),
                    "threshold_seconds": threshold,
                }
                promoted = self._one(
                    connection.execute(
                        """SELECT count(*) AS promoted_versions
                           FROM dataset_versions
                           WHERE organization_id = %s AND service_status = 'promoted'""",
                        (organization_id,),
                    )
                ) or {"promoted_versions": 0}
                required_datasets = {
                    "status": "ready" if promoted["promoted_versions"] else "unavailable",
                    **promoted,
                }
        storage_provider = os.getenv("CITYGAP_ATTACHMENT_STORAGE_PROVIDER", "local")
        if storage_provider == "local":
            attachment_path = Path(os.getenv("CITYGAP_ATTACHMENT_DIRECTORY", "var/attachments"))
            storage_ready = attachment_path.exists() and os.access(attachment_path, os.W_OK)
            storage_detail = str(attachment_path)
        else:
            storage_ready = bool(
                os.getenv("CITYGAP_S3_ENDPOINT") and os.getenv("CITYGAP_S3_BUCKET")
            )
            storage_detail = "S3-compatible provider configuration"
        dependencies = {
            "service": {"status": "ready"},
            "database": {"status": "ready" if database_ready else "unavailable"},
            "worker": worker,
            "object_storage": {
                "status": "ready" if storage_ready else "unavailable",
                "provider": storage_provider,
                "detail": storage_detail,
            },
            "required_datasets": required_datasets,
            "tile_service": tile,
        }
        required_statuses = [
            dependencies[key]["status"]
            for key in ("database", "worker", "object_storage", "tile_service")
        ]
        return {
            "status": "ready"
            if all(value == "ready" for value in required_statuses)
            else "degraded",
            "checked_at": datetime.now(UTC).isoformat(),
            "dependencies": dependencies,
            "process_readiness": process,
        }
