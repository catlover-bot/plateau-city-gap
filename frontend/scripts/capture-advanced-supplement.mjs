import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Actual production navigation and native capture only. No app-data mutation,
// hidden loading states, composites, cleanup, or changes to existing assets.
const hash = (bytes) => createHash("sha256").update(bytes).digest("hex");
const area = "533513314";

async function readAdvanced(page) {
  return page.evaluate(() => ({
    url: location.href,
    selected_area: new URL(location.href).searchParams.get("selection"),
    mesh: new URL(location.href).searchParams.get("mesh"),
    product: { ...document.querySelector(".product-app")?.dataset },
    readiness: { ...document.documentElement.dataset },
    upgrade: window.__cityGapFullDataUpgrade,
    map_style_loaded: document.querySelector(".analytical-map-canvas")?.__cityGapMap?.isStyleLoaded() ?? false,
    map_view: (() => { const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap; return map ? { longitude: map.getCenter().lng, latitude: map.getCenter().lat, zoom: map.getZoom(),
      mesh_fill_visibility: map.getLayoutProperty("mesh-fill", "visibility"), mesh_selected_visibility: map.getLayoutProperty("mesh-selected", "visibility"),
      rendered_selected_mesh_features: map.queryRenderedFeatures(undefined, { layers: ["mesh-fill", "mesh-selected"] }).filter((feature) => String(feature.properties?.mesh_code) === "533513314").length } : null; })(),
    inspector: document.querySelector(".context-inspector")?.textContent,
    selection_facts: document.querySelector(".selection-facts")?.textContent,
    object_lens: document.querySelector(".object-lens-current")?.textContent,
    technical_id: document.querySelector(".technical-details code")?.textContent,
    inspector_scroll_top: document.querySelector(".inspector-scroll")?.scrollTop,
    loading_visible: [...document.querySelectorAll(".state-screen, [aria-busy='true']")].some((node) => { const box = node.getBoundingClientRect(); return box.width > 0 && box.height > 0; }),
  }));
}

async function waitAdvanced(page, timeout = 90_000) {
  await page.locator('.product-app[data-experience="advanced"] .context-inspector.open').waitFor({ timeout });
  await page.waitForFunction(() => window.__cityGapFullDataUpgrade?.mode === "full"
    && window.__cityGapFullDataUpgrade?.settleResult === "success"
    && document.querySelector(".analytical-map-canvas")?.__cityGapMap?.isStyleLoaded(), null, { timeout });
  await page.evaluate(async () => { await document.fonts.ready; await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))); });
  const evidence = await readAdvanced(page);
  if (evidence.selected_area !== area || evidence.mesh !== area || evidence.technical_id !== area || evidence.loading_visible) throw new Error(`Advanced lost selected Area or remains loading: ${JSON.stringify(evidence)}`);
  return evidence;
}

