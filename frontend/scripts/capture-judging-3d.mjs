import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "playwright-core";

// No cleanup or overwrite: failed frames, profiles, and encodes remain available.
const scriptPath = fileURLToPath(import.meta.url);
const repositoryRoot = path.resolve(path.dirname(scriptPath), "../..");
export const monotonicMilliseconds = () => Number(process.hrtime.bigint()) / 1e6;
export const pause = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
export const hash = (buffer) => createHash("sha256").update(buffer).digest("hex");

export async function createOutputDirectory(label = "trial", requestedPath) {
  const directory = path.resolve(requestedPath ?? path.join(tmpdir(), `citygap-judging-3d-${label}-${process.pid}-${Date.now()}`));
  const relative = path.relative(repositoryRoot, directory);
  if (!relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative)) {
    throw new Error("Capture output must be outside the repository");
  }
  await mkdir(directory, { recursive: false });
  return directory;
}

export function jpegDimensions(buffer) {
  if (buffer.readUInt16BE(0) !== 0xffd8) throw new Error("Capture frame is not JPEG");
  let offset = 2;
  while (offset < buffer.length) {
    while (buffer[offset] === 0xff) offset += 1;
    const marker = buffer[offset++];
    if (marker === 0xd9 || marker === 0xda) break;
    if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue;
    const length = buffer.readUInt16BE(offset);
    if ([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf].includes(marker)) {
      return { width: buffer.readUInt16BE(offset + 5), height: buffer.readUInt16BE(offset + 3) };
    }
    offset += length;
  }
  throw new Error("JPEG dimension marker missing");
}

export async function openCaptureBrowser({ directory, viewport = { width: 1920, height: 1080 }, executablePath, cdpEndpoint } = {}) {
  const options = { viewport, screen: viewport, deviceScaleFactor: 1, locale: "ja-JP", serviceWorkers: "block" };
  const connectedBrowser = cdpEndpoint ? await chromium.connectOverCDP(cdpEndpoint) : null;
  const context = connectedBrowser
    ? await connectedBrowser.newContext(options)
    : await chromium.launchPersistentContext(path.join(directory, "chromium-profile"), {
      ...options,
      executablePath: executablePath ?? (process.platform === "win32" ? "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" : chromium.executablePath()),
      headless: true,
      args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist"],
    });
  const browser = connectedBrowser ?? context.browser();
  const page = context.pages()[0] ?? await context.newPage();
  page.setDefaultTimeout(30_000);
  const errors = [];
  page.on("pageerror", (error) => errors.push({ kind: "page", message: error.message }));
  page.on("requestfailed", (request) => {
    if (request.failure()?.errorText !== "net::ERR_ABORTED") errors.push({ kind: "request", url: request.url(), message: request.failure()?.errorText });
  });
  page.on("response", (response) => {
    if (response.status() >= 400) errors.push({ kind: "http", url: response.url(), status: response.status() });
  });
  return { browser, context, page, errors, directory, viewport };
}

export async function rendererEvidence(page) {
  return page.evaluate(() => {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
    const info = gl?.getExtension("WEBGL_debug_renderer_info");
    return {
      userAgent: navigator.userAgent,
      viewport: { width: innerWidth, height: innerHeight },
      device_pixel_ratio: devicePixelRatio,
      renderer: info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl?.getParameter(gl.RENDERER),
      vendor: info ? gl.getParameter(info.UNMASKED_VENDOR_WEBGL) : gl?.getParameter(gl.VENDOR),
    };
  });
}

export async function sceneEvidence(page) {
  return page.evaluate(() => {
    const viewer = window.__cityGapCesiumViewer;
    const container = document.querySelector("[data-building-source][data-local-dem]");
    const primitives = viewer?.scene.primitives;
    const tilesets = [];
    for (let index = 0; index < (primitives?.length ?? 0); index += 1) {
      const primitive = primitives.get(index);
      if (!primitive.root || !primitive.statistics) continue;
      const stats = primitive.statistics;
      tilesets.push({
        url: primitive._url ?? primitive.resource?.url ?? null,
        show: primitive.show,
        tiles_loaded: primitive.tilesLoaded,
        content_ready: stats.numberOfTilesWithContentReady,
        selected_features: stats.numberOfFeaturesSelected,
        loaded_features: stats.numberOfFeaturesLoaded,
        selected_tiles: primitive._selectedTiles?.length ?? null,
        pending: stats.numberOfPendingRequests,
        processing: stats.numberOfTilesProcessing,
      });
    }
    return {
      url: location.href,
      root: { ...document.querySelector(".guided-spatial-app")?.dataset },
      readiness: { ...container?.dataset },
      canvas: viewer ? { width: viewer.scene.drawingBufferWidth, height: viewer.scene.drawingBufferHeight } : null,
      globe_visible: viewer?.scene.globe.show ?? null,
      camera: viewer ? { height: viewer.camera.positionCartographic.height, heading: viewer.camera.heading, pitch: viewer.camera.pitch } : null,
      tilesets,
      inspector_text: document.querySelector(".guided-story-panel")?.textContent ?? null,
      checks: [...document.querySelectorAll(".guided-check-list > li")].map((element) => element.textContent),
    };
  });
}

