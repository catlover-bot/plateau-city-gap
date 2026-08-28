import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "analysis/outputs/real"

def test_current_public_facts_match_published_outputs() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs/architecture.md").read_text(encoding="utf-8")
    plateau = json.loads(
        (ROOT / "frontend/public/data/plateau_metadata.json").read_text(encoding="utf-8")
    )
    maizuru = json.loads((REAL / "maizuru_summary.json").read_text(encoding="utf-8"))
    fujisawa = json.loads((REAL / "fujisawa_summary.json").read_text(encoding="utf-8"))

    assert maizuru["record_counts"]["population_meshes_intersecting_city"] == 495
    assert fujisawa["record_counts"]["population_meshes_intersecting_city"] == 327
    assert plateau["building_layer"]["source_distribution_unique_buildings"] == 44_640
    assert plateau["building_layer"]["records"] == 0
    assert plateau["reference_layer"]["records"] == 856
    assert plateau["reference_layer"]["deep_dive_buildings"] == 296
    assert plateau["reference_layer"]["deep_dive_mesh_code"] == "533513314"

    for required_text in (
        "舞鶴市495メッシュと藤沢市327メッシュ",
        "全市配信44,640建物",
        "検証済み856棟subset",
        "対象メッシュ内296棟",
        "Top 10メッシュの公式建物coverageは0棟",
        "モデル推計配分であり、実居住者数ではありません",
        "experimental PLATEAU LOD1 road-surface adjacency",
        "DEMから歩行負荷・危険度・斜度を推定しません",
    ):
        assert required_text in readme

    assert "Finding ─ derived from → metric + source + method + limitation" in architecture
    assert "city → district → mesh → building_group → building → road → site" in architecture


def test_final_audit_records_metric_medical_and_border_sensitivities() -> None:
    audit = json.loads((REAL / "final_audit.json").read_text(encoding="utf-8"))
    maizuru = audit["cities"]["maizuru"]
    fujisawa = audit["cities"]["fujisawa"]

    assert maizuru["score_audit"]["stored_score_c_max_abs_error"] < 1e-12
    assert fujisawa["score_audit"]["stored_score_c_max_abs_error"] < 1e-12
    assert maizuru["score_audit"]["variants"]["B_elderly_ratio_transport_medical"]["top10_overlap_with_A"] == 3
    assert fujisawa["score_audit"]["variants"]["B_elderly_ratio_transport_medical"]["A_rank_one_position"] == 23

    assert maizuru["facility_audit"]["access_class_counts"]["uncertain_access"] == 6
    assert fujisawa["facility_audit"]["access_class_counts"]["uncertain_access"] == 13
    assert fujisawa["facility_audit"]["medical_sensitivity"]["C_hospital_only"]["primary_rank_one_position"] == 14

    raw_border = fujisawa["facility_audit"]["boundary_sensitivity"]
    conservative_border = fujisawa["facility_audit"]["boundary_sensitivity_excluding_uncertain_medical"]
    assert raw_border["outside_city_bus_stops_added"] == 660
    assert raw_border["outside_city_medical_added"] == 272
    assert raw_border["primary_rank_one_position"] == 32
    assert conservative_border["primary_rank_one_position"] == 1
    assert conservative_border["top10_overlap_with_primary"] == 7
