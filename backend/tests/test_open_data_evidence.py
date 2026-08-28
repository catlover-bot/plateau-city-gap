from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.citygap_platform.ingestion.open_data_evidence import (
    export_open_data_evidence,
)


def _package() -> dict[str, object]:
    return {
        "cities": ["舞鶴市", "藤沢市"],
        "urban_states": ["maizuru-2025-observed", "fujisawa-2025-observed"],
        "source_timeline": [{"reference_year": 2020, "source": "census"}],
        "analyses": [{"analysis_id": "medical-access-v2", "tier": "BASE"}],
        "findings": [],
        "source_contributions": [],
        "lineage": {"algorithm_version": "municipal-open-data-analysis-1.0.0"},
        "missing_data": ["official_pedestrian_network"],
        "limitations": ["not a policy decision"],
        "review_status": "unvalidated_review_candidates",
        "human_workflow": {
            "investigations_created": False,
            "decisions_created": False,
            "next_action": "explicit human triage",
        },
        "public_distribution": False,
    }


def test_open_data_evidence_is_deterministic_and_escapes_html(tmp_path: Path) -> None:
    package = _package()
    package["limitations"] = ["<script>alert(1)</script>", '=WEBSERVICE("bad")']
    first = export_open_data_evidence(package, tmp_path, package_key="municipal_open_data")
    first_hashes = dict(first.sha256)
    second = export_open_data_evidence(package, tmp_path, package_key="municipal_open_data")
    assert second.sha256 == first_hashes
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "municipal-open-data-evidence-1.0.0"
    rendered = first.html_path.read_text(encoding="utf-8")
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "'=WEBSERVICE" in first.csv_path.read_text(encoding="utf-8")


def test_open_data_evidence_rejects_public_or_automatic_workflow(tmp_path: Path) -> None:
    package = _package()
    package["public_distribution"] = True
    with pytest.raises(ValueError, match="internal mesh context"):
        export_open_data_evidence(package, tmp_path, package_key="unsafe")
    package = _package()
    package["human_workflow"] = {
        "investigations_created": True,
        "decisions_created": False,
    }
    with pytest.raises(ValueError, match="auto-create investigations"):
        export_open_data_evidence(package, tmp_path, package_key="unsafe")