export async function waitForReal3D(page, timeout = 45_000) {
  await page.waitForFunction(() => {
    const container = document.querySelector("[data-building-source][data-local-dem]");
    const data = container?.dataset;
    return window.__cityGapCesiumViewer && data?.packArtifactsReady === "true"
      && data?.buildingContentReady === "true" && data?.captureStrictReady === "true"
      && data?.localDemReady === "true" && data?.roadsReady === "true"
      && data?.cameraSettled === "true" && Number(data?.stableFrames) >= 3
      && Number(data?.visibleTargetBuildingCount) > 0 && data?.criticalRequests === "0";
  }, null, { timeout });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  const evidence = await sceneEvidence(page);
  const required = evidence.tilesets.filter((tileset) => tileset.show);
  if (!required.some((tileset) => tileset.selected_features > 0 && tileset.content_ready > 0)
      || required.some((tileset) => !tileset.tiles_loaded || tileset.pending > 0 || tileset.processing > 0)) {
    throw new Error(`Current camera content is not ready: ${JSON.stringify(evidence)}`);
  }
  return evidence;
}

export async function clickFeaturedBuilding(page, metadata, { click = true } = {}) {
  const featured = metadata.featured_building;
  if (!featured?.id || !Number.isFinite(featured.longitude) || !Number.isFinite(featured.latitude)) throw new Error("Verified metadata has no featured building coordinate");
  const target = await page.evaluate((building) => {
    const viewer = window.__cityGapCesiumViewer;
    if (!viewer) throw new Error("Cesium viewer missing");
    const coordinate = { longitude: building.longitude * Math.PI / 180, latitude: building.latitude * Math.PI / 180, height: 0 };
    const sampledHeight = viewer.scene.sampleHeightSupported ? viewer.scene.sampleHeight(coordinate) : undefined;
    if (!Number.isFinite(sampledHeight)) throw new Error("Rendered featured building surface height is unavailable");
    coordinate.height = sampledHeight;
    const point = viewer.scene.cartesianToCanvasCoordinates(viewer.scene.globe.ellipsoid.cartographicToCartesian(coordinate));
    if (!point) throw new Error("Featured building does not project into the current scene");
    const canvasBox = viewer.scene.canvas.getBoundingClientRect();
    for (const [dx, dy] of [[0, 0], [3, 0], [-3, 0], [0, 3], [0, -3], [6, 3], [-6, -3]]) {
      const position = { x: point.x + dx, y: point.y + dy };
      const picked = viewer.scene.drillPick(position, 20).find((feature) => typeof feature.getProperty === "function" && feature.getProperty("gml_id") === building.id);
      if (!picked) continue;
      const attributes = picked.getProperty("attributes") ?? {};
      const read = (key) => picked.getProperty(key) ?? attributes[key] ?? null;
      return {
        x: canvasBox.x + position.x, y: canvasBox.y + position.y,
        id: picked.getProperty("gml_id"), lod: picked.getProperty("_lod"),
        usage: read("bldg:usage"), measured_height_m: read("bldg:measuredHeight"),
        storeys_above_ground: read("bldg:storeysAboveGround"),
        sampled_surface_elevation_m: sampledHeight,
      };
    }
    throw new Error(`Real scene picking did not find ${building.id} at its metadata coordinate`);
  }, featured);
  if (target.id !== featured.id || Number(target.measured_height_m) !== featured.measured_height_m
      || Number(target.storeys_above_ground) !== featured.storeys_above_ground || target.usage !== featured.usage) {
    throw new Error(`Picked object attributes differ from metadata: ${JSON.stringify(target)}`);
  }
  if (click) {
    await page.mouse.click(target.x, target.y);
    await page.locator(`.guided-spatial-app[data-object-kind="building"][data-object-id="${featured.id}"]`).waitFor();
    await page.locator(`[data-selected-building-id="${featured.id}"]`).waitFor();
  }
  return target;
}

