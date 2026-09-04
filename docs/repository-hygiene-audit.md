# Repository hygiene audit

Status: `R4_CONSOLIDATION_VERIFIED_LOCAL`

This audit records the repository before the refinement pass on
`feat/guided-spatial-storytelling-v1`. It distinguishes current product assets,
historical evidence, reproducible generated files, and source that is actually
unused. A filename alone is not removal evidence.

## Locked source state

| Item | Value |
| --- | --- |
| Audit date | 2026-09-05 JST |
| Starting HEAD and upstream | `23b1646655c7c58d9a2188bbb08b5e764b199175` |
| `origin/main` | `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff` |
| Initial worktree | clean |
| Current UI CI | Municipal Pilot CI `33896647149`, 9/9 jobs successful |
| Current UI Pages deployment | `33896991067`, build and deploy successful |
| Temporary visual baseline | `/tmp/citygap-refactor-baseline/`, 22 captures, diagnostics 0 |

The temporary baseline is not a presentation package and is intentionally
outside the repository. It covers Public, Guided intro, all three Guided
scenes, another Area, fallback, exact road, exact building, facility, mobile,
DPR 2, hover, and Advanced loading/ready.

## Repository inventory before refinement

The inventory uses `git ls-files`, file byte sizes from the working tree, and
SHA-256 over tracked file contents. Git's object figures come from
`git count-objects -vH`.

| Top-level path | Tracked files | Tracked bytes |
| --- | ---: | ---: |
| `.dockerignore` | 1 | 145 |
| `.env.example` | 1 | 1,622 |
| `.github` | 2 | 12,801 |
| `.gitignore` | 1 | 860 |
| `analysis` | 255 | 81,122,383 |
| `backend` | 139 | 1,587,836 |
| `data` | 4 | 489 |
| `docker-compose.yml` | 1 | 4,017 |
| `docs` | 427 | 156,143,035 |
| `frontend` | 729 | 70,867,665 |
| `infra` | 33 | 351,789 |
| `LICENSE` | 1 | 1,080 |
| `pyproject.toml` | 1 | 957 |
| `README.md` | 1 | 7,796 |
| **Total** | **1,596** | **310,102,475** |

Git contains 273 loose objects (37.40 MiB) and one pack with 4,232 objects
(149.16 MiB). There is no Git garbage. History-size rewriting is outside this
pass.

### Tracked files at least 10 MB (10,000,000 bytes)

| Bytes | Path | Decision |
| ---: | --- | --- |
| 23,541,121 | `analysis/outputs/real/open_data/demographic_economic_canonical.jsonl` | keep; canonical analysis output |
| 17,377,198 | `analysis/outputs/real/open_data/mhlw_health_canonical.jsonl` | keep; canonical analysis output |

### Other tracked files at least 1 MB (1,000,000 bytes)

