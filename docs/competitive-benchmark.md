# Competitive benchmark and market whitespace

Status: M0 goal lock for `competitive-product-synthesis-v1`.

Only capabilities stated by the linked official source are treated as confirmed. Field/offline/lifecycle behavior not described there is recorded as unconfirmed rather than inferred.

## Product matrix

| Product | Primary job | Confirmed flow or strength | Field / offline / collaboration / 3D | CITY GAP boundary |
|---|---|---|---|---|
| [LINKS Mobilys](https://www.mlit.go.jp/commmmons/document/008/) | Public-transport planning from GTFS and ridership | Import, visualize, edit service conditions, compare | Field/offline/task lifecycle unconfirmed; 3D not central | Learn direct map interaction; do not enter GTFS or timetable editing |
| [PLATEAU urban-structure evaluation tool](https://www.mlit.go.jp/plateau/use-case/uc25-09/) | Calculate and explain urban-structure indicators | Select indicators, change conditions, aggregate and map | Field assignment/offline unconfirmed; PLATEAU is an input | Learn source and limitation disclosure; do not become a generic indicator catalog |
| [Remix](https://ridewithvia.com/solutions/remix/planning) | Edit and compare transit plans | Draw and revise service directly on a map | Project sharing confirmed; offline unconfirmed; no central 3D | Learn map-first selection; do not enter route/frequency planning |
| [Conveyal Analysis](https://docs.conveyal.com/) | Compare baseline and scenario accessibility | Region, project, scenario, accessibility comparison | Field/offline/3D are not central | Learn explicit baseline/scenario separation; do not build a routing-analysis platform |
| [UrbanFootprint Analyst](https://urbanfootprint.com/platform/analyst/) | Compare planning and resilience scenarios | Built-in data, spatial analysis, linked maps and reports | Web project/scenario workflow; offline unconfirmed; 3D insight available | Learn continuity from map to report; do not become a generic scenario product |
| [ArcGIS Urban](https://doc.arcgis.com/en/urban/12.0/get-started/get-started-what-is-urban.htm) | Edit and compare land-use and building plans | Plan/project preparation, 3D editing, metrics and sharing | Collaboration and 3D are central; offline unconfirmed | Use contextual 3D only; do not enter zoning/parcel/building editing |
| [ArcGIS Field Maps](https://doc.arcgis.com/en/field-maps/latest/prepare-maps/configure-tasks.htm) | Execute assigned field tasks | To-do, assign/pick up/start/finish, map and evidence | Assignment lifecycle and offline maps/data are strengths | Integrate or coexist for collection; compete only on analysis-to-task provenance |
| [ArcGIS Survey123](https://doc.arcgis.com/en/survey123/get-started/faqgeneral.htm) | Collect structured location-aware forms | Distributed survey, conditional form, photo and GPS response | Offline forms confirmed; organization sharing; no central 3D | Learn fixed evidence patterns; do not build a form designer |
| [My City Report](https://www.mycityreport.jp/) | Citizen-to-municipality issue reporting | Position/photo report and visible response status | Citizen–municipality lifecycle; offline/3D unconfirmed | Learn one-sentence value and status feedback; do not enter citizen reporting |
| [Maptionnaire](https://www.maptionnaire.com/product) | Map-based public engagement | Design, collect, analyze, report, communicate | Team workspace; offline/3D not central or unconfirmed | Learn connected collection/analysis; do not enter generic participation |
| [ArcGIS StoryMaps](https://storymaps.arcgis.com/briefings/1e1e70c3204d42229609cefe21f9b18c) | Publish map-led narratives | Compose, preview, publish and share | Sharing and embedded scenes; not an operational task tool | Learn short public explanation order; do not build a story authoring product |

## Market map

| Stage | Representative products | CITY GAP posture | CITY GAP scope |
|---|---|---|---|
| Analyze | LINKS, PLATEAU evaluation, Conveyal, UrbanFootprint | Integrate / learn | Extract decision-relevant unknowns left by analysis |
| Plan | Remix, Conveyal, UrbanFootprint, ArcGIS Urban | Integrate / do not enter | Return evidence needed before planning, not a plan editor |
| Communicate | My City Report, Maptionnaire, StoryMaps | Learn | Explain value, state, sources and limits in a short order |
| Assign | Field Maps | Coexist / limited compete | Preserve why the task exists; do not optimize generic task management |
| Collect | Field Maps, Survey123 | Integrate / do not enter | A fixed evidence contract only |
| Review | Field Maps, My City Report | Limited compete | Put hypothesis, PLATEAU target and evidence in one traceable chain |
| Update | Maptionnaire, My City Report | Compete on provenance | Return a human conclusion to Finding without overwriting source data |

## Selected whitespace

The selected novelty is not any single field-task feature. It is the traceable chain:

```text
Analysis uncertainty
  -> source limitation
  -> Finding
  -> versioned PLATEAU object or honest mesh fallback
  -> bounded field task
  -> human evidence and review
  -> separate Finding field-validation state
```

H1 alone overlaps generic task creation. H2 alone overlaps 3D object inspection. H3 alone overlaps connected collection and reporting. H1 + H2 + H3 is retained because provenance across all three is the differentiator to test at M3.

## Do-not-compete guardrails

The product, navigation, API and copy must not introduce:

1. GTFS, timetable, frequency or route editing.
2. A generic urban-indicator catalog.
3. A generic form builder.
4. A generic field GIS or arbitrary feature editor.
5. Citizen reporting or public submissions.
6. A generic participation/survey platform.
7. Zoning, parcel or building-plan editing.
8. Fabricated cities, hazards, scores, future effects, photos, GPS, answers or reviews.
9. Automated confirmation, policy judgment or hazard judgment.

## M3 checkpoint question

Before M4, decide explicitly:

> Does the public slice make the analysis limitation → Finding → PLATEAU object → field task provenance meaningfully different from products whose strength is assigning or collecting field work?

Until human and municipal observation exists, keep `AWAITING_HUMAN_TEST` and `AWAITING_MUNICIPAL_REVIEW`.
