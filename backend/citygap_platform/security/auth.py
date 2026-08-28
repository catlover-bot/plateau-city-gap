"""Explicit development identity and an OIDC verification boundary.

OIDC tokens must be verified by an injected verifier.  The platform deliberately does
not decode unverified JWT claims and never presents development headers as production
authentication.
"""

from __future__ import annotations

import os
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import HTTPException, Request

DEFAULT_ORGANIZATION_ID = "00000000-0000-0000-0000-000000000001"
ROLES = frozenset({"viewer", "analyst", "planner", "field_staff", "data_manager", "administrator"})
ROLE_PERMISSIONS = {
    "viewer": frozenset(
        {
            "platform:read",
            "activity:read",
            "analysis:read",
            "dataset:read",
            "evidence:read",
            "field:read",
            "finding:read",
            "investigation:read",
            "review:read",
            "scenario:read",
        }
    ),
    "analyst": frozenset(
        {
            "platform:read",
            "activity:read",
            "analysis:read",
            "analysis:run",
            "comment:write",
            "dataset:read",
            "evidence:read",
            "field:read",
            "finding:read",
            "finding:write",
            "investigation:read",
            "investigation:write",
            "review:read",
            "scenario:read",
            "scenario:draft",
            "stress_test:create",
            "validation:run",
        }
    ),
    "planner": frozenset(
        {
            "platform:read",
            "activity:read",
            "analysis:read",
            "analysis:run",
            "assignment:write",
            "comment:write",
            "decision:write",
            "dataset:read",
            "evidence:read",
            "evidence:export",
            "field:read",
            "finding:read",
            "finding:write",
            "investigation:read",
            "investigation:write",
            "report:create",
            "review:read",
            "review:write",
            "scenario:read",
            "scenario:draft",
            "scenario:review",
            "stress_test:create",
            "outcome:review",
            "field:write",
            "field:sync",
            "validation:run",
            "validation:review",
        }
    ),
    "field_staff": frozenset(
        {
            "platform:read",
            "activity:read",
            "analysis:read",
            "comment:write",
            "dataset:read",
            "evidence:read",
            "field:read",
            "field:write",
            "field:sync",
            "finding:read",
            "investigation:read",
            "scenario:read",
        }
    ),
    "data_manager": frozenset(
        {
            "platform:read",
            "activity:read",
            "analysis:read",
            "comment:write",
            "dataset:read",
            "dataset:register",
            "dataset:validate",
            "dataset:accept",
            "dataset:promote",
            "evidence:read",
            "finding:read",
            "investigation:read",
            "scenario:read",
            "validation:reference:register",
            "validation:run",
        }
    ),
    "administrator": frozenset({"*"}),
}
SAFE_ACTOR = re.compile(r"^[A-Za-z0-9._:@+-]{1,200}$")


@dataclass(frozen=True, slots=True)
class Identity:
    actor: str
    issuer: str
    roles: frozenset[str]
    organization_id: str | None = None

    def permits(self, permission: str) -> bool:
        return any(
            "*" in ROLE_PERMISSIONS.get(role, frozenset())
            or permission in ROLE_PERMISSIONS.get(role, frozenset())
            for role in self.roles
        )


@dataclass(frozen=True, slots=True)
class AuthSettings:
    environment: str
    mode: str
    oidc_issuer: str | None = None
    oidc_audience: str | None = None

    @classmethod
    def from_environment(cls) -> AuthSettings:
        settings = cls(
            environment=os.getenv("CITYGAP_ENVIRONMENT", "development").lower(),
            mode=os.getenv("CITYGAP_AUTH_MODE", "development").lower(),
            oidc_issuer=os.getenv("CITYGAP_OIDC_ISSUER"),
            oidc_audience=os.getenv("CITYGAP_OIDC_AUDIENCE"),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.environment in {"production", "pilot"} and self.mode == "development":
            raise RuntimeError("Development authentication is forbidden in pilot/production")
        if self.mode not in {"development", "oidc"}:
            raise RuntimeError(f"Unsupported CITYGAP_AUTH_MODE: {self.mode}")
        if self.mode == "oidc" and (not self.oidc_issuer or not self.oidc_audience):
            raise RuntimeError("OIDC mode requires CITYGAP_OIDC_ISSUER and CITYGAP_OIDC_AUDIENCE")


OidcVerifier = Callable[[str, str, str], Identity]


def resolve_identity(
    request: Request,
    settings: AuthSettings,
    oidc_verifier: OidcVerifier | None = None,
) -> Identity:
    if settings.mode == "development":
        actor = request.headers.get("X-CITYGAP-Actor", "local-administrator")
        raw_roles = request.headers.get("X-CITYGAP-Roles", "administrator")
        organization_id = request.headers.get("X-CITYGAP-Organization", DEFAULT_ORGANIZATION_ID)
        roles = frozenset(role.strip() for role in raw_roles.split(",") if role.strip())
        try:
            parsed_organization_id = str(uuid.UUID(organization_id))
        except ValueError as error:
            raise HTTPException(
                status_code=401, detail="Invalid development identity headers"
            ) from error
        if not SAFE_ACTOR.fullmatch(actor) or not roles or not roles <= ROLES:
            raise HTTPException(status_code=401, detail="Invalid development identity headers")
        return Identity(
            actor=actor,
            issuer="citygap-development",
            roles=roles,
            organization_id=parsed_organization_id,
        )

    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer ") or not oidc_verifier:
        raise HTTPException(status_code=401, detail="A verified OIDC bearer token is required")
    identity = oidc_verifier(
        authorization.removeprefix("Bearer ").strip(),
        settings.oidc_issuer or "",
        settings.oidc_audience or "",
    )
    if not identity.roles or not identity.roles <= ROLES:
        raise HTTPException(status_code=401, detail="Verified identity contains invalid roles")
    return identity


def require_permission(permission: str):
    def dependency(request: Request) -> Identity:
        identity: Identity | None = getattr(request.state, "identity", None)
        if identity is None:
            raise HTTPException(status_code=401, detail="Identity unavailable")
        if not identity.permits(permission):
            raise HTTPException(status_code=403, detail=f"Permission required: {permission}")
        return identity

    return dependency


def require_organization(request: Request) -> str:
    """Require the verified tenant claim used by every municipal-service route."""

    identity: Identity | None = getattr(request.state, "identity", None)
    if identity is None:
        raise HTTPException(status_code=401, detail="Identity unavailable")
    if identity.organization_id is None:
        raise HTTPException(status_code=403, detail="Organization context is required")
    try:
        return str(uuid.UUID(identity.organization_id))
    except ValueError as error:
        raise HTTPException(status_code=403, detail="Organization context is invalid") from error
