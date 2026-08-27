from __future__ import annotations

from io import BytesIO

import pandas as pd

from analysis.src.temporal_validation import (
    classify_version_diff,
    incremental_rebuild_check,
    iter_citygml_features,
)


def test_streaming_feature_hashes_and_diff_are_deterministic() -> None:
    xml = b'''<core:CityModel xmlns:core="http://www.opengis.net/citygml/2.0"
      xmlns:gml="http://www.opengis.net/gml" xmlns:bldg="http://www.opengis.net/citygml/building/2.0">
      <core:cityObjectMember><bldg:Building gml:id="b-1">
        <bldg:usage>411</bldg:usage><gml:posList srsDimension="3">35 139 0 35 139.001 0</gml:posList>
      </bldg:Building></core:cityObjectMember></core:CityModel>'''
    rows = list(
        iter_citygml_features(
            BytesIO(xml), theme="bldg", source_member="udx/bldg/a.gml", source_member_crc32="abc"
        )
    )
    assert len(rows) == 1
    assert rows[0]["feature_id"] == "b-1"
    assert rows[0]["coordinate_count"] == 2

    old = pd.DataFrame(rows)
    new = old.copy()
    new.loc[0, "attribute_hash"] = "changed"
    diff = classify_version_diff(old, new)
    assert diff["counts"]["attribute_changed"] == 1
    assert diff["match_audit"]["same_gml_id_count"] == 1
    rebuild = incremental_rebuild_check(old, new)
    assert rebuild["count_agreement"] is True
    assert rebuild["hash_agreement"] is True


def test_ambiguous_hash_candidates_are_not_forced() -> None:
    old = pd.DataFrame(
        [
            {"feature_id": "o1", "feature_type": "Road", "geometry_hash": "same", "attribute_hash": "a", "centroid_lon": 139.0, "centroid_lat": 35.0, "bbox": None},
            {"feature_id": "o2", "feature_type": "Road", "geometry_hash": "same", "attribute_hash": "b", "centroid_lon": 139.0, "centroid_lat": 35.0, "bbox": None},
        ]
    )
    new = pd.DataFrame(
        [
            {"feature_id": "n1", "feature_type": "Road", "geometry_hash": "same", "attribute_hash": "c", "centroid_lon": 139.0, "centroid_lat": 35.0, "bbox": None},
            {"feature_id": "n2", "feature_type": "Road", "geometry_hash": "same", "attribute_hash": "d", "centroid_lon": 139.0, "centroid_lat": 35.0, "bbox": None},
        ]
    )
    result = classify_version_diff(old, new)
    assert result["match_audit"]["matched_count"] == 0
    assert result["match_audit"]["ambiguous_old_count"] == 2
    assert result["counts"]["added"] == 2
    assert result["counts"]["removed"] == 2
