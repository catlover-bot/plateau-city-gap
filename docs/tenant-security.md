# Tenant security and threat model

## Protected assets

Municipal identities, investigation notes, restricted attachments, unpublished spatial
views, building-level estimates, Decision Records, source files and audit history are
protected assets.

## Principal threats and controls

| Threat | Control |
| --- | --- |
| Cross-tenant ID enumeration | organization predicate on every `/api/v1` query; uniform 404 |
| Forged OIDC role | signature/audience/issuer verifier plus active membership lookup |
| Development headers in production | startup validation rejects development auth in pilot/production |
| Cross-tenant write reference | composite `(organization_id, id)` foreign keys |
| Path traversal through attachment name | server-generated object key; plain filename validation; storage-root containment |
| Oversized upload | content-length gate plus streaming byte counter; 25 MiB attachment cap |
| Content confusion | explicit MIME allow-list and `nosniff` download header |
| Offline silent overwrite | record version, idempotent client operation and explicit 409 conflict |
| Public data leakage | separate deployment surface and classification-gated exports |
| Audit tampering | immutable audit trigger and Administrator-only tenant API |
| Secret disclosure | API allow-list plus recursive secret-bearing key rejection; DB key guard |

## Attachment model

Authorization metadata is read from PostGIS before bytes are opened. Local storage keys
are generated as organization/city/random UUID and never use the uploaded filename. The
local volume is the implemented provider. `s3_compatible` is an explicit unavailable
boundary until a client and credentials are supplied; credentials are never persisted in
organization configuration.

## Residual risks

The pilot does not yet provide database RLS, malware scanning, customer-managed
encryption keys or a production S3 adapter. Shared-device browser storage needs the
municipality's device/session policy. These are production acceptance items, not
features to claim as complete.
