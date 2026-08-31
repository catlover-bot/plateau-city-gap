# Current goal

Active goal: `area-known-unknown-to-task-v1`

Current milestone: A5 Preservation & Validation Prep complete

Gate: `HOLD_P1_M4_M6`

Checkpoint state:

- branch: `feat/area-known-unknown-a5`
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
- Public copy comprehension: `AWAITING_HUMAN_TEST`

Product boundary:

- `Investigation Area` is the center; station is one convenient `point_radius` origin.
- P0 supports station/map point, 500/800/1000m and bounded custom radius.
- 800m is a policy-analysis radius, not an actual walking-time isochrone.
- Existing M3 remains the primary public entry until first-time-user validation; Area is a secondary experimental route.
- Public Area displays no photo, GPS, answer, assignee, or municipal review.
- Area selection and aggregation are not the novelty. The provisional differentiation is the traceable Area → Known/Unknown → Finding → PLATEAU target → verification chain.
- M4 Photo/GPS/Offline, M5 Municipal Review, M6 Finding Feedback, pedestrian isochrone, polygon drawing, and Borehole Observation Layer are not authorized by this goal.

Next action: use the prepared 30–60 second comprehension protocol and municipal workflow review artifact. Do not begin P1 or M4–M6 automatically.
