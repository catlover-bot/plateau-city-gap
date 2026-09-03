# CITY GAP presentation demo runbook

## 1. Live demo start URL

<https://catlover-bot.github.io/plateau-city-gap/?experience=guided>

Open the URL in a new browser window before the presentation. The deployed visual source is commit `33466bd97a20d96fafa7cf2906a1e89676e7da07`, Pages run `33756795063`.

## 2. Main presentation video

[Captioned 1080p MP4](assets/demo-video/city-gap-demo-presentation-1080p.mp4)

This is the default slide-embedded backup and requires no narration to identify the transitions.

## 3. Backup videos

- [Clean 1080p MP4](assets/demo-video/city-gap-demo-clean-1080p.mp4) — use with live narration.
- [Short 15-second MP4](assets/demo-video/city-gap-demo-short-15s.mp4) — use when the presentation slot is compressed; it concentrates on the PLATEAU/Section and exact-target transition.

Keep a local copy of the three MP4 files with the slide deck. Do not depend on GitHub Pages to play a video during the event.

## 4. Live click sequence

1. Confirm the Guided intro and select `デモを始める`.
2. Focus another candidate once, then select `常団地前周辺`.
3. Select `街の形を見る`.
4. Wait until the PLATEAU buildings/roads and the A–B Section are visible.
5. Move across the Section once to relate it to the map.
6. Select `確認場所を見る`.
7. Point out the exact road polygon, `未確認`, and the four checks.

Do not open `詳細分析` unless the audience asks for the specialist interface.

## 5. Spoken script

Use the 30–60 second script in [the video script](demo-video-script.md#3060-second-spoken-script). The claim boundary is important: the product connects data limits to a concrete place and checks; it does not claim a completed field observation, pedestrian-network result, safety decision, or policy recommendation.

## 6. Preload procedure

1. Use Chromium/Chrome at 1920×1080 with browser zoom 100%.
2. Open the live start URL at least once on the presentation network.
3. Enter Scene 2 and Scene 3 once so the Area context and Section are cached.
4. Use the browser Back path or reopen the live start URL.
5. Confirm the title `舞鶴の地域を、地図からたどる。` and a nonblank map before presenting.

Prewarming is for presentation smoothness only. Do not present it as measured load-time improvement.

## 7. Production availability check

Before the event:

```bash
curl -fIs 'https://catlover-bot.github.io/plateau-city-gap/?experience=guided' | head
```

Then visually confirm intro, Scene 1, Scene 2 Section, Scene 3 exact road, and `詳細分析`. The automated production capture manifest is [here](assets/final-visual-checkpoint/manifest.json).

## 8. Network failure fallback

If the live URL, GSI basemap, or Area artifact is slow or unavailable, stop the live path and play the captioned MP4. The local vectors and product boundary may remain visible during an external basemap failure, but a degraded live display is not preferable to the verified video during a timed presentation.

## 9. Advanced loading fallback

If `詳細分析` is opened and the bounded loading screen remains visible, return to the Guided URL rather than waiting on stage. Use the captioned MP4 if the return also stalls. Do not reload repeatedly or improvise an unverified route.

## 10. Rollback command — document only

```bash
gh workflow run deploy-pages.yml --ref main
```

This command is a documented recovery option. Do not execute it without a separate deployment decision. This goal does not merge or push to `main`.

## 11. Presentation hygiene

- Close mail, chat, calendar, CI, terminal, and notification tabs.
- Disable system and browser notifications.
- Hide bookmarks and developer tools.
- Keep only the live demo tab and slide deck open.
- Verify that the browser profile does not expose account or autofill UI.

## 12. Display recommendation

- Resolution: 1920×1080, 16:9.
- Browser zoom: 100%.
- OS scaling: verify in advance; avoid changing it mid-demo.
- Video playback: full-screen, start automatically or on a single presenter click, audio muted.

## Final fallback order

1. Live production Guided path.
2. Captioned 54-second MP4.
3. Clean 54-second MP4 with narration.
4. Captioned 15-second short MP4.
5. [Production poster](assets/demo-video/city-gap-demo-poster.png) with the spoken summary.
