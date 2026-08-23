"""Ingest the Maizuru 2025 PLATEAU CityGML archive into PostGIS."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from backend.citygap_platform.ingestion import detect_archive_profile
from backend.citygap_platform.ingestion.postgis import DatasetMetadata, ingest_archive

DEFAULT_ARCHIVE = Path(
    "data/raw/plateau_citygml/26202_maizuru-shi_city_2025_citygml_1_op.zip"
)
DEFAULT_SOURCE_URL = (
    "https://www.geospatial.jp/ckan/dataset/plateau-26202-maizuru-shi-2025"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument(
        "--database-url",
        default=os.getenv(
            "CITYGAP_DATABASE_URL",
            "postgresql://citygap:citygap_dev@localhost:5432/citygap",
        ),
    )
    args = parser.parse_args()

    profile = detect_archive_profile(args.archive)
    result = ingest_archive(
        args.archive,
        args.database_url,
        DatasetMetadata(
            city_id="26202",
            city_name="舞鶴市",
            dataset_year=2025,
            dataset_name="3D都市モデル（舞鶴市）2025年度",
            product_specification_version=profile.product_specification_version,
            ade_schema_version=profile.ade_schema_version,
            source_url=DEFAULT_SOURCE_URL,
            published_at="2026-03-20",
        ),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
