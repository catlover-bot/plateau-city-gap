"""Build a full streaming inventory of the Maizuru 2025 PLATEAU archive."""

from __future__ import annotations

import argparse
import json
import resource
from pathlib import Path

from backend.citygap_platform.ingestion import build_archive_inventory, detect_archive_profile

DEFAULT_ARCHIVE = Path(
    "data/raw/plateau_citygml/26202_maizuru-shi_city_2025_citygml_1_op.zip"
)
DEFAULT_OUTPUT = Path("analysis/outputs/real/maizuru_plateau_inventory.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    profile = detect_archive_profile(args.archive)
    inventory = build_archive_inventory(
        args.archive,
        city_id="26202",
        dataset_year=2025,
        product_specification_version=profile.product_specification_version,
        ade_schema_version=profile.ade_schema_version,
    )
    inventory["dataset"]["readme_member"] = profile.readme_member
    inventory["dataset"]["ade_schema_versions"] = profile.ade_schema_versions
    inventory["runtime"] = {
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "note": "Linux ru_maxrss; includes interpreter and parser process",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(inventory["totals"], ensure_ascii=False))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
