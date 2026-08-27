from __future__ import annotations

import json
from pathlib import Path

from backend.citygap_platform.ingestion.evidence_v3 import export_evidence_v3


def test_evidence_v3_exports_json_csv_and_print_html_deterministically(tmp_path: Path) -> None:
    package = {
        "city": "舞鶴市",
        "urban_state": "maizuru-2025",
        "dataset_years": [2020, 2025],
        "network": {"version": "road-v1"},
        "assumptions": {"explicit": True},
        "stress_test": {"type": "hazard_counterfactual"},
        "affected_areas": {"aggregated": True},
        "critical_roads": [],
        "scenario_alternatives": [],
        "limitations": ["not a road-passability prediction"],
        "field_verification": {"status": "pending"},
    }
    first = export_evidence_v3(package, tmp_path, package_key="maizuru-2025-flood")
    first_hashes = dict(first.sha256)
    second = export_evidence_v3(package, tmp_path, package_key="maizuru-2025-flood")
    assert second.sha256 == first_hashes
    assert json.loads(first.manifest_path.read_text(encoding="utf-8"))["schema_version"] == (
        "evidence-v3.0.0"
    )
    assert "@media print" in first.html_path.read_text(encoding="utf-8")
    assert first.csv_path.read_text(encoding="utf-8").startswith("field,value")
