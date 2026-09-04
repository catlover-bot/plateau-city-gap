import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { chromium } from "playwright-core";

const parameters = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const key = process.argv[index];
  if (!key.startsWith("--")) continue;
  const value = process.argv[index + 1];
  parameters.set(key, value && !value.startsWith("--") ? value : "true");
  if (value && !value.startsWith("--")) index += 1;
}

const repositoryRoot = path.resolve(process.cwd(), "..");
const outputDirectory = path.resolve(
  process.cwd(),
  parameters.get("--output") ?? "../docs/assets/demo-video",
);
const sourceUrl = new URL(
  parameters.get("--url") ?? "https://catlover-bot.github.io/plateau-city-gap/?experience=guided",
);
const sourceCommit = execFileSync(
  "git",
  ["rev-parse", `${parameters.get("--source-commit") ?? "HEAD"}^{commit}`],
  { cwd: repositoryRoot, encoding: "utf8" },
).trim();
const sourceBranch = execFileSync("git", ["branch", "--show-current"], {
  cwd: repositoryRoot,
  encoding: "utf8",
}).trim();
const pagesRunId = parameters.get("--pages-run-id") ?? null;
const ffmpeg = parameters.get("--ffmpeg") ?? "ffmpeg";
const ffprobe = parameters.get("--ffprobe") ?? "ffprobe";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const playwrightPackage = JSON.parse(
  await readFile(path.resolve(process.cwd(), "node_modules/playwright-core/package.json"), "utf8"),
);
const viewport = { width: 1920, height: 1080 };
const rawVideoSize = { width: 960, height: 540 };
const selectedArea = "533513314";
const sectionArtifactId = "maizuru-533513314-plateau-2025-v1";
const durationSeconds = 55;
const rawDirectory = path.join(tmpdir(), `citygap-demo-${process.pid}-${Date.now()}`);
const profileDirectory = path.join(rawDirectory, "chromium-profile");
const chromiumArgs = [
  "--no-sandbox",
  "--disable-dev-shm-usage",
  "--enable-webgl",
  "--ignore-gpu-blocklist",
  "--enable-unsafe-swiftshader",
  "--use-gl=angle",
  "--use-angle=swiftshader",
];
const variants = [
  { id: "presentation", filename: "city-gap-demo-presentation-1080p.mp4", captioned: true },
  { id: "clean", filename: "city-gap-demo-clean-1080p.mp4", captioned: false },
];
const diagnostics = [];
const choreography = [
  { start: 0, end: 4, scene: "Guided intro", caption: "舞鶴市の地域を、地図からたどる" },
  { start: 4, end: 8, scene: "citywide candidates and focus", caption: "詳しく見る地域を選ぶ" },
  { start: 8, end: 12, scene: "select 常団地前周辺", caption: "人口・交通・医療から候補を確認" },
  { start: 12, end: 29, scene: "PLATEAU context and A–B Section", caption: "地域の統計を、建物・道路・地形までたどる" },
  { start: 29, end: 43, scene: "exact PLATEAU road target", caption: "データだけでは分からない場所を見つける" },
  { start: 43, end: 52, scene: "four required checks", caption: "現地で確かめるポイントへ" },
  { start: 52, end: 55, scene: "final hold", caption: "データから、現地確認の入口をつくる" },
];

function phase(message) {
  process.stderr.write(`[demo-video] ${message}\n`);
}

function sha256(buffer) {
  return createHash("sha256").update(buffer).digest("hex");
}

function versionLine(command) {
  return execFileSync(command, ["-version"], { encoding: "utf8" }).split("\n")[0].trim();
}

function guidedUrl(story) {
  const target = new URL(sourceUrl);
  target.search = "";
  target.searchParams.set("experience", "guided");
  target.searchParams.set("story", story);
  target.searchParams.set("mesh", selectedArea);
  return target.toString();
}

