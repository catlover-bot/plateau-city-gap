from pathlib import Path

from backend.citygap_platform.api.app import create_app


class NoopRepository:
    pass


def test_spatial_pack_routes_are_present_on_stable_v1_surface() -> None:
    paths = create_app(repository=NoopRepository()).openapi()["paths"]
    expected = {
        "/api/v1/investigations/{investigation_id}/spatial-packs": "post",
        "/api/v1/spatial-packs/{pack_id}": "get",
        "/api/v1/spatial-packs/{pack_id}/manifest": "get",
        "/api/v1/spatial-packs/{pack_id}/objects": "get",
        "/api/v1/spatial-packs/{pack_id}/sections": "get",
        "/api/v1/spatial-packs/{pack_id}/refresh": "post",
    }
    for path, method in expected.items():
        assert method in paths[path]
    object_parameters = paths["/api/v1/spatial-packs/{pack_id}/objects"]["get"]["parameters"]
    limit = next(parameter for parameter in object_parameters if parameter["name"] == "limit")
    assert limit["schema"]["maximum"] == 200


def test_spatial_pack_bbox_queries_use_the_supported_postgis_box3d_signature() -> None:
    source = Path("backend/citygap_platform/api/service_repository.py").read_text(
        encoding="utf-8"
    )
    assert "ST_Box3D" not in source
    assert "CAST(%s AS text) IS NULL OR object_type=%s" in source
