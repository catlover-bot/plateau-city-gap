import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "analysis/outputs/real"


def _rank_one(city: str) -> dict[str, str]:
    with (REAL / f"{city}_city_gap_top10.csv").open(encoding="utf-8", newline="") as stream:
        return next(csv.DictReader(stream))


def test_presentation_facts_match_published_outputs() -> None:
    facts = (ROOT / "docs/presentation-facts.md").read_text(encoding="utf-8")
    audit = json.loads((REAL / "final_audit.json").read_text(encoding="utf-8"))
    maizuru = _rank_one("maizuru")
    fujisawa = _rank_one("fujisawa")

    assert maizuru["mesh_code"] == "533512753"
    assert int(float(maizuru["population"])) == 91
    assert int(float(maizuru["elderly_population"])) == 56
    assert fujisawa["mesh_code"] == "533913073"
    assert int(float(fujisawa["population"])) == 3590
    assert int(float(fujisawa["elderly_population"])) == 921

    assert audit["what_if"]["exact_match"] is True
    assert audit["what_if"]["reproduced"]["affected_elderly_population"] == 241
    assert (
        audit["cities"]["fujisawa"]["facility_audit"]
        ["boundary_sensitivity_excluding_uncertain_medical"]["top10_overlap_with_primary"]
        == 7
    )

    for required_text in (
        "2.32km",
        "3.32km",
        "3,590人 / 921人",
        "交通346m、医療506m",
        "241人は利用者、受益者、需要、乗客の予測ではありません",
    ):
        assert required_text in facts


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
