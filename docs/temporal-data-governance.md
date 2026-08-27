# Temporal data governance and correctness

## State identity and lifecycle

An urban state is immutable after validation except for controlled lifecycle transition. Its
identity includes city, kind, effective date, source snapshot date and a stable state key. Exact
dataset/network/analysis links are many-to-many records, not an implicit lookup of the current
version.

Allowed lifecycle:

```text
draft -> validated -> current -> superseded -> archived
          |                         |
          +-------------------------+
```

Only validated source versions can participate in current analysis. A city may have one current
state per state kind/effective-date contract. Historic state links remain addressable after a
new version is promoted.

## Difference matching

Comparison is deterministic and conservative:

1. normalize geometry and important attributes;
2. match unique `gml:id` within the two exact versions;
3. classify matched records by geometry/attribute hash;
4. for unmatched records only, accept a unique geometry + important-attribute hash fallback;
5. leave ambiguous records as removed/added instead of inventing identity.

The engine records `match_method`, old/new identifiers and hashes, changed attribute names,
geometry and classification. `gml:id` is not assumed globally stable across years. Geometry hash
precision and important-attribute schema are part of the algorithm version.

## Dependency graph and recomputation

Dependency nodes identify source role, analysis product and version. Directed edges carry the
impact rule and scope strategy. Current strategies are:

- building -> intersecting building allocation and mesh metrics;
- road/topology -> affected graph component, accessibility and dependent scenarios;
- facility -> service category and potentially reachable network region;
- population -> affected mesh/building allocation and accessibility burden;
- planning/hazard -> intersecting context/stress-test products.

The recompute planner emits an explicit scope plus the reason. A missing/ambiguous scope escalates
to full rebuild. It never guesses that a smaller region is safe.

`incremental_recompute_validations` stores full and incremental hashes/counts for the same fixture.
A mismatch blocks promotion of that incremental algorithm version. This turns incremental compute
into an optimization with a correctness oracle, not a different result definition.

## Assumptions, cache and provenance

A stress-test cache key is derived from city, urban state, network version, canonical assumption
hash and algorithm version. State/network versions are immutable inputs; changing a rule or
algorithm cannot reuse an old result.

Hazard overlap alone never closes an edge. The persisted assumption must identify dataset version,
hazard type/class, closure rule, source and actor. Completion is blocked until at least one explicit
assumption and metrics exist. Service changes are user input only.

Temporal provenance links every result to the state, exact dataset and network versions, algorithm,
scenario/stress test and evidence export hash. Annual reports consume structured version-diff and
outcome records and do not use generated narrative.

## Privacy and claim boundaries

- Public artifacts contain reviewed aggregates and no per-building estimated demographics.
- Future population is an official scenario spatially allocated by a model, not predicted residents.
- Criticality candidates are graph-cut review evidence, not dangerous-road designations.
- Planning comparison is not a legal determination.
- Shelter routing is network reachability, not evacuation/crowd simulation.
- Planned effect and observed change do not establish causality.
- The experimental road-surface graph is not a validated pedestrian network.

## Offline conflict governance

Offline packages are restricted to selected sites and carry an immutable package version/content
hash. Each queued mutation includes client operation UUID, base record version, actor and
timezone-aware timestamp. Operation UUID makes replay idempotent.

If the server version differs, the API creates a conflict record with server/client state and
returns 409. Resolution requires `use_server`, `use_client` or a supplied merged state. Resolution
actor/time and before/after values enter the audit log. Last-write-wins is not used.

## Municipal gates still required

Software validation does not replace municipal acceptance. Before production use, owners must:

1. load and reconcile approved complete datasets in the intended PostGIS instance;
2. approve the network source and shelter snap tolerances;
3. review official future series and planning target interpretation;
4. configure OIDC issuer/audience/role claims and audit retention;
5. validate offline devices, GPS/privacy policy and conflict operating procedure;
6. register a real implemented intervention and later observed state before outcome use;
7. complete legal, licensing, accessibility, security, backup/restore and publication review.
