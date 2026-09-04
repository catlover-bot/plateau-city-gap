# Repository refactor checkpoint

Status: `R4_LOCAL_GATES_PASSED`

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

## Remaining remote gates

1. Push this feature branch normally; do not force-push or integrate `main`.
2. Require all nine Municipal Pilot CI jobs to pass for the exact checkpoint SHA.
3. Deploy that exact SHA through `deploy-pages.yml` and verify build, deploy, artifact, and live-source identity.
4. Audit Public, Guided Scenes 1–3, and Advanced on production.
5. Capture and verify the eight-image presentation package and contact sheet from production.
6. Record and verify the captioned, clean, short, poster, captions, and manifest package in `/tmp/citygap-demo-video-next/` before atomic replacement.
7. Commit only presentation assets/docs, push normally, and require a second 9/9 CI result.

Automated checks do not establish human comprehension, aesthetic preference, or municipal workflow acceptance.