| Bytes | Path | Decision |
| ---: | --- | --- |
| 6,722,880 | `analysis/outputs/real/open_data/geospatial_resilience_canonical.jsonl` | keep |
| 6,220,613 | `analysis/outputs/real/open_data/municipal_open_data_analysis.geojson` | keep |
| 5,664,974 | `docs/assets/demo-video/city-gap-demo-clean-1080p.mp4` | keep until verified atomic replacement |
| 5,371,034 | `analysis/outputs/real/maizuru_scenario_candidate_context.csv` | keep |
| 5,355,138 | `docs/assets/demo-video/city-gap-demo-presentation-1080p.mp4` | keep until verified atomic replacement |
| 4,925,485 | `analysis/outputs/real/open_data/maizuru_p0_canonical.jsonl` | keep |
| 3,564,617 | `analysis/outputs/real/maizuru_mesh_plateau_context.csv` | keep current tracked state; scope does not alter data |
| 3,243,343 | `frontend/public/data/cartography/plateau_buildings.geojson` | keep runtime asset |
| 2,353,372 | `frontend/public/data/plateau/data/data284.b3dm` | keep runtime asset |
| 2,002,153 | `analysis/outputs/real/maizuru_network_scenarios.json` | keep |
| 1,883,408 | `frontend/public/data/plateau/data/data285.b3dm` | keep runtime asset |
| 1,876,782 | `docs/assets/cartographic-checkpoint/17-retina-dpr2-target-road.png` | remove with superseded checkpoint |
| 1,856,457 | `docs/assets/final-visual-checkpoint/13-dpr2-scene2.png` | remove with superseded checkpoint |
| 1,831,808 | `docs/assets/guided-spatial-checkpoint/dpr2-understand-section.png` | keep Guided evidence |
| 1,577,417 | `docs/assets/demo-video/city-gap-demo-poster.png` | keep until verified atomic replacement |
| 1,575,692 | `frontend/public/data/plateau-terrain/terrain.glb` | keep runtime asset |
| 1,416,995 | `frontend/public/data/cartography/plateau_roads.geojson` | keep runtime asset |
| 1,295,230 | `docs/assets/demo-video/city-gap-demo-short-15s.mp4` | keep until verified atomic replacement |
| 1,288,032 | `docs/assets/m3-checkpoint/04-unverified-tasks.png` | archive checkpoint metadata; remove superseded binary |
| 1,281,244 | `docs/assets/m3-checkpoint/02-uncertainties.png` | archive checkpoint metadata; remove superseded binary |
| 1,272,299 | `docs/assets/current/03-candidate-brief.png` | remove after README/current asset links move |
| 1,258,304 | `docs/assets/public-product-audit/production-guided-task.png` | remove superseded product capture |
| 1,258,304 | `docs/assets/current/05-field-checklist.png` | remove after README/current asset links move |
| 1,251,399 | `analysis/outputs/real/cartographic-performance-profile-baseline.json` | keep evidence |
| 1,251,107 | `docs/assets/public-product-language-checkpoint/after-06-unknown-dpr2.png` | remove with superseded checkpoint |
| 1,245,344 | `docs/assets/current/07-municipal-review.png` | remove after README/current asset links move |
| 1,231,679 | `docs/assets/current/06-investigation-sheet.png` | remove after README/current asset links move |
| 1,226,339 | `docs/assets/cartographic-performance-checkpoint/12-area-1km.png` | remove duplicate/superseded capture |
| 1,226,322 | `docs/assets/cartographic-checkpoint/12-area-1km.png` | remove superseded capture |
| 1,207,830 | `docs/assets/public-product-language-cartography/12-area-1km.png` | remove superseded capture |
| 1,195,548 | `docs/assets/public-product-language-checkpoint/after-04-population-dpr2.png` | remove with superseded checkpoint |
| 1,155,439 | `analysis/outputs/real/open_data/demographic_economic_mesh_context.geojson` | keep |
| 1,087,200 | `frontend/public/data/network_scenario_map.geojson` | keep runtime asset |
| 1,053,041 | `docs/assets/guided-spatial-checkpoint/desktop-verify-533513314.png` | keep Guided evidence |
| 1,047,139 | `docs/assets/guided-spatial-checkpoint/desktop-verify-building.png` | keep Guided evidence |
| 1,036,586 | `docs/assets/cartographic-benchmark/platone.png` | keep benchmark provenance |
| 1,025,799 | `docs/assets/harbor-atlas-v2/after/18-public-landing-1920.png` | keep current Harbor evidence |

## Asset inventory and retention classification

