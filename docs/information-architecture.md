# Municipal service information architecture

## Global shell

The authenticated shell always exposes organization, selected city, signed-in role,
global search and the current service page. Search results are tenant-scoped and may
represent a city, finding, investigation, scenario, facility, PLATEAU building `gml:id`
or 500 m mesh.

## Primary navigation

1. **Home** — assigned work, freshness, current capability and recent human activity.
2. **Cities** — city selection and truthful onboarding state.
3. **Data** — dataset registration, quality gates, versions and Urban States.
4. **Analysis** — versioned runs, typed parameters and Findings.
5. **Measures** — saved scenarios and two-to-three option comparisons.
6. **Review** — Investigation case, review, selected-site offline field work,
   attachments and Decision Record.
7. **Evidence** — validation manifests and deterministic reports.
8. **Operations** — durable jobs, backup/release records and Administrator audit events.

Navigation is role-sensitive but authorization is always enforced again at the API and
repository boundaries. Hiding a menu item is not an access control.

## Public showcase boundary

The public application has a separate build-time surface and read-only endpoints. It
shows reviewed aggregated evidence only. Authenticated case data, identities,
restricted attachments and building-level estimated demographics are not public
navigation states or assets.
