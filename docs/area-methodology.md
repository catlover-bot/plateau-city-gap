# Investigation Area methodology

## Purpose and evidence boundary

CITY GAP P0 uses a versioned Investigation Area to quantify what municipal staff already sense about a place, then separates what the available sources can and cannot answer.

```text
LOCAL INTUITION
  -> QUANTIFIED EVIDENCE
  -> KNOWN / PARTIAL / UNKNOWN / UNAVAILABLE
  -> source limitation
  -> Finding
  -> versioned PLATEAU target / honest fallback
  -> 3–5 verification checks
```

This does not claim that AI knows the locality better than municipal staff. Area selection and aggregation are common GIS capabilities and are not claimed as novelty.

Direct municipal evidence currently supports:

- arbitrary point-and-radius analysis;
- practical use of 500m, 800m and boundary-based scopes;
- the first Area Summary domains;
- the importance of explicitly showing what data alone cannot determine.

It does not yet establish that the Unknown-to-Verification workflow fits a municipal process.

## Area definition

P0 uses `point_radius`, `source_boundary`, and existing mesh scopes. A station is a convenient origin, not the domain center.

A station origin stores a versioned official source feature ID. Client-supplied station coordinates are not authoritative. A map-point origin stores the selected point. Area changes create a new version; an analysis run retains its geometry hash, rule version, source versions, and urban state.

Geometry storage uses EPSG:4326. Buffer, overlap, distance, and area calculation for Maizuru use EPSG:6674. Requested geometry is clipped to the official versioned municipal boundary. A fully outside area is rejected; partial clipping retains the clipped-area ratio.

Custom radius is an integer from 100m through 3000m. P0 exposes one-click 500m, 800m, and 1000m presets plus one custom numeric field. It does not expose a generic GIS buffer editor.

## Radius semantics

| Radius | Public label | Meaning |
|---|---|---|
| 500m | 500m（高齢者徒歩圏の目安） | MLIT handbook reference radius for an elderly walking area; not a network reachability result |
| 800m | 800m（徒歩圏の目安） | MLIT handbook general/station walking-area reference radius; not a network reachability result |
| 1000m | 1km（広域確認） | broad-context radius; never called a walking area |
| custom | その他の半径 | a simple municipal analysis radius with no inferred policy meaning |

Required 800m explanation:

> 国土交通省「都市構造の評価に関するハンドブック」の一般的な徒歩圏800mを用いた半径ベースの分析範囲です。実際の徒歩10分到達圏を示すものではありません。

P0 does not use the PLATEAU LOD1 road-surface adjacency graph as a validated pedestrian network. It makes no affirmative walking-time, reachability, or isochrone claim.

References:

- MLIT, 都市構造の評価に関するハンドブック: https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000004.html
- MLIT walking-area note: https://www.mlit.go.jp/common/001247988.pdf

## Source-boundary semantics

The only P0 candidate boundary is labelled:

> 2020年国勢調査小地域（町丁・字等）

It is a statistical boundary. It is not presented as the current administrative town boundary, address town, neighborhood association, or municipality-specific operational area. The current Public fixture does not contain a versioned Maizuru small-area boundary and therefore shows this route as unavailable instead of substituting another boundary.

Reference: https://www.e-stat.go.jp/help/data-definition-information/download

## Deterministic aggregation

| Data | P0 rule | Required limitation |
|---|---|---|
| population and age | sum of mesh value multiplied by AOI overlap ratio | area-weighted estimate; missing/suppressed values are not filled with zero |
| establishments and employees | sum of economic-mesh value multiplied by AOI overlap ratio | area-weighted estimate; not current business operation |
| PLATEAU buildings | unique GML IDs whose official footprint intersects AOI | official usage attribute at source date; not current use |
| PLATEAU planning objects | clipped official objects ordered by clipped area, then GML ID | available official objects only; not a complete definition of municipal restrictions |
| stations and bus stops | source points covered by AOI | registered locations; not service availability or pedestrian reachability |
| facilities | source points covered by AOI, kept in secondary context or a specific Unknown | registration does not establish current availability |
| roads | versioned official object identity and geometry | road surface is not a validated pedestrian network |
| terrain | covered samples only | no interpolation into uncovered areas |

Each metric carries dataset/version provenance, source date, calculation/rule version, coverage, exact/estimated/modelled semantics, freshness, and a source limitation. No composite score is calculated.

The fixture generator reads the complete official Maizuru CityGML building set and its official package usage code mapping. It does not use the strict-residential demographics subset as a building-use distribution.

## Population and age audit boundary

