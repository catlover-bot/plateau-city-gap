import pytest

from backend.citygap_platform.api.service_repository import MunicipalServiceRepository

PARAMETERS = [
    {
        "parameter_key": "candidate_limit",
        "value_type": "integer",
        "default_value": 10,
        "minimum": 1,
        "maximum": 100,
        "allowed_values": None,
    },
    {
        "parameter_key": "include_partial",
        "value_type": "boolean",
        "default_value": False,
        "minimum": None,
        "maximum": None,
        "allowed_values": None,
    },
]


def test_typed_analysis_parameters_apply_defaults_and_bounds() -> None:
    assert MunicipalServiceRepository._validated_analysis_parameters(
        PARAMETERS, {"candidate_limit": 25}
    ) == {"candidate_limit": 25, "include_partial": False}
    with pytest.raises(ValueError, match="must be integer"):
        MunicipalServiceRepository._validated_analysis_parameters(
            PARAMETERS, {"candidate_limit": True}
        )
    with pytest.raises(ValueError, match="exceeds its maximum"):
        MunicipalServiceRepository._validated_analysis_parameters(
            PARAMETERS, {"candidate_limit": 101}
        )
    with pytest.raises(ValueError, match="Unknown analysis parameters"):
        MunicipalServiceRepository._validated_analysis_parameters(PARAMETERS, {"undeclared": 1})


def test_report_digest_is_deterministic_and_sensitive_to_content() -> None:
    first_json, first_digest = MunicipalServiceRepository._report_digest(
        {"title": "品質", "inputs": {"population": "v1", "plateau": "v2"}}
    )
    reordered_json, reordered_digest = MunicipalServiceRepository._report_digest(
        {"inputs": {"plateau": "v2", "population": "v1"}, "title": "品質"}
    )
    _, changed_digest = MunicipalServiceRepository._report_digest(
        {"title": "品質", "inputs": {"population": "v3", "plateau": "v2"}}
    )
    assert first_json == reordered_json
    assert first_digest == reordered_digest
    assert first_digest != changed_digest
    assert len(first_digest) == 64
