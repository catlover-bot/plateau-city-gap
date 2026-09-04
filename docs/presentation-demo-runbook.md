# CITY GAP presentation demo runbook

## Live demo

Open <https://catlover-bot.github.io/plateau-city-gap/?experience=guided> in a clean Chromium/Chrome window at 1920×1080 and 100% zoom. Before the event, confirm that the deployed commit and Pages run match the canonical media manifest.

The current package records UI source `9c8a99c530ca375758686c6d6431e76d80c5c748` from successful Pages run `33909833987`.

## Primary and backup media

- [Captioned 1080p MP4](assets/demo-video/city-gap-demo-presentation-1080p.mp4): default slide-embedded backup
- [Clean 1080p MP4](assets/demo-video/city-gap-demo-clean-1080p.mp4): use with live narration
- [Short 15-second MP4](assets/demo-video/city-gap-demo-short-15s.mp4): compressed fallback
- [Poster](assets/demo-video/city-gap-demo-poster.png): static fallback
- [Captions](assets/demo-video/city-gap-demo-captions.vtt)
- [Machine-readable manifest](assets/demo-video/manifest.json)

Keep local copies with the slide deck. Do not rely on network video playback during a timed presentation.

## Live click sequence

1. From the Guided intro, choose `地域を選ぶ`.
2. Briefly focus another candidate, then choose `常団地前周辺`.
3. Choose `街の形を見る`.
4. Wait for PLATEAU buildings/roads and the A–B Urban Section.
5. Move across the Section once to show the linked map position.
6. Choose `確認場所を見る`.
7. Point out the exact road polygon, `未確認`, and the four field checks.

Do not open `詳細分析` unless the audience asks for the specialist interface.

## Spoken summary

Use the 30–60 second script in [demo-video-script.md](demo-video-script.md#3060-second-spoken-script). State the boundary explicitly: CITY GAP links public-data limitations to a concrete place and verification questions; it does not claim a completed field observation, pedestrian-network result, safety decision, or policy recommendation.

## Preload

1. Open the live start URL once on the presentation network.
2. Enter Scene 2 and Scene 3 once so the selected Area context and Section are cached.
3. Return to the Guided intro.
4. Confirm the title `舞鶴の地域を、地図からたどる。` and a nonblank map.

Prewarming is presentation hygiene, not a measured load-time improvement.

## Availability check

```bash
curl -fIs 'https://catlover-bot.github.io/plateau-city-gap/?experience=guided' | head
```

Then confirm intro, Scene 1, Scene 2 Section, Scene 3 exact road, and `詳細分析`. Use the current production slide manifest referenced by [presentation-assets.md](presentation-assets.md) for the exact deployed source.

## Failure handling

- If the live URL, external GSI basemap, or Area artifact is slow, stop the live path and play the captioned MP4.
- If `詳細分析` remains in its bounded loading state, return to the Guided URL. Use the video if the return also stalls.
- Do not repeatedly reload or improvise an unverified route on stage.

The local product vectors and boundaries may remain visible during an external basemap failure, but a degraded live display is not preferable to verified media during a timed presentation.

## Rollback command — documentation only

```bash
gh workflow run deploy-pages.yml --ref main
```

This is a documented recovery option. Do not execute it without a separate deployment decision. The current work does not merge or push to `main`.

## Presentation hygiene

- Close mail, chat, calendar, CI, terminal, and notification tabs.
- Disable system and browser notifications.
- Hide bookmarks and developer tools.
- Keep only the live demo tab and slide deck open.
- Ensure the browser profile exposes no account, autofill, or extension UI.
- Play video full-screen, muted, with a single presenter action.

## Fallback order

1. Live production Guided path.
2. Captioned full-length MP4.
3. Clean full-length MP4 with narration.
4. Captioned 15-second short MP4.
5. Production poster with the spoken summary.
