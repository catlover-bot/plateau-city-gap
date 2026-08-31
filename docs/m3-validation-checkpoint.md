# M3 validation checkpoint

Checkpoint date: 2026-08-31 JST

Scope: M0–M3 only. M4 Photo/GPS/Offline, M5 Municipal Review, and M6 Finding Feedback are not authorized to continue from this checkpoint.

## Outcome

M3 is implemented as a public four-step vertical slice and stops at `未確認`.

| Check | Observed result |
|---|---|
| Production build | `npm run build` succeeded; final Vite production bundle completed in 37.94s |
| Public candidate | 常団地前周辺, mesh `533513314` |
| Public path | Candidate → 4 uncertainties → versioned object/mesh targets → 4 tasks |
| Required checks | 5, 4, 5, and 4; every task stays within 3–5 |
| Task status | All four are `未確認` |
| Fake evidence | No photo, GPS, answer, or municipal-review value is rendered |
| Evidence inputs | 0 public input/select/textarea controls in the M3 panel |
| Desktop click count | 5 |
| First meaningful render | 2,603ms in local headless Chromium against the final production preview |
| Human validation | `AWAITING_HUMAN_TEST` |
| Municipal validation | `AWAITING_MUNICIPAL_REVIEW` |

The render time is one local observation, not a performance guarantee or user-study result.

## Public screenshots

- [Landing](assets/m3-checkpoint/01-landing.png)
- [Four uncertainties](assets/m3-checkpoint/02-uncertainties.png)
- [PLATEAU and real-object targets](assets/m3-checkpoint/03-object-targets.png)
- [Four unverified tasks](assets/m3-checkpoint/04-unverified-tasks.png)
- [390 × 844 mobile task view](assets/m3-checkpoint/05-mobile-unverified-tasks.png)
- [Machine-readable capture evidence](assets/m3-checkpoint/manifest.json)

## Deterministic 30–60 second walkthrough

The narration target below is 55 seconds. It is a demonstration script, not a measured usability completion time.

1. 0–8s: Read “地図だけでは分からないことを、現地で確かめる場所とタスクに変える。”
2. 8–16s: Select the real Maizuru candidate 常団地前周辺 on the map.
3. 16–28s: Show the three known facts and four decision-relevant unknowns. Point to “なぜ重要？” rather than a generic task title.
4. 28–42s: Show the versioned targets: a bus-stop point, PLATEAU road, medical-facility point, PLATEAU building context, and an honest mesh fallback.
5. 42–55s: Show four tasks, each with 3–5 required checks, all marked `未確認`. State that no field answer or municipal conclusion has been invented.

The deterministic browser run reaches the last step in five clicks:

1. 地図から確認候補を選ぶ
2. 常団地前周辺を明示選択
3. まだ分からないことを見る
4. 確かめる場所を見る
5. 現地確認タスクを見る

## Candidate → uncertainty → object → task evidence

All target IDs below were found in the existing public spatial pack or retained as the analysis mesh itself.

| Uncertainty | Why it can change the finding | Target | Provenance | Required checks |
|---|---|---|---|---|
| 運行頻度・曜日・時間 | A nearby stop is not useful transport if service is absent | `bus-071` 常団地前バス停 | P11 2022 tracked derivative in pack `maizuru-533513314-plateau-2025-v1` | 5 |
| 実際の歩行経路 | An impassable segment invalidates straight-line accessibility | `tran_05dbefba-6a77-40ea-88ac-a568a63a2f05-0` 京月中央通線 | Project PLATEAU 舞鶴市2025 道路LOD1 | 4 |
| 医療・介護施設の現在の利用条件 | A closed or inaccessible facility cannot support the accessibility claim | `medical-105` 鹿野医院 plus context object `bldg_00962182-17d0-4fde-8970-784dd489dcf5` | P04 2020 tracked derivative plus Project PLATEAU 舞鶴市2025 building | 5 |
| 地域内の既存サービスと移動実態 | Existing local transport can change need and target population | mesh `533513314` | Honest mesh fallback; no PLATEAU object is claimed for an unrecorded service | 4 |