| Asset set | Files | Bytes | Classification | Evidence and action |
| --- | ---: | ---: | --- | --- |
| `area-checkpoint` | 6 | 2,094,239 | `ARCHIVE_LIGHTWEIGHT` | old UI checkpoint; retain textual data conclusion, not all rasters |
| `cartographic-benchmark` | 8 | 3,214,349 | `KEEP_EVIDENCE` | external-product comparison provenance |
| `cartographic-checkpoint` | 20 | 10,764,532 | `REMOVE_DUPLICATE` | superseded and overlaps later cartographic/language packages |
| `cartographic-performance-checkpoint` | 20 | 10,384,850 | `REMOVE_DUPLICATE` | superseded; many exact matches with the prior set |
| `current` | 9 | 6,356,364 | `REMOVE_UNREFERENCED` | old eight-screen workflow; README will point to current presentation evidence |
| `demo-video` | 6 | 13,905,108 | `KEEP_CURRENT` | canonical paths; current files stay until the replacement passes every gate |
| `final-visual-checkpoint` | 14 | 7,632,606 | `REMOVE_GENERATED` | records pre-Harbor commit `33466bd`; superseded by Harbor/current production |
| `guided-spatial-checkpoint` | 23 | 15,050,205 | `KEEP_EVIDENCE` | required initial Guided contract and provenance checkpoint |
| `harbor-atlas-v2/after` | 31 | 11,138,144 | `KEEP_CURRENT` | current visual baseline and automated evidence |
| `harbor-atlas-v2/before` | 26 | 9,331,438 | `KEEP_EVIDENCE` | retain only representative before comparisons plus lightweight metadata |
| `harbor-atlas-v2/palette-study` | 22 | 9,018,957 | `REMOVE_GENERATED` | decision is frozen; study remains recoverable from Git history |
| `m3-checkpoint` | 6 | 3,407,969 | `ARCHIVE_LIGHTWEIGHT` | old workflow UI; retain textual conclusion only |
| `map-section-refinement-v1` | 39 | 14,358,627 | `REMOVE_DUPLICATE` | later Harbor baseline contains exact copies of 12 captured states |
| `public-first-run-ux` | 11 | 2,911,785 | `REMOVE_GENERATED` | superseded public first-run state |
| `public-product-audit` | 25 | 7,849,922 | `ARCHIVE_LIGHTWEIGHT` | keep benchmark provenance where unique; remove superseded product captures |
| `public-product-language-cartography` | 20 | 10,022,647 | `REMOVE_DUPLICATE` | superseded; several exact copies remain in other old packages |
| `public-product-language-checkpoint` | 30 | 14,627,312 | `REMOVE_DUPLICATE` | superseded before/after package |
| `public-product-language-first-run` | 11 | 3,498,191 | `REMOVE_DUPLICATE` | superseded and its manifest has no inbound documentation link |

No canonical video variant is a duplicate: presentation, clean, and short have
different hashes and intended uses. The package itself is stale because it
records deployed source `33466bd97a20d96fafa7cf2906a1e89676e7da07`, not the
current Harbor source. Its six file hashes match the manifest.

## Duplicate and near-duplicate findings

The SHA-256 scan found 44 exact duplicate groups containing 97 files. Keeping
one copy per group would remove 53 redundant files and 20,578,314 bytes. Of
those, 38 groups and 20,181,071 redundant bytes are PNG screenshots. Four
non-screenshot groups intentionally mirror canonical analysis output into
runtime public assets and are retained.

Representative exact duplicate groups:

| SHA-256 | Copies | Paths / explanation |
| --- | ---: | --- |
| `8c0fa49c2fd6e9977c4adcc3289a9e4e48cbb492bac4b430a2d1165b6e6d897e` | 4 | the same exact-road image across language cartography/checkpoint/first-run packages |
| `d90ece54b24943d20a4c91dafee21e42687899c4ac8520081afda64919b4cd3f` | 4 | the same population image across two cartographic packages, public audit, and language baseline |
| `1f0d2357a05a029c20bc31eb59a608a2d728855961698a15dffa40ce8e5eb8dc` | 3 | identical pre-language desktop unknown state |
| `4eacc4e14ed8494d24d018cf4b4ce270f18f87846f8a58a8883fc4d4886e5708` | 3 | identical pre-language mobile unknown state |
| `98a1ffa153dc0acda0d51f3dc2486f3cc804c8522cf82bef53edf59f7619fc45` | 3 | identical Area-fallback image |
| `039f6ee11a4a4c0a43863c0da31fc1270c3f8b5219bd9994535ca298d190e70d` | 2 | Harbor `before` Scene 2 combined equals map/Section refinement `after` |
| `fca7fc7be73b261b0ec0f12855c9614f9b3ddac6248e60e129d5aab3a19d14b0` | 2 | Harbor `before` exact road equals map/Section refinement `after` |
| `76bde84c4bd8129fa7bd5795b57d42074e7e86677b812afedcf81735783181e1` | 2 | intentional validation manifest mirror from analysis output to public runtime |
| `1f72d3fcab19cb1103763620b142ce616bc0102158af71610908e09faf605b0b` | 2 | intentional platform registry mirror from analysis output to public runtime |

