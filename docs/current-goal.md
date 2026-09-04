# Current goal

Active goal: `repository-refinement-and-presentation-assets-v1`

Status: refactor, remote validation, deployment, production audits, and presentation recapture passed; final asset commit, push, and second remote CI remain.

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

## Evidence state

- current approved visual baseline: [Harbor Atlas checkpoint](harbor-atlas-ux-checkpoint.md) and `docs/assets/harbor-atlas-v2/after/`
- current production slide package: `docs/assets/presentation-images/`; eight images, contact sheet, and manifest from source `9c8a99c530ca375758686c6d6431e76d80c5c748` / Pages `33909833987`, machine-verified and visually reviewed
- current demo package: `docs/assets/demo-video/`; captioned, clean, short, poster, captions, and manifest from the same deployed source, machine-verified and visually reviewed
- repository audit: [repository-hygiene-audit.md](repository-hygiene-audit.md)
- presentation asset policy: [presentation-assets.md](presentation-assets.md)

## Remaining gates

1. Commit the verified production presentation assets, tooling, and documentation without changing runtime application source or lockfiles.
2. Record the media commit in the demo manifest through a small follow-up provenance commit.
3. Push only this feature branch normally and require a second all-green nine-job CI run for the exact final HEAD.
4. Confirm final branch/upstream/main invariants, repository integrity, and a clean worktree.

No human comprehension, aesthetic preference, accessibility acceptance, or municipal workflow result is claimed by automated validation.
