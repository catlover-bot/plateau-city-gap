"""Municipal service domain rules shared by the API, worker and tests.

The module deliberately contains no optimizer-to-decision shortcut.  Findings are
review candidates, reviews are not administrative approvals, and decisions require
an explicit human actor.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

SERVICE_ENTITIES = (
    "Organization",
    "Tenant",
    "User",
    "Role",
    "City",
    "Workspace",
    "Dataset",
    "DatasetVersion",
    "UrbanState",
    "AnalysisRun",
    "Finding",
    "Investigation",
    "Scenario",
    "ScenarioComparison",
    "StressTest",
    "Review",
    "FieldObservation",
    "DecisionRecord",
    "ImplementationRecord",
    "EvidencePackage",
    "ValidationRun",
    "Job",
    "AuditEvent",
)


class ProductRole(str, Enum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    PLANNER = "planner"
    FIELD_STAFF = "field_staff"
    DATA_MANAGER = "data_manager"
    ADMINISTRATOR = "administrator"


class DataClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"


class FindingType(str, Enum):
    ACCESSIBILITY_GAP = "accessibility_gap"
    NETWORK_CRITICALITY = "network_criticality"
    PLANNING_CONTEXT = "planning_context"
    TEMPORAL_CHANGE = "temporal_change"
    RESILIENCE_IMPACT = "resilience_impact"
    DATA_QUALITY_ISSUE = "data_quality_issue"


class FindingStatus(str, Enum):
    NEW = "new"
    TRIAGED = "triaged"
    INVESTIGATING = "investigating"
    REVIEW_REQUIRED = "review_required"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    ARCHIVED = "archived"


class InvestigationStatus(str, Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    FIELD_CHECK = "field_check"
    DECISION_PENDING = "decision_pending"
    CLOSED = "closed"
    ARCHIVED = "archived"


class ReviewStatus(str, Enum):
    REQUESTED = "requested"
    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    REVIEWED = "reviewed"


class DecisionValue(str, Enum):
    ADOPTED = "adopted"
    ON_HOLD = "on_hold"
    REJECTED = "rejected"
    ADDITIONAL_INVESTIGATION = "additional_investigation"


class DatasetReleaseStatus(str, Enum):
    REGISTERED = "registered"
    VALIDATING = "validating"
    VALIDATED = "validated"
    ACCEPTED = "accepted"
    INGESTING = "ingesting"
    ANALYSIS_READY = "analysis_ready"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    FAILED = "failed"


FINDING_TRANSITIONS: dict[FindingStatus, frozenset[FindingStatus]] = {
    FindingStatus.NEW: frozenset(
        {FindingStatus.TRIAGED, FindingStatus.DISMISSED, FindingStatus.ARCHIVED}
    ),
    FindingStatus.TRIAGED: frozenset(
        {FindingStatus.INVESTIGATING, FindingStatus.DISMISSED, FindingStatus.ARCHIVED}
    ),
    FindingStatus.INVESTIGATING: frozenset(
        {
            FindingStatus.REVIEW_REQUIRED,
            FindingStatus.RESOLVED,
            FindingStatus.DISMISSED,
            FindingStatus.ARCHIVED,
        }
    ),
    FindingStatus.REVIEW_REQUIRED: frozenset(
        {
            FindingStatus.INVESTIGATING,
            FindingStatus.RESOLVED,
            FindingStatus.DISMISSED,
            FindingStatus.ARCHIVED,
        }
    ),
    FindingStatus.RESOLVED: frozenset({FindingStatus.INVESTIGATING, FindingStatus.ARCHIVED}),
    FindingStatus.DISMISSED: frozenset({FindingStatus.INVESTIGATING, FindingStatus.ARCHIVED}),
    FindingStatus.ARCHIVED: frozenset(),
}

REVIEW_TRANSITIONS: dict[ReviewStatus, frozenset[ReviewStatus]] = {
    ReviewStatus.REQUESTED: frozenset({ReviewStatus.IN_REVIEW}),
    ReviewStatus.IN_REVIEW: frozenset({ReviewStatus.CHANGES_REQUESTED, ReviewStatus.REVIEWED}),
    ReviewStatus.CHANGES_REQUESTED: frozenset({ReviewStatus.IN_REVIEW}),
    ReviewStatus.REVIEWED: frozenset(),
}

DATASET_TRANSITIONS: dict[DatasetReleaseStatus, frozenset[DatasetReleaseStatus]] = {
    DatasetReleaseStatus.REGISTERED: frozenset(
        {DatasetReleaseStatus.VALIDATING, DatasetReleaseStatus.REJECTED}
    ),
    DatasetReleaseStatus.VALIDATING: frozenset(
        {DatasetReleaseStatus.VALIDATED, DatasetReleaseStatus.FAILED}
    ),
    DatasetReleaseStatus.VALIDATED: frozenset(
        {DatasetReleaseStatus.ACCEPTED, DatasetReleaseStatus.REJECTED}
    ),
    DatasetReleaseStatus.ACCEPTED: frozenset({DatasetReleaseStatus.INGESTING}),
    DatasetReleaseStatus.INGESTING: frozenset(
        {DatasetReleaseStatus.ANALYSIS_READY, DatasetReleaseStatus.FAILED}
    ),
    DatasetReleaseStatus.ANALYSIS_READY: frozenset({DatasetReleaseStatus.PROMOTED}),
    DatasetReleaseStatus.PROMOTED: frozenset(),
    DatasetReleaseStatus.REJECTED: frozenset({DatasetReleaseStatus.VALIDATING}),
    DatasetReleaseStatus.FAILED: frozenset({DatasetReleaseStatus.VALIDATING}),
}

INVESTIGATION_TRANSITIONS: dict[InvestigationStatus, frozenset[InvestigationStatus]] = {
    InvestigationStatus.OPEN: frozenset(
        {
            InvestigationStatus.IN_REVIEW,
            InvestigationStatus.FIELD_CHECK,
            InvestigationStatus.ARCHIVED,
        }
    ),
    InvestigationStatus.IN_REVIEW: frozenset(
        {
            InvestigationStatus.OPEN,
            InvestigationStatus.FIELD_CHECK,
            InvestigationStatus.DECISION_PENDING,
        }
    ),
    InvestigationStatus.FIELD_CHECK: frozenset(
        {
            InvestigationStatus.OPEN,
            InvestigationStatus.IN_REVIEW,
            InvestigationStatus.DECISION_PENDING,
        }
    ),
    InvestigationStatus.DECISION_PENDING: frozenset(
        {
            InvestigationStatus.IN_REVIEW,
            InvestigationStatus.FIELD_CHECK,
            InvestigationStatus.CLOSED,
        }
    ),
    InvestigationStatus.CLOSED: frozenset({InvestigationStatus.OPEN, InvestigationStatus.ARCHIVED}),
    InvestigationStatus.ARCHIVED: frozenset(),
}


def _validate_transition(
    current: Enum, proposed: Enum, allowed: dict[Enum, frozenset[Enum]]
) -> None:
    if current == proposed:
        raise ValueError("A lifecycle transition must change status")
    if proposed not in allowed[current]:
        raise ValueError(f"Invalid lifecycle transition: {current.value} -> {proposed.value}")


def validate_finding_transition(current: FindingStatus, proposed: FindingStatus) -> None:
    _validate_transition(current, proposed, FINDING_TRANSITIONS)


def validate_review_transition(current: ReviewStatus, proposed: ReviewStatus) -> None:
    _validate_transition(current, proposed, REVIEW_TRANSITIONS)


def validate_dataset_transition(
    current: DatasetReleaseStatus, proposed: DatasetReleaseStatus
) -> None:
    _validate_transition(current, proposed, DATASET_TRANSITIONS)


def validate_investigation_transition(
    current: InvestigationStatus, proposed: InvestigationStatus
) -> None:
    _validate_transition(current, proposed, INVESTIGATION_TRANSITIONS)


@dataclass(frozen=True, slots=True)
class ParameterDefinition:
    key: str
    value_type: str
    description: str
    default: int | float | str | bool
    minimum: int | float | None = None
    maximum: int | float | None = None


@dataclass(frozen=True, slots=True)
class AnalysisDefinition:
    analysis_id: str
    name: str
    purpose: str
    required_capabilities: tuple[str, ...]
    algorithm_version: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    parameters: tuple[ParameterDefinition, ...]
    claim_boundary: str


ANALYSIS_CATALOG = (
    AnalysisDefinition(
        "accessibility-gap",
        "生活サービスへのアクセス候補抽出",
        "500mメッシュ単位で追加調査候補を抽出する",
        ("screening", "building_detail"),
        "city-gap-screening-v1",
        ("urban_state", "population", "facilities", "plateau_buildings"),
        ("findings", "mesh_metrics"),
        (ParameterDefinition("candidate_limit", "integer", "表示する候補数", 10, 1, 100),),
        "候補は政策上の問題認定、危険度、優先順位ではない。",
    ),
    AnalysisDefinition(
        "building-accessibility",
        "建物アクセシビリティ",
        "PLATEAU建物を起点に施設へのモデル距離を確認する",
        ("building_detail",),
        "building-accessibility-v2",
        ("plateau_buildings", "facilities"),
        ("building_accessibility_metrics",),
        (),
        "建物別推計人口は観測値ではなく、公開出力へ含めない。",
    ),
    AnalysisDefinition(
        "network-criticality",
        "道路ネットワーク確認候補",
        "道路graph上で接続性の確認候補を抽出する",
        ("road_network",),
        "network-criticality-v1",
        ("network_version", "building_snap"),
        ("criticality_findings",),
        (),
        "道路の危険性、行政上の重要度、実際の通行可否を断定しない。",
    ),
    AnalysisDefinition(
        "stress-test",
        "仮定条件によるStress Test",
        "明示した利用不可仮定の下でサービス継続性を比較する",
        ("road_network", "hazard"),
        "stress-test-v1",
        ("network_version", "closure_assumptions"),
        ("stress_test_result",),
        (),
        "災害予測や実際の通行止めではない。",
    ),
    AnalysisDefinition(
        "future-accessibility",
        "将来人口シナリオ比較",
        "公式人口シナリオを固定サービス仮定の下で比較する",
        ("future_population", "scenario"),
        "future-accessibility-v1",
        ("future_urban_state", "fixed_service_assumption"),
        ("future_accessibility_metrics",),
        (),
        "建物別人口予測や最良シナリオの選定ではない。",
    ),
    AnalysisDefinition(
        "temporal-diff",
        "年度差分",
        "version間の追加・削除・形状・属性差分を再現可能に分類する",
        ("temporal_diff",),
        "temporal-diff-v1",
        ("from_dataset_version", "to_dataset_version"),
        ("change_set", "impacted_analyses"),
        (),
        "source仕様変更が都市変化として現れる可能性をEvidenceへ残す。",
    ),
)


@dataclass(frozen=True, slots=True)
class DecisionRecordDraft:
    decision: DecisionValue
    reason: str
    actor: str
    review_status: ReviewStatus
    related_evidence_ids: tuple[str, ...]
    source: str = "human_entry"

    def validate(self) -> None:
        if self.source != "human_entry":
            raise ValueError("Decision Records must be created by an explicit human action")
        if not self.actor.strip() or not self.reason.strip():
            raise ValueError("Decision Records require an actor and reason")
        if self.review_status is not ReviewStatus.REVIEWED:
            raise ValueError("Decision Records require a completed review")
        if not self.related_evidence_ids:
            raise ValueError("Decision Records require related evidence")


def encode_cursor(values: dict[str, Any]) -> str:
    payload = json.dumps(values, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        padding = "=" * (-len(value) % 4)
        result = json.loads(base64.urlsafe_b64decode(value + padding))
    except (ValueError, json.JSONDecodeError) as error:
        raise ValueError("Invalid pagination cursor") from error
    if not isinstance(result, dict) or not result:
        raise ValueError("Invalid pagination cursor")
    return result