export async function moveRealCamera(page, seconds = 3) {
  const canvas = page.locator(".guided-3d-view .cesium-widget canvas");
  const box = await canvas.boundingBox();
  if (!box) throw new Error("Visible Cesium canvas missing");
  const before = await page.evaluate(() => {
    const camera = window.__cityGapCesiumViewer.camera;
    return { heading: camera.heading, pitch: camera.pitch };
  });
  const x = box.x + box.width * 0.51;
  const y = box.y + box.height * 0.46;
  const started = monotonicMilliseconds();
  await page.mouse.move(x, y);
  await page.mouse.down({ button: "middle" });
  try {
    for (let step = 1; step <= 90; step += 1) {
      const hold = started + step * seconds * 1000 / 90 - monotonicMilliseconds();
      if (hold > 0) await pause(hold);
      await page.mouse.move(x + step * box.width * 0.035 / 90, y + step * box.height * 0.012 / 90);
    }
  } finally { await page.mouse.up({ button: "middle" }); }
  const after = await page.evaluate(() => {
    const camera = window.__cityGapCesiumViewer.camera;
    return { heading: camera.heading, pitch: camera.pitch };
  });
  if (Math.abs(after.heading - before.heading) + Math.abs(after.pitch - before.pitch) < 0.005) throw new Error("Actual mouse drag did not move the 3D camera");
  return { input: "middle mouse drag", before, after, elapsed_seconds: (monotonicMilliseconds() - started) / 1000 };
}

export async function createNativeScreencast({ page, context, directory, viewport }) {
  const framesDirectory = path.join(directory, "frames");
  await mkdir(framesDirectory, { recursive: false });
  const cdp = await context.newCDPSession(page);
  const frames = [];
  const writes = [];
  let frameError;
  let accepting = false;
  let started = 0;
  let wallStarted = 0;
  const retain = (buffer, seconds, cdpTimestamp = null) => {
    const dimensions = jpegDimensions(buffer);
    if (dimensions.width !== viewport.width || dimensions.height !== viewport.height) {
      throw new Error(`Native frame size ${dimensions.width}x${dimensions.height} differs from ${viewport.width}x${viewport.height}`);
    }
    const filename = `frame-${String(frames.length).padStart(6, "0")}.jpg`;
    frames.push({ filename, offset_seconds: seconds, cdp_timestamp: cdpTimestamp, ...dimensions, bytes: buffer.length });
    writes.push(writeFile(path.join(framesDirectory, filename), buffer, { flag: "wx" }).catch((error) => { frameError ??= error; }));
  };
  const screenshot = async () => Buffer.from((await cdp.send("Page.captureScreenshot", {
    format: "jpeg", quality: 95, fromSurface: true, captureBeyondViewport: false,
    clip: { x: 0, y: 0, ...viewport, scale: 1 },
  })).data, "base64");
  cdp.on("Page.screencastFrame", (event) => {
    void cdp.send("Page.screencastFrameAck", { sessionId: event.sessionId }).catch((error) => { frameError ??= error; });
    if (!accepting) return;
    try { retain(Buffer.from(event.data, "base64"), (monotonicMilliseconds() - started) / 1000, event.metadata.timestamp ?? null); }
    catch (error) { frameError ??= error; accepting = false; }
  });
  return {
    async start() {
      const initial = await screenshot();
      started = monotonicMilliseconds();
      wallStarted = Date.now();
      retain(initial, 0);
      accepting = true;
      await cdp.send("Page.startScreencast", { format: "jpeg", quality: 95, maxWidth: viewport.width, maxHeight: viewport.height, everyNthFrame: 1 });
      return started;
    },
    async stop() {
      accepting = false;
      const duration = (monotonicMilliseconds() - started) / 1000;
      await cdp.send("Page.stopScreencast");
      retain(await screenshot(), duration);
      await Promise.all(writes);
      const record = {
        method: "Chromium DevTools Page.screencastFrame, JPEG quality 95, everyNthFrame 1",
        frame_cadence: "Event-driven variable compositor frames; receipt times use process.hrtime.bigint()",
        viewport, actual_capture_pixels: viewport, output_pixels: viewport, device_pixel_ratio: 1,
        native_capture: true, spatial_upscale: false, output_fps: 30,
        temporal_normalization: "FFmpeg fps=30 may duplicate or drop acquired frames; no generated motion interpolation",
        duration_seconds: duration, frame_count: frames.length,
        wall_clock_elapsed_seconds: (Date.now() - wallStarted) / 1000,
        monotonic_duration_seconds: duration,
        frames,
      };
      await writeFile(path.join(directory, "capture.json"), `${JSON.stringify(record, null, 2)}\n`, { flag: "wx" });
      await cdp.detach();
      if (frameError) throw frameError;
      return record;
    },
  };
}

