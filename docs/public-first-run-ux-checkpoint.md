# Public first-run UX automated checkpoint

Goal: `public-first-run-ux-v1`

Evidence build commit: `54d0781ab0f98b7f46bd4c57204f1032dd3a558c`

Machine-readable evidence: [manifest](assets/public-first-run-ux/manifest.json)

This is an automated UX checkpoint. It is not a human usability result or a municipal workflow approval.

## 1–5. Repository checkpoint

1. Branch: `feat/public-first-run-ux-v1`.
2. Baseline / `origin/main` at branch creation: `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff`.
3. Evidence build HEAD: `54d0781ab0f98b7f46bd4c57204f1032dd3a558c`.
4. Commits preserve the source history; no reset, clean, rebase, squash, or force push was used.
5. The evidence build worktree contained only the U4 audit script, tests, documents, and screenshot evidence awaiting the final atomic checkpoint commit.

Main, GitHub Pages, and the production Public root were not changed.

## 6. Before / after screenshots

Before evidence from the preserved A5 journey:

- [Before: Area origin](assets/area-checkpoint/01-area-origin.png)
- [Before: Known / Unknown](assets/area-checkpoint/02-area-known-unknown-800m.png)
- [Before: unverified tasks](assets/area-checkpoint/03-area-unverified-tasks-800m.png)
- [Before: mobile task](assets/area-checkpoint/05-area-mobile-tasks-800m.png)

After evidence:

- [Landing desktop](assets/public-first-run-ux/01-landing-desktop.png)
- [Place / radius desktop](assets/public-first-run-ux/02-place-radius-desktop.png)
- [Known / Unknown desktop](assets/public-first-run-ux/03-known-unknown-desktop.png)
- [Target / task desktop](assets/public-first-run-ux/04-target-task-desktop.png)
- [Contextual 3D enabled](assets/public-first-run-ux/05-contextual-3d-enabled.png)
- [Landing mobile](assets/public-first-run-ux/06-landing-mobile.png)
- [Place / radius mobile](assets/public-first-run-ux/07-place-radius-mobile.png)
- [Known / Unknown mobile](assets/public-first-run-ux/08-known-unknown-mobile.png)
- [Target / task mobile](assets/public-first-run-ux/09-target-task-mobile.png)
- [Mesh fallback with 3D disabled](assets/public-first-run-ux/10-mesh-fallback-3d-disabled.png)

The manifest records viewport, URL, evidence-build commit, byte size, and SHA-256 for every after screenshot.

## 7–9. Density comparison

| Viewport / state | Visible controls before | Visible controls after | Map share before | Map share after | Occlusion before | Occlusion after |
|---|---:|---:|---:|---:|---:|---:|
| 1440×900 landing | 14 | 6 | 46% | 67.9% | 7.9% | 0.2% |
| 1280×720 landing | 13 | 6 | 46% | 67.9% | 11.3% | 0.3% |
| 390×844 place/radius | 12 | 10 | 29% | 44.5% | 38.8% | 2.8% |
| 390×844 result | 12 | 6 | 29% | 31.8% | 38.8% | 3.9% |
| 390×844 target | 12 | 5 | 29% | 31.8% | 38.8% | 3.9% |

The prior 20px mobile overlap is reduced to zero measured map/panel overlap and zero horizontal overflow.

## 10–11. Navigation and primary actions

- Public top-level primary navigation: 0.
- Header secondary action: one, `詳細分析`.
- Primary CTA count:
  - Intro: 1.
  - Place: 1.
  - Radius: 1 after the radius choice.
  - Result: 1.
  - Target: 0 because it is the terminal evidence state.
- Landing to target: 5 clicks.

## 12. Technical and internal terms removed

The Public first view no longer exposes:

- `QUANTIFIED EVIDENCE`
- `KNOWN / UNKNOWN`
- `PLATEAU TARGET → VERIFICATION`
- `旧M3`
- `object ID` as initial content
- long methodology descriptions inside radius buttons
- the word `今` in the landing heading

The compatibility route `?journey=m3` remains available without exposing the internal route name in the first-run body.

The prohibited walking claims scan found none of:

- `徒歩10分圏`
- `10分以内に歩ける`
- `walking isochrone`
- `実際に徒歩で到達できる`
- `道路ネットワーク上の徒歩圏`

## 13. Final landing copy

> 気になる場所を、  
> 地図とデータで確かめる。

> 場所と範囲を選ぶと、人口・年齢、建物の使われ方、事業所、都市計画、交通をまとめて確認できます。データだけでは判断できない点も整理します。

Primary CTA: `地図で場所を調べる`.

## 14. Final radius copy

Persistent buttons contain only:

- `500m`
- `800m`
- `1km`
- `その他`

The selected radius is explained progressively. The exact 800m explanation is:

> 800mは、国土交通省の都市構造評価で一般的な徒歩圏の目安として使われる距離です。実際の徒歩10分到達圏を示すものではありません。

Custom radius remains a single integer field bounded to 100–3000m.

## 15. Area Summary presentation

The first summary is five groups, not a 20-card dashboard:

