import hashlib
import json
from pathlib import Path

from analysis.scripts.export_scenario_comparison_evidence import DEFAULT_PLANS, export


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
