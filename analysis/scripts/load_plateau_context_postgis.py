"""Load verified city-prefixed PLATEAU context Parquets into a migrated PostGIS database."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from backend.citygap_platform.ingestion.context import load_context_artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, default=Path("analysis/outputs/real"))
    parser.add_argument("--artifact-prefix", default="maizuru")
    parser.add_argument(
        "--database-url",
        default=os.getenv(
            "CITYGAP_DATABASE_URL",
            "postgresql://citygap:citygap_dev@localhost:5432/citygap",
        ),
    )
    arguments = parser.parse_args()
    result = load_context_artifacts(
        arguments.database_url,
        arguments.output_directory,
        arguments.artifact_prefix,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
