from backend.citygap_platform.open_data.health import (
    canonicalize_care_rows,
    canonicalize_medical_facilities,
    canonicalize_medical_services,
    care_schema_audit,
    compare_facility_identities,
    medical_schema_audit,
)


def _row(locator: str, **values: str) -> dict:
    return {"source_row_locator": locator, "values": values}


def test_medical_facility_and_department_keep_real_time_availability_unknown() -> None:
    facilities, quality = canonicalize_medical_facilities(
        resource_code="01-1",
        resource_id="hospital.zip",
        raw_sha256="a" * 64,
        reference_date="2026-06-01",
        city_code="26202",
        normalized_rows=(
            _row(
                "row:2",
                ID="medical-1",
                正式名称="公式病院",
                都道府県コード="26",
                市区町村コード="202",
                所在地="京都府舞鶴市テスト1",
                **{
                    "所在地座標（緯度）": "35.47",
                    "所在地座標（経度）": "135.39",
                    "合計病床数": "100",
                    "毎週決まった曜日に休診（日）": "1",
                    "案内用ホームページアドレス": "https://example.invalid/",
                },
            ),
            _row(
                "row:3",
                ID="outside",
                正式名称="市外病院",
                都道府県コード="26",
                市区町村コード="201",
                所在地="京都市",
                **{"所在地座標（緯度）": "35", "所在地座標（経度）": "135"},
            ),
        ),
    )
    assert quality["canonical_records"] == 1
    assert facilities[0]["attributes"]["current_acceptance"] == "unknown"
    assert facilities[0]["attributes"]["published_total_beds"] == 100
    assert facilities[0]["attributes"]["published_schedule"] == {
        "毎週決まった曜日に休診（日）": "1"
    }

    services, service_quality = canonicalize_medical_services(
        resource_code="01-2",
        resource_id="hours.zip",
        raw_sha256="b" * 64,
        reference_date="2026-06-01",
        facility_ids={"medical-1": facilities[0]},
        normalized_rows=(
            _row(
                "row:2",
                ID="medical-1",
                診療科目コード="01",
                診療科目名="内科",
                診療時間帯="1",
                月_診療開始時間="09:00",
            ),
        ),
    )
    assert service_quality["canonical_records"] == 1
    assert services[0]["attributes"]["current_availability"] == "unknown"
    assert services[0]["attributes"]["published_schedule"] == {"月_診療開始時間": "09:00"}
    assert services[0]["spatial_links"][0]["match_method"] == "exact"


def test_care_canonicalization_keeps_official_category_capacity_and_eligibility_separate() -> None:
    records, quality = canonicalize_care_rows(
        service_code="150",
        resource_id="care.csv",
        raw_sha256="c" * 64,
        reference_date="2026-06-30",
        city_code="14205",
        normalized_rows=(
            _row(
                "row:2",
                都道府県コード又は市町村コード="142051",
                事業所番号="1470000001",
                事業所名="公式通所介護",
                サービスの種類="通所介護",
                住所="藤沢市テスト1",
                緯度="35.33",
                経度="139.49",
                定員="20",
                利用可能曜日="平日",
            ),
        ),
    )
    assert quality["facility_records"] == quality["service_offering_records"] == 1
    facility, service = records
    assert facility["attributes"]["published_capacity"] == 20
    assert facility["attributes"]["current_capacity"] == "unknown"
    assert service["attributes"]["official_service_code"] == "150"
    assert service["attributes"]["user_eligibility"] == "unknown"


def test_health_schema_audits_reject_semantic_drift() -> None:
    assert (
        medical_schema_audit(
            "01-1",
            (
                "ID",
                "正式名称",
                "都道府県コード",
                "市区町村コード",
                "所在地",
                "所在地座標（緯度）",
                "所在地座標（経度）",
            ),
        )["status"]
        == "passed"
    )
    assert medical_schema_audit("01-2", ("ID", "診療科目名"))["status"] == "failed"
    assert care_schema_audit(("事業所番号", "事業所名"))["status"] == "failed"


def test_identity_comparison_never_promotes_name_only_to_matched() -> None:
    primary = {
        "canonical_id": "mhlw-medical:hospital:1",
        "external_record_id": "mhlw-1",
        "display_name": "舞鶴共済病院",
        "attributes": {"address": "京都府舞鶴市浜1035"},
        "geometry": {"type": "Point", "coordinates": [135.4, 35.47]},
    }
    probable = compare_facility_identities(
        (primary,),
        (
            {
                "source": "municipal-ods",
                "reference_id": "A1",
                "official_ids": (),
                "name": "舞鶴共済病院",
                "address": "京都府舞鶴市浜1035",
                "geometry": {"type": "Point", "coordinates": [135.4, 35.47]},
            },
        ),
    )[0]
    assert probable["status"] == "probable"
    matched = compare_facility_identities(
        (primary,),
        (
            {
                "source": "verified-official-id-source",
                "reference_id": "B1",
                "official_ids": ("mhlw-1",),
                "name": "別名",
                "address": "別住所",
                "geometry": None,
            },
        ),
    )[0]
    assert matched["status"] == "matched"
