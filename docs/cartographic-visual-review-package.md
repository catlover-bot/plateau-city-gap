# Cartographic visual review package

Goal: `citygap-cartographic-visual-productization-v1`

Status: `READY_FOR_VISUAL_REVIEW / READY_FOR_HUMAN_TEST`

Responses recorded: **none**

This worksheet is prepared for real participants. It intentionally contains no generated, inferred, or placeholder participant answer. Automated screenshot evidence is supporting material only.

## Suggested participants

- Five or more people seeing CITY GAP for the first time.
- About two with municipal, GIS, planning, or related domain experience.
- About three without that domain background.
- At least one participant on a mobile-size viewport.
- Municipal workflow fit is reviewed separately from first-run comprehension.

## Moderator setup

1. Use the feature-branch production build; do not use or modify `main`.
2. Start at the Public root with no explanation of the intended concept.
3. Ask the participant to investigate the displayed Maizuru Area and reach a verification target.
4. Do not explain the map legend, Area radius, exact/reference/fallback distinction, or Unknown in advance.
5. Record observed actions and verbatim responses. Do not paraphrase a negative response into a positive one.

## 30–60 second task

> 気になる場所と範囲を選び、この地域についてデータから確認できたこと、まだ判断できないこと、現地で確認する場所を見つけてください。

Mobile participants use the same task at 390 x 844 or an equivalent device viewport.

## Review sequence

| Scene | Evidence | Question |
|---|---|---|
| 800m Area | [800m screenshot](assets/cartographic-checkpoint/02-area-800m-population-age.png) | Three seconds以内に選択範囲と起点を指せるか |
| 500m / 1km | [500m](assets/cartographic-checkpoint/11-area-500m.png) / [1km](assets/cartographic-checkpoint/12-area-1km.png) | 半径変更が地図の範囲変更として理解できるか |
| Summary story | [building use](assets/cartographic-checkpoint/03-story-building-use.png) | 数値と地図表現を同じ根拠の説明として結び付けられるか |
| Unknown | [road Unknown](assets/cartographic-checkpoint/07-unknown-road-highlight.png) | 何が未確認で、なぜ確認が必要か説明できるか |
| Exact road/building | [road](assets/cartographic-checkpoint/08-target-road-exact.png) / [building](assets/cartographic-checkpoint/09-target-building-exact.png) | PLATEAUの実形状が確認対象だと理解できるか |
| Registered position | [facility](assets/cartographic-checkpoint/10-target-facility-reference.png) | 実形状ではなく登録位置だけだと区別できるか |
| Area fallback | [fallback](assets/cartographic-checkpoint/13-target-area-fallback.png) | 対象objectを捏造していないことが伝わるか |
| Basemap unavailable | [degraded](assets/cartographic-checkpoint/14-basemap-degraded-local-vectors.png) | 背景地図障害と分析データを区別し、現在地を見失わないか |
| Mobile | [result](assets/cartographic-checkpoint/15-mobile-result.png) / [target](assets/cartographic-checkpoint/16-mobile-target-road-exact.png) | mapとpanelを往復し、未確認状態を発見できるか |

## Empty participant record

Participant ID: __________

Date/time: __________

Viewport/device: __________

Domain experience: __________

| Observation | Record |
|---|---|
| First meaningful action | |
| Click count | |
| Time to first Area recognition | |
| Time to target | |
| Hesitation/backtracking | |
| Keyboard/touch/accessibility observation | |
| Verbatim explanation of Known/Unknown | |
| Verbatim explanation of PLATEAU target | |
| Exact/reference/fallback distinction | |
| 800m radius versus actual walking reach distinction | |
| `未確認` state found | |
| Mistaken AI/policy/safety interpretation | |
| Most confusing point | |
| Most useful point | |

No participant response has been entered.

## Comprehension prompts

Ask only after the unguided task:

1. この地図で最初に分かったことは何ですか。
2. 何がまだデータだけでは判断できませんか。
3. 紫色で示された対象は何ですか。
4. 建物・道路の実形状、登録地点、範囲fallbackの違いは何ですか。
5. 800mは実際に徒歩10分で到達できる範囲ですか。
6. CITY GAPは地域の安全性や政策を自動判断していますか。

## Acceptance method

- Record real answers first, then score against the predeclared criteria.
- First-run comprehension target remains at least four of five participants explaining Area → quantified evidence → Known/Unknown → PLATEAU target in their own words.
- At least four of five must reject AI policy/safety judgment and distinguish the 800m radius from an actual walking-time isochrone.
- At least four of five must distinguish an exact PLATEAU shape from a registered position and honest Area fallback.
- The mobile participant must complete the journey without horizontal overflow and find `未確認`.
- A slow or failed target load is a failure observation, not a reason to coach the participant.
- Negative or contradictory results remain in the record.

Passing this first-run package does not by itself validate municipal workflow fit. Municipal workflow review remains `AWAITING_MUNICIPAL_WORKFLOW_REVIEW`.

## Current decision

```text
READY_FOR_VISUAL_REVIEW
READY_FOR_HUMAN_TEST
AWAITING_HUMAN_TEST
AWAITING_MUNICIPAL_WORKFLOW_REVIEW
HOLD_MAIN_PROMOTION
HOLD_P1_M4_M6
```

No promotion decision is authorized by this package.
