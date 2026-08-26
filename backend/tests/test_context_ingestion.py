from __future__ import annotations

from typing import Any

from backend.citygap_platform.ingestion.citygml import FeatureEnd
from backend.citygap_platform.ingestion.context import context_config_hash
from backend.citygap_platform.ingestion.postgis import _insert_typed_row


class RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def execute(self, sql: str, parameters: tuple[Any, ...]) -> None:
        self.calls.append((sql, parameters))


def test_typed_ingestion_uses_actual_hazard_rank_fields_and_feature_type() -> None:
    connection = RecordingConnection()
    _insert_typed_row(
        connection,
        "fld",
        10,
        "WaterBody",
        FeatureEnd(attributes={"rankOrg": "3", "description": "9"}),
    )
    assert connection.calls[-1][1] == (10, "flood", "3", None, None)

    _insert_typed_row(
        connection,
        "lsld",
        11,
        "SedimentDisasterProneArea",
        FeatureEnd(attributes={"areaType": "2", "disasterType": "1"}),
    )
    assert connection.calls[-1][1] == (11, "landslide", "2", None, None)

    _insert_typed_row(
        connection,
        "urf",
        12,
        "UseDistrict",
        FeatureEnd(attributes={"function": "11", "name": "用途地域"}),
    )
    assert connection.calls[-1][1][1] == "UseDistrict"


def test_context_config_hash_is_canonical_and_version_sensitive() -> None:
    summary = {
        "algorithm_version": "plateau-context-1.0.0",
        "dataset": {
            "archive_sha256": "a" * 64,
            "analysis_crs": "EPSG:6674",
        },
        "targets": {"census_meshes": 495},
        "hazard_interpretation": {"overlap_means": "additional_confirmation_required"},
    }
    first = context_config_hash(summary)
    assert first == context_config_hash(dict(reversed(list(summary.items()))))
    changed = {**summary, "algorithm_version": "plateau-context-2.0.0"}
    assert first != context_config_hash(changed)
    assert len(first) == 64
