# CITY GAP production demo video script

Goal: `final-visual-polish-and-demo-video-v1`

This package records the deployed feature-branch Guided experience itself. It is not a slideshow, design mock, local-preview substitute, or simulated field result.

## Source and fixed contract

- Live source: <https://catlover-bot.github.io/plateau-city-gap/?experience=guided>
- Deployed UI commit: `33466bd97a20d96fafa7cf2906a1e89676e7da07`
- Pages run: `33756795063`
- Area: `533513314` / 常団地前周辺
- Exact target: `road:tran_05dbefba-6a77-40ea-88ac-a568a63a2f05:0`
- Section artifact: `maizuru-533513314-plateau-2025-v1`
- Section source shape: A–B `[[135.398125, 35.44583333333334], [135.398125, 35.45]]`
- Terminal state: exact PLATEAU road polygon, four required checks, status `未確認`

The recording contains no photograph, GPS value, field answer, assignee, municipal review, internal ID in the visible UI, browser chrome, audio, or external presentation asset. It retains the product's existing official map/data display and attribution.

## Presentation choreography

The final captioned recording observed these cue boundaries. Production rendering is allowed to occupy part of a cue; the next caption is set immediately before its corresponding operation, not after a loading state.

| Time | Screen operation | Caption |
|---:|---|---|
| 00:00.000–00:03.006 | Guided intro | 舞鶴市の地域を、地図からたどる |
| 00:03.006–00:10.025 | Start demo; show and focus the citywide candidates | 詳しく見る地域を選ぶ |
| 00:10.025–00:18.117 | Select 常団地前周辺; fit the Area | 人口・交通・医療から候補を確認 |
| 00:18.117–00:33.392 | Load the same Area's PLATEAU buildings/roads and verified A–B Section | 500mの統計を、建物・道路・地形へ |
| 00:33.392–00:42.102 | Open the exact PLATEAU road target | データだけでは分からない場所を特定 |
| 00:42.102–00:50.002 | Hold the exact target and its four checks | 現地で確認するポイントへ |
| 00:50.002–00:54.012 | Final hold | データから、現地確認の入口をつくる |

The clean version repeats the same browser operations without recording-only caption or cursor overlays. Its observed state boundaries are stored separately in the [machine-readable manifest](assets/demo-video/manifest.json).

## 30–60 second spoken script

> CITY GAPでは、まず舞鶴市の地図から詳しく見る地域を選びます。ここでは人口、交通、医療の公開データから常団地前周辺を確認します。次に、同じ500メートル範囲へPLATEAUの建物と道路、地形の断面を重ね、集計値を街の形へ結び付けます。一方、道路面が見えても、実際に歩けるかまではデータだけでは判断できません。そこで実在する道路を確認場所として示し、現地で確かめる四つのポイントへつなげます。回答や確認結果はまだなく、状態は未確認です。

## Recording implementation

[`record-presentation-demo.mjs`](../frontend/scripts/record-presentation-demo.mjs) performs all readiness checks before the retained portion of each recording. It waits for the deployed map, selected Area, candidate list, Section data, exact target, four checks, fonts, and same-origin requests. It prewarms the same browser page, returns that page to the intro without remounting its MapLibre instance, and then performs the complete story in one continuous session.

The browser viewport is 1920×1080 at DPR 1. To keep headless Chromium's continuous frame capture from delaying the production transitions beyond 55 seconds, Playwright records a 960×540 stream of that viewport. FFmpeg converts it with Lanczos scaling and light sharpening to the final 1920×1080 H.264/yuv420p/30fps PowerPoint-compatible MP4. The condition is disclosed in the manifest and is not treated as a performance benchmark.

Example reproduction command (the FFmpeg paths are environment-specific and remain outside the repository):

```bash
cd frontend
LD_LIBRARY_PATH=/path/to/ffmpeg/lib npm run record:demo -- \
  --url 'https://catlover-bot.github.io/plateau-city-gap/?experience=guided' \
  --source-commit 33466bd97a20d96fafa7cf2906a1e89676e7da07 \
  --pages-run-id 33756795063 \
  --ffmpeg /path/to/ffmpeg \
  --ffprobe /path/to/ffprobe
```

The raw WebM and browser profile use the OS temporary directory and are removed after a successful package build. No FFmpeg package or binary is added to the application dependencies.

## Review boundary

Automated metadata, decode, frame, and browser checks support `READY_FOR_SELF_VISUAL_REVIEW` and `READY_FOR_DEMO_REVIEW`. They do not establish aesthetic quality, first-run comprehension, or municipal workflow fit; those remain human decisions.
