"""Deterministic uncertainty-to-field-verification rules.

This module is intentionally closed: CITY GAP derives bounded evidence requests
from declared analysis limitations. It is not a form builder and never converts
field evidence into an administrative or policy decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

RULE_VERSION = "citygap-field-verification@1.0.0"


class VerificationKind(str, Enum):
    GTFS_SERVICE = "gtfs_service"
    WALKING_CONNECTIVITY = "walking_connectivity"
    FACILITY_AVAILABILITY = "facility_availability"
    PLATEAU_COVERAGE = "plateau_coverage"
    LOCAL_SERVICE_CONTEXT = "local_service_context"
    NETWORK_MODEL_DISAGREEMENT = "network_model_disagreement"
    TERRAIN_ACCESS = "terrain_access"


class VerificationTaskStatus(str, Enum):
    UNVERIFIED = "unverified"
    ASSIGNED = "assigned"
    IN_FIELD = "in_field"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    NEEDS_MORE_DATA = "needs_more_data"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TargetScope(str, Enum):
    MESH = "mesh"
    PLATEAU_OBJECT = "plateau_object"
    PLATEAU_OBJECT_GROUP = "plateau_object_group"


class TargetObjectType(str, Enum):
    MESH = "mesh"
    BUILDING = "building"
    ROAD = "road"
    TERRAIN = "terrain"
    LANDUSE = "landuse"
    PLANNING = "planning"
    HAZARD = "hazard"
    FACILITY = "facility"


class GpsCaptureState(str, Enum):
    CAPTURED = "captured"
    PERMISSION_DENIED = "permission_denied"
    UNAVAILABLE = "unavailable"
    NOT_ATTEMPTED = "not_attempted"


class FieldConclusion(str, Enum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    PARTIALLY_SUPPORTED = "partially_supported"
    NEEDS_MORE_DATA = "needs_more_data"
    NOT_ASSESSED = "not_assessed"


class MunicipalDisposition(str, Enum):
    CONTINUE_REVIEW = "continue_review"
    EXISTING_MEASURES = "existing_measures"
    OUT_OF_SCOPE = "out_of_scope"


class TaskPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class EvidenceRequirement:
    key: str
    label: str
    input_type: str
    required: bool = True
    relevant_when: str | None = None


@dataclass(frozen=True, slots=True)
class VerificationTemplate:
    kind: VerificationKind
    title: str
    reason: str
    priority: TaskPriority
    requirements: tuple[EvidenceRequirement, ...]


COMMON_PHOTOS = (
    EvidenceRequirement("close_photo", "対象の近景写真を記録する", "photo"),
    EvidenceRequirement("context_photo", "周辺を含む全景写真を記録する", "photo"),
)


TEMPLATES: dict[VerificationKind, VerificationTemplate] = {
    VerificationKind.GTFS_SERVICE: VerificationTemplate(
        VerificationKind.GTFS_SERVICE,
        "停留所と運行実態を確認",
        "公開位置データでは停留所の現存や運行状況を確認できないため。",
        TaskPriority.HIGH,
        (
            EvidenceRequirement("stop_present", "停留所が現地に存在するか", "choice"),
            EvidenceRequirement("service_notice", "運行案内を確認できるか", "choice"),
            *COMMON_PHOTOS,
            EvidenceRequirement(
                "removal_or_alternative",
                "撤去痕跡または代替位置を記録する",
                "text",
                relevant_when="stop_present=no",
            ),
        ),
    ),
    VerificationKind.WALKING_CONNECTIVITY: VerificationTemplate(
        VerificationKind.WALKING_CONNECTIVITY,
        "歩行経路の接続を確認",
        "直線距離では、実際に歩ける接続や横断・段差・通行止めを判断できないため。",
        TaskPriority.HIGH,
        (
            EvidenceRequirement("walkable", "対象経路を通行できるか", "choice"),
            EvidenceRequirement("barrier", "移動を妨げる条件があるか", "choice"),
            *COMMON_PHOTOS,
        ),
    ),
    VerificationKind.FACILITY_AVAILABILITY: VerificationTemplate(
        VerificationKind.FACILITY_AVAILABILITY,
        "施設の利用可能性を確認",
        "施設位置データだけでは営業・移転・入口の利用条件を判断できないため。",
        TaskPriority.HIGH,
        (
            EvidenceRequirement("facility_open", "施設が現在利用できるか", "choice"),
            EvidenceRequirement("entrance_access", "入口まで到達できるか", "choice"),
            *COMMON_PHOTOS,
            EvidenceRequirement(
                "closure_notice",
                "閉鎖掲示や移転先の手掛かりを記録する",
                "text",
                relevant_when="facility_open=no",
            ),
        ),
    ),
    VerificationKind.PLATEAU_COVERAGE: VerificationTemplate(
        VerificationKind.PLATEAU_COVERAGE,
        "PLATEAU収録外の現況を確認",
        "対象範囲にPLATEAUオブジェクトがなく、別地域の3Dで補えないため。",
        TaskPriority.MEDIUM,
        (
            EvidenceRequirement("representative_context", "メッシュ内の代表的な現況を確認する", "choice"),
            *COMMON_PHOTOS,
        ),
    ),
    VerificationKind.LOCAL_SERVICE_CONTEXT: VerificationTemplate(
        VerificationKind.LOCAL_SERVICE_CONTEXT,
        "地域サービスの実態を確認",
        "公開データにない送迎・移動販売・地域支援が判断を変える可能性があるため。",
        TaskPriority.MEDIUM,
        (
            EvidenceRequirement("service_present", "地域サービスが存在するか", "choice"),
            EvidenceRequirement("access_condition", "利用条件や対象者を記録する", "text"),
            *COMMON_PHOTOS,
        ),
    ),
    VerificationKind.NETWORK_MODEL_DISAGREEMENT: VerificationTemplate(
        VerificationKind.NETWORK_MODEL_DISAGREEMENT,
        "経路モデルとの差異を確認",
        "道路データ上の接続と実際の通行可否が一致するか判断できないため。",
        TaskPriority.HIGH,
        (
            EvidenceRequirement("route_connected", "対象道路が現地で接続しているか", "choice"),
            EvidenceRequirement("blocking_condition", "遮断条件を記録する", "text"),
            *COMMON_PHOTOS,
        ),
    ),
    VerificationKind.TERRAIN_ACCESS: VerificationTemplate(
        VerificationKind.TERRAIN_ACCESS,
        "勾配と歩行支援を確認",
        "PLATEAU地形から勾配の可能性は分かるが、現地の通行状態は判断できないため。",
        TaskPriority.HIGH,
        (
            EvidenceRequirement("steep_slope", "急な勾配があるか", "choice"),
            EvidenceRequirement("handrail_or_detour", "手すりや迂回路があるか", "choice"),
            *COMMON_PHOTOS,
            EvidenceRequirement(
                "slope_detail",
                "勾配状態を記録する",
                "text",
                relevant_when="steep_slope=yes",
            ),
        ),
    ),
}


TASK_TRANSITIONS: dict[VerificationTaskStatus, frozenset[VerificationTaskStatus]] = {
    VerificationTaskStatus.UNVERIFIED: frozenset(
        {VerificationTaskStatus.ASSIGNED, VerificationTaskStatus.CANCELLED}
    ),
    VerificationTaskStatus.ASSIGNED: frozenset(
        {VerificationTaskStatus.IN_FIELD, VerificationTaskStatus.CANCELLED}
    ),
    VerificationTaskStatus.IN_FIELD: frozenset(
        {VerificationTaskStatus.SUBMITTED, VerificationTaskStatus.CANCELLED}
    ),
    VerificationTaskStatus.SUBMITTED: frozenset({VerificationTaskStatus.UNDER_REVIEW}),
    VerificationTaskStatus.UNDER_REVIEW: frozenset(
        {VerificationTaskStatus.CLOSED, VerificationTaskStatus.NEEDS_MORE_DATA}
    ),
    VerificationTaskStatus.NEEDS_MORE_DATA: frozenset(
        {VerificationTaskStatus.ASSIGNED, VerificationTaskStatus.CANCELLED}
    ),
    VerificationTaskStatus.CLOSED: frozenset(),
    VerificationTaskStatus.CANCELLED: frozenset(),
}


def derive_template(kind: VerificationKind | str) -> VerificationTemplate:
    """Return the immutable rule snapshot for a supported uncertainty kind."""

    return TEMPLATES[VerificationKind(kind)]


def validate_task_transition(
    current: VerificationTaskStatus, proposed: VerificationTaskStatus
) -> None:
    if current == proposed or proposed not in TASK_TRANSITIONS[current]:
        raise ValueError(
            f"Invalid verification task transition: {current.value} -> {proposed.value}"
        )


def finding_field_validation(conclusion: FieldConclusion) -> str | None:
    return {
        FieldConclusion.SUPPORTED: "supported_by_field",
        FieldConclusion.CONTRADICTED: "contradicted_by_field",
        FieldConclusion.PARTIALLY_SUPPORTED: "partially_supported",
        FieldConclusion.NEEDS_MORE_DATA: "needs_more_data",
        FieldConclusion.NOT_ASSESSED: None,
    }[conclusion]


def review_task_status(
    conclusion: FieldConclusion, disposition: MunicipalDisposition
) -> VerificationTaskStatus:
    if disposition in {
        MunicipalDisposition.EXISTING_MEASURES,
        MunicipalDisposition.OUT_OF_SCOPE,
    }:
        return VerificationTaskStatus.CLOSED
    if conclusion is FieldConclusion.NEEDS_MORE_DATA:
        return VerificationTaskStatus.NEEDS_MORE_DATA
    return VerificationTaskStatus.CLOSED


def automatic_confirmation_allowed() -> bool:
    return False