The complete scan is reproducible with:

```bash
git ls-files -z | xargs -0 sha256sum | sort
```

Near-duplicate screenshot groups were identified by matching state, viewport,
and capture lineage, then checked against manifests and representative images.
They are not called exact unless the SHA-256 values match.

| State family | Packages | Decision |
| --- | --- | --- |
| Public landing / place / radius | `public-first-run-ux`, `public-product-language-first-run`, `public-product-language-checkpoint` | keep current production presentation view only |
| Population / building / unknown / exact target | two cartographic packages plus three language packages | remove superseded packages; retain data/methodology docs |
| Guided intro and Scenes 1–3 | `guided-spatial-checkpoint`, `final-visual-checkpoint`, `map-section-refinement-v1`, Harbor | keep Guided provenance and current Harbor; remove intermediate rasters |
| Scene 2 Section desktop/mobile/DPR2 | Guided, final visual, map/Section, Harbor | keep Guided provenance and current Harbor states |
| Advanced loading/ready | Harbor and temporary R0 baseline | keep tracked Harbor only; temporary baseline stays outside Git |
| Palette candidates/simulations | Harbor palette study and Harbor final simulations | remove candidate study; retain final automated simulations |

There are no standalone tracked PNGs outside an evidence package. Package-level
orphaning exists for `docs/assets/current/manifest.json` and
`docs/assets/public-product-language-first-run/manifest.json`, which have no
direct inbound Markdown link. The former is also described indirectly by the
README; the latter is fully superseded.

## Documentation audit

`npm --prefix frontend run check:docs` passes all 100 Markdown files; there are
no broken local links at baseline. A link-graph scan finds 62 documents with no
inbound Markdown link, primarily because the repository has no `docs/README.md`
index. That count is a navigation finding, not deletion evidence.

The following checkpoint families describe superseded UI states and should be
consolidated or moved behind an archive index: Area validation, M3, public
first-run, public-language, cartographic validation/performance, final visual,
and map/Section refinement. `guided-spatial-checkpoint.md` remains the initial
Guided contract checkpoint; `harbor-atlas-ux-checkpoint.md` remains the current
visual checkpoint.

Specific stale or misleading current documentation:

- `docs/current-goal.md` says Harbor CI and Pages deployment are next, although
  exact-HEAD CI and deployment have completed.
- `docs/presentation-demo-runbook.md` and `docs/demo-video-script.md` describe
  the older `33466bd` production recording.
- the README leads with the older `docs/assets/current` workflow image and its
  capture command rather than the current Public/Guided experience.
- no `docs/presentation-assets.md` or presentation-image package exists.
- there are no local absolute paths in tracked README/docs files.
- names such as `current`, `final-visual`, `v1`, `v2`, `before`, and `after`
  reflect chronological phases rather than canonical purpose. New assets will
  use stable presentation names; no new `final-new-v2` generation is added.

## Source, CSS, scripts, and generated-file audit

### Before-refactor metrics

| Measurement | Baseline |
| --- | ---: |
| `GuidedSpatialWorkspace.tsx` | 631 lines |
| `UrbanSection.tsx` | 532 lines |
| pure `sectionAnnotations.ts` | 161 lines |
| `AnalyticalMap.tsx` | 969 lines |
| `ProductApp.tsx` | 610 lines |
| detected TSX component definitions | 95 |
| CSS files | 15 |
| CSS selector occurrences / unique selectors | 2,134 / 462 |
| static unused-selector candidates | 15 |
| raw CSS color occurrences outside `tokens.css` | 628 occurrences / 407 unique |
| TypeScript export declarations | 443 |
| single-occurrence export candidates | 14 |
| Vitest | 30 files / 130 tests, all passing |
| application runtime JS chunks | 526,150 bytes |
| CSS bundles | 242,200 bytes |

The application JS figure includes the entry, React, ProductApp, and ServiceApp
chunks and excludes the separately loaded Cesium and MapLibre worker chunks.
The CSS figure is the sum of emitted CSS assets. The same definitions will be
used after refinement.

