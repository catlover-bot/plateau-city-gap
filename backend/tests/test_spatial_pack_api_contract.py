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
