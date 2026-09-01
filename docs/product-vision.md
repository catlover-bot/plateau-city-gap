# CITY GAP Municipal Urban Intelligence Platform

## Product purpose

CITY GAP is a municipal operations system for turning versioned urban data into
reviewable findings, investigations, scenario comparisons, field observations and
human-authored decision records. Its differentiator is traceable spatial computation:
every result remains linked to an Urban State, explicit dataset versions, algorithm
version, parameters, validation evidence and stated limitations.

The Public first-run product is positioned as:

**気になる場所を、地図とデータで確かめる。**

`Investigation Area → quantified evidence → Known / Unknown → source limitation → PLATEAU target when needed → unverified checks`

Its primary users are municipal officers examining a station, facility or arbitrary
map point. The first view prioritizes population and age, building use,
establishments, available planning context and transport context. The public output is
an Area Summary and a traceable set of still-unverified questions—not a policy
recommendation or a replacement for the wider platform.

The primary operating loop is:

`Data onboarding → Observe → Detect → Investigate → Compare → Review → Field check → Human decision → Re-evaluate`

The public investigation surface expresses that loop spatially:

`Place → versioned Area → quantified evidence → Known / Unknown → building / road / site when field confirmation is appropriate`

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
- Area selection and aggregation are established GIS capabilities and are not claimed
  as CITY GAP novelty.
- Direct Maizuru evidence confirms overlap with a current-year use case combining
  PLATEAU 3D, borehole columns, liquefaction maps and other hazard data. CITY GAP will
  not build or claim novelty for a borehole viewer, 3D column viewer, or combined
  hazard-and-borehole viewer.
- Borehole work is `INTEGRATE / RESEARCH ONLY`, not an automatic P1 item. A future,
  separately approved goal may assess Maizuru outputs as a versioned official Area
  source; it must not recreate the specialist viewer or infer continuous geology.

## Success measures

Measure adoption with non-sensitive usage events, completion of real lifecycle steps,
time-to-review and data freshness. Do not substitute fictional satisfaction scores,
invented municipal usage, unmeasured SLA claims or fabricated human-test responses.
