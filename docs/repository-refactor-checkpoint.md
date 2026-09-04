# Repository refactor checkpoint

Status: `R6_PRODUCTION_MEDIA_PASSED`

This checkpoint freezes the local result of the repository-refinement pass before the feature branch is pushed, run through the remote nine-job CI matrix, and deployed for production presentation capture.

## Source under test

| Item | Value |
| --- | --- |
| Branch | `feat/guided-spatial-storytelling-v1` |
| Recovered remote baseline | `23b1646655c7c58d9a2188bbb08b5e764b199175` |
| UI refactor commits | `fbdf276`, `90b698f` |
| Consolidation commit | `926a6670f9d4ccf6c63736ee6cb0108eb467e46a` |
| Preview | production build at `http://127.0.0.1:4175/plateau-city-gap/` |
| Validation date | 2026-09-05 JST |
| Main integration | none |

The README evidence-boundary restoration and the active accessibility/video validation updates are included with this checkpoint commit. The deployed UI source will therefore be the checkpoint commit itself, not the consolidation commit listed above.

## Repository result

| Measurement | Baseline | Consolidated result |
| --- | ---: | ---: |
| Tracked files | 1,596 | 1,352 before this checkpoint document |
| Tracked bytes | 310,102,475 | 206,854,961 before this checkpoint document |
| Tracked presentation/evidence assets | 328 | 95 |
| Tracked asset bytes | 155,570,590 | 52,642,589 |
| Exact duplicate groups | 44 | 6 intentional data/text groups |
| Duplicate PNG groups | 38 | 0 |
| Frontend scripts | 29 | 20 |
| CSS files | 15 | 14 |
| CSS bundle bytes | 242,200 | 227,414 (-6.1%) |
| App runtime JS bytes | 526,150 | 529,347 (+0.6%) |
| Vitest | 30 files / 130 tests | 31 files / 133 tests |

The pass removes 233 superseded asset files and approximately 103.2 MB from the tracked checkout without rewriting history. Canonical analysis outputs, runtime assets, migrations, tests, current Harbor Atlas evidence, Guided provenance evidence, and the existing video package remain tracked.

## Static, unit, build, and security gates

| Gate | Result |
| --- | --- |
| `git diff --check` | pass |
| ESLint | pass |
| Markdown links | 93 files pass |
| TypeScript | pass |
| Vitest | 31 files / 133 tests pass |
| Public production build | pass |
| Municipal production build | pass |
| Ruff | pass |
| Python tests | 414 passed / 3 skipped; only two dependency deprecation warnings |
| npm audit at high severity | 0 vulnerabilities |
| pip-audit | no known vulnerabilities; editable local package skipped as expected |
| Public/raw-data boundary | full Python suite passes; only `data/raw/.gitkeep` is tracked |

The first Python run correctly rejected a shortened README that had dropped eight public-fact strings. The strings were restored from canonical outputs and the complete suite then passed. No test or assertion was weakened.

## Browser and interaction gates

| Gate | Result |
| --- | --- |
| Public first-run audit | pass; median first meaningful render 348 ms, no critical accessibility or diagnostic record, no tested overflow |
| Visual identity | five viewports pass; no console or same-origin HTTP errors, no horizontal overflow |
| PLATEAU-native | 19/19 checks pass |
| Guided flow | intro plus Scenes 1–3 pass |
| Area switching | six distinct Areas, geometries, labels, and context signatures pass in one workspace |
| Lazy/stale-safe context | no initial Area-context request; stale Section rejection passes |
| Exact/fallback targets | exact road, exact building, registered facility reference, and honest Area fallback pass |
| Mobile / DPR2 / reduced motion | pass |
| Keyboard-only flow | named focus-visible controls pass |
| 200% zoom | 1440×900 at 200% reflow-equivalent 720×450 CSS viewport passes with no axe violation, structural failure, diagnostic, or horizontal overflow |
| Accessibility | eight Public/Guided states; 0 critical/serious, 0 total axe violations, 0 structural failures, 0 diagnostics |
| Map instance | one MapLibre initialization throughout each Guided workspace |
| Advanced readiness capture | strict `02-resolution-lift` capture passes; no readiness failure artifact |

## Urban Section gates

- Map source and Section use the same verified A–B coordinates: `[[135.398125, 35.44583333333334], [135.398125, 35.45]]`.
- The owning Area resolves artifact `maizuru-533513314-plateau-2025-v1`, 94 terrain samples, 17 directly intersected buildings, and 14 directly intersected roads.
- Desktop/compact/mobile render 6/6/4 annotations and 4/4/2 named road labels with zero internal collision.
- Observed layout calculation values were 13.7, 8.1, and 0.6 ms: median 8.1 ms and maximum 13.7 ms, within the 16 ms median and 50 ms hard gates.
- Desktop Section output remained byte-identical through the refactor; mobile and DPR2 comparisons exceeded SSIM 0.99995, with only raster antialiasing noise.

