# Municipal service deployment

## Surfaces

- `CITYGAP_API_SURFACE=municipal`: exposes `/api/v1`, health/readiness and matching
  OpenAPI only.
- `CITYGAP_API_SURFACE=public-showcase`: exposes read-only non-service routes and a
  read-only OpenAPI surface.
- `combined`: development and backward-compatibility mode; do not use as the default
  municipal deployment.

The Docker Compose frontend selects the municipal product. GitHub Pages remains the
independent public showcase.

## Required production settings

- `CITYGAP_ENVIRONMENT=pilot` or `production`
- `CITYGAP_AUTH_MODE=oidc`
- `CITYGAP_OIDC_ISSUER` and `CITYGAP_OIDC_AUDIENCE`
- database URL from the deployment secret provider
- durable attachment volume and `CITYGAP_ATTACHMENT_PROVIDER=local`, or a completed
  reviewed S3-compatible adapter
- worker and API replicas with the same release and migration version

Development authentication is rejected at startup in pilot/production. Do not store
secrets in repository files or organization configuration.

## Deployment order

1. backup and record the backup run;
2. run forward-only migrations once;
3. run schema/integrity smoke checks;
4. deploy API and worker;
5. deploy the municipal frontend with the matching API contract;
6. verify health, readiness, worker heartbeat, required city data and object storage;
7. record the service release and rollback reference.

PostGIS and pgRouting integration tests run in CI. A workstation without Docker cannot
substitute static SQL inspection for that execution evidence.
