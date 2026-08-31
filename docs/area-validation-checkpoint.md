# Investigation Area A5 validation checkpoint

Date: 2026-08-31

Goal: `area-known-unknown-to-task-v1`

Checkpoint decision: `TECHNICAL_VERTICAL_SLICE_PASS / HOLD_VALUE_CLAIM / HOLD_P1_M4_M6`

## Repository state

| Item | Result |
|---|---|
| branch | `feat/area-known-unknown-a5` |
| product checkpoint | `d829defc54dc9417d3045d2c2ecfb9f19558e08a` |
| origin/main | `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff` |
| commits since `2f28cd1` | atomic product and evidence commits; documentation commit follows |
| preservation | prior M3/028 and A0–A5 work retained |
| merge | not performed |

No reset, clean, rebase, squash, force push, or loss of existing work occurred.

## Production evidence

| Gate | Result |
|---|---|
| production build | PASS, 67.12s wall time |
| direct Area URL to tasks | 3 clicks |
| existing landing to tasks | 4 clicks |
| FMR samples | 1,046 / 712 / 619 / 1,672 / 3,130ms |
| FMR median | 1,046ms |
| first-view domains | population, age, building use, establishments, planning, transport |
| Unknowns | 3 |
| required checks | 4 / 5 / 4 |
| task status | all `未確認` |
| fake photo/GPS/answer/review | none |
| 390×844 | 390px document width, no horizontal overflow, 3 tasks and 3 unverified labels |

Machine-readable evidence: [manifest](assets/area-checkpoint/manifest.json)

Same-condition 500m/800m evidence: [machine-readable comparison](../analysis/outputs/real/maizuru_area_500_800_comparison.json)

The comparison records independent axes only. It contains no composite score or ranking.

Screenshots:

- [Area origin](assets/area-checkpoint/01-area-origin.png)
- [Known/Unknown at 800m](assets/area-checkpoint/02-area-known-unknown-800m.png)
- [Unverified targets and tasks at 800m](assets/area-checkpoint/03-area-unverified-tasks-800m.png)
- [Known/Unknown at 500m](assets/area-checkpoint/04-area-known-unknown-500m.png)
- [390×844 task view](assets/area-checkpoint/05-area-mobile-tasks-800m.png)

The screenshots were captured from the production preview, not the development server. File hashes, viewport, URL, and scene are recorded in the manifest.

## Deterministic 30–60 second walkthrough

This is a repeatable script, not a measured human-comprehension result.

1. From the existing landing, select **場所と範囲から調べる（検証中）**.
2. Select **西舞鶴駅**. The UI treats the station as a versioned point origin.
3. Select **800m（徒歩圏の目安）**. The open methodology note says this is a radius and not an actual ten-minute walking-time area.
4. Read the six municipal-priority evidence domains and the three Unknowns on the same continuous page.
5. Select **PLATEAU上の確認対象を見る**.
6. Confirm that each Unknown retains its reason, a real source object or official target, 3–5 checks, and status **未確認**.

The direct Area URL omits step 1 and therefore takes three clicks; the current product landing takes four.

## 500m / 800m evidence

All values use the same `citygap-investigation-area@1.0.0` rule and checked-in Maizuru sources.

| Domain | West Maizuru 500m | West Maizuru 800m | Boundary |
|---|---:|---:|---|
| population | 3,087 | 6,755 | 2020 census 500m mesh, area-weighted estimate |
| age 65+ | 970 (31%) | 2,038 (30%) | partial age distribution, area-weighted estimate |
| leading building uses | 住宅 1,312 / 不明 288 / 商業施設 124 | 住宅 3,094 / 不明 619 / 共同住宅 215 | unique official CityGML footprints intersecting AOI |
| establishments | 266 | 475 | 2021 economic census mesh, area-weighted estimate |
| employees | 1,909 | 3,684 | 2021 economic census mesh, area-weighted estimate |
| planning context | 都市計画区域 / 市街化区域 / 第2種住居地域 | 都市計画区域 / 市街化区域 / 準防火地域 | available official PLATEAU objects ordered by clipped area |
| stations | 1 | 1 | registered source point |
| bus stops | 4 | 6 | registered source point |

The building-use distribution uses the complete official Maizuru CityGML building set and official package code list. It does not use the residential-only demographics subset.

Population and age are never allocated to individual buildings. At 500m, all eight intersecting Census meshes are disclosure-unaffected. At 800m, fourteen of sixteen are unaffected; one is a suppressed source and one an aggregation destination. Total-population coverage remains 100%, while usable 65+ coverage is 97.25%. Missing age cells are not imputed or disaggregated. Full mesh codes and overlap ratios are in the machine-readable comparison.

800m passes the technical selection gates: at least three real Known facts, three decision-relevant Unknowns, real targets, 3–5 checks, four clicks from the existing landing, 390px layout, FMR median below three seconds, and no affirmative walking-time claim. It is therefore the preferred experimental Area fixture. This is not evidence that 800m is the best scope for every municipal job.

## Area → Known/Unknown → target → task manifest

| Unknown | Source limitation / reason | Target | Checks | Status |
|---|---|---|---:|---|
| actual walking continuity | a radius and LOD1 road surface do not establish crossings, stairs, restrictions, or pedestrian reachability | PLATEAU road `tran_46c7e1e5-07ba-424d-ba29-2ae7f0464a21` | 4 | 未確認 |
| current building use | the PLATEAU usage attribute is source-dated and does not establish current use or vacancy | PLATEAU building `bldg_155e6675-6981-450f-8e73-df0b43418cc2` | 5 | 未確認 |
| current facility availability | a registered official facility point does not establish opening status, hours, or entrance | official facility record `medical-026` | 4 | 未確認 |

