from __future__ import annotations

import json
from pathlib import Path


def test_real_canonical_manifest_records_versions_counts_and_unexecuted_db_boundary() -> None:
    manifest = json.loads(
        Path("analysis/outputs/real/maizuru_scenario_canonical_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["dataset_version_key"].startswith("26202:2025:")
    assert manifest["network_version"].startswith("exp-")
    assert len(manifest["context_config_hash"]) == 64
    assert len(manifest["config_hash"]) == 64
    assert manifest["canonical_tables"]["scenario_runs"]["row_count"] == 30
    assert manifest["canonical_tables"]["scenario_sites"]["row_count"] == 90
    assert manifest["canonical_tables"]["scenario_constraints"]["row_count"] == 630
    assert manifest["lifecycle_initial_status"] == "draft"
    assert manifest["database_executed"] is False
    assert "not executed" in manifest["database_status"]
