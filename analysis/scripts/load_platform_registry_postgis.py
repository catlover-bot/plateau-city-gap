"""Load the evidence-backed city/dataset registry into migrated PostGIS."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from backend.citygap_platform.ingestion.registry import load_platform_registry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("analysis/outputs/real/platform_registry.json"),
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv(
            "CITYGAP_DATABASE_URL",
            "postgresql://citygap:citygap_dev@localhost:5432/citygap",
        ),
    )
    arguments = parser.parse_args()
    result = load_platform_registry(arguments.database_url, arguments.registry)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
