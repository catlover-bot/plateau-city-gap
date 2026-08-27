"""Validation contracts for claims, evidence and municipal review.

Validation status is deliberately a recorded governance decision.  Passing a
test or computing a comparison never promotes a claim automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ValidationStatus(StrEnum):
    UNVALIDATED = "unvalidated"
    INTERNALLY_VERIFIED = "internally_verified"
    CROSS_VALIDATED = "cross_validated"
    EXTERNALLY_VALIDATED = "externally_validated"
    MUNICIPALLY_REVIEWED = "municipally_reviewed"


class MunicipalFeedback(StrEnum):
    CONFIRMED = "confirmed"
    CONTRADICTED = "contradicted"
    PARTIALLY_SUPPORTED = "partially_supported"
    NEEDS_MORE_DATA = "needs_more_data"
    NOT_REVIEWED = "not_reviewed"


class EvidenceValue(StrEnum):
    YES = "YES"
    NO = "NO"
    NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass(frozen=True, slots=True)
class ClaimDefinition:
    claim_key: str
    what_it_means: str
    what_it_does_not_mean: str
    required_data: tuple[str, ...]
    validation_method: tuple[str, ...]
    current_validation_status: ValidationStatus


CLAIM_REGISTRY: tuple[ClaimDefinition, ...] = (
    ClaimDefinition(
        "building_population_allocation",
        "500m census totals are deterministically allocated to qualifying PLATEAU buildings under the stated capacity rule.",
        "It is not an observed household register or a person count for an individual building.",
        ("official_500m_census", "plateau_buildings", "building_use"),
        ("mass_conservation", "allocation_rule_sensitivity"),
        ValidationStatus.INTERNALLY_VERIFIED,
    ),
    ClaimDefinition(
        "building_euclidean_accessibility",
        "Straight-line separation from a building representative point to a versioned facility point is reproducible.",
        "It is not a walking route, travel time, entrance-to-entrance path, or proof of facility availability.",
        ("plateau_buildings", "public_facilities"),
        ("independent_geometry_certificate",),
        ValidationStatus.INTERNALLY_VERIFIED,
    ),
    ClaimDefinition(
        "experimental_network_accessibility",
        "A shortest path exists on the experimental PLATEAU LOD1 road-surface adjacency graph under its explicit topology rules.",
        "It is not an official or field-verified pedestrian route and does not encode all crossings, permissions, entrances, or one-way rules.",
        ("plateau_tran_lod1", "public_facilities", "reference_network"),
        ("shortest_path_certificate", "independent_reference_network_comparison"),
        ValidationStatus.CROSS_VALIDATED,
    ),
    ClaimDefinition(
        "hazard_stress_test",
        "Reachability changes are counterfactual results under a named edge-closure assumption.",
        "It is not a disaster probability, forecast, passability observation, or designation of a dangerous road.",
        ("network_version", "official_hazard_geometry", "closure_rule"),
        ("assumption_matrix", "rule_reproducibility"),
        ValidationStatus.INTERNALLY_VERIFIED,
    ),
    ClaimDefinition(
        "network_criticality",
        "Edges whose removal changes graph connectivity are review candidates under a stated graph model.",
        "It is not proof that a real road is critical, impassable, unsafe, or a priority for construction.",
        ("network_version", "building_snap", "demographic_estimates"),
        ("topology_sensitivity", "map_audit"),
        ValidationStatus.INTERNALLY_VERIFIED,
    ),
    ClaimDefinition(
        "future_population_allocation",
        "An official population series is allocated to buildings under a named fixed-service and capacity assumption.",
        "It is not a building-level forecast and does not choose a best official projection.",
        ("official_population_projection", "plateau_buildings", "allocation_rule"),
        ("allocation_rule_sensitivity", "official_series_comparison"),
        ValidationStatus.INTERNALLY_VERIFIED,
    ),
    ClaimDefinition(
        "scenario_improvement",
        "A scenario changes model metrics relative to the declared baseline under fixed assumptions.",
        "It is not an optimal policy, causal effect, budget estimate, implementation promise, or guaranteed real-world improvement.",
        ("urban_state", "scenario_definition", "algorithm_version"),
        ("canonical_replay", "assumption_comparison"),
        ValidationStatus.INTERNALLY_VERIFIED,
    ),
    ClaimDefinition(
        "planning_context",
        "PLATEAU planning and land-use attributes can be joined to model candidates for review.",
        "It is not a legal opinion, compliance decision, development permission, or statement of feasibility.",
        ("plateau_urf", "plateau_luse", "dataset_versions"),
        ("provenance_and_join_coverage",),
        ValidationStatus.INTERNALLY_VERIFIED,
    ),
    ClaimDefinition(
        "shelter_reachability",
        "A model path to a published shelter point is available under a named network and stress assumption.",
        "It is not confirmation that the shelter is open, suitable, reachable during an event, or assigned to that building.",
        ("published_shelters", "network_version", "stress_assumption"),
        ("network_comparison", "facility_availability_review"),
        ValidationStatus.UNVALIDATED,
    ),
)


EVIDENCE_DIMENSIONS = (
    "source_verified",
    "reproducible",
    "independent_verifier",
    "reference_model_agreement",
    "assumption_sensitive",
    "municipal_review",
    "field_verified",
)


UNCERTAINTY_CATEGORIES = (
    "data_coverage",
    "temporal_mismatch",
    "model_approximation",
    "network_semantics",
    "facility_availability",
    "scenario_assumption",
    "population_allocation",
    "optimization_approximation",
)


def claim_registry_payload() -> list[dict[str, Any]]:
    return [
        {
            "claim_key": claim.claim_key,
            "what_it_means": claim.what_it_means,
            "what_it_does_not_mean": claim.what_it_does_not_mean,
            "required_data": list(claim.required_data),
            "validation_method": list(claim.validation_method),
            "current_validation_status": claim.current_validation_status.value,
        }
        for claim in CLAIM_REGISTRY
    ]


def validate_evidence_strength(values: dict[str, str]) -> dict[str, str]:
    """Validate a non-aggregated YES/NO/NOT_AVAILABLE evidence matrix."""

    if set(values) != set(EVIDENCE_DIMENSIONS):
        raise ValueError("Evidence strength must declare every dimension exactly once")
    allowed = {value.value for value in EvidenceValue}
    if any(value not in allowed for value in values.values()):
        raise ValueError("Evidence strength accepts only YES, NO, or NOT_AVAILABLE")
    return dict(values)


def validation_priority_key(record: dict[str, Any]) -> tuple[Any, ...]:
    """Transparent lexicographic ordering; deliberately not a weighted score."""

    return (
        -int(record.get("connectivity_disagreement", False)),
        -int(record.get("reference_agreement") == "large_difference"),
        -int(record.get("assumption_sensitive", False)),
        -float(record.get("affected_population_estimate") or 0.0),
        -int(record.get("network_disconnected", False)),
        float(record.get("coverage") if record.get("coverage") is not None else 1.0),
        str(record.get("sample_id", "")),
    )

