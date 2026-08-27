from __future__ import annotations

from pathlib import Path

import pytest

from backend.citygap_platform.ingestion.planning import (
    load_external_costs,
    load_municipal_targets,
)


def test_municipal_targets_are_only_values_present_in_source(tmp_path: Path) -> None:
    path = tmp_path / "targets.csv"
    path.write_text(
        "target_key,target_type,target_year,target_value,unit,area_key,source_record_id\n"
        "coverage-2040,facility_coverage,2040,85,percent,district-a,official-1\n",
        encoding="utf-8",
    )
    records = load_municipal_targets(path)
    assert len(records) == 1
    assert records[0].target_value == 85


def test_target_adapter_rejects_unsupported_or_missing_values(tmp_path: Path) -> None:
    path = tmp_path / "targets.csv"
    path.write_text(
        "target_key,target_type,target_year,target_value,unit,area_key,source_record_id\n"
        "x,fabricated_prediction,2040,1,people,city,record-1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unsupported"):
        load_municipal_targets(path)


def test_external_costs_require_explicit_versionable_values(tmp_path: Path) -> None:
    path = tmp_path / "costs.csv"
    path.write_text(
        "site_id,cost,year,category,currency,source_record_id\n"
        "site-1,1200000,2028,construction,JPY,cost-register-8\n",
        encoding="utf-8",
    )
    records = load_external_costs(path)
    assert records[0].cost == 1_200_000
    assert records[0].currency == "JPY"

    path.write_text(
        "site_id,cost,year,category,currency,source_record_id\n"
        "site-1,-1,2028,construction,JPY,cost-register-8\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="non-negative"):
        load_external_costs(path)