Spatial-pack evidence:

- Pack ID: `maizuru-533513314-plateau-2025-v1`
- Pack schema: `citygap.spatial-evidence-pack@1`
- Public classification: `public`
- Pack content SHA-256: `d5f0f99a32b3a956e48b96c5b6c78db04aba03dd4bc1e246e1dc49950303c804`
- Existing inventory: 296 buildings, 135 roads, 16 facilities, one analysis relation
- Finding: `mesh-533513314-accessibility-gap`
- Rule: `citygap-field-verification@1.0.0`

## Required task boundaries

The public slice displays requirements but does not collect them.

| Task | Required items | Conditional item |
|---|---:|---|
| Stop and service reality | 5 | Removal trace or alternative position only when no stop exists |
| Walking connectivity | 4 | None |
| Facility availability | 5 | Closure notice or relocation clue only when closed |
| Local service context | 4 | None |

Near/context photo labels are future evidence requirements only. There are no demo image files, attachment IDs, coordinates, answers, assignees, or reviews.

## Competitor-overlap audit

| Product strength | Overlap at M3 | Boundary observed |
|---|---|---|
| Field Maps assignment/status | Low at the public slice | No assignment optimization or generic task layer; only `未確認` is shown |
| Survey123 structured collection | Low at the public slice | No form builder and no public evidence collection |
| ArcGIS Urban 3D object inspection | Partial | 3D supplies target context, but the core screen starts from an analysis limitation and source boundary |
| PLATEAU urban-structure evaluation | Partial | CITY GAP does not add an indicator catalog; it turns unresolved limits into object-linked checks |
| Maptionnaire connected collection/analysis | Partial | No participation survey; stable Finding, target, and rule IDs are the distinguishing contract |
| My City Report lifecycle | Low | No citizen post, public report, or fabricated submitted state |
| Remix/Conveyal transport planning | Low | No route, frequency, timetable, GTFS, or scenario editor is introduced |

No official source reviewed in M0 confirmed the whole chain “analysis limitation → Finding → versioned PLATEAU object → bounded field task → human result back to Finding” as its central product flow. This is an official-source finding, not proof that no implementation exists anywhere.

## Current novelty assessment

Decision: `PROVISIONALLY_DIFFERENTIATED_AT_M3`.

The M3 slice is visibly different from a generic field-task product because the task reason, source limitation, Finding ID, dataset version, spatial-pack ID, object ID, and fixed rule version remain in one chain. It is also different from a generic PLATEAU viewer because the object is selected to resolve a stated analysis uncertainty, not merely inspected.

This is enough differentiation to justify human and municipal testing. It is not enough evidence to claim product value, workflow adoption, time savings, or superiority over Field Maps/Survey123.

Gate decision: `HOLD_M4_M6`.

Do not continue M4–M6 until a human/municipal checkpoint explicitly accepts the core chain or the user authorizes proceeding despite the remaining risks.

## Remaining value risks

1. A user may still perceive the task list as a thin Field Maps/Survey123 pre-step.
2. The representative building is context-only and must not be mistaken for the medical-facility building.
3. The 3D scene adds target understanding but may cost attention and load time.
4. Four tasks with up to five requirements may still be too dense for a 30-second first run.
5. The mesh fallback is honest but may weaken the perceived PLATEAU necessity for local-service uncertainty.
6. The public fixture and future municipal API can drift without a shared-schema CI check.
7. No first-time user has yet explained the closed loop in their own words.
8. No municipality has yet confirmed that provenance is more valuable than its current Field Maps, Survey123, paper, or consultant workflow.
9. Photo/GPS privacy, offline retention, conflict resolution, and review projection remain provisional and unvalidated.

## Provisional later-phase work

The uncommitted migration `028_field_verification_loop.sql` contains M4–M6-oriented schema work started before the course correction. It is retained, not extended, and is not evidence that Photo/GPS/Offline, Municipal Review, or Finding Feedback is value-validated.
