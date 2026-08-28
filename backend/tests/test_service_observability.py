from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.citygap_platform.observability import (
    render_request_metrics,
    request_observability_middleware,
    reset_request_metrics,
)


def test_request_metrics_use_route_templates_instead_of_resource_ids() -> None:
    reset_request_metrics()
    app = FastAPI()
    app.middleware("http")(request_observability_middleware)

    @app.get("/resources/{resource_id}")
    def resource(resource_id: str) -> dict[str, str]:
        return {"id": resource_id}

    client = TestClient(app)
    assert client.get("/resources/private-id-1").status_code == 200
    assert client.get("/resources/private-id-2").status_code == 200
    metrics = render_request_metrics()
    assert 'route="/resources/{resource_id}"' in metrics
    assert "private-id-1" not in metrics
    assert "private-id-2" not in metrics
    assert metrics.count("citygap_http_requests_total{") == 1
