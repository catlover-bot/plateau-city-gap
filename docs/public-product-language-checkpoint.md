# Public product language automated checkpoint

Goal: `public-product-language-and-section-v1`  
Baseline: `a365dc04ccbcfad020d8f6ff2cd63db6e7865d60`  
Execution branch: `feat/public-product-language-section-v1`

This checkpoint records production-preview behavior and repeatable visual inventory. It does **not** establish that the Japanese sounds natural to people or that the interface has ceased to look like a prototype. Those remain human judgments.

## Outcome

- The Public journey remains five clicks: place → radius → Area evidence → uncertainty → verified target or honest fallback.
- Desktop map/panel remains `67.9 / 32.1`; mobile map share is `44.5%` while selecting and `31.8%` for result/target.
- Map/panel overlap and horizontal overflow are zero at 1440×900, 1280×720, 390×844, and DPR 2.
- The initial reading path has no detected English internal terms; exact provenance remains inside `出典・データの注意点`.
- Exact road/building geometry, registered facility position, Area fallback, five stories, and the existing data contract are unchanged.
- Urban Section decision is **C / Advanced only**. No Public section, cut line, or section legend was added. Legacy M3 and Advanced remain reachable.
- Subjective tone and visual finish are explicitly awaiting human review.

## Production, feature baseline, and after evidence

The public GitHub Pages production was captured independently and was not changed:

- [production desktop](assets/public-product-audit/production-landing-desktop.png)
- [production mobile](assets/public-product-audit/production-landing-mobile.png)
- [production guided Urban Section](assets/public-product-audit/production-guided-section.png)
- [production Advanced Urban Section](assets/public-product-audit/production-advanced-section.png)

The exact feature baseline commit was rebuilt in a detached worktree and compared with the current branch under the same Playwright Chromium protocol:

| State | Before | After |
|---|---|---|
| Landing | [before](assets/public-product-language-checkpoint/before-01-landing-desktop.png) | [after](assets/public-product-language-checkpoint/after-01-landing-desktop.png) |
| Place | [before](assets/public-product-language-checkpoint/before-02-place-desktop.png) | [after](assets/public-product-language-checkpoint/after-02-place-desktop.png) |
| Radius | [before](assets/public-product-language-checkpoint/before-03-radius-desktop.png) | [after](assets/public-product-language-checkpoint/after-03-radius-desktop.png) |
| Population story | [before](assets/public-product-language-checkpoint/before-04-population-desktop.png) | [after](assets/public-product-language-checkpoint/after-04-population-desktop.png) |
| Building story | [before](assets/public-product-language-checkpoint/before-05-building-desktop.png) | [after](assets/public-product-language-checkpoint/after-05-building-desktop.png) |
| Selected uncertainty | [before](assets/public-product-language-checkpoint/before-06-unknown-desktop.png) | [after](assets/public-product-language-checkpoint/after-06-unknown-desktop.png) |
| Exact road | [before](assets/public-product-language-checkpoint/before-07-road-target-desktop.png) | [after](assets/public-product-language-checkpoint/after-07-road-target-desktop.png) |

Additional after evidence:

- [exact building](assets/public-product-language-checkpoint/after-08-building-target-desktop.png)
- [registered facility position](assets/public-product-language-checkpoint/after-09-facility-reference-desktop.png)
- [honest Area fallback](assets/public-product-language-checkpoint/after-10-area-fallback-desktop.png)
- [mobile result](assets/public-product-language-checkpoint/after-04-population-mobile.png)
- [mobile target](assets/public-product-language-checkpoint/after-07-road-target-mobile.png)
- [DPR 2 target](assets/public-product-language-checkpoint/after-07-road-target-dpr2.png)

Every screenshot record includes URL, viewport, device scale factor, commit, byte size, physical dimensions, and SHA-256 in [the comparison manifest](assets/public-product-language-checkpoint/manifest.json). The separate [cartographic manifest](assets/public-product-language-cartography/manifest.json) verifies rendered pixels and source provenance.

## Automated visual inventory

Counts use the same DOM/computed-style procedure before and after. They are diagnostics, not an aesthetic score.

| State | Cards before→after | Nested surfaces | Pills/badges | Rounded containers | Bordered containers | Explanatory paragraphs |
|---|---:|---:|---:|---:|---:|---:|
| Landing | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 | 2→1 |
| Place | 2→2 | 0→0 | 4→0 | 3→0 | 9→4 | 4→3 |
| Radius | 0→0 | 0→0 | 4→0 | 0→0 | 6→2 | 2→1 |
| Result | 7→8 | 4→5 | 13→5 | 2→0 | 12→9 | 3→2 |
| Selected uncertainty | 8→8 | 6→7 | 8→2 | 4→0 | 13→12 | 3→3 |
| Exact road target | 1→1 | 1→1 | 5→0 | 2→0 | 8→5 | 3→1 |

