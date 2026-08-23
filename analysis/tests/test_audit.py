import pandas as pd

from analysis.src.audit import (
    classify_medical_access,
    medical_access_class,
    ordered_mesh_codes,
    rank_correlation,
    tie_summary,
)


def test_medical_access_requires_evidence_for_confirmed_public() -> None:
    assert medical_access_class("山口クリニック") == ("likely_public", None)
    assert medical_access_class(
        "山口クリニック", confirmed_public_names=["山口クリニック"]
    ) == ("confirmed_public", None)
    classification = classify_medical_access(
        pd.Series(["会社 健康管理室", "一般内科"])
    )
    assert classification["medical_access_class"].tolist() == [
        "uncertain_access",
        "likely_public",
    ]


def test_rank_audit_helpers_handle_ties_deterministically() -> None:
    frame = pd.DataFrame({"mesh_code": ["3", "1", "2"]})
    score = pd.Series([0.5, 0.5, 0.1])
    eligible = pd.Series([True, True, True])
    assert ordered_mesh_codes(frame, score, eligible, limit=3) == ["1", "3", "2"]
    assert rank_correlation(score, score) == 1.0
    summary = tie_summary(score)
    assert summary["tied_value_groups"] == 1
    assert summary["largest_tie"] == 2
