# Authentication, RBAC and audit

CITY GAP separates identity verification from authorization. The application has two
explicit authentication modes:

- `development`: bounded identity and roles are supplied through
  `X-CITYGAP-Actor` and `X-CITYGAP-Roles`. It defaults to a local administrator so a
  clone can be explored without an external identity service.
- `oidc`: requires issuer, audience and an injected token verifier. The platform never
  decodes or trusts an unverified JWT. Municipal deployment must provide the verifier
  and identity-provider configuration.

`CITYGAP_ENVIRONMENT=pilot` or `production` refuses to start with development auth.
This guard prevents convenient local headers from silently becoming production auth.

## Roles

| Role | Read | Run analysis / draft | Review / field check | Dataset, roles, platform |
|---|---:|---:|---:|---:|
| viewer | yes | no | no | no |
| analyst | yes | yes | no | no |
| planner | yes | yes | yes | no |
| administrator | yes | yes | yes | yes |

City-scoped grants are stored in `platform_user_roles`. The current HTTP boundary
enforces analyst permission for job creation, planner permission for scenario lifecycle
and field checks, and administrator permission for platform job transitions and audit
access. Read routes remain available to authenticated viewers.

## Audit evidence

`audit_log` is append-only application evidence containing actor, action, resource,
timestamp, before/after state and request ID. Scenario transitions, field checks and job
creation/transitions write audit rows in the same database transaction as the mutation.
`GET /admin/audit` is administrator-only. Audit data records human/platform actions; it
must not be interpreted as a policy recommendation.

Request logs are structured JSON and include request ID, actor, city, job/scenario,
duration and result. Authorization headers, request bodies, database URLs and secrets
are not logged.
