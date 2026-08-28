from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.citygap_platform.ingestion.future_population import (
    IpssWorkbookAdapter,
    OfficialFuturePopulationAdapter,
    allocate_projection_to_buildings,
    future_accessibility_summary,
)

SOURCE = Path("analysis/sources/official_future_population.csv")


def test_tracked_official_projection_has_only_published_years_and_conserves_age_groups() -> None:
    adapter = OfficialFuturePopulationAdapter(SOURCE)
    maizuru = adapter.records("26202", "ipss-regional-2023")
    fujisawa = adapter.records("14205", "fujisawa-municipal-2023")
    assert [row.year for row in maizuru] == [2020, 2025, 2030, 2035, 2040, 2045, 2050]
    assert [row.year for row in fujisawa] == [2020, 2025, 2030, 2035, 2040, 2045, 2050]
    assert maizuru[4].total_population == 62426
    assert maizuru[4].age_65_plus == 23855
    assert fujisawa[4].total_population == 452293
    assert fujisawa[4].age_65_plus == 149274


def test_ipss_workbook_adapter_matches_normalized_official_rows_when_raw_source_exists() -> None:
    workbook = Path("data/raw/future_population/ipss_shicyoson_2023_projection.xlsx")
    if not workbook.exists():
        pytest.skip("EXPECTED_EXTERNAL: ignored official IPSS workbook is not present")
    extracted = IpssWorkbookAdapter(
        workbook,
        "dc503ef87559db7f45d6baa754c8920de0be0d6073d00cef84705219ea9b2b92",
    ).municipality("26202")
    normalized = OfficialFuturePopulationAdapter(SOURCE).records(
        "26202", "ipss-regional-2023"
    )
    assert extracted == tuple(
        {
            "year": row.year,
            "total_population": row.total_population,
            "age_0_14": row.age_0_14,
            "age_15_64": row.age_15_64,
            "age_65_plus": row.age_65_plus,
            "age_65_74": row.age_65_74,
            "age_75_plus": row.age_75_plus,
        }
        for row in normalized
    )


def test_capacity_allocation_conserves_official_totals_and_reports_fixed_service_burden() -> None:
    projection = OfficialFuturePopulationAdapter(SOURCE).records(
        "26202", "ipss-regional-2023"
    )[4]
    allocation = allocate_projection_to_buildings(
        pd.DataFrame(
            {
                "building_id": ["a", "b"],
                "mesh_code": ["1", "2"],
                "capacity_weight": [1.0, 3.0],
            }
        ),
        projection,
    )
    assert allocation.estimated_future_population.sum() == pytest.approx(62426)
    assert allocation.estimated_future_elderly_population.sum() == pytest.approx(23855)
    summary = future_accessibility_summary(
        allocation,
        pd.DataFrame(
            {
                "building_id": ["a", "b"],
                "transport_distance_m": [1200.0, 100.0],
                "medical_distance_m": [100.0, None],
            }
        ),
    )
    assert summary["fixed_service_assumption"] is True
    assert summary["estimated_population_transport_burden"] == pytest.approx(62426 / 4)
    assert summary["estimated_population_medical_burden"] == pytest.approx(62426 * 3 / 4)


def test_projection_adapter_rejects_unverified_or_invented_rows(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    frame = pd.read_csv(SOURCE, dtype={"city_code": str}).head(1)
    frame.loc[0, "source_verified"] = False
    frame.to_csv(bad, index=False)
    with pytest.raises(ValueError, match="verified official"):
        OfficialFuturePopulationAdapter(bad)
