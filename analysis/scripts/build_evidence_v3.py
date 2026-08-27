"""Export the reviewed Maizuru resilience validation as Evidence Package V3."""

from __future__ import annotations

import json
from pathlib import Path

from backend.citygap_platform.ingestion.evidence_v3 import export_evidence_v3

ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "analysis/outputs/real/urban_futures_validation.json"
OUTPUT = ROOT / "analysis/outputs/evidence-v3"


def build(output_dir: Path = OUTPUT) -> dict[str, object]:
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    city = validation["cities"]["maizuru"]
    flood = city["stress_tests"]["flood"]
    package = {
        "city": {"city_id": city["city_id"], "city_code": city["city_code"], "name": city["city_name"]},
        "urban_state": city["urban_state"],
        "dataset_years": {
            "population": 2020,
            "plateau": int(city["urban_state"].split("-")[1]),
        },
        "network": city["network"],
        "assumptions": flood["assumption"],
        "stress_test": flood["result"],
        "affected_areas": {
            "delivery": "aggregated metrics; building-level demographics excluded",
            "component_fragmentation_increase": flood["result"][
                "component_fragmentation_increase"
            ],
        },
        "critical_roads": city["criticality"]["top_candidates"],
        "scenario_alternatives": [city["redundancy"]],
        "limitations": city["limitations"],
        "field_verification": {"status": "municipal review pending", "automatic_approval": False},
    }
    artifacts = export_evidence_v3(package, output_dir, package_key="maizuru-2025-flood")
    return {
        "schema_version": "evidence-v3.0.0",
        "artifacts": {
            "json": str(artifacts.manifest_path),
            "csv": str(artifacts.csv_path),
            "html": str(artifacts.html_path),
        },
        "sha256": dict(artifacts.sha256),
    }


def main() -> None:
    print(json.dumps(build(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
