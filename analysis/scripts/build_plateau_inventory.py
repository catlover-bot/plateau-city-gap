"""Build a full streaming inventory of any PLATEAU CityGML archive."""

from __future__ import annotations

import argparse
import json
import re
import resource
from pathlib import Path

from backend.citygap_platform.ingestion import build_archive_inventory, detect_archive_profile

DEFAULT_ARCHIVE = Path(
    "data/raw/plateau_citygml/26202_maizuru-shi_city_2025_citygml_1_op.zip"
)
DEFAULT_OUTPUT = Path("analysis/outputs/real/maizuru_plateau_inventory.json")
ARCHIVE_ID_PATTERN = re.compile(r"(?P<city_id>\d{5}).*?(?P<year>20\d{2}).*?citygml", re.IGNORECASE)


def _dataset_identity(archive: Path, city_id: str | None, dataset_year: int | None) -> tuple[str, int]:
    match = ARCHIVE_ID_PATTERN.search(archive.name)
    resolved_city_id = city_id or (match.group("city_id") if match else None)
    resolved_year = dataset_year or (int(match.group("year")) if match else None)
    if resolved_city_id is None or resolved_year is None:
        raise ValueError(
            "city and year could not be inferred from the archive name; "
            "pass --city-id and --dataset-year"
        )
    return resolved_city_id, resolved_year


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--city-id", help="five-digit Japanese municipality code")
    parser.add_argument("--dataset-year", type=int)
    args = parser.parse_args()

    city_id, dataset_year = _dataset_identity(args.archive, args.city_id, args.dataset_year)
    output = args.output or (
        DEFAULT_OUTPUT
        if args.archive == DEFAULT_ARCHIVE
        else Path(f"analysis/outputs/real/{city_id}_plateau_inventory.json")
    )
    profile = detect_archive_profile(args.archive)
    inventory = build_archive_inventory(
        args.archive,
        city_id=city_id,
        dataset_year=dataset_year,
        product_specification_version=profile.product_specification_version,
        ade_schema_version=profile.ade_schema_version,
    )
    inventory["dataset"]["readme_member"] = profile.readme_member
    inventory["dataset"]["ade_schema_versions"] = profile.ade_schema_versions
    inventory["runtime"] = {
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "note": "Linux ru_maxrss; includes interpreter and parser process",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(inventory["totals"], ensure_ascii=False))
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
