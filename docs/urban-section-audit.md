# Urban section audit

Goal: `public-product-language-and-section-v1`  
Decision recommendation after H0: **Option C — keep the section out of the Public first-run; retain it in legacy M3 and Advanced.**

## Where the section exists

| Experience | Observed state | Evidence |
|---|---|---|
| GitHub Pages legacy guided experience | Section is rendered in guided steps 3–4 with a 3D/static fallback. | `production-guided-section.png` |
| GitHub Pages Advanced | Full `PLATEAU URBAN SECTION` is present and can be opened/closed. | `production-advanced-section.png` |
| Feature Area Public root | `PublicAreaJourney` does not import or render `UrbanSection`. Result and target use the 2D cartography and exact target geometry. | feature baseline screenshots and source audit |
| Feature legacy M3 / Advanced routes | Components and routes remain in the source tree. | regression gate at H5 |

## Current-section semantics

| Audit item | Observed implementation | Assessment |
|---|---|---|
| User-facing title | Guided: `街の断面` / `実際の地形・建物・道路`; Advanced: `PLATEAU URBAN SECTION` / `実DEM × 建物 × 道路` | Guided title names a format, not a user question. Advanced terminology is appropriate only for expert inspection. |
| Purpose | The plot juxtaposes terrain, nearby buildings, intersecting roads, and some service/scenario relations. | It can support expert source inspection, but the Area first-run does not ask a terrain/building-height question that requires it. |
| Source data | Verified transect JSON from PLATEAU local DEM, building, road, facility/scenario data with pack metadata. | Provenance is strong; usefulness is the issue, not data integrity. |
| Terrain meaning | A sampled terrain profile using documented datum/transformation. | Technically meaningful, visually dominant. |
| Building meaning | Buildings near/directly intersecting the transect; height is not fabricated when missing. | Correct, but dense at 900 px and hard to relate to a specific Public unknown. |
| Road meaning | Markers for intersecting roads. | Visible but small and weakly labeled. |
| Selected target | Advanced supports building selection; guided section is not tied to the Area Public selected road/building target. | Fails the Public contextual-target requirement. |
| Horizontal axis | Transect distance with tick labels. | Truthful but small. |
| Vertical axis | Elevation/profile with datum statement; plot uses an explicit exaggeration value in the footer. | Truthful but difficult for first-run users to parse. |
| Scale / exaggeration | Advanced footer reports exaggeration 1.0 in the observed capture. | Technically adequate. |
| Labels | Facility labels, source facts, ticks, counts, and relation notes compete at small sizes. | Too dense for Public. |
| Legend | Guided map legend adds building/road/terrain while plot has its own symbol vocabulary. | Map and plot grammar are not sufficiently unified. |
| Map correspondence | The section data has a transect, but the legacy Public map does not present a clear A/B cut line aligned with the plot. | Fails a required condition for A/B. |
| Direction | No prominent A → B orientation is visible to a first-run user. | Fails a required condition for A/B. |
| Camera | 3D and section can coexist, but section remains readable mainly as a separate expert plot. | Does not solve correspondence. |
| Mobile | Guided CSS hides the regular section on small screens except a compressed static fallback; text can become 8–10 px. | Does not meet the Public 14–16 px reading target. |
| Accessibility | SVG has title/description and avoids fabricating missing values. Guided buildings are hidden from focus. | Better than a decorative figure, but it lacks a concise task-specific text summary. |
| Empty/loading | Guided messages say the verified section is available while 3D loads and permit continuing on failure. | Honest and resilient. |
| Public need | The new Area flow already shows the Area, five stories, uncertainty, and exact target in 2D. No Public task currently needs a cross-section to understand the selected uncertainty. | Explanation cost is greater than demonstrated value. |

## Decision rationale

Option A and B both require a target-linked question, A/B cut line, orientation, selected-target hierarchy, mobile presentation, and an accessible summary. Adding those to the new Area Public would be a new visualization feature with no demonstrated first-run need. It would also risk the established performance and map-first hierarchy.

Option C is therefore the disciplined product decision:

- do not add `UrbanSection` to `PublicAreaJourney`;
- preserve the existing legacy M3 and Advanced component, data, route, and verified semantics;
- add a regression assertion that the Public first-run has no section while Advanced/M3 remain reachable;
- do not rename or redesign the Advanced expert plot as part of Public polish;
- reconsider only in a separately approved goal when a Public question specifically requires elevation/building-height/road cross-section evidence.

This is a scope decision, not a claim that the existing section data is invalid. No section geometry or provenance is deleted.