function linuxPath(value) {
  return process.platform === "win32" ? execFileSync("wsl.exe", ["-d", "Ubuntu-24.04", "--exec", "wslpath", "-u", value], { encoding: "utf8" }).trim() : value;
}

function ffmpegTool(tool, args) {
  return process.platform === "win32"
    ? execFileSync("wsl.exe", ["-d", "Ubuntu-24.04", "--exec", `/home/mhirotaka/.local/bin/${tool}`, ...args], { encoding: "utf8", timeout: 180_000, maxBuffer: 4 * 1024 * 1024 })
    : execFileSync(tool, args, { encoding: "utf8", timeout: 180_000, maxBuffer: 4 * 1024 * 1024 });
}

export async function encodeCapture(directory, filename = "city-gap-3d-demo-clean.mp4") {
  const capture = JSON.parse(await readFile(path.join(directory, "capture.json"), "utf8"));
  const frameRoot = linuxPath(path.join(directory, "frames"));
  if (frameRoot.includes("'")) throw new Error("Output path cannot contain apostrophes for FFmpeg concat");
  const lines = ["ffconcat version 1.0"];
  for (let index = 0; index < capture.frames.length - 1; index += 1) {
    const frame = capture.frames[index];
    lines.push(`file '${frameRoot}/${frame.filename}'`, "option framerate 1000", `duration ${Math.max(0.000001, capture.frames[index + 1].offset_seconds - frame.offset_seconds).toFixed(6)}`);
  }
  lines.push(`file '${frameRoot}/${capture.frames.at(-1).filename}'`, "option framerate 1000");
  const concatPath = path.join(directory, "frames.ffconcat");
  await writeFile(concatPath, `${lines.join("\n")}\n`, { flag: "wx" });
  const outputPath = path.join(directory, filename);
  ffmpegTool("ffmpeg", ["-n", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", linuxPath(concatPath),
    "-t", capture.duration_seconds.toFixed(6), "-vf", "fps=30,scale=iw:ih:in_range=pc:out_range=tv,format=yuv420p",
    "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", linuxPath(outputPath)]);
  ffmpegTool("ffmpeg", ["-v", "error", "-i", linuxPath(outputPath), "-f", "null", "-"]);
  const probe = JSON.parse(ffmpegTool("ffprobe", ["-v", "error", "-show_streams", "-show_format", "-of", "json", linuxPath(outputPath)]));
  const video = probe.streams.find((stream) => stream.codec_type === "video");
  if (video?.width !== capture.actual_capture_pixels.width || video?.height !== capture.actual_capture_pixels.height
      || video?.codec_name !== "h264" || video?.pix_fmt !== "yuv420p" || video?.avg_frame_rate !== "30/1"
      || probe.streams.some((stream) => stream.codec_type === "audio")) throw new Error("Encoded media contract failed");
  const bytes = await readFile(outputPath);
  const outputFrames = Number(video.nb_frames);
  const longHoldCount = capture.frames.slice(1).filter((frame, index) => frame.offset_seconds - capture.frames[index].offset_seconds > 2 / 30).length;
  const evidence = { filename, bytes: bytes.length, sha256: hash(bytes), probe, source_capture: "capture.json", resized: false,
    acquired_frame_count: capture.frame_count, output_frame_count: outputFrames,
    static_hold_frame_duplication: longHoldCount > 0,
    acquired_intervals_longer_than_two_output_frames: longHoldCount,
    temporal_processing: "Input timestamps retain variable acquired intervals with millisecond demuxer timebase; fps=30 duplicates held frames and may drop surplus frames. No motion interpolation.",
  };
  await writeFile(path.join(directory, "encode.json"), `${JSON.stringify(evidence, null, 2)}\n`, { flag: "wx" });
  return evidence;
}

