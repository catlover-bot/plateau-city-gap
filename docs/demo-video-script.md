# CITY GAP production demo video script

Goal: `repository-refinement-and-presentation-assets-v1`

This package records the deployed feature-branch Guided experience itself. It is not a slideshow, design mock, local-preview substitute, or simulated field result.

## Source and fixed contract

- Live source: <https://catlover-bot.github.io/plateau-city-gap/?experience=guided>
- Deployed UI commit: `9c8a99c530ca375758686c6d6431e76d80c5c748`
- Pages run: `33909833987`
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
| 00:00.000–00:04.002 | Guided intro | 舞鶴市の地域を、地図からたどる |
| 00:04.002–00:08.485 | Start demo; show and focus the citywide candidates | 詳しく見る地域を選ぶ |
| 00:08.485–00:12.003 | Select 常団地前周辺; fit the Area | 人口・交通・医療から候補を確認 |
| 00:12.003–00:29.003 | Load the same Area's PLATEAU buildings/roads and verified A–B Section | 地域の統計を、建物・道路・地形までたどる |
| 00:29.003–00:43.002 | Open the exact PLATEAU road target | データだけでは分からない場所を見つける |
| 00:43.002–00:52.003 | Hold the exact target and its four checks | 現地で確かめるポイントへ |
| 00:52.003–00:54.752 | Final hold | データから、現地確認の入口をつくる |

The clean version repeats the same browser operations without recording-only caption or cursor overlays. Its observed state boundaries are stored separately in the [machine-readable manifest](assets/demo-video/manifest.json).

## 30–60 second spoken script

> CITY GAPでは、まず舞鶴市の地図から詳しく見る地域を選びます。ここでは人口、交通、医療の公開データから常団地前周辺を確認します。次に、同じ500メートル範囲へPLATEAUの建物と道路、地形の断面を重ね、集計値を街の形へ結び付けます。一方、道路面が見えても、実際に歩けるかまではデータだけでは判断できません。そこで実在する道路を確認場所として示し、現地で確かめる四つのポイントへつなげます。回答や確認結果はまだなく、状態は未確認です。

## Recording implementation

[`record-presentation-demo.mjs`](../frontend/scripts/record-presentation-demo.mjs) performs all readiness checks before the retained portion of each recording. It waits for the deployed map, selected Area, candidate list, Section data, exact target, four checks, fonts, and same-origin requests. It prewarms the production route, performs a normal cached navigation back to a fresh intro document, and then records the complete story in one continuous session with one MapLibre initialization.

The browser viewport is 1600×900 at DPR 1. Chromium DevTools captures acknowledged JPEG screencast frames at up to 800×450, stopping frame acquisition at the final cue before FFmpeg runs. FFmpeg applies explicit full-range-to-TV-range conversion, Lanczos scaling, and light sharpening to produce a 1920×1080 H.264/yuv420p/30fps PowerPoint-compatible MP4. This bounded capture path avoids a continuous VP8 writer competing with software WebGL. The source frame count and method are disclosed per video in the manifest and are not treated as performance measurements.

Example reproduction command (the FFmpeg paths are environment-specific and remain outside the repository):

```bash
cd frontend
LD_LIBRARY_PATH=/path/to/ffmpeg/lib npm run record:demo -- \
  --url 'https://catlover-bot.github.io/plateau-city-gap/?experience=guided' \
  --source-commit 9c8a99c530ca375758686c6d6431e76d80c5c748 \
  --pages-run-id 33909833987 \
  --output /tmp/citygap-demo-video-next \
  --ffmpeg /path/to/ffmpeg \
  --ffprobe /path/to/ffprobe
```

The temporary JPEG sequence and browser profile use the OS temporary directory and are removed after a successful package build. No FFmpeg package or binary is added to the application dependencies.

## Review boundary

Automated metadata, decode, frame, and browser checks passed. The captioned/clean timeline sheets and poster also passed self visual and presentation-readiness review. First-run comprehension and municipal workflow fit remain untested human decisions.