The semantic `article`/group count does not fall in every result state: result increases by one and measured nesting increases by one because separately selectable information and uncertainty rows remain represented as semantic objects. The reduction is in repeated decorative badges, rounding, borders, duplicate headings, and explanatory prose. This distinction prevents a lower component count from being presented as proof of better UX.

No panel shadow or decorative gradient was introduced. Public Urban Section labels and legends are `0` in every measured state.

## Copy review evidence

The complete current/problem/proposed/rationale inventory is in [the copy deck](public-copy-deck.md).

| Category | Before | Final |
|---|---|---|
| Landing support — shortened | `場所と範囲を選ぶと、人口・年齢、建物の使われ方、事業所、都市計画、交通をまとめて確認できます。データだけでは判断できない点も整理します。` | `場所と範囲を選ぶと、人口や建物、事業所、都市計画、交通をまとめて見られます。データだけでは分からないことも示します。` |
| Landing disclaimer — moved | Claim-boundary paragraph visible before action | Removed from Landing; claim boundaries remain with methodology/source details |
| Progress — replaced | Four numbered circles | One line: `1 / 4 場所` through `4 / 4 現地確認` |
| Place — renamed | `どこを調べますか？` / `選んだ駅を起点にする` / `地図上の任意地点` | `調べる場所を選ぶ` / `この駅を選ぶ` / `地図から選ぶ` |
| Radius — shortened | `どの範囲を見ますか？` / `この範囲を調べる` | `範囲を選ぶ` / `この範囲を見る` |
| Result — renamed | `分かっていることと、まだ分からないこと` plus a duplicate evidence heading | `この範囲で分かること` |
| Uncertainty — renamed | Long `ただし…` sentence in a strong callout | `まだ現地で確かめたいこと` with plain selectable rows |
| Target — renamed | `データだけでは分からないことを、場所で確かめる` | `現地で確認する場所` |
| Checks — named plainly | Unlabelled list | `現地で見るポイント` |
| Map target — renamed | `PLATEAU上の確認対象` / `実データ上の確認対象` | `確認する場所` and the actual target kind |
| Sources — moved to details | `coverage`, `version`, `Area/content`, raw object metadata in visible prose | `出典・データの注意点`; exact identity only under a Japanese label in details |
| Claim safety — unchanged | 800 m is a radius reference, not actual ten-minute reach | Same meaning retained under `半径800mについて` |

### Final copy by stage

- Landing: `気になる場所を、地図とデータで確かめる。`
- Place: `調べる場所を選ぶ`; `駅を選ぶ`; `この駅を選ぶ`; `地図から選ぶ`; `この場所を選ぶ`
- Radius: `範囲を選ぶ`; `500m / 800m / 1km / その他`; `この範囲を見る`
- Result: `この範囲で分かること`
- Uncertainty: `まだ現地で確かめたいこと`
- Target: `現地で確認する場所`; `現地で見るポイント`; one `未確認`
- Sources/details: `出典・データの注意点`

Public contains no new claim of current/latest/real-time data, recommendation, safety, AI judgment, or actual walking-time reach.

## Urban Section decision

Decision: **Option C — move it out of the Public first-run and retain it in Advanced/legacy M3.**

The cross-section is valid expert evidence, but it does not answer a demonstrated question in the Area first-run, is not synchronized to its selected target with an A/B line, and becomes too dense on mobile. Adding that missing behavior would be a new visualization feature with no validated first-run need. The Public user-facing title, map/section synchronization, and Public mobile section are therefore **not applicable**, not silently missing. Full rationale is in [the Urban Section audit](urban-section-audit.md).

## Layout and interaction

| Viewport/state | Map / panel | Map occlusion | Controls | Primary CTA | Overflow / overlap |
|---|---:|---:|---:|---:|---:|
| 1440×900 result | 67.9 / 32.1% | 0.2% | 10–13 by selected state | 1 | 0 / 0 |
| 1280×720 result | 67.9 / 32.1% | 0.3% | 10–12 | 1 | 0 / 0 |
| 390×844 selection | 44.5 / 55.5% | 2.8% | 8–10 | 1 | 0 / 0 |
| 390×844 result/target | 31.8 / 68.2% | 3.9% | 5–11 | 1 / 0 terminal | 0 / 0 |

Public top-level primary navigation remains `0`; the header contains the one secondary utility `詳細分析`. Landing-to-target remains `5` clicks. The target state is terminal and therefore has no primary CTA.

## Cartography and target integrity

- Five Summary stories remain available; one story layer is active at a time.
- Exact road and building targets render the source polygons; the facility renders its registered source position; the fallback renders the Area and does not invent an object.
- The cartographic derivative manifest validates the same Maizuru 2025 CityGML source hash, Area ID/version/hash, generator/rule version, target IDs, feature counts, geometry types, and artifact hashes.
- Public shows no evidence input and no raw internal object ID in its initial reading path.
- Contextual 3D displays `0` buttons by design: the resolved single-road case is technically eligible but adds no decision information beyond exact 2D, while fallback is ineligible. Zero display is an accepted and tested outcome.