No field evidence has been collected. The IDs above prove target provenance only; they are not a field conclusion.

For an arbitrary map point without a generated PLATEAU pack, the Public preview keeps building/economic/planning metrics unavailable and uses an explicitly labelled 500m-mesh fallback. It does not borrow the West Maizuru objects.

## Area Summary evidence update

The first view follows direct Kyoto municipal feedback:

1. population;
2. age distribution;
3. building-use distribution;
4. establishments;
5. available planning context;
6. transport context.

Medical, care, public-facility, hazard, and future-population assets were not deleted. They are not shown as equal first-view KPI cards.

The product does not decide what “planning restrictions” means. Current Public data shows only official objects and its limitation. Zoning, building coverage ratio, floor-area ratio, district plans, planning-area status, and other possible requirements remain a municipal question.

## Competitor overlap audit

| Capability | Established overlap | CITY GAP decision |
|---|---|---|
| point/radius selection and Area aggregation | generic GIS, PLATEAU structure evaluation, UrbanFootprint | integrate/learn; never claim as novelty |
| map-first direct selection | Remix and other planning GIS | learn the interaction, not route/service planning |
| 3D object inspection | ArcGIS Urban and PLATEAU viewers | use contextually; do not build a generic 3D editor |
| assignment and field collection | ArcGIS Field Maps / Survey123 | do not compete on generic assignment, form, photo, GPS, or offline collection |
| submitted-state feedback | Field Maps and My City Report | retain only as a later municipal workflow boundary |
| connected collection/analysis/reporting | Maptionnaire and municipal GIS stacks | provisional overlap; require workflow review |
| source limitation → Finding → versioned PLATEAU target | not established in the current official-source benchmark as one core workflow | provisional whitespace, not a proven uniqueness claim |

The technical slice is differentiated from a generic field-task manager because it starts with an Area version and preserves the source limitation and target provenance. It is not yet proven to be meaningfully different in municipal use.

Current novelty assessment: `PROVISIONALLY_DIFFERENTIATED_AT_A5`.

## Public copy assessment

The deterministic preview defaults to candidate A:

> 調べたい場所を選ぶ。<br>
> 分かっていることと、まだ確かめるべきことが分かる。

Candidates B and C remain selectable with `?copy=B` and `?copy=C`. No copy has won a first-time-user test. The UI contains no language implying that AI knows the area better than municipal staff.

Status: `AWAITING_HUMAN_TEST`.

Prepared review artifacts:

- [30–60 second human comprehension protocol](area-human-test.md)
- [municipal workflow review](area-municipal-review.md)

## Test record

| Check | Result |
|---|---|
| Backend full pytest | 409 passed, 1 deprecation warning |
| Frontend typecheck | passed |
| Frontend lint | passed |
| Frontend Vitest | 83 passed across 22 files |
| Markdown link check | 73 files, all local links resolved |
| npm / pip dependency audit | 0 known vulnerabilities |
| Open Data final audit | 120 goals / 42 checks passed |
| migration checksum/status | 001–029 ready, no problems |
| fresh PostGIS integration DB | 18 passed, 1 deprecation warning |
| production build | passed |
| API and frontend container builds | passed |
| Area deterministic desktop/mobile capture | passed |
| PLATEAU-native browser audit | 19 checks passed |
| visual identity browser audit | 5 viewports passed |
| existing M3 guided regression | desktop/mobile passed; 4 tasks, 0 evidence inputs |
| `git diff --check` | passed |

The current rerun used a separate `citygap_a5_final_20260831` database, migrated from 001 through 029, passed all 18 integration tests, and was then removed. The existing `citygap` and `citygap_guided_final` databases were not reset or deleted.

The first PLATEAU-native browser attempts exposed navigation-cancelled GSI tile requests as `net::ERR_ABORTED`. The audit now ignores only that expected cancellation while still failing local asset errors, non-abort GSI failures, and console errors. The final run passed all 19 checks.

## Remaining value risks

1. No human has yet shown that copy A/B/C communicates the value within 30 seconds.
2. Direct feedback supports Known/Unknown, but does not yet support the Unknown-to-field-task workflow in an actual meeting, GIS, form, or review process.
3. “Planning restrictions” still lacks an agreed municipal minimum field set.
4. The public arbitrary-point preview has honest unavailable states until per-area PLATEAU/economic/planning packs are generated by the backend.
5. PLATEAU usage attributes and facility registries are source-dated; current status requires verification.
6. A 500m mesh fallback is traceable but may be too coarse for some Unknowns.
7. The workflow may still be perceived as Field Maps/Survey123 task preparation unless municipal reviewers value the upstream Area/source-limitation chain.
8. Generalisation beyond Maizuru remains untested.
9. Existing M4–M6 migration/code is provisional and has not been value-validated by A5.

## Validation status and stop

- `AOI_NEED = DIRECT_MUNICIPAL_NEED_CONFIRMED`
- `AREA_SUMMARY_CONTENT = DIRECT_MUNICIPAL_NEED_PARTIALLY_CONFIRMED`
- `KNOWN_UNKNOWN_VALUE = DIRECT_MUNICIPAL_VALUE_SIGNAL_CONFIRMED`
- `UNKNOWN_TO_FIELD_TASK_WORKFLOW = AWAITING_MUNICIPAL_WORKFLOW_REVIEW`
- `PUBLIC_COPY = AWAITING_HUMAN_TEST`

A5 is complete. Work stops here. P1 walking/borehole work and M4 Photo/GPS/Offline, M5 Municipal Review, and M6 Finding Feedback must not start without a new approval.