function attachDiagnostics(page, label) {
  const pending = new Set();
  const ownOrigin = sourceUrl.origin;
  const critical = (url) => url.startsWith(ownOrigin);
  page.on("request", (request) => {
    if (critical(request.url())) pending.add(request);
  });
  page.on("requestfinished", (request) => pending.delete(request));
  page.on("requestfailed", (request) => {
    pending.delete(request);
    if (critical(request.url()) && request.failure()?.errorText !== "net::ERR_ABORTED") {
      diagnostics.push({ variant: label, kind: "request", url: request.url(), message: request.failure()?.errorText ?? "unknown" });
    }
  });
  page.on("pageerror", (error) => diagnostics.push({ variant: label, kind: "page", message: error.message }));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("cyberjapandata.gsi.go.jp")) {
      diagnostics.push({ variant: label, kind: "console", message: message.text() });
    }
  });
  page.on("response", (response) => {
    if (critical(response.url()) && response.status() >= 400) {
      diagnostics.push({ variant: label, kind: "http", url: response.url(), status: response.status() });
    }
  });
  return pending;
}

async function settle(page) {
  await page.evaluate(async () => {
    await document.fonts?.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
}

async function waitForPending(page, pending) {
  await page.waitForFunction(() => document.readyState === "complete", null, { timeout: 180_000 });
  const started = Date.now();
  while (pending.size > 0) {
    if (Date.now() - started > 30_000) {
      throw new Error(`critical requests did not settle: ${[...pending].map((request) => request.url()).join(", ")}`);
    }
    await page.waitForTimeout(50);
  }
  await settle(page);
}

async function waitState(page, story, { pending, exact = false } = {}) {
  const contextStatus = story === "intro" || story === "find" ? "idle" : "ready";
  await page.locator(
    `.guided-spatial-app[data-guided-story="${story}"][data-area-id="${selectedArea}"][data-context-status="${contextStatus}"]`,
  ).waitFor({ timeout: 180_000 });
  await page.waitForFunction(
    () => document.querySelector(".analytical-map-shell")?.getAttribute("data-guided-visual-ready") === "true",
    null,
    { timeout: 180_000 },
  );
  if (story === "understand") {
    await page.locator(`.guided-spatial-app[data-section-pack="${sectionArtifactId}"]`).waitFor({ timeout: 180_000 });
    await page.locator('.urban-section[data-terrain-samples="94"][data-direct-building-count="17"][data-direct-road-count="14"]').waitFor({ timeout: 180_000 });
  }
  if (exact || story === "verify") {
    await page.locator('.guided-spatial-app[data-target-kind="road"][data-target-resolution="exact"]').waitFor({ timeout: 180_000 });
    const checkCount = await page.locator(".guided-check-list > li").count();
    if (checkCount !== 4) throw new Error(`expected four checks, received ${checkCount}`);
  }
  if (pending) await waitForPending(page, pending);
  else await settle(page);
}

async function primeRecordingPage(page, pending, variant) {
  phase(`${variant}: prewarm the recording page`);
  let sectionContract = null;
  await page.goto(guidedUrl("intro"), { waitUntil: "domcontentloaded", timeout: 180_000 });
  await waitState(page, "intro", { pending });
  await page.getByRole("button", { name: "地域を選ぶ", exact: true }).evaluate((element) => element.click());
  await waitState(page, "find", { pending });
  await page.getByRole("button", { name: "街の形を見る", exact: true }).evaluate((element) => element.click());
  await waitState(page, "understand", { pending });
  sectionContract = await page.evaluate(() => {
    const root = document.querySelector(".guided-spatial-app");
    const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
    return {
      artifactId: root?.getAttribute("data-section-pack"),
      coordinates: map?.getSource("guided-section")?.serialize?.().data?.features?.[0]?.geometry?.coordinates ?? null,
    };
  });
  await page.getByRole("button", { name: "確認場所を見る", exact: true }).evaluate((element) => element.click());
  await waitState(page, "verify", { pending, exact: true });
  const contract = await page.evaluate(() => {
    const root = document.querySelector(".guided-spatial-app");
    const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
    const target = map?.getSource("guided-target")?.serialize?.().data?.features?.[0];
    const section = map?.getSource("guided-section")?.serialize?.().data?.features?.[0];
    return {
      area: root?.getAttribute("data-area-id"),
      targetKey: root?.getAttribute("data-target-key"),
      targetSourceId: target?.id ?? target?.properties?.object_id ?? target?.properties?.source_id ?? target?.properties?.source_object_id ?? null,
      targetGeometryType: target?.geometry?.type ?? null,
      sectionCoordinates: section?.geometry?.coordinates ?? null,
      sectionArtifactId: root?.getAttribute("data-section-pack"),
      mapRenderState: document.querySelector(".analytical-map-shell")?.getAttribute("data-map-render-state"),
      mapInitializationCount: window.__cityGapMapInitCount,
    };
  });
  contract.sectionCoordinates = sectionContract?.coordinates ?? contract.sectionCoordinates;
  contract.sectionArtifactId = sectionContract?.artifactId ?? contract.sectionArtifactId;
  if (contract.area !== selectedArea || contract.targetGeometryType !== "Polygon" || contract.mapRenderState !== "ready" || contract.sectionArtifactId !== sectionArtifactId) {
    throw new Error(`production recording contract is not ready: ${JSON.stringify(contract)}`);
  }
  await page.getByRole("button", { name: "街の形へ戻る", exact: true }).evaluate((element) => element.click());
  await waitState(page, "understand", { pending });
  await page.getByRole("button", { name: "範囲選択へ戻る", exact: true }).evaluate((element) => element.click());
  await waitState(page, "find", { pending });
  await page.evaluate((url) => {
    const target = new URL(url);
    history.replaceState(null, "", `${target.pathname}${target.search}${target.hash}`);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, guidedUrl("intro"));
  await waitState(page, "intro", { pending });
  return contract;
}

async function installOverlay(page, captioned) {
  if (!captioned) return;
  await page.evaluate(() => {
    const style = document.createElement("style");
    style.dataset.citygapRecording = "true";
    style.textContent = `
      #citygap-recording-caption {
        position: fixed; z-index: 2147483646; top: 9px; left: 50%; transform: translateX(-50%);
        max-width: 760px; min-height: 40px; padding: 9px 22px 8px; box-sizing: border-box;
        color: #162d2b; background: rgba(255,255,255,.96); border: 1px solid rgba(22,45,43,.22);
        border-radius: 4px; box-shadow: 0 3px 12px rgba(18,35,34,.12);
        font: 700 17px/1.3 -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans JP", sans-serif;
        letter-spacing: .01em; text-align: center; pointer-events: none;
      }
      #citygap-recording-cursor {
        position: fixed; z-index: 2147483647; width: 25px; height: 25px; margin: -12.5px 0 0 -12.5px;
        border: 2px solid #fff; border-radius: 50%; background: rgba(0,91,82,.78);
        box-shadow: 0 0 0 2px rgba(0,91,82,.35); pointer-events: none;
        transition: transform 120ms ease, background 120ms ease;
      }
      #citygap-recording-cursor.active { transform: scale(.72); background: rgba(196,82,27,.9); }
    `;
    document.head.append(style);
    const caption = document.createElement("div");
    caption.id = "citygap-recording-caption";
    caption.setAttribute("aria-hidden", "true");
    const cursor = document.createElement("div");
    cursor.id = "citygap-recording-cursor";
    cursor.setAttribute("aria-hidden", "true");
    document.body.append(caption, cursor);
    window.__cityGapRecording = {
      setCaption(value) { caption.textContent = value; },
      press(value) { cursor.classList.toggle("active", value); },
      move(x, y) {
        cursor.animate(
          [{ left: cursor.style.left || "50vw", top: cursor.style.top || "50vh" }, { left: `${x}px`, top: `${y}px` }],
          { duration: 420, easing: "cubic-bezier(.22,.8,.32,1)", fill: "forwards" },
        );
        cursor.style.left = `${x}px`;
        cursor.style.top = `${y}px`;
      },
    };
  });
}

async function caption(page, value, captioned) {
  if (captioned) await page.evaluate((text) => window.__cityGapRecording?.setCaption(text), value);
}

async function moveTo(page, locator, captioned) {
  const box = await locator.boundingBox();
  if (!box) throw new Error("recording target has no bounding box");
  if (captioned) {
    await page.evaluate(
      ({ x, y }) => window.__cityGapRecording?.move(x, y),
      { x: box.x + box.width / 2, y: box.y + box.height / 2 },
    );
    await page.waitForTimeout(460);
  }
  await locator.focus();
}

async function clickLocator(page, locator, captioned) {
  await moveTo(page, locator, captioned);
  if (captioned) await page.evaluate(() => window.__cityGapRecording?.press(true));
  await page.waitForTimeout(110);
  await locator.evaluate((element) => element.click());
  if (captioned) await page.evaluate(() => window.__cityGapRecording?.press(false));
}

async function moveCursor(page, x, y, captioned) {
  if (!captioned) return;
  await page.evaluate(({ left, top }) => window.__cityGapRecording?.move(left, top), { left: x, top: y });
  await page.waitForTimeout(460);
}

async function recordVariant(variant) {
  const context = await chromium.launchPersistentContext(profileDirectory, {
    executablePath,
    headless: true,
    args: chromiumArgs,
    viewport,
    deviceScaleFactor: 1,
    locale: "ja-JP",
    reducedMotion: "reduce",
    recordVideo: { dir: rawDirectory, size: rawVideoSize },
  });
  const page = context.pages()[0] ?? await context.newPage();
  page.setDefaultTimeout(180_000);
  const pending = attachDiagnostics(page, variant.id);
  const pageCreatedAt = Date.now();
  const contract = await primeRecordingPage(page, pending, variant.id);
  await installOverlay(page, variant.captioned);
  await caption(page, choreography[0].caption, variant.captioned);
  await moveCursor(page, 960, 540, variant.captioned);
  await settle(page);
  const recordingStart = Date.now();
  const elapsed = () => ((Date.now() - recordingStart) / 1000).toFixed(1);
  const observedChoreography = [{ ...choreography[0], start: 0, end: null }];
  const setSceneCaption = async (index) => {
    const start = Number(((Date.now() - recordingStart) / 1000).toFixed(3));
    observedChoreography[observedChoreography.length - 1].end = start;
    observedChoreography.push({ ...choreography[index], start, end: null });
    await caption(page, choreography[index].caption, variant.captioned);
  };
  const holdUntil = async (milliseconds) => {
    const remaining = recordingStart + milliseconds - Date.now();
    if (remaining > 0) await page.waitForTimeout(remaining);
  };

  phase(`${variant.id}: record ${durationSeconds}s choreography`);
  await holdUntil(4000);
  await setSceneCaption(1);
  await clickLocator(page, page.getByRole("button", { name: "地域を選ぶ", exact: true }), variant.captioned);
  await waitState(page, "find", { pending });
  phase(`${variant.id}: Scene 1 ready at ${elapsed()}s`);
  await holdUntil(6000);
  await moveTo(page, page.getByRole("button", { name: /二尾バス停周辺/ }).first(), variant.captioned);
  await holdUntil(8000);
  const tsune = page.getByRole("button", { name: /常団地前周辺/ }).first();
  await moveTo(page, tsune, variant.captioned);
  await holdUntil(8000);
  await setSceneCaption(2);
  await clickLocator(page, tsune, variant.captioned);
  await waitState(page, "find", { pending });
  phase(`${variant.id}: Area selected at ${elapsed()}s`);
  const areaReadyAt = Date.now() - recordingStart;
  await holdUntil(Math.max(12_000, areaReadyAt + 1500));
  await setSceneCaption(3);
  await clickLocator(page, page.getByRole("button", { name: "街の形を見る", exact: true }), variant.captioned);
  await waitState(page, "understand", { pending });
  phase(`${variant.id}: Scene 2 and Section ready at ${elapsed()}s`);
  const sectionReadyAt = Date.now() - recordingStart;
  await holdUntil(Math.max(22_000, sectionReadyAt + 3500));
  const section = page.locator(".guided-section-dock .urban-section svg");
  const sectionBox = await section.boundingBox();
  if (!sectionBox) throw new Error("A–B Section is not visible during recording");
  await moveCursor(page, sectionBox.x + sectionBox.width * 0.62, sectionBox.y + sectionBox.height * 0.42, variant.captioned);
  await section.focus();
  await page.keyboard.press("ArrowRight");
  await holdUntil(Math.max(26_000, sectionReadyAt + 5500));
  const targetButton = page.getByRole("button", { name: "確認場所を見る", exact: true });
  await moveTo(page, targetButton, variant.captioned);
  await holdUntil(Math.max(29_000, sectionReadyAt + 7000));
  await setSceneCaption(4);
  await clickLocator(page, targetButton, variant.captioned);
  await waitState(page, "verify", { pending, exact: true });
  phase(`${variant.id}: Scene 3 exact target ready at ${elapsed()}s`);
  const targetReadyAt = Date.now() - recordingStart;
  const targetCaptionEnd = Math.max(43_000, targetReadyAt + 4000);
  await holdUntil(targetCaptionEnd);
  await setSceneCaption(5);
  const checks = page.locator(".guided-check-list > li");
  const secondCheck = await checks.nth(1).boundingBox();
  if (secondCheck) await moveCursor(page, secondCheck.x + secondCheck.width / 2, secondCheck.y + secondCheck.height / 2, variant.captioned);
  await holdUntil(Math.max(47_000, targetCaptionEnd + 3000));
  const fourthCheck = await checks.nth(3).boundingBox();
  if (fourthCheck) await moveCursor(page, fourthCheck.x + fourthCheck.width / 2, fourthCheck.y + fourthCheck.height / 2, variant.captioned);
  const checksCaptionEnd = Math.max(52_000, targetCaptionEnd + 7000);
  await holdUntil(checksCaptionEnd);
  await setSceneCaption(6);
  await moveCursor(page, 960, 660, variant.captioned);
  const finalEnd = Math.max(durationSeconds * 1000 - 250, checksCaptionEnd + 2500);
  await holdUntil(finalEnd);
  const choreographyElapsedSeconds = (Date.now() - recordingStart) / 1000;
  observedChoreography[observedChoreography.length - 1].end = Number(choreographyElapsedSeconds.toFixed(3));
  if (choreographyElapsedSeconds > 55) {
    throw new Error(`recorded choreography exceeded 55 seconds: ${choreographyElapsedSeconds.toFixed(3)}s`);
  }

  const terminal = await page.evaluate(() => {
    const root = document.querySelector(".guided-spatial-app");
    const text = document.querySelector(".guided-story-panel")?.textContent ?? "";
    return {
      story: root?.getAttribute("data-guided-story"),
      area: root?.getAttribute("data-area-id"),
      targetKey: root?.getAttribute("data-target-key"),
      targetKind: root?.getAttribute("data-target-kind"),
      targetResolution: root?.getAttribute("data-target-resolution"),
      sectionArtifactId: root?.getAttribute("data-section-pack"),
      checks: document.querySelectorAll(".guided-check-list > li").length,
      fakeEvidence: /写真|GPS|回答済み|レビュー済み/.test(text),
      internalIdVisible: /tran_[0-9a-f-]+|bldg_[0-9a-f-]+|533513314/.test(text),
      mapInitializationCount: window.__cityGapMapInitCount,
    };
  });
  if (terminal.story !== "verify" || terminal.area !== selectedArea || terminal.targetKind !== "road" || terminal.targetResolution !== "exact" || terminal.checks !== 4 || terminal.fakeEvidence || terminal.internalIdVisible || terminal.mapInitializationCount !== contract.mapInitializationCount) {
    throw new Error(`terminal recording contract failed: ${JSON.stringify(terminal)}`);
  }
  if (diagnostics.some((item) => item.variant === variant.id || item.variant === `${variant.id}-prewarm`)) {
    throw new Error(`recording diagnostics are not empty for ${variant.id}`);
  }

  const video = page.video();
  if (!video) throw new Error("Playwright video handle is unavailable");
  await context.close();
  const rawPath = await video.path();
  const outputPath = path.join(outputDirectory, variant.filename);
  const wallLeadSeconds = Math.max(0, (recordingStart - pageCreatedAt) / 1000);
  const rawProbe = JSON.parse(execFileSync(ffprobe, [
    "-v", "error", "-show_format", "-of", "json", rawPath,
  ], { encoding: "utf8" }));
  const rawDurationSeconds = Number(rawProbe.format.duration);
  const leadSeconds = Math.max(0, rawDurationSeconds - choreographyElapsedSeconds);
  execFileSync(ffmpeg, [
    "-y", "-hide_banner", "-loglevel", "error",
    "-i", rawPath,
    "-ss", leadSeconds.toFixed(3),
    "-t", choreographyElapsedSeconds.toFixed(3),
    "-vf", "fps=30,scale=1920:1080:flags=lanczos,unsharp=5:5:0.45:5:5:0",
    "-c:v", "libx264", "-preset", "slow", "-crf", "24",
    "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
    outputPath,
  ], { stdio: "inherit" });
  execFileSync(ffmpeg, ["-v", "error", "-i", outputPath, "-f", "null", "-"], { stdio: "inherit" });
  const probe = JSON.parse(execFileSync(ffprobe, [
    "-v", "error", "-show_streams", "-show_format", "-of", "json", outputPath,
  ], { encoding: "utf8" }));
  const stream = probe.streams.find((candidate) => candidate.codec_type === "video");
  const audioStreams = probe.streams.filter((candidate) => candidate.codec_type === "audio");
  const duration = Number(probe.format.duration);
  if (!stream || stream.codec_name !== "h264" || stream.width !== viewport.width || stream.height !== viewport.height || stream.pix_fmt !== "yuv420p" || audioStreams.length || duration < 42 || duration > 55) {
    throw new Error(`encoded video quality gate failed: ${JSON.stringify({ stream, audioStreams: audioStreams.length, duration })}`);
  }
  const buffer = await readFile(outputPath);
  return {
    ...variant,
    path: path.relative(repositoryRoot, outputPath).replaceAll(path.sep, "/"),
    bytes: buffer.length,
    sha256: sha256(buffer),
    duration_seconds: duration,
    codec: stream.codec_name,
    pixel_format: stream.pix_fmt,
    width: stream.width,
    height: stream.height,
    frame_rate: stream.avg_frame_rate,
    audio_streams: audioStreams.length,
    raw_lead_trim_seconds: Number(leadSeconds.toFixed(3)),
    raw_wall_lead_seconds: Number(wallLeadSeconds.toFixed(3)),
    raw_duration_seconds: rawDurationSeconds,
    raw_video_width: rawVideoSize.width,
    raw_video_height: rawVideoSize.height,
    choreography_elapsed_seconds: Number(choreographyElapsedSeconds.toFixed(3)),
    observed_choreography: observedChoreography,
    contract,
    terminal,
  };
}

async function runDryValidation() {
  const browser = await chromium.launch({ executablePath, headless: true, args: chromiumArgs });
  const context = await browser.newContext({
    viewport,
    deviceScaleFactor: 1,
    locale: "ja-JP",
    reducedMotion: "reduce",
    serviceWorkers: "block",
  });
  const page = await context.newPage();
  page.setDefaultTimeout(180_000);
  const pending = attachDiagnostics(page, "dry-run");
  try {
    await page.goto(guidedUrl("intro"), { waitUntil: "domcontentloaded", timeout: 180_000 });
    await waitState(page, "intro", { pending });
    await page.goto(guidedUrl("understand"), { waitUntil: "domcontentloaded", timeout: 180_000 });
    await waitState(page, "understand", { pending });
    await page.locator('.urban-section[data-annotation-overlap-count="0"]').waitFor({ timeout: 180_000 });
    await page.goto(guidedUrl("verify"), { waitUntil: "domcontentloaded", timeout: 180_000 });
    await waitState(page, "verify", { pending, exact: true });
    const contract = await page.evaluate(() => {
      const root = document.querySelector(".guided-spatial-app");
      return {
        story: root?.getAttribute("data-guided-story"),
        area: root?.getAttribute("data-area-id"),
        targetKind: root?.getAttribute("data-target-kind"),
        targetResolution: root?.getAttribute("data-target-resolution"),
        checks: document.querySelectorAll(".guided-check-list > li").length,
        mapInitializationCount: window.__cityGapMapInitCount,
      };
    });
    if (contract.story !== "verify" || contract.area !== selectedArea || contract.targetKind !== "road" || contract.targetResolution !== "exact" || contract.checks !== 4 || contract.mapInitializationCount !== 1) {
      throw new Error(`video dry-run contract failed: ${JSON.stringify(contract)}`);
    }
    if (diagnostics.length) throw new Error(`video dry-run diagnostics are not empty: ${JSON.stringify(diagnostics)}`);
    return {
      dry_run: true,
      source_url: sourceUrl.toString(),
      source_commit: sourceCommit,
      source_branch: sourceBranch,
      planned_duration_seconds: durationSeconds,
      choreography,
      contract,
      diagnostics: diagnostics.length,
      tools: {
        ffmpeg: versionLine(ffmpeg),
        ffprobe: versionLine(ffprobe),
        playwright: playwrightPackage.version,
      },
      passed: true,
    };
  } finally {
    await context.close();
    await browser.close();
  }
}

if (parameters.has("--dry-run")) {
  process.stdout.write(`${JSON.stringify(await runDryValidation(), null, 2)}\n`);
} else {
  await mkdir(outputDirectory, { recursive: true });
  await mkdir(rawDirectory, { recursive: true });
  let videoRecords;
  videoRecords = [];
  for (const variant of variants) videoRecords.push(await recordVariant(variant));

  const presentationPath = path.join(outputDirectory, variants[0].filename);
  const presentationChoreography = videoRecords.find((item) => item.id === "presentation")?.observed_choreography ?? choreography;
  const posterSecond = (presentationChoreography[3]?.end ?? 29) - 1;
  const posterPath = path.join(outputDirectory, "city-gap-demo-poster.png");
  execFileSync(ffmpeg, [
  "-y", "-hide_banner", "-loglevel", "error", "-ss", String(posterSecond), "-i", presentationPath,
  "-frames:v", "1", "-vf", "scale=1920:1080:flags=lanczos", posterPath,
], { stdio: "inherit" });
  const poster = await readFile(posterPath);

  const captionsPath = path.join(outputDirectory, "city-gap-demo-captions.vtt");
  const timestamp = (value) => {
  const milliseconds = Math.round(value * 1000);
  const seconds = Math.floor(milliseconds / 1000);
  return `00:00:${String(seconds).padStart(2, "0")}.${String(milliseconds % 1000).padStart(3, "0")}`;
  };
  const captions = `WEBVTT\n\n${presentationChoreography.map((item, index) => `${index + 1}\n${timestamp(item.start)} --> ${timestamp(item.end)}\n${item.caption}`).join("\n\n")}\n`;
  await writeFile(captionsPath, captions);

  const shortPath = path.join(outputDirectory, "city-gap-demo-short-15s.mp4");
  execFileSync(ffmpeg, [
  "-y", "-hide_banner", "-loglevel", "error", "-ss", String(Math.max(0, (presentationChoreography[3]?.start ?? 12) - 1)), "-i", presentationPath, "-t", "15",
  "-vf", "fps=30,scale=1920:1080:flags=lanczos,unsharp=5:5:0.45:5:5:0", "-c:v", "libx264", "-preset", "slow", "-crf", "24",
  "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", shortPath,
], { stdio: "inherit" });
  let shortRecord = null;
  const mainVideoBytes = videoRecords.reduce((sum, item) => sum + item.bytes, 0);
  const shortBuffer = await readFile(shortPath);
  if (mainVideoBytes + shortBuffer.length <= 35 * 1024 * 1024) {
  const shortProbe = JSON.parse(execFileSync(ffprobe, ["-v", "error", "-show_streams", "-show_format", "-of", "json", shortPath], { encoding: "utf8" }));
  const shortStream = shortProbe.streams.find((candidate) => candidate.codec_type === "video");
  shortRecord = {
    id: "short",
    filename: path.basename(shortPath),
    path: path.relative(repositoryRoot, shortPath).replaceAll(path.sep, "/"),
    captioned: true,
    bytes: shortBuffer.length,
    sha256: sha256(shortBuffer),
    duration_seconds: Number(shortProbe.format.duration),
    codec: shortStream?.codec_name,
    pixel_format: shortStream?.pix_fmt,
    width: shortStream?.width,
    height: shortStream?.height,
    frame_rate: shortStream?.avg_frame_rate,
    audio_streams: shortProbe.streams.filter((candidate) => candidate.codec_type === "audio").length,
  };
    videoRecords.push(shortRecord);
  } else {
    await rm(shortPath);
  }

  const captionBuffer = await readFile(captionsPath);
  const manifest = {
  schema_version: "citygap.production-demo-video@1",
  generated_at: new Date().toISOString(),
  source_production_url: sourceUrl.toString(),
  recording_start_url: guidedUrl("intro"),
  source_branch: sourceBranch,
  source_commit: sourceCommit,
  pages_run_id: pagesRunId,
  recording: {
    viewport,
    raw_video_size: rawVideoSize,
    device_pixel_ratio: 1,
    output_fps: 30,
    prewarmed: true,
    browser_chrome: false,
    audio: false,
    selected_area: selectedArea,
    selected_target: videoRecords[0].terminal.targetKey,
    section_artifact_id: sectionArtifactId,
    planned_choreography: choreography,
    exact_choreography: presentationChoreography,
    readiness: [
      "deployed source commit",
      "map rendered",
      "selected Area and candidate list rendered",
      "A–B line and Section artifact ready",
      "exact road target and four checks ready",
      "document fonts ready",
      "same-origin requests settled",
    ],
  },
  tools: {
    ffmpeg: versionLine(ffmpeg),
    ffprobe: versionLine(ffprobe),
    playwright: playwrightPackage.version,
    chromium_executable: executablePath,
  },
  diagnostics: {
    console_errors: diagnostics.filter((item) => item.kind === "console").length,
    page_errors: diagnostics.filter((item) => item.kind === "page").length,
    request_errors: diagnostics.filter((item) => item.kind === "request" || item.kind === "http").length,
    records: diagnostics,
  },
  files: {
    videos: videoRecords,
    poster: {
      path: path.relative(repositoryRoot, posterPath).replaceAll(path.sep, "/"),
      bytes: poster.length,
      sha256: sha256(poster),
      source_second: posterSecond,
    },
    captions: {
      path: path.relative(repositoryRoot, captionsPath).replaceAll(path.sep, "/"),
      bytes: captionBuffer.length,
      sha256: sha256(captionBuffer),
      cues: choreography.length,
    },
  },
  repository_video_bytes: videoRecords.reduce((sum, item) => sum + item.bytes, 0),
  human_review: {
    visual_quality: "READY_FOR_SELF_VISUAL_REVIEW",
    presentation: "READY_FOR_DEMO_REVIEW",
    human_test: "AWAITING_HUMAN_TEST",
    municipal_workflow: "AWAITING_MUNICIPAL_WORKFLOW_REVIEW",
  },
  };
  await writeFile(path.join(outputDirectory, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);

  await rm(rawDirectory, { recursive: true, force: true });
  phase(`complete: ${videoRecords.length} videos, ${(manifest.repository_video_bytes / 1024 / 1024).toFixed(1)} MiB`);
  process.stdout.write(`${JSON.stringify({ outputDirectory, sourceCommit, pagesRunId, videoRecords, diagnostics: diagnostics.length }, null, 2)}\n`);
}
