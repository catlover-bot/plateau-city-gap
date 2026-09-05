# Presentation assets

Presentation media is evidence derived from a verified production deployment. It is not a substitute for source data, browser tests, or human review.

## Current sets

- `docs/assets/harbor-atlas-v2/after/`: current automated Harbor Atlas visual checkpoint, including desktop, mobile, DPR2, accessibility, performance, and color-vision evidence.
- `docs/assets/harbor-atlas-v2/before/`: the retained direct comparison baseline for that checkpoint.
- `docs/assets/demo-video/`: the existing six-file demo package. Until its replacement is fully verified, it remains historical evidence from deployed source `33466bd97a20d96fafa7cf2906a1e89676e7da07`.

The repository does not treat every historical screenshot run as canonical. Superseded packages are recoverable through Git history instead of remaining duplicated in the current checkout.

## Capture policy

1. Build the exact feature-branch commit in production mode.
2. Require the full remote CI matrix to pass before deployment.
3. Deploy that exact commit to GitHub Pages and confirm the Pages run completed successfully.
4. Capture from the production URL with fixed viewport, DPR, reduced motion, font readiness, map readiness, and stable compositor frames.
5. Write new images and video to a temporary directory first.
6. Reject output with browser diagnostics, same-origin HTTP failures, wrong state, missing target/Section data, more than one map initialization, overflow, or provenance mismatch.
7. Verify file count, dimensions, codec, duration, captions, temporal content, and SHA-256 before replacing canonical media.
8. Record source commit, production URL, Pages run, tool/runtime versions, state URL, and hashes in a manifest.

## Retention policy

- Keep the current production slide set, its manifest, and one contact sheet.
- Keep one direct visual baseline only when it materially supports comparison.
- Keep the current demo video, clean master, short backup, poster, captions, and manifest.
- Remove palette explorations, duplicate viewport runs, and superseded checkpoint packages after their conclusion is recorded.
- Never delete source/methodology/provenance records, canonical analysis outputs, tests, or a previously canonical video before its replacement passes all gates.

## Claim boundary

A clean capture proves that a particular build rendered a particular automated state. It does not prove that a person understood the scene, preferred its visual design, or could use it successfully in municipal work.
