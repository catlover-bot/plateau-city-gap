from __future__ import annotations

from backend.citygap_platform.open_data.standard_ods import canonicalize_rows, schema_audit


def test_standard_ods_canonicalization_keeps_lineage_and_excludes_contact_fields() -> None:
    values = {
        "ID": "hospital-1",
        "名称": "検証病院",
        "所在地_連結表記": "京都府舞鶴市検証1",
        "緯度": "35.4",
        "経度": "135.4",
        "医療機関の種類": "病院",
        "病床数": "20",
        "電話番号": "0773-00-0000",
        "連絡先メールアドレス": "private@example.invalid",
    }
    audit = schema_audit("262021_hospital", values)
    assert audit["status"] == "passed"
    records, quality = canonicalize_rows(
        dataset_id="262021_hospital",
        resource_id="resource-1",
        source_sha256="a" * 64,
        normalized_rows=({"source_row_locator": "row:2", "values": values},),
    )
    assert quality["canonical_records"] == 1
    record = records[0]
    assert record["external_record_id"] == "hospital-1"
    assert record["attributes"]["beds"] == 20
    assert record["geometry"]["coordinates"] == [135.4, 35.4]
    assert "電話番号" not in record["attributes"]
    assert "連絡先メールアドレス" not in record["attributes"]
    assert record["source"]["raw_sha256"] == "a" * 64


def test_standard_ods_rejects_missing_or_duplicate_official_identity_without_fabricating() -> None:
    rows = (
        {"source_row_locator": "row:2", "values": {"名称": "IDなし"}},
        {
            "source_row_locator": "row:3",
            "values": {"ID": "same", "名称": "施設A", "緯度": "35.4", "経度": "135.4"},
        },
        {
            "source_row_locator": "row:4",
            "values": {"ID": "same", "名称": "施設B", "緯度": "35.4", "経度": "135.4"},
        },
    )
    records, quality = canonicalize_rows(
        dataset_id="262021_hospital",
        resource_id="resource-1",
        source_sha256="b" * 64,
        normalized_rows=rows,
    )
    assert [item["external_record_id"] for item in records] == ["same"]
    assert [item["reason"] for item in quality["rejected_rows"]] == [
        "missing_official_identity",
        "duplicate_official_identity",
    ]


def test_population_identity_uses_two_official_key_fields_without_dropping_years() -> None:
    rows = tuple(
        {
            "source_row_locator": f"row:{index + 2}",
            "values": {
                "行政区コード": "area-1",
                "行政区名": "検証地区",
                "調査年月日": date,
                "計": total,
            },
        }
        for index, (date, total) in enumerate((("2022-04-01", "100"), ("2023-04-01", "98")))
    )
    records, quality = canonicalize_rows(
        dataset_id="262021_population",
        resource_id="population-resource",
        source_sha256="c" * 64,
        normalized_rows=rows,
    )
    assert quality["rejected_rows"] == []
    assert [item["external_record_id"] for item in records] == [
        "area-1|2022-04-01",
        "area-1|2023-04-01",
    ]
