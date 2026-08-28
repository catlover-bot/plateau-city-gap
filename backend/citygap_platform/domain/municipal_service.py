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
    "OpenDataAdapter",
    "OpenDataSource",
    "DataCoverage",
    "CanonicalOpenDataRecord",
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
    CARE_ACCESS_REVIEW_CANDIDATE = "care_access_review_candidate"
    ACTIVITY_SERVICE_GAP_CANDIDATE = "activity_service_gap_candidate"
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


class DatasetRequirementLevel(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    ENHANCEMENT = "enhancement"


class AnalysisTier(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    BASE = "BASE"
    ENHANCED = "ENHANCED"


@dataclass(frozen=True, slots=True)
class DatasetRequirement:
    dataset_family: str
    level: DatasetRequirementLevel
    selection_rule: str


@dataclass(frozen=True, slots=True)
class AnalysisTierEvaluation:
    tier: AnalysisTier
    missing_required: tuple[str, ...]
    missing_optional: tuple[str, ...]
    missing_enhancement: tuple[str, ...]


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
    dataset_requirements: tuple[DatasetRequirement, ...] = ()


def evaluate_analysis_tier(
    definition: AnalysisDefinition, available_dataset_families: set[str] | frozenset[str]
) -> AnalysisTierEvaluation:
    """Evaluate availability without converting optional context into a hard dependency."""

    missing = {
        level: tuple(
            requirement.dataset_family
            for requirement in definition.dataset_requirements
            if requirement.level is level
            and requirement.dataset_family not in available_dataset_families
        )
        for level in DatasetRequirementLevel
    }
    has_enhancement = any(
        requirement.level is DatasetRequirementLevel.ENHANCEMENT
        for requirement in definition.dataset_requirements
    )
    if missing[DatasetRequirementLevel.REQUIRED]:
        tier = AnalysisTier.UNAVAILABLE
    elif has_enhancement and not missing[DatasetRequirementLevel.ENHANCEMENT]:
        tier = AnalysisTier.ENHANCED
    else:
        tier = AnalysisTier.BASE
    return AnalysisTierEvaluation(
        tier=tier,
        missing_required=missing[DatasetRequirementLevel.REQUIRED],
        missing_optional=missing[DatasetRequirementLevel.OPTIONAL],
        missing_enhancement=missing[DatasetRequirementLevel.ENHANCEMENT],
    )


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
    AnalysisDefinition(
        "medical-access-v2",
        "Medical Access V2",
        "公式医療機関点と500mメッシュの距離文脈を追加調査候補として確認する",
        ("screening", "medical"),
        "medical-access-v2.0.0",
        ("urban_state", "population_500m", "mhlw_medical_facilities"),
        ("medical_access_context", "findings"),
        (),
        "直線距離は到達時間、診療可否、受入能力、医療不足、政策優先順位ではない。",
        (
            DatasetRequirement(
                "census_population_500m",
                DatasetRequirementLevel.REQUIRED,
                "latest promoted official 500m census mesh",
            ),
            DatasetRequirement(
                "mhlw_medical",
                DatasetRequirementLevel.REQUIRED,
                "latest promoted official medical-facility release",
            ),
            DatasetRequirement(
                "plateau_buildings",
                DatasetRequirementLevel.OPTIONAL,
                "current validated PLATEAU building version",
            ),
            DatasetRequirement(
                "road_network",
                DatasetRequirementLevel.OPTIONAL,
                "current experimental graph kept as a separate metric",
            ),
            DatasetRequirement(
                "official_pedestrian_network",
                DatasetRequirementLevel.ENHANCEMENT,
                "official pedestrian network covering the audited city",
            ),
        ),
    ),
    AnalysisDefinition(
        "care-access",
        "Care Access",
        "高齢者人口、公式介護事業所、PLATEAU空間文脈から現地確認候補を抽出する",
        ("screening", "building_detail", "care"),
        "care-access-1.0.0",
        ("urban_state", "elderly_population_500m", "mhlw_care_facilities", "plateau_buildings"),
        ("care_access_context", "care_access_review_candidate"),
        (),
        "候補は介護不足、需要、利用資格、空床、政策優先順位の認定ではない。",
        (
            DatasetRequirement(
                "census_elderly_population_500m",
                DatasetRequirementLevel.REQUIRED,
                "official disclosed 2020 elderly population mesh",
            ),
            DatasetRequirement(
                "mhlw_care",
                DatasetRequirementLevel.REQUIRED,
                "latest promoted official care-establishment release",
            ),
            DatasetRequirement(
                "plateau_buildings",
                DatasetRequirementLevel.REQUIRED,
                "current validated PLATEAU building version",
            ),
            DatasetRequirement(
                "road_network",
                DatasetRequirementLevel.OPTIONAL,
                "current experimental graph kept as a separate metric",
            ),
            DatasetRequirement(
                "official_pedestrian_network",
                DatasetRequirementLevel.ENHANCEMENT,
                "official pedestrian network covering the audited city",
            ),
            DatasetRequirement(
                "social_participation",
                DatasetRequirementLevel.ENHANCEMENT,
                "official participation data with documented spatial and temporal coverage",
            ),
        ),
    ),
    AnalysisDefinition(
        "future-population-spatial",
        "将来公式人口の空間比較",
        "公式250m将来人口系列を500mメッシュへ決定論的に集約して年度間を比較する",
        ("screening", "future_population"),
        "future-population-spatial-1.0.0",
        ("urban_state", "mlit_future_population_250m"),
        ("future_population_mesh_context",),
        (),
        "公式試算は観測値や保証された予測ではなく、最良シナリオを自動選択しない。",
        (
            DatasetRequirement(
                "mlit_future_population_250m",
                DatasetRequirementLevel.REQUIRED,
                "official R6 trial projection series",
            ),
            DatasetRequirement(
                "census_population_500m",
                DatasetRequirementLevel.REQUIRED,
                "official observed mesh context kept temporally separate",
            ),
            DatasetRequirement(
                "plateau_buildings",
                DatasetRequirementLevel.OPTIONAL,
                "current validated PLATEAU building version",
            ),
        ),
    ),
    AnalysisDefinition(
        "daytime-activity-context",
        "Daytime Activity Context",
        "事業所・従業者集積をサービス到達文脈と別々の指標で確認する",
        ("screening", "economic_activity"),
        "daytime-activity-context-1.0.0",
        ("economic_census_500m", "urban_state"),
        ("activity_service_context", "activity_service_gap_candidate"),
        (),
        "従業者数は昼間人口、サービス需要、混雑、政策上の不足を意味しない。",
        (
            DatasetRequirement(
                "economic_census_500m",
                DatasetRequirementLevel.REQUIRED,
                "latest promoted official economic-census mesh",
            ),
            DatasetRequirement(
                "mhlw_medical",
                DatasetRequirementLevel.OPTIONAL,
                "latest promoted medical-facility release",
            ),
            DatasetRequirement(
                "transport_points",
                DatasetRequirementLevel.OPTIONAL,
                "promoted official transport-point dataset",
            ),
            DatasetRequirement(
                "official_pedestrian_network",
                DatasetRequirementLevel.ENHANCEMENT,
                "official pedestrian network covering the audited city",
            ),
        ),
    ),
    AnalysisDefinition(
        "earthquake-ground-context",
        "Earthquake / Ground Context",
        "J-SHIS表層地盤モデルを監査対象500mメッシュへ集約する",
        ("screening", "ground"),
        "earthquake-ground-context-1.0.0",
        ("jshis_ground_250m", "urban_state"),
        ("ground_context",),
        (),
        "地盤モデル値は地震確率、被害予測、危険度、政策リスクスコアではない。",
        (
            DatasetRequirement(
                "jshis_surface_ground",
                DatasetRequirementLevel.REQUIRED,
                "published V4 250m surface-ground model",
            ),
            DatasetRequirement(
                "plateau_buildings",
                DatasetRequirementLevel.OPTIONAL,
                "current validated PLATEAU building version",
            ),
        ),
    ),
    AnalysisDefinition(
        "historical-traffic-safety-context",
        "Historical Traffic Safety Context",
        "人身事故履歴を500mメッシュで集計し現地調査の文脈として表示する",
        ("screening", "traffic_accident"),
        "historical-traffic-safety-context-1.0.0",
        ("npa_historical_accidents", "urban_state"),
        ("historical_accident_context",),
        (),
        "事故件数は交通量で正規化しておらず、現在の危険度、原因、確率、予測ではない。",
        (
            DatasetRequirement(
                "npa_traffic_accident",
                DatasetRequirementLevel.REQUIRED,
                "latest promoted complete official annual injury/fatal accident file",
            ),
            DatasetRequirement(
                "road_network",
                DatasetRequirementLevel.OPTIONAL,
                "current experimental graph, without identity conflation",
            ),
            DatasetRequirement(
                "traffic_volume",
                DatasetRequirementLevel.ENHANCEMENT,
                "official stable traffic-volume denominator with matching coverage",
            ),
        ),
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
