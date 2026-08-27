from __future__ import annotations

import pandas as pd
import pytest

from analysis.src.planning_monitoring import compare_planning_context


def test_planning_comparison_is_observational_and_never_a_legal_claim() -> None:
    demographics = pd.DataFrame(
        {
            "gml_id": ["b1", "b2"],
            "residential_class": ["residential", "mixed_residential"],
            "estimated_population": [8.0, 4.0],
            "estimated_elderly_population": [3.0, 1.0],
        }
    )
    context = pd.DataFrame(
        {
            "gml_id": ["b1", "b2", "b2"],
            "context_type": ["planning", "planning", "planning"],
            "planning_type": ["UseDistrict", "UseDistrict", "UrbanPlanningArea"],
            "planning_label": ["第1種住居地域", "第1種住居地域", "都市計画区域"],
        }
    )

    comparison = compare_planning_context(demographics, context)[0]
    assert comparison.building_count == 2
    assert comparison.estimated_population == 12
    assert comparison.building_use_composition == {
        "mixed_residential": 1,
        "residential": 1,
    }
    assert comparison.candidate_label == "planning-context mismatch candidate"
    assert comparison.legal_compliance_claimed is False


def test_planning_comparison_rejects_missing_or_invalid_demographics() -> None:
    context = pd.DataFrame(
        {
            "gml_id": ["b1"],
            "context_type": ["planning"],
            "planning_type": ["UseDistrict"],
            "planning_label": ["zone"],
        }
    )
    with pytest.raises(ValueError, match="missing required"):
        compare_planning_context(pd.DataFrame({"gml_id": ["b1"]}), context)
    invalid = pd.DataFrame(
        {
            "gml_id": ["b1"],
            "residential_class": ["residential"],
            "estimated_population": [-1],
            "estimated_elderly_population": [0],
        }
    )
    with pytest.raises(ValueError, match="non-negative"):
        compare_planning_context(invalid, context)
