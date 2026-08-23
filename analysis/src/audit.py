"""Reusable data-quality helpers for the final CITY GAP audit."""

from __future__ import annotations

import re
from collections.abc import Iterable

import pandas as pd

UNCERTAIN_ACCESS_TERMS = (
    "健康管理室",
    "事業所診療所",
    "社内診療所",
    "職員診療所",
    "医務室",
)

INSTITUTION_TERMS = (
    "株式会社",
    "（株）",
    "(株)",
    "工場",
    "事業所",
    "製作所",
    "銀行",
    "大学",
    "警察",
    "自衛隊",
)


def normalize_facility_name(value: object) -> str:
    """Normalize whitespace without altering the official facility name."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def medical_access_class(
    name: object,
    *,
    confirmed_public_names: Iterable[str] = (),
) -> tuple[str, str | None]:
    """Classify access confidence without deleting a P04 facility.

    The P04 category says whether a record is a hospital or clinic, not whether
    any resident can use it. Name-based rules therefore only flag uncertainty.
    A facility becomes ``confirmed_public`` solely through an explicit reviewed
    evidence list.
    """
    normalized = normalize_facility_name(name)
    confirmed = {normalize_facility_name(value) for value in confirmed_public_names}
    if normalized in confirmed:
        return "confirmed_public", None
    for term in UNCERTAIN_ACCESS_TERMS:
        if term in normalized:
            return "uncertain_access", f"name_contains:{term}"
    if "健康管理センター" in normalized and any(
        term in normalized for term in INSTITUTION_TERMS
    ):
        return "uncertain_access", "institutional_health_management_center"
    return "likely_public", None


def classify_medical_access(
    names: pd.Series,
    *,
    confirmed_public_names: Iterable[str] = (),
) -> pd.DataFrame:
    """Return access class and audit reason for each official P04 name."""
    classified = [
        medical_access_class(value, confirmed_public_names=confirmed_public_names)
        for value in names
    ]
    return pd.DataFrame(
        {
            "medical_access_class": [value[0] for value in classified],
            "medical_access_reason": [value[1] for value in classified],
        },
        index=names.index,
    )


def rank_correlation(left: pd.Series, right: pd.Series) -> float:
    """Spearman correlation without requiring SciPy."""
    paired = pd.concat(
        [pd.to_numeric(left, errors="coerce"), pd.to_numeric(right, errors="coerce")],
        axis=1,
    ).dropna()
    if len(paired) < 2:
        return float("nan")
    left_rank = paired.iloc[:, 0].rank(method="average")
    right_rank = paired.iloc[:, 1].rank(method="average")
    return float(left_rank.corr(right_rank, method="pearson"))


def ordered_mesh_codes(
    frame: pd.DataFrame,
    score: pd.Series,
    eligible: pd.Series,
    *,
    limit: int,
) -> list[str]:
    """Order a score deterministically using mesh code as the tie-breaker."""
    ranked = pd.DataFrame(
        {
            "mesh_code": frame["mesh_code"].astype(str),
            "score": pd.to_numeric(score, errors="coerce"),
            "eligible": eligible.astype(bool),
        },
        index=frame.index,
    )
    return (
        ranked.loc[ranked["eligible"] & ranked["score"].notna()]
        .sort_values(["score", "mesh_code"], ascending=[False, True])
        .head(limit)["mesh_code"]
        .tolist()
    )


def tie_summary(values: pd.Series) -> dict[str, int]:
    """Summarize exact ties among non-missing values."""
    counts = pd.to_numeric(values, errors="coerce").dropna().value_counts()
    repeated = counts.loc[counts.gt(1)]
    return {
        "observations": int(counts.sum()),
        "distinct_values": len(counts),
        "tied_value_groups": len(repeated),
        "observations_in_ties": int(repeated.sum()),
        "largest_tie": int(repeated.max()) if not repeated.empty else 1,
    }