export default async function run({ page, context, viewport, directory, mode, sourceUrl, sourceCommit, pagesRun, helpers }) {
  const { pause, waitForReal3D, sceneEvidence, createNativeScreencast, monotonicMilliseconds } = helpers;
  const url = new URL(sourceUrl);
  if (url.origin !== "https://catlover-bot.github.io" || url.pathname !== "/plateau-city-gap/"
      || url.searchParams.get("selection") !== area || !sourceCommit || !pagesRun) throw new Error("Explicit deployed same-Area URL and source identity are required");
  const root = new URL("/plateau-city-gap/", url);
  const dist = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../dist");
  const liveIndex = await (await context.request.get(root.href, { timeout: 30_000 })).body();
  if (!(await readFile(path.join(dist, "index.html"))).equals(liveIndex)) throw new Error("Production index differs from local declared build");
  const assets = [];
  for (const name of (await readdir(path.join(dist, "assets"))).filter((value) => /\.(js|css)$/.test(value))) {
    const assetPath = `assets/${name}`;
    const bytes = await (await context.request.get(new URL(assetPath, root).href, { timeout: 30_000 })).body();
    if (!(await readFile(path.join(dist, assetPath))).equals(bytes)) throw new Error(`Production asset differs: ${assetPath}`);
    assets.push({ path: assetPath, bytes: bytes.length, sha256: hash(bytes), matches_local_build: true });
  }
  const evidence = {
    schema_version: "citygap.advanced-supplement-capture@1", production_url: url.href, ui_source_commit: sourceCommit, pages_run: pagesRun,
    selected_area: area, viewport, live_build: { index_sha256: hash(liveIndex), assets },
    prewarming: "Before recording, the same page visits Guided and clicks Advanced. It then reloads Guided without bare-ID selection parameters so the existing default-Area initialization hydrates real 533513314 properties. Browser HTTP cache is warm; page-local loader memory is recreated. This is not cold-load performance evidence.",
    composition: { browser_chrome: false, images_cropped: false, images_composited: false, loading_hidden: false, attributes_injected: false },
    scenes: [], files: [],
  };
  let recorder;
  let started;
  let stopped = false;
  const at = () => started === undefined ? undefined : (monotonicMilliseconds() - started) / 1000;
  const screenshot = async (filename, label) => {
    await page.waitForFunction(() => document.documentElement.dataset.captureStrictReady === "true"
      && document.documentElement.dataset.visualReady === "true", null, { timeout: 12_000 });
    const scene = await waitAdvanced(page, 12_000);
    await page.mouse.move(8, viewport.height - 8);
    const bytes = await page.screenshot({ type: "png", fullPage: false, animations: "allow", caret: "hide" });
    if (bytes.readUInt32BE(16) !== viewport.width || bytes.readUInt32BE(20) !== viewport.height) throw new Error("PNG is not native viewport size");
    await writeFile(path.join(directory, filename), bytes, { flag: "wx" });
    evidence.files.push({ filename, bytes: bytes.length, sha256: hash(bytes), width: viewport.width, height: viewport.height });
    evidence.scenes.push({ label, at_seconds: at(), evidence: scene });
  };
  const scrollToLens = async () => {
    const bounds = await page.locator(".inspector-scroll").boundingBox();
    const delta = await page.evaluate(() => {
      const scroll = document.querySelector(".inspector-scroll").getBoundingClientRect();
      return document.querySelector(".object-lens").getBoundingClientRect().top - scroll.top - 16;
    });
    await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
    for (let index = 0; index < 20; index += 1) { await page.mouse.wheel(0, delta / 20); await pause(55); }
    await pause(300);
  };
  try {
    process.stdout.write(`[advanced] ${assets.length} live assets match; prewarm real transition\n`);
    await page.goto(url.href, { waitUntil: "domcontentloaded", timeout: 45_000 });
    await waitForReal3D(page);
    evidence.prewarm_guided = await sceneEvidence(page);
    await page.getByRole("button", { name: "詳細分析", exact: true }).click();
    evidence.prewarm_advanced = await waitAdvanced(page);
    process.stdout.write(`[advanced] actual Advanced URL: ${page.url()}\n`);
    if (mode === "advanced-inspect") {
      await pause(1200);
      await screenshot("diagnostic-advanced-top.png", "Advanced selected-Area summary and workflow");
      await scrollToLens();
      await screenshot("diagnostic-advanced-lens.png", "Selected-Area Object Lens source and analysis attributes");
      return;
    }
    if (!["advanced-master", "advanced-area-image"].includes(mode)) throw new Error(`Unsupported supplemental mode ${mode}`);
    const hydratedGuidedUrl = new URL(url);
    for (const key of ["selectionType", "selection", "mesh"]) hydratedGuidedUrl.searchParams.delete(key);
    evidence.hydrated_guided_entry_url = hydratedGuidedUrl.href;
    await page.goto(hydratedGuidedUrl.href, { waitUntil: "domcontentloaded", timeout: 45_000 });
    await waitForReal3D(page);
    await pause(1200);
    const preparedGuided = await sceneEvidence(page);
    if (preparedGuided.root.areaId !== area) throw new Error("Default Guided initialization did not preserve the intended Area");
    evidence.scenes.push({ label: "Same Area in Guided before recorded click", at_seconds: 0, evidence: preparedGuided });
    if (mode === "advanced-area-image") {
      await page.getByRole("button", { name: "詳細分析", exact: true }).click();
      await waitAdvanced(page);
      const canvas = await page.locator(".analytical-map-canvas").boundingBox();
      await page.mouse.move(canvas.x + canvas.width / 2, canvas.y + canvas.height / 2);
      for (let step = 0; step < 8; step += 1) {
        const zoom = await page.evaluate(() => document.querySelector(".analytical-map-canvas").__cityGapMap.getZoom());
        if (zoom <= 14.25) break;
        await page.mouse.wheel(0, 60);
        await pause(400);
      }
      await pause(1000);
      const current = await waitAdvanced(page, 12_000);
      evidence.area_image_attempt = current;
      if (current.map_view.rendered_selected_mesh_features < 1) throw new Error("Same-Area mesh overlay remains unavailable after bounded normal zoom; no further image recapture");
      await screenshot("01-advanced-area-analysis.png", "Same-Area selected mesh overlay and hydrated aggregate summary at mesh scale");
      return;
    }
    recorder = await createNativeScreencast({ page, context, directory, viewport });
    evidence.recording_started_utc = new Date().toISOString();
    started = await recorder.start();
    const holdUntil = async (seconds) => { const remaining = started + seconds * 1000 - monotonicMilliseconds(); if (remaining > 0) await pause(remaining); };
    await holdUntil(1.8);
    evidence.advanced_click_started_seconds = at();
    await page.getByRole("button", { name: "詳細分析", exact: true }).click();
    const advancedReady = await waitAdvanced(page, 10_000);
    if (!advancedReady.selection_facts.includes("200人") || !advancedReady.selection_facts.includes("563 m") || !advancedReady.selection_facts.includes("1,451 m")) throw new Error("Actual selected-Area summary lacks the known source-hydrated values");
    evidence.scenes.push({ label: "Real Guided-to-Advanced click settled with same Area", at_seconds: at(), evidence: advancedReady });
    await holdUntil(5);
    await screenshot("01-advanced-area-analysis.png", "Advanced selected-Area aggregate summary and workflow");
    await holdUntil(7);
    evidence.inspector_scroll_started_seconds = at();
    await scrollToLens();
    await screenshot("02-advanced-object-lens.png", "Selected-Area Object Lens source and analysis attributes");
    await holdUntil(13);
    evidence.recording = await recorder.stop();
    stopped = true;
    evidence.recording_finished_utc = new Date().toISOString();
    if (evidence.recording.duration_seconds < 10 || evidence.recording.duration_seconds > 15) throw new Error("Supplemental recording is outside 10–15 seconds");
    process.stdout.write(`[advanced] complete: ${evidence.recording.frame_count} native frames, ${evidence.recording.duration_seconds.toFixed(3)}s\n`);
  } finally {
    if (recorder && !stopped) evidence.failed_recording = await recorder.stop();
    await writeFile(path.join(directory, "advanced-capture.json"), `${JSON.stringify(evidence, null, 2)}\n`, { flag: "wx" });
  }
}

