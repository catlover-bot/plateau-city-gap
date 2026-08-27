import hashlib
import json
from pathlib import Path

from analysis.scripts.export_scenario_comparison_evidence import DEFAULT_PLANS, export
from backend.citygap_platform.ingestion.evidence import validate_evidence_manifest


def test_evidence_v2_exports_three_unranked_plans_and_print_sections(tmp_path: Path) -> None:
    manifest = export(DEFAULT_PLANS, tmp_path)
    package = json.loads((tmp_path / "comparison.json").read_text(encoding="utf-8"))
    rendered = (tmp_path / "print.html").read_text(encoding="utf-8")
    assert manifest["schema_version"] == "2.0.0"
    assert manifest["recommendation"] is None
    assert [item["comparison_label"] for item in package["comparison"]] == ["A", "B", "C"]
    assert package["review_boundary"]["preferred_scenario"] is None
    for heading in (
        "前提とデータ年",
        "A/B/C 比較",
        "候補位置・計画・災害",
        "候補位置図",
        "道路network caveat",
        "現地確認",
        "Provenance / Algorithm",
        "Limitations",
    ):
        assert heading in rendered
    assert "<svg" in rendered
    for name, detail in manifest["formats"].items():
        artifact = tmp_path / ("comparison.json" if name == "json" else "print.html")
        assert detail["sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()


def test_tracked_evidence_v2_manifest_resolves_exact_artifacts_and_versions() -> None:
    manifest, artifacts, dataset_key, plan_ids = validate_evidence_manifest(
        Path("analysis/outputs/real/evidence_packages/scenario-comparison-v2/manifest.json")
    )
    assert manifest["recommendation"] is None
    assert set(artifacts) == {"json", "html"}
    assert dataset_key.startswith("26202:2025:")
    assert plan_ids == DEFAULT_PLANS
