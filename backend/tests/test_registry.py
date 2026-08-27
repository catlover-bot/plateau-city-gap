from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from backend.citygap_platform.domain.registry import CAPABILITIES, validate_platform_registry

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "analysis/outputs/real/platform_registry.json"


def _registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_real_registry_declares_every_capability_without_faking_fujisawa() -> None:
    registry = _registry()
    validate_platform_registry(registry)
    by_city = {
        city_code: {
            row["capability"]: row
            for row in registry["capabilities"]
            if row["city_code"] == city_code
        }
        for city_code in ("26202", "14205")
    }
    assert set(by_city["26202"]) == set(CAPABILITIES)
    assert set(by_city["14205"]) == set(CAPABILITIES)
    assert by_city["26202"]["road_network"]["status"] == "partial"
    assert by_city["26202"]["gtfs"]["status"] == "unavailable"
    assert by_city["14205"]["screening"]["status"] == "available"
    for capability in ("building_detail", "land_use", "urban_planning", "hazard"):
        assert by_city["14205"][capability]["status"] == "available"
    for capability in ("road_network", "terrain"):
        assert by_city["14205"][capability]["status"] == "partial"
    for capability in ("scenario", "gtfs"):
        assert by_city["14205"][capability]["status"] == "unavailable"
    for city_code in ("26202", "14205"):
        for capability in (
            "future_population",
            "hazard_stress_test",
            "criticality",
            "evacuation_reachability",
            "planning_monitoring",
        ):
            assert by_city[city_code][capability]["status"] == "available"
        for capability in ("temporal_diff", "field_mode", "outcome_monitoring"):
            assert by_city[city_code][capability]["status"] == "partial"
    assert not any(version["format"].lower() == "gtfs" for version in registry["dataset_versions"])


def test_registry_requires_complete_evidence_backed_capability_matrix() -> None:
    registry = _registry()
    missing = deepcopy(registry)
    missing["capabilities"].pop()
    with pytest.raises(ValueError, match="must declare every capability"):
        validate_platform_registry(missing)

    unsupported = deepcopy(registry)
    gtfs = next(
        row
        for row in unsupported["capabilities"]
        if row["city_code"] == "26202" and row["capability"] == "gtfs"
    )
    gtfs["status"] = "available"
    gtfs["evidence"] = [{"artifact": "not-a-feed"}]
    with pytest.raises(ValueError, match="without a GTFS dataset version"):
        validate_platform_registry(unsupported)


def test_registry_dataset_and_analysis_versions_are_explicit_and_unique() -> None:
    registry = _registry()
    version_ids = [row["dataset_version_id"] for row in registry["dataset_versions"]]
    run_ids = [row["analysis_run_id"] for row in registry["analysis_runs"]]
    assert len(version_ids) == len(set(version_ids)) == 12
    assert len(run_ids) == len(set(run_ids)) == 13
    assert all(len(run["config_hash"]) == 64 for run in registry["analysis_runs"])
    assert all(run["dataset_version_ids"] for run in registry["analysis_runs"])
    assert "never implicit latest" in registry["policy"]["version_selection"]


def test_public_and_canonical_registries_are_identical() -> None:
    public = ROOT / "frontend/public/data/platform_registry.json"
    assert (
        hashlib.sha256(public.read_bytes()).hexdigest()
        == hashlib.sha256(REGISTRY.read_bytes()).hexdigest()
    )


def test_dataset_registry_migration_models_first_class_entities() -> None:
    sql = (ROOT / "infra/migrations/006_dataset_city_registry.sql").read_text(encoding="utf-8")
    for required in (
        "CREATE TABLE cities",
        "CREATE TABLE datasets",
        "CREATE TABLE dataset_versions",
        "CREATE TABLE analysis_runs",
        "CREATE TABLE analysis_run_dataset_versions",
        "CREATE TABLE city_capabilities",
        "CREATE VIEW dataset_registry_provenance",
        "registry_version_id",
        "available', 'partial', 'unavailable",
        "no API or analysis job may silently substitute latest",
    ):
        assert required in sql
