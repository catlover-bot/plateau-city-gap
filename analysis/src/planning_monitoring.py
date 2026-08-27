"""Deterministic planning-context monitoring without legal-compliance claims."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

REVIEW_LABEL = "planning-context mismatch candidate"


@dataclass(frozen=True, slots=True)
class PlanningContextComparison:
    comparison_key: str
    planning_designation: str
    building_count: int
    building_use_composition: dict[str, int]
    estimated_population: float
    estimated_elderly_population: float
    candidate_label: str = REVIEW_LABEL
    legal_compliance_claimed: bool = False

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def compare_planning_context(
    demographics: pd.DataFrame,
    building_context: pd.DataFrame,
    *,
    planning_type: str = "UseDistrict",
) -> tuple[PlanningContextComparison, ...]:
    """Aggregate current building use/demographics by a PLATEAU designation.

    Every designation is a reviewable observation. The function deliberately has no
    zoning rule matrix and never infers a violation, illegality or non-conformance.
    """

    demographic_columns = {
        "gml_id",
        "residential_class",
        "estimated_population",
        "estimated_elderly_population",
    }
    context_columns = {"gml_id", "context_type", "planning_type", "planning_label"}
    missing_demographic = demographic_columns - set(demographics.columns)
    missing_context = context_columns - set(building_context.columns)
    if missing_demographic or missing_context:
        raise ValueError(
            "Planning comparison input is missing required columns: "
            f"demographics={sorted(missing_demographic)}, context={sorted(missing_context)}"
        )

    planning = building_context.loc[
        building_context["context_type"].eq("planning")
        & building_context["planning_type"].eq(planning_type)
        & building_context["planning_label"].notna(),
        ["gml_id", "planning_label"],
    ].copy()
    planning["planning_label"] = planning["planning_label"].astype(str).str.strip()
    planning = planning.loc[planning["planning_label"].ne("")].drop_duplicates()
    demographic = demographics[list(demographic_columns)].copy()
    for column in ("estimated_population", "estimated_elderly_population"):
        demographic[column] = pd.to_numeric(demographic[column], errors="coerce")
        if demographic[column].isna().any() or demographic[column].lt(0).any():
            raise ValueError("Planning comparison demographics must be finite and non-negative")
    demographic = (
        demographic.groupby(["gml_id", "residential_class"], as_index=False)
        .agg(
            estimated_population=("estimated_population", "sum"),
            estimated_elderly_population=("estimated_elderly_population", "sum"),
        )
    )
    merged = planning.merge(demographic, on="gml_id", how="left", validate="many_to_many")
    merged["residential_class"] = merged["residential_class"].fillna("unallocated")
    merged[["estimated_population", "estimated_elderly_population"]] = merged[
        ["estimated_population", "estimated_elderly_population"]
    ].fillna(0.0)

    comparisons: list[PlanningContextComparison] = []
    for designation, group in merged.groupby("planning_label", sort=True):
        composition = (
            group.drop_duplicates(["gml_id", "residential_class"])["residential_class"]
            .value_counts()
            .sort_index()
            .astype(int)
            .to_dict()
        )
        population_rows = group.drop_duplicates(["gml_id", "residential_class"])
        comparison_key = f"{planning_type}:{designation}"
        comparisons.append(
            PlanningContextComparison(
                comparison_key=comparison_key,
                planning_designation=str(designation),
                building_count=int(group["gml_id"].nunique()),
                building_use_composition=composition,
                estimated_population=float(population_rows["estimated_population"].sum()),
                estimated_elderly_population=float(
                    population_rows["estimated_elderly_population"].sum()
                ),
            )
        )
    return tuple(comparisons)
