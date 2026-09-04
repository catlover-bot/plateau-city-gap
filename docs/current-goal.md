# Current goal

Active goal: `repository-refinement-and-presentation-assets-v1`

Status: local refactor and consolidation gates passed; remote validation, deployment, and production presentation recapture remain.

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

## Evidence state

- current approved visual baseline: [Harbor Atlas checkpoint](harbor-atlas-ux-checkpoint.md) and `docs/assets/harbor-atlas-v2/after/`
- current demo package: `docs/assets/demo-video/`; preserved historical evidence from deployed source `33466bd97a20d96fafa7cf2906a1e89676e7da07` until replacement media passes every verification gate
- repository audit: [repository-hygiene-audit.md](repository-hygiene-audit.md)
- presentation asset policy: [presentation-assets.md](presentation-assets.md)

## Remaining gates

1. Push only this feature branch and require all nine CI jobs to pass for the exact refactor-checkpoint HEAD.
2. Deploy that exact green HEAD to GitHub Pages; audit the production URL.
3. Capture production slide images and the replacement demo video into temporary directories.
4. Verify dimensions, duration, codecs, captions, hashes, diagnostics, temporal content, and source commit before replacing the canonical presentation package.
5. Commit final assets, push normally, and require a second all-green nine-job CI run.

No human comprehension, aesthetic preference, accessibility acceptance, or municipal workflow result is claimed by automated validation.