export async function captionMaster(directory, outputDirectory = directory) {
  const clean = path.join(directory, "city-gap-3d-demo-clean.mp4");
  const cleanRecord = JSON.parse(await readFile(path.join(directory, "encode.json"), "utf8"));
  const cleanBytes = await readFile(clean);
  if (hash(cleanBytes) !== cleanRecord.sha256) throw new Error("Clean master differs from its verified encode");
  const production = JSON.parse(await readFile(path.join(directory, "production-capture.json"), "utf8"));
  const buildingStart = production.scenes.find((scene) => scene.label === "Real building selected during recording")?.start_seconds;
  const sectionStart = production.scenes.find((scene) => scene.label === "Same A–B and focused Section")?.start_seconds;
  const checksStart = production.scenes.find((scene) => scene.label === "Same selected building with its unconfirmed checks")?.start_seconds;
  if (![buildingStart, sectionStart, checksStart].every(Number.isFinite)) throw new Error("Caption timings require completed master choreography evidence");
  const cues = [
    { start: 0, end: buildingStart, text: "PLATEAUの街を、立体で見る" },
    { start: buildingStart, end: sectionStart, text: "建物の形と高さ・用途を確認" },
    { start: sectionStart, end: checksStart, text: "地形との関係を、同じ断面で見る" },
    { start: checksStart, end: Number(cleanRecord.probe.format.duration), text: "分からない点を、現地で確認する場所へ" },
  ];
  const stamp = (seconds, ass = false) => ass
    ? `0:${String(Math.floor(seconds / 60)).padStart(2, "0")}:${(seconds % 60).toFixed(2).padStart(5, "0")}`
    : `00:${String(Math.floor(seconds / 60)).padStart(2, "0")}:${(seconds % 60).toFixed(3).padStart(6, "0")}`;
  const captions = `WEBVTT\n\n${cues.map((cue) => `${stamp(cue.start)} --> ${stamp(cue.end)}\n${cue.text}\n`).join("\n")}`;
  const captionsPath = path.join(outputDirectory, "captions.vtt");
  await writeFile(captionsPath, captions, { flag: "wx" });
  const cleanVideo = cleanRecord.probe.streams.find((stream) => stream.codec_type === "video");
  const assPath = path.join(outputDirectory, "captions.ass");
  const ass = `[Script Info]\nScriptType: v4.00+\nPlayResX: ${cleanVideo.width}\nPlayResY: ${cleanVideo.height}\nWrapStyle: 2\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Default,Noto Sans CJK JP,${Math.round(cleanVideo.width / 64)},&H00FFFFFF,&H00FFFFFF,&H20292F2D,&H20292F2D,0,0,0,0,100,100,0,0,3,6,0,8,36,36,12,1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n${cues.map((cue) => `Dialogue: 0,${stamp(cue.start, true)},${stamp(cue.end, true)},Default,,0,0,0,,${cue.text}`).join("\n")}\n`;
  await writeFile(assPath, ass, { flag: "wx" });
  const subtitlesPath = linuxPath(assPath);
  if (subtitlesPath.includes("'")) throw new Error("Subtitle path cannot contain apostrophes");
  const outputPath = path.join(outputDirectory, "city-gap-3d-demo-captioned.mp4");
  ffmpegTool("ffmpeg", ["-n", "-hide_banner", "-loglevel", "error", "-i", linuxPath(clean),
    "-vf", `ass=filename='${subtitlesPath}'`,
    "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", linuxPath(outputPath)]);
  ffmpegTool("ffmpeg", ["-v", "error", "-i", linuxPath(outputPath), "-f", "null", "-"]);
  const probe = JSON.parse(ffmpegTool("ffprobe", ["-v", "error", "-show_streams", "-show_format", "-of", "json", linuxPath(outputPath)]));
  const video = probe.streams.find((stream) => stream.codec_type === "video");
  if (video?.width !== cleanVideo.width || video?.height !== cleanVideo.height || video?.codec_name !== "h264"
      || video?.pix_fmt !== "yuv420p" || video?.avg_frame_rate !== "30/1" || video?.nb_frames !== cleanVideo.nb_frames
      || probe.streams.some((stream) => stream.codec_type === "audio")) throw new Error("Captioned derivation changed the master video contract");
  const bytes = await readFile(outputPath);
  const evidence = {
    filename: path.basename(outputPath), bytes: bytes.length, sha256: hash(bytes), probe,
    derived_from: { filename: path.basename(clean), sha256: cleanRecord.sha256 },
    processing: "Offline subtitles on the one clean master; no separate recording, resizing, or motion interpolation",
    captions: { filename: "captions.vtt", bytes: Buffer.byteLength(captions), sha256: hash(Buffer.from(captions)), cues: cues.length, timing: "Observed master scene transition times", placement: "Top-center in unused application header space" },
  };
  await writeFile(path.join(outputDirectory, "captioned.json"), `${JSON.stringify(evidence, null, 2)}\n`, { flag: "wx" });
  return evidence;
}

