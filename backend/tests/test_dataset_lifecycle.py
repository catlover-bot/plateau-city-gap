from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

import pytest
from shapely.geometry import Point

from backend.citygap_platform.cli import build_parser
from backend.citygap_platform.domain.temporal import (
    FeatureScope,
    UrbanStateDefinition,
    incremental_matches_full,
    plan_incremental_recomputation,
)
from backend.citygap_platform.ingestion.differential import (
    AnalysisDependency,
    FeatureFingerprint,
    diff_fingerprints,
    impacted_dependencies,
)
from backend.citygap_platform.ingestion.quality import (
    QualityMeasurements,
    QualityThresholds,
    evaluate_quality,
)
from backend.citygap_platform.ingestion.uploads import inspect_zip


def _fingerprint(gml_id: str, x: float, usage: str) -> FeatureFingerprint:
    return FeatureFingerprint.create(gml_id, "Building", Point(x, 35).wkb, {"usage": usage})


def test_feature_diff_uses_geometry_and_important_attribute_hashes() -> None:
    before = [_fingerprint("same", 135, "residential"), _fingerprint("removed", 136, "other")]
    after = [
        _fingerprint("same", 135, "commercial"),
        _fingerprint("added", 137, "residential"),
    ]
    changes = diff_fingerprints(before, after)
    assert {row.gml_id: row.change_type for row in changes} == {
        "added": "added",
        "removed": "removed",
        "same": "attribute_changed",
    }
    assert next(row for row in changes if row.gml_id == "same").changed_attributes == ("usage",)
    dependencies = [
        AnalysisDependency("network", "road-v1", frozenset({"Road"})),
        AnalysisDependency("analysis", "population-v1", frozenset({"Building"})),
        AnalysisDependency("scenario", "scenario-v1"),
    ]
    impacted = impacted_dependencies(changes, dependencies)
    assert [(row.dependent_type, row.dependent_id) for row in impacted] == [
        ("analysis", "population-v1"),
        ("scenario", "scenario-v1"),
    ]


def test_quality_gate_reports_measured_reasons_and_never_marks_validation_analysis_ready() -> None:
    report = evaluate_quality(
        QualityMeasurements(
            feature_count=100,
            invalid_geometry_count=2,
            crs="EPSG:4326",
            resolved_code_count=85,
            coded_feature_count=100,
            spatial_coverage=0.8,
            attribute_coverage={"usage": 0.7},
        ),
        QualityThresholds(
            minimum_codelist_resolution=0.95,
            minimum_spatial_coverage=0.9,
            required_attribute_coverage={"usage": 0.9},
            allowed_crs=frozenset({"EPSG:6674"}),
        ),
    )
    assert report.status == "failed"
    assert report.analysis_ready is False
    assert set(report.reasons) >= {
        "invalid_geometry_fraction_exceeded",
        "crs_not_allowed",
        "codelist_resolution_below_minimum",
        "spatial_coverage_below_minimum",
        "required_attribute_coverage:usage",
    }


def test_archive_safety_rejects_traversal_symlink_expansion_and_xml_entities(tmp_path: Path) -> None:
    traversal = tmp_path / "traversal.zip"
    with zipfile.ZipFile(traversal, "w") as archive:
        archive.writestr("../escape.gml", "<root/>")
    with pytest.raises(ValueError, match="path traversal"):
        inspect_zip(traversal, expected="citygml")

    entity = tmp_path / "entity.zip"
    with zipfile.ZipFile(entity, "w") as archive:
        archive.writestr("udx/bldg/test.gml", '<!DOCTYPE x [<!ENTITY y "z">]><x/>')
    with pytest.raises(ValueError, match="DTD and entity"):
        inspect_zip(entity, expected="citygml")

    bomb = tmp_path / "bomb.zip"
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("udx/bldg/test.gml", "0" * 50_000)
    with pytest.raises(ValueError, match="compression ratio"):
        inspect_zip(bomb, expected="citygml", max_compression_ratio=2)


def test_municipal_cli_exposes_complete_workflow_and_explicit_versions() -> None:
    parser = build_parser()
    for command in ("city-init", "dataset-add", "validate", "evidence-register"):
        with pytest.raises(SystemExit) as exit_info:
            parser.parse_args([command, "--help"])
        assert exit_info.value.code == 0

    scenario = parser.parse_args(
        [
            "scenario",
            "--city",
            "26202",
            "--dataset-version",
            "00000000-0000-0000-0000-000000000001",
            "--algorithm-version",
            "scenario-1",
        ]
    )
    assert scenario.dataset_version == ["00000000-0000-0000-0000-000000000001"]


def test_dataset_lifecycle_migration_enforces_diff_dependency_quality_and_metric_versions() -> None:
    sql = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "infra/migrations/009_dataset_lifecycle.sql",
            "infra/migrations/011_temporal_urban_states.sql",
        )
    )
    for required in (
        "dataset_feature_fingerprints",
        "dataset_version_diffs",
        "'added', 'removed', 'geometry_changed', 'attribute_changed'",
        "analysis_dependencies",
        "CREATE VIEW impacted_analysis",
        "quality_status",
        "analysis_ready_gate",
        "accessibility_metric_versions",
        "experimental_surface_adjacency",
        "official_drive",
        "official_walk",
    ):
        assert required in sql


def test_feature_diff_reconciles_changed_source_identifier_without_hiding_real_change() -> None:
    before = [_fingerprint("old-id", 135.0, "residential")]
    same_geometry = [_fingerprint("new-id", 135.0, "commercial")]
    change = diff_fingerprints(before, same_geometry)[0]
    assert change.feature_key == "old-id=>new-id"
    assert change.matched_by == "geometry_hash"
    assert change.change_type == "attribute_changed"

    ambiguous_before = [
        _fingerprint("old-a", 135.0, "residential"),
        _fingerprint("old-b", 135.0, "residential"),
    ]
    ambiguous_after = [
        _fingerprint("new-a", 135.0, "residential"),
        _fingerprint("new-b", 135.0, "residential"),
    ]
    assert {row.change_type for row in diff_fingerprints(ambiguous_before, ambiguous_after)} == {
        "added",
        "removed",
    }


def test_incremental_plan_is_local_only_when_scope_is_proven_and_matches_full() -> None:
    changes = diff_fingerprints(
        [_fingerprint("building-1", 135.0, "residential")],
        [_fingerprint("building-1", 135.1, "residential")],
    )
    plan = plan_incremental_recomputation(
        changes, {"building-1": FeatureScope(mesh_codes=("53351362",))}
    )
    assert {(row.analysis_type, row.scope_type, row.scope_key) for row in plan} == {
        ("building_demographics", "building", "building-1"),
        ("mesh_metrics", "mesh", "53351362"),
    }
    assert incremental_matches_full(
        [{"mesh": "53351362", "population": 12.0}],
        [{"population": 12.0, "mesh": "53351362"}],
    )
    assert not incremental_matches_full(
        [{"mesh": "53351362", "population": 11.9}],
        [{"mesh": "53351362", "population": 12.0}],
    )


def test_future_state_requires_official_population_version_and_base_state() -> None:
    with pytest.raises(ValueError, match="base observed state"):
        UrbanStateDefinition(
            city_code="26202",
            state_key="2040-ipss",
            effective_date=date(2040, 10, 1),
            state_type="future",
            plateau_version="plateau-2025",
            population_version="ipss-2023-2040",
        )