## Performance

The exact source baseline was:

| Path | Baseline median | H5 isolated median | Gate |
|---|---:|---:|---:|
| FMR | 1685.3 ms | 1549.8 ms | ≤2000 ms — pass |
| 800m Area | 174.4 ms | 135.8 ms | ≤1000 ms — pass |
| Building story cold / warm | 2673.4 / 1739.5 ms | 2366.9 / 1336.3 ms | ≤3000 / ≤2000 — pass |
| Exact building cold / warm | 1295.0 / 1098.3 ms | 1063.9 / 1016.1 ms | ≤3500 / ≤2500 — pass |
| Facility cold / warm | 1227.9 / 938.0 ms | 1081.2 / 1022.1 ms | ≤2500 / ≤1500 — pass |
| Exact road cold / warm | 1045.3 / 1052.5 ms | 928.0 / 961.0 ms | ≤2500 / ≤1800 — pass |

An earlier H5 five-sample run recorded FMR `[1864.6, 2602.7, 7506.9, 3141.0, 1407.5]`, median `2602.7 ms`, and therefore failed the FMR gate. The isolated repeat recorded `[3628.8, 1564.8, 1296.7, 1370.0, 1549.8]`, median `1549.8 ms`. Both raw profiles are retained. The final isolated protocol passes, but cold-start variance remains a measured risk rather than being hidden.

## Accessibility and regression evidence

- Automated accessibility: critical/serious `0`; visible H1 count `1`; unnamed controls `0`; duplicate IDs `0`.
- Keyboard sequence and visible focus: pass in the cartographic checkpoint.
- Mobile touch targets, reduced motion, and no horizontal overflow: pass in PLATEAU-native and legacy M3 browser checks.
- Public forbidden-copy, internal-ID, fake/restricted evidence input, and invented target scans: pass.
- Advanced and legacy M3 routes: pass; M3 retains 3 known facts, 4 uncertainties, 5 real targets, 4 tasks, checks `[5,4,5,4]`, status `未確認`, and zero field-evidence inputs.

## Local verification

| Gate | Result |
|---|---|
| ESLint | pass |
| TypeScript | pass |
| Vitest | 24 files / 104 tests passed |
| Public production build | pass |
| Municipal production build | pass with `VITE_CITYGAP_SURFACE=municipal` |
| Markdown links | 88 files passed |
| Ruff | pass |
| Python unit/API tests | 414 passed; one upstream Starlette deprecation warning |
| Fresh migrations | 001–029 applied; status ready, problems `[]` |
| PostGIS/API integration | 18 passed on a dedicated temporary database |
| `pip-audit` | no known vulnerabilities; editable project explicitly skipped |
| `npm audit --audit-level=high` | 0 vulnerabilities |
| Public browser | pass after an isolated rerun; 5 clicks, all viewport/layout gates met |
| PLATEAU-native browser | 19 checks passed |
| Cartographic checkpoint | 19 screenshots, exact/reference/fallback targets, provenance and accessibility passed |
| Legacy M3 | pass after an isolated rerun; first parallel run timeout retained as environment-contention evidence |
| Urban Futures / Open Data audit | 20 / 42 checks passed; 120 open-data goals verified |
| `git diff --check` | pass |

The migration/integration database was created only for H5, verified, and removed after the tests. No existing development or municipal database was used or deleted.

## Human review boundary

[The human review sheet](public-product-human-review.md) is blank and ready for real participants. No answer, aesthetic preference, comprehension result, or municipal workflow result was generated or inferred.

Current status:

```text
AUTOMATED_PUBLIC_PRODUCT_LANGUAGE_CHECKPOINT_COMPLETE
READY_FOR_SELF_VISUAL_REVIEW
READY_FOR_COPY_REVIEW
SUBJECTIVE_TONE_AWAITING_HUMAN_REVIEW
AWAITING_HUMAN_TEST
AWAITING_MUNICIPAL_WORKFLOW_REVIEW
HOLD_MAIN_PROMOTION
HOLD_P1_M4_M6
BOREHOLE_INTEGRATE_RESEARCH_ONLY
```

## Remaining risks

1. Naturalness, restraint, and perceived product maturity are subjective and still untested with real people.
2. Result/Unknown still contains multiple semantic rows and dividers; automated counts cannot determine whether it feels dense.
3. The 32% desktop panel requires scrolling to see all five stories and uncertainty; human review must determine whether the reading sequence is obvious.
4. Cold FMR remains variable even though the isolated five-sample median passes.
5. The 4,898-feature building story remains the heaviest valid layer.
6. Public removing the cross-section may hide a useful expert question not yet discovered; Advanced preserves it while evidence is gathered.
7. External basemap availability remains outside CITY GAP control; the local-vector degraded path is tested but should be reviewed on real devices.