async function main() {
  const args = new Map();
  for (let index = 2; index < process.argv.length; index += 2) args.set(process.argv[index], process.argv[index + 1]);
  const mode = args.get("--mode") ?? "diagnose";
  if (mode === "encode") {
    process.stdout.write(`${JSON.stringify(await encodeCapture(args.get("--output"), args.get("--filename")), null, 2)}\n`);
    return;
  }
  if (mode === "caption") {
    const captionOutput = args.get("--caption-output") ? await createOutputDirectory("captions", args.get("--caption-output")) : args.get("--output");
    process.stdout.write(`${JSON.stringify(await captionMaster(args.get("--output"), captionOutput), null, 2)}\n`);
    return;
  }
  if (mode === "package") {
    const directory = await createOutputDirectory("package", args.get("--output"));
    const driver = await import("./capture-judging-3d-driver.mjs");
    process.stdout.write(`${JSON.stringify(await driver.packageJudgingAssets({ directory, imagesDirectory: args.get("--images"), areaImageDirectory: args.get("--area-image"), masterDirectory: args.get("--master"), captionDirectory: args.get("--captions"), trialDirectory: args.get("--trial") }), null, 2)}\n`);
    return;
  }
  const directory = await createOutputDirectory(mode, args.get("--output"));
  const width = Number(args.get("--width") ?? 1920);
  if (![1920, 1280].includes(width)) throw new Error("Only native 1920x1080 or 1280x720 capture is permitted");
  const session = await openCaptureBrowser({ directory, viewport: { width, height: width * 9 / 16 }, cdpEndpoint: args.get("--cdp") });
  try {
    const renderer = await rendererEvidence(session.page);
    await writeFile(path.join(directory, "renderer.json"), `${JSON.stringify(renderer, null, 2)}\n`, { flag: "wx" });
    process.stdout.write(`${JSON.stringify({ directory, renderer }, null, 2)}\n`);
    if (mode === "inspect") {
      await session.page.goto(args.get("--url"), { waitUntil: "domcontentloaded", timeout: 45_000 });
      try {
        await waitForReal3D(session.page);
        const metadataUrl = new URL("data/plateau/metadata.json", args.get("--url"));
        const metadata = await (await session.context.request.get(metadataUrl.href)).json();
        const movement = await moveRealCamera(session.page);
        await waitForReal3D(session.page);
        if (args.get("--zoom")) {
          const target = await clickFeaturedBuilding(session.page, metadata, { click: false });
          await session.page.mouse.move(target.x, target.y);
          await session.page.mouse.wheel(0, -240);
          await pause(1000);
          await waitForReal3D(session.page);
        }
        const picked = await clickFeaturedBuilding(session.page, metadata);
        await writeFile(path.join(directory, "interaction.json"), `${JSON.stringify({ movement, picked }, null, 2)}\n`, { flag: "wx" });
        if (args.get("--section")) {
          await session.page.screenshot({ path: path.join(directory, "local-hero.png"), fullPage: false });
          await session.page.getByRole("button", { name: "街の断面", exact: true }).click();
          await session.page.locator('.guided-map-stage[data-section-expanded="true"] .urban-section').waitFor();
          await waitForReal3D(session.page);
        }
      } finally {
        await writeFile(path.join(directory, "scene.json"), `${JSON.stringify(await sceneEvidence(session.page), null, 2)}\n`, { flag: "wx" });
        await session.page.screenshot({ path: path.join(directory, "local-diagnostic.png"), fullPage: false });
      }
    } else if (mode !== "diagnose") {
      if (!args.get("--driver")) throw new Error("A production choreography driver is required for trial/master capture");
      const driver = await import(pathToFileURL(path.resolve(args.get("--driver"))).href);
      await driver.default({ ...session, mode, sourceUrl: args.get("--url"), sourceCommit: args.get("--source-commit"), pagesRun: args.get("--pages-run"), helpers: { waitForReal3D, sceneEvidence, createNativeScreencast, clickFeaturedBuilding, moveRealCamera, pause, monotonicMilliseconds } });
    }
  } finally {
    await writeFile(path.join(directory, "diagnostics.json"), `${JSON.stringify(session.errors, null, 2)}\n`, { flag: "wx" });
    await session.context.close();
    await session.browser.close();
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === scriptPath) {
  await main();
}
