# Cartographic performance review package

Goal: `cartographic-interaction-performance-v1`

Status: `READY_FOR_SELF_VISUAL_REVIEW / READY_FOR_HUMAN_TEST / AWAITING_HUMAN_TEST`

No participant response is pre-filled. This worksheet is preparation only.

## Evidence to review

- [Automated checkpoint](cartographic-performance-checkpoint.md)
- [Machine-readable screenshot manifest](assets/cartographic-performance-checkpoint/manifest.json)
- [Area and population](assets/cartographic-performance-checkpoint/02-area-800m-population-age.png)
- [Building-use story](assets/cartographic-performance-checkpoint/03-story-building-use.png)
- [Planning story](assets/cartographic-performance-checkpoint/05-story-urban-planning.png)
- [Transport story](assets/cartographic-performance-checkpoint/06-story-transport.png)
- [Unknown selection](assets/cartographic-performance-checkpoint/07-unknown-road-highlight.png)
- [Exact road target](assets/cartographic-performance-checkpoint/08-target-road-exact.png)
- [Exact building target](assets/cartographic-performance-checkpoint/09-target-building-exact.png)
- [Facility registered position](assets/cartographic-performance-checkpoint/10-target-facility-reference.png)
- [Honest fallback](assets/cartographic-performance-checkpoint/13-target-area-fallback.png)
- [Mobile result](assets/cartographic-performance-checkpoint/15-mobile-result.png)
- [Mobile exact road](assets/cartographic-performance-checkpoint/16-mobile-target-road-exact.png)

## Self visual-review checklist

Record `pass`, `fail`, or `unclear`; add the observed reason rather than an inferred one.

| Check | Result | Observation |
|---|---|---|
| Area boundary and outside mask remain understandable |  |  |
| Population legend and 2020/500 m mesh limitation remain visible |  |  |
| Building-use legend says official attribute, not current inferred use |  |  |
| Planning and transport each show only their intended story |  |  |
| Unknown selection explains why confirmation is needed |  |  |
| Exact road shape is visibly a road object, not a point substitute |  |  |
| Exact building shape is visibly a building object, not a point substitute |  |  |
| Facility is clearly a registered position, not PLATEAU exact geometry |  |  |
| Fallback is clearly an Area/mesh fallback |  |  |
| Loading and degraded states are honest and non-blocking |  |  |
| Mobile retains map context, current story, and primary action |  |  |
| No visual redesign or information loss is observed relative to C5 |  |  |

## First-run human task

Participant profile: CITY GAP初見。At least one mobile participant is recommended. Municipal workflow fit is evaluated separately.

1. Open the Public feature-branch URL.
2. Choose the station origin and 800 m radius.
3. Explain what the map and Summary say is known.
4. Switch to building use, planning, and transport.
5. Choose one Unknown and open its confirmation place.
6. Return and compare an exact building, exact road, facility position, and fallback when prompted by the moderator.
7. On mobile, repeat the building story and exact-road target path.

Do not teach target grammar before the participant attempts the task.

## Empty response sheet

Participant ID:  
Date / device / viewport:  
Domain background:  

| Observation | Result / words used | Time or clicks |
|---|---|---:|
| First meaningful content recognized |  |  |
| 800 m Area understood as a radius, not walking-time reach |  |  |
| Known/Unknown relationship explained |  |  |
| Building story understood without inferred-current-use claim |  |  |
| Exact PLATEAU object distinguished from registered position |  |  |
| Honest fallback distinguished from exact object |  |  |
| Loading/degraded state noticed and trusted |  |  |
| `未確認` meaning found |  |  |
| Mobile task completed |  |  |
| Confusing or slow moment, verbatim |  |  |

Accessibility observations: keyboard/focus/zoom/motion/contrast/assistive technology notes.  

## Municipal workflow review — separate sheet

Reviewer role / organization:  
Date:  

1. Which meeting, GIS, report, or investigation step could use Area → Known/Unknown → confirmation place?
2. Is the exact object / registered position / fallback distinction operationally useful?
3. Does performance feel adequate on the municipality's actual device and network?
4. Which delays or degraded states would prevent use?
5. Does the workflow duplicate an existing specialized viewer or field-task product?

Verbatim answer and decision:  

The checkpoint remains `AWAITING_HUMAN_TEST` and `AWAITING_MUNICIPAL_WORKFLOW_REVIEW` until real responses are supplied. Automated timing and Codex self-review must not be substituted for either decision.
