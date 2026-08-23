from pathlib import Path

import yaml


def test_compose_keeps_static_demo_and_platform_services_separate() -> None:
    compose = yaml.safe_load(Path("docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert set(services) == {"postgres", "api", "frontend"}
    assert services["postgres"]["image"].startswith("pgrouting/pgrouting:16-")
    assert "./infra/migrations:/docker-entrypoint-initdb.d:ro" in services["postgres"]["volumes"]
    assert services["api"]["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert services["frontend"]["ports"] == ["${CITYGAP_FRONTEND_PORT:-8080}:80"]


def test_raw_data_is_excluded_from_docker_build_context() -> None:
    dockerignore = Path(".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "data/raw" in dockerignore
    assert "analysis/outputs" in dockerignore
