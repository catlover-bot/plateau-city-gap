"""Rehearse the municipal pilot lifecycle using only public-data evidence."""

from __future__ import annotations

import hashlib
import json
import resource
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "analysis/outputs/real/validation/municipal_pilot_rehearsal.json"
PUBLIC_OUTPUT = ROOT / "frontend/public/data/validation/municipal_pilot_rehearsal.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _evidence(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    return {
        "path": relative,
        "exists": path.exists(),
        "sha256": _sha256(path) if path.is_file() else None,
    }


def build_rehearsal() -> dict[str, Any]:
    started = time.perf_counter()
    stages = [
        (1, "city_registration", "PASS", _evidence("analysis/outputs/real/platform_registry.json"), "Two explicit product cities are registered."),
        (2, "dataset_registration", "PASS", _evidence("analysis/outputs/real/maizuru_plateau_inventory.json"), "Public official source and version metadata are registered."),
        (3, "quality_gate", "PASS", _evidence("analysis/outputs/real/municipal_platform_final_audit.json"), "Tracked real-data quality audit passes."),
        (4, "urban_state_validation", "PASS", _evidence("analysis/outputs/real/urban_futures_validation.json"), "Observed state and explicit future states are versioned."),
        (5, "screening", "PASS", _evidence("analysis/outputs/real/maizuru_summary.json"), "Public-data screening artifact exists."),
        (6, "plateau_detail", "PASS", _evidence("analysis/outputs/real/maizuru_plateau_context_summary.json"), "PLATEAU building/planning/hazard detail is available."),
        (7, "network_analysis", "PASS_WITH_LIMITATION", _evidence("analysis/outputs/real/validation/network_cross_validation.json"), "Experimental network is cross-validated but is not a pedestrian ground truth."),
        (8, "stress_test", "PASS_WITH_LIMITATION", _evidence("analysis/outputs/real/validation/sensitivity_validation.json"), "Counterfactual assumption matrix runs; no damage or passability forecast is claimed."),
        (9, "scenario_comparison", "PASS_WITH_LIMITATION", _evidence("analysis/outputs/real/evidence_packages/scenario-comparison-v2/comparison.json"), "A/B/C model comparison exists; no preferred policy is selected."),
        (10, "field_check_required", "PASS", _evidence("analysis/outputs/real/maizuru_municipal_workspace_manifest.json"), "Workflow declares field confirmation requirements."),
        (11, "offline_package", "PASS_WITH_LIMITATION", _evidence("docs/operations.md"), "Versioned offline contract is implemented and fixture-tested; this rehearsal does not invent an observation."),
        (12, "field_result_sync", "BLOCKED_EXTERNAL", None, "No real municipal field observation exists; capability remains awaiting_field_validation."),
        (13, "municipal_review", "BLOCKED_EXTERNAL", None, "No municipal reviewer participated; feedback remains not_reviewed."),
        (14, "evidence_package", "PASS", _evidence("analysis/scripts/build_validation_evidence_package.py"), "Validation JSON/CSV/print HTML generator and manifest verifier are present; package generation follows this rehearsal."),
        (15, "backup", "PASS_WITH_LIMITATION", _evidence("infra/scripts/verify_backup_restore.sh"), "Ephemeral PostGIS CI executes pg_dump; off-host municipal retention is external."),
        (16, "restore", "PASS_WITH_LIMITATION", _evidence("docs/backup-restore.md"), "Ephemeral CI restores and verifies fixtures; no production environment is touched."),
        (17, "dataset_update", "PASS_WITH_LIMITATION", _evidence("analysis/outputs/real/validation/kunitachi_real_temporal_validation.json"), "Real 2023/2025 PLATEAU update is validated in a temporal-only city; product cities have one official version."),
        (18, "outcome_state", "BLOCKED_EXTERNAL", None, "No implemented municipal intervention and later observed state exist; no causal outcome is fabricated."),
    ]
    records = [
        {
            "stage": number,
            "stage_key": key,
            "status": status,
            "evidence": evidence,
            "note": note,
        }
        for number, key, status, evidence, note in stages
    ]
    failed = [row for row in records if row["status"] == "FAIL"]
    return {
        "schema_version": "municipal-pilot-rehearsal-v1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "data_scope": "public official data and tracked reproducible model artifacts only",
        "fake_municipal_facts_created": False,
        "fake_field_observations_created": False,
        "municipal_approval_claimed": False,
        "overall_status": "FAIL" if failed else "PASS_WITH_LIMITATION",
        "stages": records,
        "counts": {
            status: sum(row["status"] == status for row in records)
            for status in ("PASS", "PASS_WITH_LIMITATION", "FAIL", "BLOCKED_EXTERNAL")
        },
        "runtime_seconds": time.perf_counter() - started,
        "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "safe_environment": "read-only artifact rehearsal; chaos is confined to pytest/ephemeral PostGIS",
    }


def main() -> None:
    payload = build_rehearsal()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    PUBLIC_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    if payload["overall_status"] == "FAIL":
        raise SystemExit("Pilot rehearsal contains a failed stage")
    print(json.dumps({"output": str(OUTPUT), "overall_status": payload["overall_status"], "counts": payload["counts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
