import pytest
from fastapi.testclient import TestClient

from backend.citygap_platform.api.app import create_app
from backend.citygap_platform.security.auth import AuthSettings


class OidcRepo:
    def cities(self):
        return []


def test_development_auth_cannot_start_in_pilot_or_production() -> None:
    for environment in ("pilot", "production"):
        with pytest.raises(RuntimeError, match="Development authentication is forbidden"):
            AuthSettings(environment=environment, mode="development").validate()


def test_oidc_mode_requires_issuer_and_audience_and_never_decodes_unverified_token() -> None:
    with pytest.raises(RuntimeError, match="OIDC mode requires"):
        AuthSettings(environment="production", mode="oidc").validate()
    settings = AuthSettings(
        environment="production",
        mode="oidc",
        oidc_issuer="https://identity.example.invalid",
        oidc_audience="citygap",
    )
    settings.validate()
    client = TestClient(create_app(OidcRepo(), auth_settings=settings))  # type: ignore[arg-type]
    assert client.get("/cities", headers={"Authorization": "Bearer unsigned.jwt.value"}).status_code == 401
