# Multi-tenancy model

## Current model

`organizations.id` is the tenant key. Every stable `/api/v1` repository method takes an
organization identifier first, and every mutable municipal table stores
`organization_id`. Cities are currently owned by one organization; city codes and keys
also remain globally unique for compatibility with the existing PLATEAU registry.

Authorization proceeds in this order:

1. verify development or OIDC identity;
2. require an organization claim/header;
3. in OIDC mode, confirm active database membership and role grants;
4. require the endpoint permission;
5. query the resource with `organization_id` and, where applicable, city;
6. enforce composite tenant foreign keys on write.

Cross-tenant object IDs return the same not-found response as nonexistent resources.
Offline IndexedDB entries also include organization and city keys and are filtered
before display.

## Database isolation decision

The current pilot uses application-enforced tenant predicates plus composite foreign
keys. PostgreSQL Row Level Security is not enabled because the service uses one pooled
database role and all supported access is through the API. This choice must be revisited
before permitting direct analyst SQL, multiple database roles, third-party BI access or
shared database access outside the service.

## Tenant-safe extension checklist

- add `organization_id NOT NULL`;
- add `UNIQUE (organization_id, id)` to referenced resources;
- add composite tenant foreign keys;
- make repository organization the first parameter;
- cover Organization A/B reads and writes in PostGIS integration tests;
- ensure audit, object storage keys, cache keys and local offline data retain tenant
  scope.
