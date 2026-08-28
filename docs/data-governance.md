# Data governance

## Registration and promotion

Registration records source URL, provider, licence, declared CRS, format, year,
classification and version key. It does not assert quality. Validation, acceptance,
ingestion readiness and promotion are separate human-visible events. Only promoted,
quality-passed, analysis-ready versions may be used by service analysis or a validated
Urban State.

## Classification

- `public`: reviewed inputs or outputs eligible for the public export path.
- `internal`: normal municipal analysis and evidence.
- `restricted`: identities, field attachments or content requiring the narrowest
  municipal handling.

Public report export is rejected unless both the report and all checked inputs are
public. The authenticated service never treats an internal object URL as a public URL.

## Provenance and reproducibility

Persist source checksum, dataset version IDs, Urban State, network version, algorithm
version, typed parameters, configuration hash, assumption hash, validation method and
limitations. Deterministic reports store a canonical content digest. Published public
artifacts remain separate from mutable service records.

## Retention and deletion

Retention classes are metadata-driven. Database rows and object bytes must be removed by
an audited operator workflow, not a UI-side best effort. No automated destructive purge
is enabled by default. Municipal policy owners must set retention periods and legal-hold
rules before production deletion jobs are enabled.

## Source truth boundary

Unavailable official future population, shelter capacity, cost, target or approval data
remains unavailable. CITY GAP may accept a versioned municipal adapter, but it does not
generate a replacement value.

Official source discovery, machine-readable licence decisions, canonical lineage,
coverage reasons and annual update stages are specified in
[Municipal Open Data Platform](open-data-platform.md).
