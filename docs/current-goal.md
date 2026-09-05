# Current goal

Active goal: `advanced-analysis-media-supplement-v1` (supplemental presentation media only).

Starting audit: local HEAD, upstream and remote feature are `4d724f32e7c286ae8e8335d7c1b3d54ab5682ef2` on `feat/guided-spatial-storytelling-v1`; remote main remains `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff`. The only initial worktree changes are the two existing presentation-image deletions and their untracked, byte-identical `copy.png` counterparts. Preserve these without staging, and preserve all prior media and temporary evidence.

Scope: reuse the published Guided/Advanced interaction and native capture helpers; add two useful Advanced stills and one 10–15 second Guided→Advanced video for the same Area `533513314`, with no fabricated values or application redesign. Deliver a separate `docs/assets/judging-advanced/` package and extend the existing [judging delivery note](judging-3d-demo.md). Exact delivery-commit CI must be nine of nine green, followed by the requested feature-branch Pages deployment and live/raw-asset verification. Main merge and history rewriting remain prohibited.

Status: two production stills, one 13-second native-1080p Guided→Advanced video, and a source/hash manifest are delivered in `docs/assets/judging-advanced/`. Real source values and same-Area identity are verified; the visuals are Inspector-focused, without a visible map analysis color surface. No application source changed. Exact delivery-commit nine-job CI, requested Pages deployment, and post-deploy live verification are the final hand-off gates; their immutable SHA/runs are reported in the hand-off.

## Previous completed 3D delivery

Guided verified-local 3D was published from UI `5d59de0852066d96d9a228c205812fe97f006dab`, with nine-job CI `33939420182`, Pages `33939684419`, matching live entry and lazy-chunk bytes, and all required production browser paths passing. The four-image package, native 1080p clean master, captioned derivative, and provenance manifest were delivered in `docs/assets/judging-3d/` by `4d724f32e7c286ae8e8335d7c1b3d54ab5682ef2`; final CI `33941032712` passed all nine jobs. This package remains unchanged by the supplemental media task.

Current starting HEAD and remote feature: `704a9b237a96aee4b71b01e9f0cd0090100764dc`. Existing image-name changes, prior media, and all backups are preserved. Recursive deletion and automatic cleanup are prohibited. The historical 2D-only Guided policy is superseded only for the verified `533513314` example; other Areas retain their own 2D context. The sections below retain the previous completed checkpoint for provenance, not the current goal's completion state.

## Execution lock

- repository: `catlover-bot/plateau-city-gap`
- branch: `feat/guided-spatial-storytelling-v1`
- canonical recovery source: GitHub remote feature branch
- recovered starting HEAD / upstream: `23b1646655c7c58d9a2188bbb08b5e764b199175`
- user-supplied historical checkpoint: `8701df282da1b60049e9806e6b13f4ddceeecadc`
- `origin/main` at recovery: `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff`
- initial worktree: clean
- main merge/rebase/push: prohibited without explicit approval
- history rewriting, reset, clean, squash, force push, and discarding existing work: prohibited

## Product priority

1. Keep the map easy to read and spatially primary.
2. Keep Public and Guided polished, compact, and consistent with Harbor Atlas.
3. Keep Urban Section annotations readable at desktop, compact, mobile, and DPR2 sizes.
4. Preserve the three-scene Guided interaction and its canonical Area selection.
5. Preserve the Guided → Advanced single-flight loading, retry, cache, Back/Forward, and state-retention fix.

## Current implementation

- `3b633ad`: repository, asset, duplicate, documentation, CSS, export, and script audit recorded.
- `fbdf276`: Guided workspace decomposed into content, targets, selection, async Area context, map stage, inspector, and typed cartography modules.
- `90b698f`: Urban Section data types, plot/focus layout, pointer projection, and async loading isolated; pure layout tests added.
- `926a667`: obsolete source, stylesheet, one-off scripts, duplicate evidence, and superseded documentation consolidated; current documentation indexed.
- [local refactor checkpoint](repository-refactor-checkpoint.md): ESLint, docs, TypeScript, 31 test files / 133 tests, Public and Municipal builds, Ruff, 414 Python tests, dependency audits, browser audits, 200% reflow, and video dry run pass.
- Guided browser regression: six Areas, exact road/building, registered facility, fallback, Section, mobile, keyboard, legacy routes, failure/retry, and Guided → Advanced pass with zero diagnostics and one map initialization.
- Urban Section capture: desktop/mobile annotations `6`/`4`, named roads `4`/`2`, zero label conflicts; deterministic Section screenshots remain unchanged.
- Remote UI checkpoint `9c8a99c530ca375758686c6d6431e76d80c5c748`: nine of nine CI jobs passed in run `33909411156`; Pages build and deploy passed in run `33909833987`.
- Production audits: Public, five visual viewports, eight accessibility states, PLATEAU-native 19/19, Guided spatial, Guided → Advanced, and strict Advanced readiness passed with zero product diagnostics.
- Production media commit `c9bed550d06ed1aa6adbf93296e3daacaa042db6`: verified slide and demo packages plus capture/verification tooling and presentation documentation.
- Media provenance commit `1b85469091884e186289c764f56207733ecb00d6`: both canonical manifests identify the immutable media commit; the feature branch and upstream matched this commit before finalization.
- The video delivery files are encoded at 1920 x 1080/30fps but derive from variable 800 x 450 DevTools frames, so their status is `CAPTURE_SPEC_DEVIATION_AWAITING_USER_REVIEW`, not user-approved native 1080p capture.

## Evidence state

- current approved visual baseline: [Harbor Atlas checkpoint](harbor-atlas-ux-checkpoint.md) and `docs/assets/harbor-atlas-v2/after/`
- current production slide package: `docs/assets/presentation-images/`; eight images, contact sheet, and manifest from source `9c8a99c530ca375758686c6d6431e76d80c5c748` / Pages `33909833987`, machine-verified and visually reviewed
- current demo package: `docs/assets/demo-video/`; captioned, clean, short, poster, captions, and manifest from the same deployed source, machine-verified and visually reviewed
- repository audit: [repository-hygiene-audit.md](repository-hygiene-audit.md)
- presentation asset policy: [presentation-assets.md](presentation-assets.md)

## Finalization gates

1. Preserve both canonical media directories outside the repository before final edits; retain the incident remnant and all temporary evidence.
2. Change only the existing capture/verification cleanup safety and the documentation of capture limitations, user-review status, and recovery boundaries.
3. Push only this feature branch normally and require one all-green nine-job CI run for the exact final delivery HEAD.
4. Confirm final branch/upstream/main invariants, repository integrity, and a clean worktree. Do not redeploy Pages because the deployed application source and output are unchanged.

No human comprehension, aesthetic preference, accessibility acceptance, or municipal workflow result is claimed by automated validation.
