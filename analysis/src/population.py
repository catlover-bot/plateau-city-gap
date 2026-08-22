"""e-Stat 2020 500 m population parsing and disclosure-status handling."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

TOTAL_POPULATION_COLUMN = "T001192001"
ELDERLY_COLUMNS = [
    "T001192043",
    "T001192046",
    "T001192049",
    "T001192052",
    "T001192055",
    "T001192058",
    "T001192061",
]
DISCLOSURE_COLUMNS = ["HTKSYORI", "HTKSAKI", "GASSAN"]


def read_estat_csv(path: Path) -> pd.DataFrame:
    """Read an e-Stat CSV while retaining mesh/status identifiers as strings."""
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "cp932"):
        try:
            return pd.read_csv(
                path,
                encoding=encoding,
                dtype=str,
                low_memory=False,
                skiprows=[1],  # Japanese labels; row 1 already contains stable field codes.
            )
        except UnicodeDecodeError as error:
            last_error = error
    assert last_error is not None
    raise last_error


def _present(value: object) -> bool:
    """Whether an e-Stat disclosure reference is materially populated."""
    if pd.isna(value):
        return False
    return str(value).strip() not in {"", "0", "0.0", "-", "nan", "None"}


def add_population_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    """Calculate elderly population without estimating suppressed values."""
    required = {TOTAL_POPULATION_COLUMN, *ELDERLY_COLUMNS, *DISCLOSURE_COLUMNS}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing e-Stat columns: {', '.join(sorted(missing))}")

    result = frame.copy()
    mesh_column = next(
        (name for name in ("KEY_CODE", "KEYCODE", "MESH_CODE") if name in result.columns),
        None,
    )
    if mesh_column is None:
        raise ValueError("No mesh code column (KEY_CODE/KEYCODE/MESH_CODE)")
    result["mesh_code"] = result[mesh_column].astype("string").str.strip()

    numeric_columns = [TOTAL_POPULATION_COLUMN, *ELDERLY_COLUMNS]
    numeric = result[numeric_columns].apply(pd.to_numeric, errors="coerce")
    result["population"] = numeric[TOTAL_POPULATION_COLUMN]
    result["elderly_population"] = numeric[ELDERLY_COLUMNS].sum(
        axis=1, min_count=len(ELDERLY_COLUMNS)
    )
    result["elderly_ratio"] = result["elderly_population"].div(
        result["population"].where(result["population"] > 0)
    )

    disclosure_code = pd.to_numeric(result["HTKSYORI"], errors="coerce").fillna(0).astype(int)
    result["disclosure_status"] = disclosure_code.map(
        {0: "unaffected", 1: "aggregation_destination", 2: "suppressed_source"}
    ).fillna("unknown")
    result["has_htksyori"] = disclosure_code.ne(0)
    result["has_htksaki"] = result["HTKSAKI"].map(_present)
    result["has_gassan"] = result["GASSAN"].map(_present)
    result["suppression_flag"] = disclosure_code.eq(2) | result["has_htksaki"]
    result["aggregation_target_flag"] = disclosure_code.eq(1)
    result["aggregation_flag"] = result["aggregation_target_flag"] | result["has_gassan"]
    result["primary_eligible_disclosure"] = ~(
        result["has_htksyori"]
        | result["has_htksaki"]
        | result["has_gassan"]
    )
    result["reported_elderly_population"] = result["elderly_population"]
    # A flag=1 row reports age bands for an aggregation group while its total
    # population remains cell-specific; the ratio would therefore be invalid.
    affected = ~result["primary_eligible_disclosure"]
    result.loc[affected, ["elderly_population", "elderly_ratio"]] = pd.NA
    return result
