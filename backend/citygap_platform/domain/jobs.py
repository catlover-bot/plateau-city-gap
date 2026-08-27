"""Stage-based job state machine; percentages are intentionally absent."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

JOB_STAGES = {
    "plateau_ingestion": (
        "validate_source",
        "inventory_members",
        "parse_citygml",
        "persist_features",
        "verify_counts",
    ),
    "building_demographics": (
        "audit_attributes",
        "map_usage_codes",
        "crosswalk_meshes",
        "allocate_demographics",
        "verify_conservation",
        "persist_artifacts",
    ),
    "road_network": (
        "parse_road_surfaces",
        "build_topology",
        "connect_demand",
        "verify_network",
        "persist_artifacts",
    ),
    "network_generation": (
        "parse_road_surfaces",
        "build_topology",
        "connect_demand",
        "verify_network",
        "persist_artifacts",
    ),
    "terrain": (
        "parse_dem",
        "sample_network_nodes",
        "summarize_routes",
        "verify_terrain",
        "persist_artifacts",
    ),
    "terrain_enrichment": (
        "parse_dem",
        "sample_network_nodes",
        "summarize_routes",
        "verify_terrain",
        "persist_artifacts",
    ),
    "spatial_context": (
        "parse_context_features",
        "spatial_join",
        "verify_context",
        "persist_artifacts",
    ),
    "scenario_optimization": (
        "prepare_candidates",
        "build_sparse_matrix",
        "optimize_objectives",
        "independent_verification",
        "persist_artifacts",
    ),
    "context_generation": (
        "parse_context_features",
        "spatial_join",
        "verify_context",
        "persist_artifacts",
    ),
    "evidence_export": (
        "collect_provenance",
        "render_package",
        "verify_artifacts",
        "persist_artifacts",
    ),
    "dataset_diff": (
        "validate_versions",
        "fingerprint_features",
        "match_features",
        "classify_changes",
        "plan_recomputation",
        "persist_artifacts",
    ),
    "incremental_recompute": (
        "load_plan",
        "execute_scopes",
        "verify_against_full_rebuild",
        "persist_artifacts",
    ),
    "future_population": (
        "validate_official_source",
        "create_urban_states",
        "allocate_residential_capacity",
        "calculate_fixed_service_accessibility",
        "quality_gate",
        "persist_artifacts",
    ),
    "stress_test": (
        "validate_explicit_assumption",
        "load_graph_precomputation",
        "apply_counterfactual_closures",
        "calculate_service_continuity",
        "independent_verification",
        "persist_artifacts",
    ),
    "criticality_analysis": (
        "load_graph_precomputation",
        "detect_bridge_candidates",
        "aggregate_demand_and_services",
        "selected_removal_verification",
        "persist_artifacts",
    ),
    "outcome_evaluation": (
        "validate_baseline_and_observed_states",
        "separate_planned_effect_and_observed_change",
        "calculate_structured_metrics",
        "enforce_human_review_boundary",
        "persist_artifacts",
    ),
    "validation_run": (
        "validate_claim_and_versions",
        "select_deterministic_samples",
        "run_primary_and_reference_models",
        "classify_disagreements",
        "verify_evidence",
        "persist_artifacts",
    ),
    "validation_reproduce": (
        "verify_source_manifest",
        "verify_data_hashes",
        "run_validation",
        "compare_summary_hashes",
        "persist_artifacts",
    ),
    "pilot_rehearsal": (
        "verify_public_inputs",
        "rehearse_workflow",
        "classify_external_blocks",
        "verify_evidence",
        "persist_artifacts",
    ),
}


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class JobSnapshot:
    job_type: str
    state: JobState = JobState.QUEUED
    current_stage: str | None = None
    completed_stages: tuple[str, ...] = ()
    error: str | None = None

    def __post_init__(self) -> None:
        if self.job_type not in JOB_STAGES:
            raise ValueError(f"Unknown job type: {self.job_type}")


def start_job(snapshot: JobSnapshot) -> JobSnapshot:
    if snapshot.state is not JobState.QUEUED:
        raise ValueError("Only a queued job can start")
    return replace(snapshot, state=JobState.RUNNING, current_stage=JOB_STAGES[snapshot.job_type][0])


def advance_job(snapshot: JobSnapshot, next_stage: str) -> JobSnapshot:
    if snapshot.state is not JobState.RUNNING or snapshot.current_stage is None:
        raise ValueError("Only a running job can advance")
    stages = JOB_STAGES[snapshot.job_type]
    current_index = stages.index(snapshot.current_stage)
    if current_index + 1 >= len(stages) or stages[current_index + 1] != next_stage:
        raise ValueError("Job stages must advance in the declared order")
    return replace(
        snapshot,
        current_stage=next_stage,
        completed_stages=(*snapshot.completed_stages, snapshot.current_stage),
    )


def succeed_job(snapshot: JobSnapshot) -> JobSnapshot:
    stages = JOB_STAGES[snapshot.job_type]
    if snapshot.state is not JobState.RUNNING or snapshot.current_stage != stages[-1]:
        raise ValueError("A job can succeed only from its final real stage")
    return replace(
        snapshot,
        state=JobState.SUCCEEDED,
        current_stage=None,
        completed_stages=(*snapshot.completed_stages, stages[-1]),
    )


def fail_job(snapshot: JobSnapshot, error: str) -> JobSnapshot:
    if snapshot.state is not JobState.RUNNING:
        raise ValueError("Only a running job can fail")
    message = error.strip()
    if not message:
        raise ValueError("A failed job requires an error message")
    return replace(snapshot, state=JobState.FAILED, current_stage=None, error=message)
