from pathlib import Path

import yaml


def test_compose_keeps_static_demo_and_platform_services_separate() -> None:
    compose = yaml.safe_load(Path("docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert set(services) == {"postgres", "migrate", "api", "worker", "frontend"}
    assert services["postgres"]["image"].startswith("pgrouting/pgrouting:16-")
    assert "@sha256:" in services["postgres"]["image"]
    assert services["migrate"]["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert services["api"]["depends_on"]["migrate"]["condition"] == (
        "service_completed_successfully"
    )
    assert services["worker"]["depends_on"]["migrate"]["condition"] == (
        "service_completed_successfully"
    )
    assert services["frontend"]["ports"] == ["${CITYGAP_FRONTEND_PORT:-8080}:80"]
    assert services["api"]["environment"]["CITYGAP_API_SURFACE"] == (
        "${CITYGAP_API_SURFACE:-municipal}"
    )
    assert services["api"]["environment"]["CITYGAP_ATTACHMENT_PROVIDER"] == (
        "${CITYGAP_ATTACHMENT_PROVIDER:-local}"
    )
    assert services["api"]["environment"]["CITYGAP_APPLICATION_VERSION"] == (
        "${CITYGAP_APPLICATION_VERSION:-unversioned-development}"
    )
    assert services["worker"]["environment"]["CITYGAP_APPLICATION_VERSION"] == (
        "${CITYGAP_APPLICATION_VERSION:-unversioned-development}"
    )
    assert "citygap_artifacts:/app/var" in services["api"]["volumes"]


def test_raw_data_is_excluded_from_docker_build_context() -> None:
    dockerignore = Path(".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "data/raw" in dockerignore
    assert "analysis/outputs" in dockerignore
