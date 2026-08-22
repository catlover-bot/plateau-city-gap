"""Synthetic e-Stat-like rows; not Maizuru observations."""

import pandas as pd

from analysis.src.population import ELDERLY_COLUMNS, add_population_metrics


def population_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "KEY_CODE": "533537411",
        "T001192001": "100",
        "HTKSYORI": "0",
        "HTKSAKI": "",
        "GASSAN": "",
    }
    row.update({column: "10" for column in ELDERLY_COLUMNS})
    row.update(overrides)
    return row


def test_elderly_age_bands_are_summed() -> None:
    result = add_population_metrics(pd.DataFrame([population_row()]))
    assert result.loc[0, "elderly_population"] == 70
    assert result.loc[0, "elderly_ratio"] == 0.7


def test_suppression_and_aggregation_are_not_primary_eligible() -> None:
    rows = [
        population_row(KEY_CODE="533537411"),
        population_row(KEY_CODE="533537412", HTKSYORI="2", HTKSAKI="533537411"),
        population_row(KEY_CODE="533537413", HTKSYORI="1", GASSAN="533537411"),
    ]
    result = add_population_metrics(pd.DataFrame(rows))
    assert result["primary_eligible_disclosure"].tolist() == [True, False, False]
    assert result["disclosure_status"].tolist() == [
        "unaffected",
        "suppressed_source",
        "aggregation_destination",
    ]
    assert pd.isna(result.loc[1, "elderly_population"])
    assert pd.isna(result.loc[2, "elderly_ratio"])
    assert result.loc[2, "reported_elderly_population"] == 70


def test_incomplete_age_bands_remain_missing() -> None:
    result = add_population_metrics(
        pd.DataFrame([population_row(**{ELDERLY_COLUMNS[0]: "*"})])
    )
    assert pd.isna(result.loc[0, "elderly_population"])
