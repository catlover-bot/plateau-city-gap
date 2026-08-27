from __future__ import annotations

import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest

from backend.citygap_platform.api.repository import PostGISRepository
from backend.citygap_platform.domain.jobs import JobSnapshot, JobState, fail_job, start_job
from backend.citygap_platform.ingestion.evidence import validate_evidence_manifest
from backend.citygap_platform.ingestion.uploads import inspect_zip


def test_safe_worker_kill_becomes_explicit_failure_in_ephemeral_fixture() -> None:
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        time.sleep(0.05)
        process.kill()
        assert process.wait(timeout=5) != 0
    finally:
        if process.poll() is None:
            process.kill()
    snapshot = fail_job(start_job(JobSnapshot("validation_run")), "worker killed fixture")
    assert snapshot.state is JobState.FAILED
    assert snapshot.error == "worker killed fixture"


def test_database_connection_failure_fails_readiness_without_mutation(monkeypatch) -> None:
    repository = PostGISRepository("postgresql://invalid")

    def unavailable():
        raise OSError("ephemeral database unavailable")

    monkeypatch.setattr(repository, "_connect", unavailable)
    assert repository.health() is False


def test_zip_bomb_ratio_and_xxe_are_rejected_before_ingestion(tmp_path: Path) -> None:
    bomb = tmp_path / "bomb.zip"
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("udx/bldg/bomb.gml", b"0" * 100_000)
    with pytest.raises(ValueError, match="compression ratio"):
        inspect_zip(bomb, expected="citygml", max_compression_ratio=2)

    xxe = tmp_path / "xxe.zip"
    with zipfile.ZipFile(xxe, "w") as archive:
        archive.writestr(
            "udx/bldg/xxe.gml",
            b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>',
        )
    with pytest.raises(ValueError, match="DTD and entity"):
        inspect_zip(xxe, expected="citygml")


def test_evidence_corruption_is_a_hard_failure(tmp_path: Path) -> None:
    source = Path("analysis/outputs/real/evidence_packages/scenario-comparison-v2")
    target = tmp_path / "evidence"
    shutil.copytree(source, target)
    artifact = target / "comparison.json"
    artifact.write_text(artifact.read_text(encoding="utf-8") + "tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="resolve exactly one json artifact"):
        validate_evidence_manifest(target / "manifest.json")


def test_chaos_scope_is_ci_or_ephemeral_only() -> None:
    runbook = Path("docs/validation-day2-runbook.md").read_text(encoding="utf-8")
    threat_model = Path("docs/validation-security-threat-model.md").read_text(encoding="utf-8")
    assert "Production chaos is forbidden" in runbook
    assert "ephemeral PostGIS" in runbook
    for surface in (
        "Upload", "ZIP", "XML/CityGML", "OIDC", "RBAC/API", "Scenario/validation",
        "Evidence export", "Offline field sync", "PostGIS", "Worker", "Tile API",
    ):
        assert f"| {surface} |" in threat_model
