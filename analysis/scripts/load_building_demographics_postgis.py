"""Load canonical building demographics Parquet into an initialized PostGIS database."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from backend.citygap_platform.ingestion.building_demographics import (
    load_building_demographics,
)

DEFAULT_PARQUET = Path("analysis/outputs/real/maizuru_building_demographics.parquet")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, default=DEFAULT_PARQUET)
    parser.add_argument("--dataset-version-id", required=True)
    parser.add_argument(
        "--database-url",
        default=os.getenv(
            "CITYGAP_DATABASE_URL",
            "postgresql://citygap:citygap_dev@localhost:5432/citygap",
        ),
    )
    args = parser.parse_args()
    result = load_building_demographics(
        args.parquet,
        args.database_url,
        dataset_version_id=args.dataset_version_id,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
