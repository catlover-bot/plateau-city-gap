# A5 municipal workflow review

Status: `AWAITING_MUNICIPAL_WORKFLOW_REVIEW`

Purpose: review whether CITY GAP's upstream reasoning chain can enter a real municipal process. This is not a review of generic assignment, form, photo, GPS, or offline collection features.

## Evidence under review

Use the same West Maizuru 500m/800m sources and `citygap-investigation-area@1.0.0` rule.

1. [800m Known/Unknown screenshot](assets/area-checkpoint/02-area-known-unknown-800m.png)
2. [800m PLATEAU target and unverified-task screenshot](assets/area-checkpoint/03-area-unverified-tasks-800m.png)
3. [500m Known/Unknown screenshot](assets/area-checkpoint/04-area-known-unknown-500m.png)
4. [390×844 task screenshot](assets/area-checkpoint/05-area-mobile-tasks-800m.png)
5. [Browser evidence manifest](assets/area-checkpoint/manifest.json)
6. [500m/800m machine-readable comparison](../analysis/outputs/real/maizuru_area_500_800_comparison.json)
7. [Methodology and claim boundaries](area-methodology.md)

The review chain is:

```text
Investigation Area version
  -> quantified facts from versioned sources
  -> Known / Partial / Unknown and source limitation
  -> Finding reason
  -> real PLATEAU object or honest source fallback
  -> 3–5 required checks
  -> status = unverified
```

There are no field photos, GPS positions, field answers, assignees, or reviews in this evidence.

## One-minute walkthrough

1. Select West Maizuru station and compare the 500m and 800m radius-based summaries.
2. Read population, age, building use, establishments, available planning context, and transport on the same page as Unknowns.
3. Open the 800m methodology note and confirm that it is not an actual walking-time area.
4. Follow each Unknown's source limitation to the road, building, or official facility record selected for verification.
5. Check that the resulting preview has 3–5 bounded checks and remains `未確認`.

The population and age values are area-weighted estimates from official 2020 Census 500m meshes. They are never allocated to individual PLATEAU buildings. In 800m, two intersecting meshes have disclosure-affected age cells; those cells are not imputed.

## Review questions — maximum five

1. Which scopes are actually used most often: 500m, 800m, 1000m, another radius, Census small area, address town, neighborhood association, or a municipal operational area?
2. For the first summary, which exact minimum facts are required, and in particular what does “planning restrictions/context” mean in the workflow: zoning, building coverage ratio, floor-area ratio, district plan, planning-area status, or something else?
3. How are an 800m reference radius and an actual pedestrian travel-time area used differently in current work?
4. For each shown Unknown, is the target granularity actionable: building, road, official facility, object group, or mesh fallback? Which checks are unnecessary or missing?
5. In which meeting, GIS, form, ledger, or decision step could the Area → source limitation → target → unverified task chain be used? If nowhere, record why.

Also record the current alternative: staff experience, paper, spreadsheet, existing municipal GIS, Field Maps, Survey123, another system, or no formal process. CITY GAP does not seek to replace generic assignment or field collection tooling.

## Review record

| Field | Value |
|---|---|
| reviewer role | transport / planning / GIS-PLATEAU / field operations / other |
| municipality or organization | name or approved anonymized label |
| review date | ISO date |
| evidence version | branch HEAD and comparison SHA-256 |
| usable workflow step | verbatim or none |
| useful facts | verbatim |
| missing facts | verbatim |
| planning-context meaning | verbatim |
| useful Unknowns | verbatim |
| rejected Unknowns | verbatim |
| target/check changes | verbatim |
| overlap with existing tool | verbatim |
| privacy/retention concern | verbatim |
| overall decision | supports workflow / partial / contradicts / not assessed |

Keep negative, partial, “existing measures,” “out of scope,” and “no connection point” responses verbatim.

## Decision boundary

Direct feedback already supports arbitrary-radius Area analysis, the six-domain summary in part, and the importance of distinguishing what data alone cannot establish. It does not yet prove that converting an Unknown into a field-verification task fits municipal operations.

Do not change `UNKNOWN_TO_FIELD_TASK_WORKFLOW` from `AWAITING_MUNICIPAL_WORKFLOW_REVIEW` until direct reviewers identify a real receiving process and assess the shown targets/checks. Do not describe A5 as value-validated, efficiency-improving, or superior to Field Maps/Survey123.
