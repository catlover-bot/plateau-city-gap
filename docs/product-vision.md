# CITY GAP Municipal Urban Intelligence Platform

## Product purpose

CITY GAP is a municipal operations system for turning versioned urban data into
reviewable findings, investigations, scenario comparisons, field observations and
human-authored decision records. Its differentiator is traceable spatial computation:
every result remains linked to an Urban State, explicit dataset versions, algorithm
The public product is positioned narrowly as:

**CITY GAP 地域交通・医療の現地調査候補をつくるツール**

`500m candidate → PLATEAU field context → data gaps → field checks → editable investigation sheet → municipal review`

Its primary user is a municipal local-public-transport officer. The public output is a
candidate shortlist, a field investigation sheet and an internal investigation
summary—not a policy recommendation or a replacement for the wider platform.
version, parameters, validation evidence and stated limitations.

The primary operating loop is:

`Data onboarding → Observe → Detect → Investigate → Compare → Review → Field check → Human decision → Re-evaluate`

The public investigation surface expresses that loop spatially:

`City → District → 500m mesh → Building group → Building → Road → Site`

Scene and spatial resolution remain independent. A user can change the question being
investigated without losing the object or scale already under review.

## PLATEAU-native resolution intelligence

PLATEAU is the Urban Object Model that connects an aggregated Finding to observable
urban structure. Buildings, roads, terrain, land use, planning and hazard objects are
linked through an Urban Object Graph and exposed through the Object Lens. The graph is
bidirectional: a Finding can be traced to supporting objects, and a selected object can
be traced back to the Finding, source, year, method and limitation.

PLATEAU does not replace CITY GAP's existing analysis. Urban X-Ray, Service Pulse,
Counterfactual Twin and Temporal Ghost visualize already-published evidence at a more
useful resolution. They do not invent geometry, resident counts, pedestrian routing or
temporal polygons.

The service is designed for recurring annual and event-driven use. It is not a one-off
competition dashboard.

## Product boundaries

- CITY GAP produces investigation candidates and counterfactual comparisons. It does
  not declare policy priorities, legal violations, road danger or administrative
  approval.
- Stress tests apply an explicit closure assumption. They are not disaster or traffic
  predictions.
- Future population uses an official projection input plus a declared spatial
  allocation model. It is not a prediction of individual building residents.
- Public building population is a model-estimated allocation, not an actual resident
  count. No per-building count is published.
- PLATEAU LOD1 road-surface adjacency is experimental. It is not a pedestrian network,
  walking route or travel-time model.
- Terrain is explanatory context only. CITY GAP does not infer walking burden, slope
  safety or danger from it.
- A Decision Record is always entered by an authorized human after review. Optimizer
  output cannot create it.
- Missing public or municipal inputs remain `unavailable`; the service does not invent
  facilities, costs, approvals or observations.
- The public GitHub Pages showcase remains aggregated, non-sensitive and read-only. It
  does not share the authenticated municipal API surface.

## Success measures

Measure adoption with non-sensitive usage events, completion of real lifecycle steps,
time-to-review and data freshness. Do not substitute fictional satisfaction scores,
invented municipal usage, or unmeasured SLA claims.
