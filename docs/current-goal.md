# Current goal

Active goal: `public-first-run-ux-v1`

Current milestone: U3 refinement complete / U4 revalidation in progress

Gate: `HOLD_MAIN_PROMOTION / HOLD_P1_M4_M6`

Checkpoint state:

- execution branch: `feat/public-first-run-ux-v1`
- source branch: `feat/area-known-unknown-a5`
- Public UX evidence build: `54d0781ab0f98b7f46bd4c57204f1032dd3a558c`
- product checkpoint: `d829defc54dc9417d3045d2c2ecfb9f19558e08a`
- evidence checkpoint: `f3ae74e`
- browser-gate checkpoint: `9dce42a`
- baseline / origin/main at branch creation: `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff`
- commits since baseline: atomic product, evidence, and documentation checkpoints
- preservation: existing M3/028 and A0–A5 work retained; no reset, clean, rebase, squash, or force
- merge: not performed

Core value hypothesis:

> 自治体職員が経験的に感じている地域の状態を公開データとPLATEAUで定量化・可視化し、データだけでは判断できない部分を明示して次の確認へつなげる。

Internal contract:

```text
LOCAL INTUITION
  -> QUANTIFIED EVIDENCE
  -> KNOWN / UNKNOWN
  -> source limitation
  -> Finding
  -> versioned PLATEAU target / honest fallback
  -> 3–5 verification checks
  -> status = unverified
```

Validation status:

- AOI need: `DIRECT_MUNICIPAL_NEED_CONFIRMED`
- Area Summary content: `DIRECT_MUNICIPAL_NEED_PARTIALLY_CONFIRMED`
- Known/Unknown value: `DIRECT_MUNICIPAL_VALUE_SIGNAL_CONFIRMED`
- Unknown-to-field-task workflow: `AWAITING_MUNICIPAL_WORKFLOW_REVIEW`
- Automated Public UX: `AUTOMATED_UX_CHECKPOINT_COMPLETE`
- Human-test readiness: `READY_FOR_HUMAN_TEST`
- Public copy comprehension: `AWAITING_HUMAN_TEST`

Product boundary:

- `Investigation Area` is the center; station is one convenient `point_radius` origin.
- P0 supports station/map point, 500/800/1000m and bounded custom radius.
- 800m is a policy-analysis radius, not an actual walking-time isochrone.
- The feature branch makes the new Area first-run journey its Public root. `main` and GitHub Pages keep the current entry until a separate promotion decision after human and municipal review.
- Public Area displays no photo, GPS, answer, assignee, or municipal review.
- Area selection and aggregation are not the novelty. The provisional differentiation is the traceable Area → Known/Unknown → Finding → PLATEAU target → verification chain.
- M4 Photo/GPS/Offline, M5 Municipal Review, M6 Finding Feedback, pedestrian isochrone, polygon drawing, and Borehole UI are not authorized by this goal.

Active Public execution rules:

- Unknown cards in the Public first view contain only what is still unknown and why it should be checked. Dataset, version, source limitation, coverage, rule, model code, and object provenance are consolidated in one collapsed `出典・データの注意点` disclosure. Only a short, material misunderstanding warning may appear inline.
- The PLATEAU object, source/version, coverage, and WebGL checks are necessary but not sufficient for 3D. `3Dで周辺を見る` is rendered only when 3D adds understandable spatial context beyond the 2D map. A technically eligible single road point or single-building current-use check remains 2D when 3D adds no decision information.
- A zero-button 3D result is an acceptable UX outcome. U4 records both the technical gate and the UX reason for every displayed or withheld case.

Maizuru borehole evidence:

- Evidence status: `DIRECT_MUNICIPAL_USE_CASE_OVERLAP_CONFIRMED`.
- Maizuru's current-year use case is considering borehole columns on a PLATEAU 3D city model together with liquefaction maps and landslide or other hazard data.
- `PLATEAU 3D + borehole columns + hazard layers` is therefore not CITY GAP novelty.
- Borehole strategy is `INTEGRATE / RESEARCH ONLY`, not an automatic P1 implementation.
- CITY GAP will not build its own borehole viewer, 3D column viewer, or hazard-and-borehole viewer. A later, separately approved goal may only assess whether Maizuru outputs can be connected as an official Investigation Area source with provenance and source limitations intact.

Current stop state:

- `AUTOMATED_UX_CHECKPOINT_COMPLETE`
- `READY_FOR_HUMAN_TEST`
- `AWAITING_HUMAN_TEST`
- `AWAITING_MUNICIPAL_WORKFLOW_REVIEW`
- `HOLD_MAIN_PROMOTION`
- `HOLD_P1_M4_M6`
- `BOREHOLE_INTEGRATE_RESEARCH_ONLY`

Next action is a real participant study and a separate municipal workflow review. Do not begin P1 or M4–M6 and do not promote to `main` automatically.
