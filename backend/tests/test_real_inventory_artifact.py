import json
from pathlib import Path


def test_maizuru_full_inventory_is_complete_and_self_consistent() -> None:
    inventory = json.loads(
        Path("analysis/outputs/real/maizuru_plateau_inventory.json").read_text(encoding="utf-8")
    )

    assert inventory["archive"]["sha256"] == (
        "13f4020ade066dc7139b7653c47a55a09af0093dee743f6b9cca5d3177a71cff"
    )
    assert inventory["archive"]["citygml_file_count"] == 369
    assert inventory["dataset"]["product_specification_version"] == "5.0"
    assert inventory["dataset"]["ade_schema_versions"] == ["3.2"]
    assert inventory["totals"] == {
        "duplicate_gml_id_count": 0,
        "feature_count": 97_140,
        "parse_seconds": inventory["totals"]["parse_seconds"],
        "unique_gml_id_count": 97_140,
    }
    assert {theme: value["feature_count"] for theme, value in inventory["themes"].items()} == {
        "bldg": 44_640,
        "dem": 23,
        "fld": 666,
        "lsld": 4_643,
        "luse": 31_067,
        "tnm": 23,
        "tran": 15_684,
        "urf": 394,
    }
    assert inventory["themes"]["dem"]["lod_feature_counts"] == {"1": 23}