## Performance gates

Five fresh 1440×900 reduced-motion browser contexts were profiled against the production build with the external basemap blocked so local product work is measured consistently.

| Interaction | Median | Gate | Result |
| --- | ---: | ---: | --- |
| First meaningful render | 356.6 ms | ≤ 2,000 ms | pass |
| Cold Area context | 488.9 ms | ≤ 1,500 ms | pass |
| Exact road | 317.0 ms | ≤ 1,200 ms | pass |
| Exact building | 262.7 ms | ≤ 1,200 ms | pass |
| Return to Scene 2 | 278.4 ms | ≤ 1,200 ms | pass |

Initial application JS changed by +0.6%; heavy Cesium and MapLibre workers remain separate and Cesium is not requested during initial 2D discovery.

## Guided to Advanced gates

- direct Advanced load: pass, one full-data start;
- Guided → Advanced: visible bounded loading state, pass, one full-data start;
- cached return: pass without a second start;
- Back/Forward and selection retention: pass;
- long URL and reload: pass;
- legacy routes 5 and 6: pass;
- forced load failure followed by retry: `full-error` generation 1, then successful generation 2;
- six transition contexts: zero console, page, request, response, or unhandled-rejection diagnostics.

## Presentation tooling gate

The production video recorder now has a non-writing `--dry-run` contract and the planned choreography is fixed at 55 seconds: intro 0–4, Area interaction 4–12, PLATEAU/Section 12–29, exact target 29–43, checks 43–52, and close 52–55. The dry run passed against the local production build with Scene 3, Area `533513314`, exact road resolution, four checks, one map initialization, FFmpeg/FFprobe availability, and zero diagnostics.

No slide or video in this checkpoint is called production evidence. Final media must be captured into temporary directories from the exact green GitHub Pages deployment, fully verified, and only then installed at its canonical path.

## Remote, deployment, and production result

- The exact UI checkpoint `9c8a99c530ca375758686c6d6431e76d80c5c748` passed all nine Municipal Pilot CI jobs in [run 33909411156](https://github.com/catlover-bot/plateau-city-gap/actions/runs/33909411156).
- Its Pages build and deploy passed in [run 33909833987](https://github.com/catlover-bot/plateau-city-gap/actions/runs/33909833987). The deployed index, entry JS, React chunk, and CSS were byte-identical to the local production build.
- Public first run, five visual viewports, eight accessibility states including 200% reflow, PLATEAU-native 19/19, full Guided spatial behavior, Guided → Advanced, and strict Advanced readiness passed on production with zero product diagnostics.
- The production image package contains eight ordered captures, a contact sheet, and a manifest. All dimensions, hashes, state contracts, source commit, Pages run, Section provenance, exact target, and diagnostics gates passed; the exact package then passed self visual and presentation-readiness review.
- The production video package contains captioned and clean 54.7667-second MP4s, a 14.9667-second short, poster, WebVTT captions, and manifest. All videos decode as silent 1920×1080 H.264/yuv420p/30fps, total 5,360,876 bytes, and the sampled timelines passed visual review without loading/error/debug frames.
- Media, tooling, and presentation documentation were committed in `c9bed550d06ed1aa6adbf93296e3daacaa042db6`; both package manifests identify that immutable asset commit.

The remaining mechanical gate is a second nine-job CI run for the final presentation-asset HEAD. No merge, rebase, or push to `main` is part of this work.

Automated checks do not establish human comprehension, aesthetic preference, or municipal workflow acceptance.

## Local cleanup incident and recovery boundary

During presentation-tooling work, a malformed cleanup invocation deleted the local checkout's `.git` directory and tracked files. The presentation-image files that remained in a permission-blocked directory were preserved. Because the deleted checkout no longer contained Git metadata, the exact pre-incident set of ignored or untracked files cannot be enumerated or proven complete.

The exact remote feature state at `9c8a99c530ca375758686c6d6431e76d80c5c748` was recovered with a new single-branch clone. Known in-session presentation tooling and documentation changes were reconstructed, the surviving image package and retained demo package were restored, and those results were committed as `c9bed550d06ed1aa6adbf93296e3daacaa042db6` with provenance follow-up `1b85469091884e186289c764f56207733ecb00d6`. This confirms recovery of the tracked remote feature state and the known presentation deliverables; it does not claim lossless recovery of every possible pre-incident ignored or untracked file.

The untouched incident remnant is retained at `/home/mhirotaka/workspace/plateau-city-gap.accidental-delete-backup-20260905T1049Z`. A separate non-overwriting final-delivery copy of both canonical media directories was created at `/home/mhirotaka/workspace/citygap-final-delivery-backup-1b854690`; all 16 copied files matched their sources by SHA-256 at creation time. Neither location is part of the repository or the remote deliverable.