The largest frontend source files are `ServiceApp.tsx` (4,385 lines),
`CesiumMap.tsx` (1,526), `AnalyticalMap.tsx` (969), `types.ts` (722),
`GuidedSpatialWorkspace.tsx` (631), `service/types.ts` (626),
`ProductApp.tsx` (610), and `UrbanSection.tsx` (532). This goal changes only
the Guided/Section responsibilities that are in scope.

### Unused source candidates

Static whole-source occurrence analysis found five unreferenced components:

- `EmptyState` in `components/AppStates.tsx`;
- `InvestigationJourney` in `features/investigation/InvestigationJourney.tsx`;
- `ShowcaseLanding` and `GuidedInvestigation` in
  `features/guided/GuidedShowcase.tsx`;
- `VerificationJourney` in `features/verification/VerificationJourney.tsx`.

It also found nine unused non-component exports: `DecisionMapPhase`,
`textValue`, `HUMAN_TEST_STATUS`, `PublicMapRenderState`,
`GuidedSectionReference`, `summarizeReadinessMetrics`, `MapEngineEvents`,
`transitionMapState`, and `deriveMapState`. Each candidate requires import/test
confirmation before removal. Removing a redundant `export` is preferred when
the value is used internally.

The 15 static unused CSS candidates include MapLibre/Cesium runtime-generated
classes and dynamically composed state classes; these are not dead. Confirmed
review candidates are the uninstantiated `source-data-badge` selector and old
`.map-container` rules. Dynamic `symbol-*` and `type-*` selectors are retained.

There are 56 repeated Japanese string candidates in frontend source. Most are
domain terms (`PLATEAU建物`, `PLATEAU道路`, `500mメッシュ`) rather than copy
duplication. Guided scene headings, captions, target copy, and checks are
currently dispersed through one component and are suitable for a small typed
content definition. No translation framework is warranted.

### Script classification

Eight scripts have no inbound package/docs/source reference. Two are current
Harbor capture helpers (`capture-harbor-atlas-study.mjs` and
`capture-harbor-atlas-supplement.mjs`); six are old one-off capture scripts.
Additional capture scripts are referenced only from superseded checkpoint
documents. Active package scripts, Guided browser tests, Guided-to-Advanced
tests, video recording/verification, documentation checks, Cesium asset sync,
and decompression remain.

No test script or test is a removal candidate. Shared readiness, diagnostics,
URL, metadata, and hash code may be extracted only where it reduces repeated
active capture/video code without changing commands.

### Temporary and generated files

The tracked tree contains no `.orig`, `.rej`, `.bak`, editor backup, `tmp/`,
`temp/`, raw video frame sequence, browser profile, `node_modules`,
`frontend/dist`, or `.venv` path. `frontend/dist/`, dependencies, Cesium sync
output, Python caches, and raw/intermediate data are already ignored.

The generated analysis files under `analysis/outputs/real/` are deliberate,
versioned canonical evidence and are not mistaken build output. Superseded
checkpoint PNGs are reproducible generated evidence and are removed only after
their newer source and replacement are identified. The ignore file does not
yet cover generic root `tmp/`/`temp/`, raw browser video, or frame-sequence
directories; narrow rules should be added without ignoring canonical docs
assets.

## Thirty-point audit result