The source is e-Stat table `T001192`, 2020 Census JGD2011 500m mesh population by five-year age group, reference date 2020-10-01. Population uses `T001192001`; age 65+ is the sum of `T001192043`, `046`, `049`, `052`, `055`, `058`, and `061` when those source cells are available.

For each intersecting source mesh, the Area value adds:

```text
source mesh value × (AOI intersection area / source mesh area)
```

The source mesh totals are official observations. The resulting circular-AOI values are classified as **estimated**, not exact or modelled, because a uniform within-mesh distribution is implicit in area weighting.

| Audit item | West Maizuru 500m | West Maizuru 800m |
|---|---:|---:|
| intersecting Census meshes | 8 | 16 |
| disclosure status | 8 unaffected | 14 unaffected, 1 suppressed source, 1 aggregation destination |
| population coverage | 100% | 100% |
| age 65+ coverage | 100% | 97.25% |
| city clipped-area ratio | 100% | 100% |
| result status | population known; age partial | population known; age partial |

At 500m, all eight intersecting source records are disclosure-unaffected. The value is still an area-weighted estimate, not an exact circular-area count. At 800m, published total-population values are available for all sixteen intersections, while two disclosure-affected records have no usable 65+ value. Those age cells remain missing; they are not replaced by zero, a mean, a neighbouring mesh, or a model.

Population and age are never allocated to individual PLATEAU buildings. Building footprints are used independently for official building-use counts and object targets. In particular, a suppression-affected Census mesh must never be disaggregated to buildings, households, or people. The values do not identify resident buildings and do not represent a validated pedestrian reachability area.

Machine-readable detail, including affected mesh codes and overlap ratios, is generated in `analysis/outputs/real/maizuru_area_500_800_comparison.json`.

## Area Summary priority

The first view contains exactly these six municipal-priority domains, in order:

1. population;
2. age distribution;
3. PLATEAU building-use distribution;
4. establishment and employee counts;
5. available official urban-planning context;
6. station and bus-stop context.

Medical/care/public facilities, hazards, and future population remain available in existing product assets but are not promoted as equal first-view KPI cards.

“Urban-planning restrictions” is not assigned a product-defined meaning. P0 displays only available official objects and says that coverage may be incomplete. Municipal review must still determine whether the operational requirement means zoning, building coverage ratio, floor-area ratio, district plan, planning-area status, or another item.

## Known / Unknown contract

- `known`: the versioned source answers the stated question within its boundary.
- `partial`: coverage, suppression, freshness, or semantic limits allow only a partial answer.
- `unknown`: no source answers the question, or field/expert judgement is necessary.
- `unavailable`: the required source, artifact, or API is unavailable.

Reason codes distinguish no source, coverage gaps, suppression, time limits, model limits, object-semantic limits, field observation, and expert judgement.

Only `field_verification` knowledge items become field-task previews. Data acquisition and expert review are never padded into field checks. At most four decision-relevant Unknowns are shown. Each preserves why it matters and its source limitation.

A Public target is a versioned PLATEAU object when provenance exists. Otherwise the UI uses an explicitly labelled mesh fallback. It never borrows an object from another place. Each preview contains 3–5 deterministic checks and status `unverified`.

## Public and workflow boundary

Public Area is a read-only preview. It does not create internal tasks and contains no field photo, GPS, answer, assignee, internal note, attachment, or municipal review.

The existing M3 remains the primary entry until human comprehension testing passes. The Area journey is a secondary experimental route. M4 Photo/GPS/Offline, M5 Municipal Review, and M6 Finding Feedback remain out of scope.

## Validation state

- AOI need: `DIRECT_MUNICIPAL_NEED_CONFIRMED`
- Area Summary content: `DIRECT_MUNICIPAL_NEED_PARTIALLY_CONFIRMED`
- Known/Unknown value: `DIRECT_MUNICIPAL_VALUE_SIGNAL_CONFIRMED`
- Unknown-to-field-task workflow: `AWAITING_MUNICIPAL_WORKFLOW_REVIEW`
- Public copy: `AWAITING_HUMAN_TEST`

Copy candidates A/B/C remain test variants. Candidate A is the deterministic preview default, not the validated winner.

## P1 boundaries

Actual pedestrian-network isochrones require a versioned, QA-reviewed pedestrian network with restrictions, crossings, stairs, ramps, barriers, cost assumptions, municipal review, and representative field validation.

The Borehole Observation Layer is a separately approved P1 candidate. It may add independent official vertical observations to Known/Unknown. It must not interpolate between boreholes, reconstruct continuous strata, infer supporting layers, recommend foundations, or make ground-safety judgements.
