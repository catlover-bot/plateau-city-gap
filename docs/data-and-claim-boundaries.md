# Data and claim boundaries

CITY GAP turns official spatial data into traceable investigation candidates. It does not turn incomplete public data into a policy decision or a field observation.

## Authority and transformation

- Source dataset identity, year, license, CRS, checksum, processing rule, and limitation are recorded in [data-sources.md](data-sources.md).
- `analysis/outputs/real/` is the analysis result SSOT. Static frontend assets are verified derivatives, not a second analysis implementation.
- The browser may filter, select, format, and compare published values. It must not manufacture a new population, distance, score, rank, or observation.
- Missing values remain unavailable. CITY GAP does not infer a facility, building height, route, field answer, approval, or local condition to fill a gap.

## Area and metrics

- A 500m mesh or selected radius is an investigation boundary, not a neighborhood definition and not a service catchment.
- Population values come from the cited census aggregation. Building-level population is a model allocation and is never presented as actual residents.
- Public transport and medical values use the documented source and distance semantics. Straight-line, experimental road-network, and policy-radius values remain visibly distinct.
- A percentile or candidate rule describes position within an eligible comparison set. It is not risk, urgency, priority, or a recommendation.

## Map geometry

- PLATEAU buildings and roads are source-backed display geometry with version and object identity where the source resolves them.
- A registered facility point is a reference position, not proof of its entrance, accessibility, opening status, or service availability.
- If an individual object cannot be resolved, the UI uses an explicitly labelled Area fallback. It does not place a plausible-looking fake target.
- Basemap availability is external context. Same-origin Area, target, and evidence layers remain the product evidence boundary.

## Urban Section

- The A–B line on the map and the Urban Section represent the same source/version pair.
- Terrain uses the documented DEM/TIN interpolation. It does not imply walking difficulty, slope safety, or hazard severity.
- Buildings distinguish direct and nearby relations. Missing height is shown without synthetic height completion.
- Road annotations identify source road surfaces; they do not assert pedestrian access or route feasibility.
- Pointer or keyboard focus links a section position to the map. It does not change the canonical selected Area.

## Guided verification

- Guided exposes three scenes: choose a region, understand its spatial form, and identify what to verify.
- The final 3–5 checks are questions that the available data cannot answer. Their initial status is unverified.
- Guided contains no photo, GPS observation, answer, assignee, approval, or municipal review result.
- Guided → Advanced preserves the selected region and display state while loading the full dataset. Loading success does not upgrade an unverified claim.

## Privacy and operations

- Public assets are aggregate, non-sensitive, and read-only. Suppressed or disclosure-sensitive values are not decomposed into building records.
- Authenticated Municipal workflows, audit logs, and offline field records have separate authorization and retention boundaries.
- A generated report or screenshot must retain enough source/version/limitation context to avoid appearing more certain than the underlying data.

## Review status

Automated unit, browser, accessibility, performance, and image checks demonstrate contract conformance only. Human comprehension, visual acceptance, field usability, and municipal workflow fit require their own recorded reviews. Until then they remain `AWAITING_*`, never silently promoted to pass.