| # | Check | Baseline result |
| ---: | --- | --- |
| 1 | tracked file count | 1,596 |
| 2 | tracked bytes | 310,102,475 |
| 3 | count by directory | recorded above |
| 4 | bytes by directory | recorded above |
| 5 | files at least 1 MB | 39, all classified above |
| 6 | files at least 10 MB | 2 canonical analysis outputs |
| 7 | duplicate SHA-256 files | 44 groups / 53 redundant files / 20,578,314 redundant bytes |
| 8 | near-duplicate screenshots | six state families across superseded capture generations |
| 9 | orphaned screenshots | none standalone; superseded packages are package-level removal candidates |
| 10 | orphaned manifests | two without direct inbound Markdown links |
| 11 | orphaned docs | 62 navigation candidates; add a canonical docs index |
| 12 | outdated checkpoints | eight UI checkpoint families identified |
| 13 | duplicated video variants | none; three distinct intended variants |
| 14 | temporary files | none tracked |
| 15 | `.orig` | none tracked |
| 16 | `.rej` | none tracked |
| 17 | `.bak` | none tracked |
| 18 | `tmp` | none tracked |
| 19 | unused scripts | six old one-off captures; current helpers classified separately |
| 20 | unused CSS selectors | two confirmed review candidates; runtime/dynamic false positives retained |
| 21 | unused TypeScript exports | 14 static candidates, listed above |
| 22 | dead components | five static candidates, listed above |
| 23 | duplicate user-facing strings | 56 candidates; Guided copy is the in-scope consolidation |
| 24 | duplicate raw color literals | 628 occurrences / 407 unique outside token source |
| 25 | generated files tracked by mistake | no runtime build output; superseded evidence is intentional historical generation |
| 26 | generated files missing from ignore | generic temp/raw recording/frame paths need narrow rules |
| 27 | broken docs links | zero across 100 Markdown files |
| 28 | stale README instructions | old canonical screenshot/capture path and incomplete current product orientation |
| 29 | old local paths | zero in tracked README/docs |
| 30 | misleading current/final/v2/new naming | chronological asset/checkpoint names identified; stable presentation names required |

## Removal gate

A file is removed in this pass only when the current-tree evidence shows it is
an exact duplicate, unreferenced, superseded by a named checkpoint, generated
and reproducible, or obsolete and unused by runtime, CI, tests, and current
documentation. Canonical data, migrations, active tests, current Guided and
Harbor evidence, privacy/security documentation, and canonical video paths are
retained. Git history is not rewritten.

## Consolidation outcome before production-media recapture

The code/document/asset consolidation is complete. Presentation media is still
excluded from the after figures below because it is added only from a verified
production deployment.

| Measurement | Baseline | After consolidation | Change |
| --- | ---: | ---: | ---: |
| tracked files | 1,596 | 1,352 | -244 |
| tracked bytes | 310,102,475 | 206,854,961 | -103,247,514 (-33.3%) |
| tracked presentation/evidence assets | 328 | 95 | -233 |
| tracked asset bytes | 155,570,590 | 52,642,589 | -102,928,001 |
| exact duplicate groups | 44 | 6 | -38 |
| exact redundant files | 53 | 8 | -45 |
| exact redundant bytes | 20,578,314 | 397,243 | -20,181,071 |
| duplicate PNG groups | 38 | 0 | -38 |
| Markdown files checked | 100 | 92 | -8 |
| frontend scripts | 29 | 20 | -9 |
| CSS files | 15 | 14 | -1 |
| CSS bundle bytes | 242,200 | 227,414 | -14,786 (-6.1%) |
| app runtime JS bytes | 526,150 | 529,347 | +3,197 (+0.6%) |
| Vitest | 30 / 130 | 31 / 133 | +1 file / +3 tests |

The eight remaining duplicate files are intentional analysis-to-runtime
mirrors or small shared text records; no duplicate PNG remains. Git history was
not rewritten, so the checkout and future clone tip are leaner while all
removed evidence remains recoverable by commit.

Implementation structure also changed materially without changing product
output:

- `GuidedSpatialWorkspace.tsx` fell from 631 to 244 lines. Content, targets,
  canonical selection, lazy/stale-safe Area context, map stage, inspector, and
  typed cartography now have separate modules.
- `UrbanSection.tsx` fell from 532 to 337 lines. Its data schema, pure plot and
  focus layout, collision policy, and abortable loading are independently
  testable.
- all five confirmed dead components, nine confirmed unused exports/functions,
  one unreachable map-state module, and the legacy Guided stylesheet were
  removed. No test was deleted.
- legacy cascade values that were part of the approved screenshot were first
  promoted to explicit Harbor Atlas tokens. Desktop Section output remained
  byte-identical; mobile and DPR2 comparison exceeded SSIM 0.99995.
- nine one-off capture scripts and 12 superseded checkpoint documents were
  removed. `docs/README.md` now routes current documentation, and stable data,
  claim, and presentation-retention boundaries have dedicated documents.

Final tracked counts, including the verified production slide and replacement
video packages, will be recorded with the presentation-asset commit.

The complete local validation result before the first remote push is recorded
in [repository-refactor-checkpoint.md](repository-refactor-checkpoint.md).
