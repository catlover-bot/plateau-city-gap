"""Tenant-scoped persistence for the municipal urban intelligence service.

Every public method takes ``organization_id`` first.  This is intentional: a new
query cannot accidentally become tenant-global, and object identifiers are never
treated as authorization by themselves.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
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
                    """SELECT dataset.dataset_key, dataset.title, version.id AS version_id,
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
            if before["investigation_id"]:
                next_investigation_status = {
                    "reviewed": "decision_pending",
                    "changes_requested": "open",
                }.get(proposed_status)
                if next_investigation_status:
                    connection.execute(
                        """UPDATE investigations SET status = %s
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
            if investigation["status"] != "in_review":
                validate_investigation_transition(
                    InvestigationStatus(investigation["status"]),
                    InvestigationStatus.IN_REVIEW,
                )
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
            return {
                "investigation": investigation,
                "findings": findings,
                "entities": entities,
                "reviews": reviews,
                "field_observations": field_observations,
                "decisions": decisions,
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
            return self._one(
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
                        payload.get("attachment_ids", []),
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
                        payload["related_evidence_ids"],
                        payload.get("official_approval_reference"),
                    ),
                )
            )
            assert result is not None
            connection.execute(
                "UPDATE investigations SET status = 'closed', updated_at = now() WHERE id = %s",
                (investigation_id,),
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
                    """SELECT dataset.id AS dataset_id, dataset.dataset_key, dataset.title,
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
            return {
                "city": city,
                "datasets": datasets,
                "quality_checks": quality,
                "plateau_model": plateau_model,
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
        with self._connect() as connection:
            connection.row_factory = dict_row
            city = self._city(connection, organization_id, city_reference)
            if city is None:
                return None
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
                        payload.get("investigation_id"),
                        payload.get("scenario_run_id"),
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

    def service_health(self) -> dict[str, Any]:
        detail = self.readiness(None)
        return {
            "status": "ready" if detail["ready"] else "degraded",
            "checked_at": datetime.now(UTC).isoformat(),
            "dependencies": detail,
        }