1. 人口・年齢
2. 建物の使われ方
3. 事業所
4. 都市計画
5. 交通

Each metric retains its source and limitation disclosure. Secondary datasets are not deleted and remain behind details when present.

## 16. Unknown presentation

Known and Unknown remain in one continuous scroll panel. Public Unknown is limited to three items. Each selectable card contains:

- `未確認`
- the unknown in plain Japanese
- why it matters
- the source limitation

The fourth contract item remains in data but is not promoted into the first view.

## 17. PLATEAU target presentation

The terminal state shows:

- a user-facing building, road, or range label
- a stable centered target marker in 2D
- 3–5 required checks
- status `未確認`

The sampled West Maizuru 800m task contained four required checks. Internal source object IDs are available only through the source disclosure. No photo, GPS, answer, assignee, or municipal review field is rendered.

## 18. Contextual 3D behavior

Automated positive case:

- resolved PLATEAU road target
- matching Area data
- matching PLATEAU source/version
- verified content hash
- WebGL available
- `3Dで場所を見る` displayed

Automated negative case:

- arbitrary map-point mesh fallback
- no resolved PLATEAU object
- 3D control absent
- 2D target presentation retained

3D is never the default.

## 19–20. Desktop and mobile results

Desktop:

- map/panel: 67.9/32.1
- maximum visible controls: 11
- maximum measured map occlusion: 0.3%
- map/panel overlap: 0
- horizontal overflow: 0

Mobile 390×844:

- place/radius map share: 44.5%
- pip security audit: no known vulnerabilities; editable CITY GAP distribution skipped as expected
- result/target map share: 31.8%
- maximum measured map occlusion: 3.9%
- map/panel overlap: 0
- horizontal overflow: 0
- current selection, back action, and primary action remain visible

## 21. Keyboard and accessibility

Deterministic checks found:

- zero critical/serious structural accessibility findings
- one visible `h1` per state
- named interactive controls
- no duplicate IDs
- no missing image alternative text
- visible focus styling on the interactive sequence
- keyboard access to brand, `詳細分析`, map, zoom, attribution, and the primary CTA
- no browser page errors or same-origin request failures

The two terminal Tab-cycle entries that returned focus to `body` are recorded in the manifest and are not counted as an interactive focus failure. A real assistive-technology study is still required.

## 22–23. Clicks and performance

- Landing → target: 5 clicks.
- Cold-navigation FMR samples: 1,823 / 1,216 / 2,534 / 1,953 / 1,190 ms.
- Median FMR: 1,823 ms.
- Target: median ≤3,000 ms.
- Public Vite production build: 39.51 seconds for the final evidence build.

## 24. Local tests

Passed locally:

- `ruff check analysis backend`
- `pytest analysis/tests backend/tests -q`: 409 passed, one dependency deprecation warning
- frontend lint: 0 errors / 0 warnings
- frontend typecheck
- frontend Vitest: 89 passed
- frontend production build
- documentation link audit: all 73 documents resolved before adding this checkpoint; rerun is required after final docs
- npm security audit: 0 vulnerabilities
- PLATEAU-native browser audit: passed
- visual-identity audit: passed, no console errors or local HTTP failures
- legacy M3 browser regression at `?journey=m3`: passed
- Municipal Service build with `VITE_CITYGAP_SURFACE=municipal`: passed
- Public fake/restricted evidence scan: no field inputs and no initially visible internal ID

Database migrations, backend contracts, and data fixtures were not changed by this goal. PostGIS migration and integration jobs remain delegated to unchanged remote CI.

## 25. Remote CI

Remote CI is recorded after the final feature-branch push. The branch must not trigger Pages deployment because Pages is limited to `main`.

If branch CI cannot run, the status remains unresolved; workflows and `main` must not be modified to work around it.

## 26–27. Human-test readiness

Status:

- `AUTOMATED_UX_CHECKPOINT_COMPLETE`
- `READY_FOR_HUMAN_TEST`
- `AWAITING_HUMAN_TEST`
- `AWAITING_MUNICIPAL_WORKFLOW_REVIEW`

Prepared package: [public first-run human-test package](public-first-run-human-test.md).

No participant response was created or inferred.

## 28. Remaining usability and value risks

- First-time users may understand Known/Unknown but not see a place for the verification result in an actual municipal meeting, GIS, or form.
- Area Summary content is only partially confirmed; the exact urban-planning restrictions still require municipal clarification.
- The target map depends on external background tiles. A deterministic center marker prevents target loss, but background detail may still arrive late.
- Contextual 3D can add explanation cost even when technically eligible.
- Some users may interpret a radius as a travel-time area despite the progressive methodology disclosure.
- Public first-run comprehension may pass while the Unknown-to-task workflow still overlaps with existing Field Maps, Survey123, or paper practice.
- The core differentiation is only provisional until real participants and a separate municipal workflow review evaluate the traceable reason chain.

## Stop decision

U4 stops here. Do not start P1, Borehole, M4 Photo/GPS/Offline, M5 Municipal Review, M6 Finding Feedback, a `main` merge, or a Pages deployment.

Borehole remains `INTEGRATE / RESEARCH ONLY`.