async function packageSupplement(sourceDirectory, directory, replacementDirectory) {
  const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
  const repositoryRoot = path.resolve(scriptDirectory, "../..");
  directory = path.resolve(directory);
  const relative = path.relative(repositoryRoot, directory);
  if (!relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative)) throw new Error("Supplement package must be outside repository");
  await mkdir(directory, { recursive: false });
  const json = async (filename) => JSON.parse(await readFile(path.join(sourceDirectory, filename), "utf8"));
  const [capture, encode, diagnostics, renderer] = await Promise.all([json("advanced-capture.json"), json("encode.json"), json("diagnostics.json"), json("renderer.json")]);
  const imageAttempt = replacementDirectory ? JSON.parse(await readFile(path.join(replacementDirectory, "advanced-capture.json"), "utf8")) : null;
  const replacement = imageAttempt?.files.length ? imageAttempt : null;
  const replacementDiagnostics = replacementDirectory ? JSON.parse(await readFile(path.join(replacementDirectory, "diagnostics.json"), "utf8")) : [];
  const finalScenes = capture.scenes.filter((scene) => scene.label.startsWith("Advanced selected-Area") || scene.label.startsWith("Selected-Area Object Lens"));
  if (finalScenes.length !== 2 || finalScenes.some((scene) => scene.evidence.technical_id !== area || scene.evidence.selected_area !== area
      || scene.evidence.readiness.captureStrictReady !== "true" || scene.evidence.readiness.visualReady !== "true"
      || scene.evidence.upgrade?.settleResult !== "success" || !scene.evidence.map_style_loaded || scene.evidence.loading_visible)) {
    throw new Error("Final stills do not prove same-Area complete readiness");
  }
  const meshUrl = new URL("data/mesh_metrics.geojson", capture.production_url).href;
  const meshResponse = await fetch(meshUrl, { signal: AbortSignal.timeout(30_000) });
  if (!meshResponse.ok) throw new Error(`Mesh source HTTP ${meshResponse.status}`);
  const liveMesh = Buffer.from(await meshResponse.arrayBuffer());
  const localMesh = await readFile(path.resolve(scriptDirectory, "../public/data/mesh_metrics.geojson"));
  if (!liveMesh.equals(localMesh)) throw new Error("Live mesh source differs from local source");
  const properties = JSON.parse(liveMesh.toString("utf8")).features.find((feature) => String(feature.properties.mesh_code) === area)?.properties;
  if (!properties) throw new Error("Selected mesh source row absent");
  const selectedFields = Object.fromEntries(["mesh_code", "area_label", "population", "elderly_population", "nearest_public_transport_distance_m", "nearest_medical_distance_m", "exploratory_score_c", "disclosure_status"].map((key) => [key, properties[key]]));
  if (finalScenes.some((scene) => !scene.evidence.object_lens.includes(String(properties.exploratory_score_c)))) throw new Error("Rendered score differs from actual mesh source row");
  const video = encode.probe.streams.find((stream) => stream.codec_type === "video");
  const files = [];
  const finalImageFiles = capture.files.map((file) => file.filename === "01-advanced-area-analysis.png" && replacement ? replacement.files[0] : file);
  if (replacement && (replacement.files.length !== 1 || replacement.files[0].filename !== "01-advanced-area-analysis.png"
      || replacement.ui_source_commit !== capture.ui_source_commit || replacement.live_build.index_sha256 !== capture.live_build.index_sha256
      || replacement.scenes.at(-1).evidence.technical_id !== area || replacement.scenes.at(-1).evidence.readiness.captureStrictReady !== "true"
      || replacement.scenes.at(-1).evidence.readiness.visualReady !== "true" || replacement.scenes.at(-1).evidence.map_view.rendered_selected_mesh_features < 1)) throw new Error("Replacement image provenance or actual mesh readiness differs");
  for (const file of [...finalImageFiles, encode]) {
    const fileDirectory = file.filename === "01-advanced-area-analysis.png" && replacement ? replacementDirectory : sourceDirectory;
    const bytes = await readFile(path.join(fileDirectory, file.filename));
    if (hash(bytes) !== file.sha256) throw new Error(`Verified payload hash changed: ${file.filename}`);
    await writeFile(path.join(directory, file.filename), bytes, { flag: "wx" });
    files.push({ filename: file.filename, bytes: bytes.length, sha256: hash(bytes), width: file.width ?? video.width, height: file.height ?? video.height,
      ...(file.probe ? { duration_seconds: Number(encode.probe.format.duration), codec: video.codec_name, pixel_format: video.pix_fmt,
        output_fps: video.avg_frame_rate, output_frames: Number(video.nb_frames), audio_streams: 0, decode: "PASS" } : {}) });
  }
  if (files.length !== 3) throw new Error("Expected two stills and one clean video");
  const offsets = capture.recording.frames.map((frame) => frame.offset_seconds);
  const gaps = offsets.slice(1).map((offset, index) => offset - offsets[index]).sort((left, right) => left - right);
  const manifest = {
    schema_version: "citygap.judging-advanced@1", generated_at: new Date().toISOString(),
    source_branch: "feat/guided-spatial-storytelling-v1", ui_source_commit: capture.ui_source_commit, pages_run: capture.pages_run,
    guided_entry_url: capture.hydrated_guided_entry_url, advanced_url: finalScenes[0].evidence.url, selected_area: area,
    live_build: capture.live_build,
    mesh_source: { url: meshUrl, bytes: liveMesh.length, sha256: hash(liveMesh), matches_local_source: true, selected_fields: selectedFields,
      semantics: "2020 Census statistical mesh and CITY GAP analysis; transport/medical metrics are mesh-center straight-line distances, not walking-network distances. PLATEAU relationships are separate 2025 geometry context." },
    preparation: capture.prewarming, cold_load_performance_evidence: false,
    composition: capture.composition,
    recording: { method: capture.recording.method, viewport: capture.viewport, native_acquired_pixels: capture.recording.actual_capture_pixels,
      device_pixel_ratio: 1, spatial_upscale: false, motion_interpolation: false,
      started_utc: capture.recording_started_utc, finished_utc: capture.recording_finished_utc,
      duration_monotonic_seconds: capture.recording.duration_seconds, wall_elapsed_seconds: capture.recording.wall_clock_elapsed_seconds,
      acquired_frames: capture.recording.frame_count, acquired_frame_offsets_seconds: offsets,
      acquisition_cadence: capture.recording.frame_cadence,
      interframe_gap_seconds: { median: gaps[Math.floor(gaps.length / 2)], p95: gaps[Math.floor(gaps.length * 0.95)], maximum: gaps.at(-1) },
      output_frames: Number(video.nb_frames), output_fps: video.avg_frame_rate, duration_encoded_seconds: Number(encode.probe.format.duration),
      temporal_processing: encode.temporal_processing, static_hold_frame_duplication: encode.static_hold_frame_duplication,
      acquired_intervals_longer_than_two_output_frames: encode.acquired_intervals_longer_than_two_output_frames,
      advanced_click_started_seconds: capture.advanced_click_started_seconds,
      inspector_scroll_started_seconds: capture.inspector_scroll_started_seconds,
      decode: "PASS", decode_method: "Full FFmpeg decode to null succeeded before encode.json was written", renderer,
      successful_recordings: 1, recording_route: "Same previously trial-proven Windows native1080 CDP route; new isolated Chrome/profile" },
    scenes: capture.scenes,
    replacement_first_image: replacement ? { scene: replacement.scenes.at(-1), note: "Only first still was retaken once using normal mouse wheel to the existing mesh scale. Original first still, entire single video and second still are unchanged and retained." } : null,
    image_only_zoom_attempt: imageAttempt && !replacement ? { result: "NO_REPLACEMENT_CAPTURED", attempts: 1,
      reason: "No rendered selected mesh feature was reported after bounded normal mouse-wheel zoom; the attempt stopped before screenshot and was not retried. Original first still is retained.",
      final_zoom: null, final_zoom_note: "The unsuccessful attempt did not serialize its final zoom; no exact value is claimed.",
      layers_or_data_modified: false, original_video_rerecorded: false } : null,
    diagnostics: { recording: diagnostics, replacement_image: replacementDiagnostics },
    files,
    review: { self_visual_review: "REVIEWED_BY_AGENTS", decoded_frames_reviewed_seconds: [1, 6, 11], user_approval: "AWAITING_USER_REVIEW", municipal_effectiveness: "UNVERIFIED" },
    limitations: ["Supplemental clip, not a replacement for the main Guided 3D master. It shows the actual same-Area Advanced inspector and Object Lens, not global EvidenceModal values.",
      "The Advanced transition first reaches full-data/map-style readiness; strict visual readiness is a separate later gate, true for both final stills. No loading frames were hidden or removed.",
      "Output 30fps duplicates static holds from variable-rate acquired compositor frames; it is not a 30fps acquisition claim.",
      "The initial default-Area hydration avoids bare-ID missing summary fields through existing application behavior. No UI/source-data values were modified.",
      "These supplemental stills are Inspector-focused: the local basemap does not show a selected mesh outline or an analysis color surface. The approved video and both original stills were retained unchanged after the optional zoom-only attempt.",
      "The map keeps the local view generated by the Guided-to-Advanced transition; the Area identity is evidenced by live URL, Inspector and source row, not an invented selection outline." ],
  };
  await writeFile(path.join(directory, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, { flag: "wx" });
  return { directory, manifest_sha256: hash(await readFile(path.join(directory, "manifest.json"))), files };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url) && process.argv[2] === "--package") {
  process.stdout.write(`${JSON.stringify(await packageSupplement(process.argv[3], process.argv[4], process.argv[5]), null, 2)}\n`);
}
