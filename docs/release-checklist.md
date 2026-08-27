# v0.x pilot release checklist

This checklist creates a pre-production municipal pilot artifact. It must not be labelled a formal production release.

## Source and CI

- [ ] Main is protected, clean and points at the reviewed commit; no force-push.
- [ ] Unit, frontend, security, public-assets, migration, API integration, PostGIS integration and container build jobs pass.
- [ ] Python/frontend dependency audits and tracked-secret/raw-data checks pass.
- [ ] Ten checksummed migrations apply to a new database and an upgrade rehearsal copy.
- [ ] API/worker/frontend images are built from the release commit and identified by immutable digest.

## Pilot instance

- [ ] Municipality-approved PLATEAU, population and facility dataset versions are registered with hashes/licenses.
- [ ] Quality gate passes and affected-analysis output is reviewed after every update.
- [ ] Network source/version and its pedestrian/experimental boundary are accepted.
- [ ] OIDC signature verifier is integration-tested; role assignments are approved.
- [ ] Encrypted off-host backup and isolated restore drill succeed; retention/RPO/RTO are owned externally.
- [ ] `citygap readiness --city CITY_CODE` has no blocker; limitations are signed off.
- [ ] 100k synthetic benchmark and pilot-hardware real API benchmark reports are attached with labels.

## Review workflow

- [ ] Draft → review → field-check → reviewed/archived history and audit retrieval are rehearsed.
- [ ] Field checklist, HTTPS photo references and notes follow municipal information policy.
- [ ] Evidence Package V2 A/B/C print output is reviewed; recommendation remains null.
- [ ] Public bundle integrity confirms no building-demographic detail or municipal database artifact.
- [ ] Release notes list code/data/operations/external limitations and rollback instructions.

Create a GitHub Release only after the pilot owner approves this checklist. Use a tag such as `v0.2.0-pilot.1`; do not use `v1.0.0` or “production ready”.
