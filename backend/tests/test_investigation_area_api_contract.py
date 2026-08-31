from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.citygap_platform.api.app import create_app
from backend.citygap_platform.api.service import InvestigationAreaCreateRequest


class NoopRepository:
    pass


def test_investigation_area_routes_are_on_the_stable_v1_surface() -> None:
    paths = create_app(repository=NoopRepository()).openapi()["paths"]
    expected = {
        "/api/v1/investigations/{investigation_id}/areas": {"get", "post"},
        "/api/v1/investigation-areas/{area_id}": {"get"},
        "/api/v1/investigation-areas/{area_id}/analyses": {"post"},
        "/api/v1/investigation-areas/{area_id}/summary": {"get"},
    }
    for path, methods in expected.items():
        assert methods <= set(paths[path])


def test_map_point_and_station_share_point_radius_without_client_station_coordinates() -> None:
    map_point = InvestigationAreaCreateRequest.model_validate(
        {
            "geometry_kind": "point_radius",
            "label": "任意地点800m",
            "origin": {"kind": "map_point", "coordinates": [135.3305, 35.4417]},
            "radius_m": 800,
            "radius_methodology": "mlit_general_walk_reference_800m",
        }
    )
    assert map_point.origin is not None
    assert map_point.origin.kind == "map_point"

    station = InvestigationAreaCreateRequest.model_validate(
        {
            "geometry_kind": "point_radius",
            "label": "西舞鶴駅800m",
            "origin": {
                "kind": "station",
                "source_dataset_version_id": "70000000-0000-0000-0000-000000000001",
                "source_feature_id": "station-007",
            },
            "radius_m": 800,
            "radius_methodology": "mlit_general_walk_reference_800m",
        }
    )
    assert station.origin is not None
    assert station.origin.coordinates is None

    with pytest.raises(ValidationError):
        InvestigationAreaCreateRequest.model_validate(
            {
                "geometry_kind": "point_radius",
                "label": "untrusted station",
                "origin": {
                    "kind": "station",
                    "coordinates": [135.3305, 35.4417],
                    "source_dataset_version_id": "70000000-0000-0000-0000-000000000001",
                    "source_feature_id": "station-007",
                },
                "radius_m": 800,
                "radius_methodology": "mlit_general_walk_reference_800m",
            }
        )


@pytest.mark.parametrize(
    ("radius", "methodology"),
    [
        (99, "custom_radius"),
        (3001, "custom_radius"),
        (800, "custom_radius"),
        (500, "mlit_general_walk_reference_800m"),
    ],
)
def test_api_rejects_unsafe_or_mislabeled_radius(radius: int, methodology: str) -> None:
    with pytest.raises(ValidationError):
        InvestigationAreaCreateRequest.model_validate(
            {
                "geometry_kind": "point_radius",
                "label": "invalid radius",
                "origin": {"kind": "map_point", "coordinates": [135.33, 35.44]},
                "radius_m": radius,
                "radius_methodology": methodology,
            }
        )


def test_repository_requires_versioned_city_boundary_and_official_station_resolution() -> None:
    source = Path("backend/citygap_platform/api/service_repository.py").read_text(
        encoding="utf-8"
    )
    assert "attributes->>'boundary_kind' = 'municipal_boundary'" in source
    assert "attributes->>'boundary_kind' = 'census_2020_small_area'" in source
    assert "record_type = 'transport_node'" in source
    assert "external_record_id = %s" in source
    assert "build_point_radius_geometry" in source
    assert "citygap.area-summary@1" in source
    assert "AWAITING_DETERMINISTIC_ANALYSIS" in source
    assert "actual walking-time isochrone" in source
