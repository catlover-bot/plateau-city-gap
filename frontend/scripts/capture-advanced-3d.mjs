import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Run only after confirming the target UI's CI/Pages/live-build hash gate.
// The delivered caption timing revision follows the retained capture-time script;
// manifests distinguish capture-time and delivered driver hashes.
// Every interaction below uses the real production UI or mouse. No data/layer
// changes, synthetic attributes, loading removal, cleanup, or media overwrites.
const area = "533513314";
const initialArea = "533512753";
const hash = (bytes) => createHash("sha256").update(bytes).digest("hex");
const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const repository = path.basename(scriptDirectory) === "scripts" && path.basename(path.dirname(scriptDirectory)) === "frontend"
  ? path.resolve(scriptDirectory, "../..")
  : process.env.CITYGAP_CAPTURE_REPOSITORY ?? (process.platform === "win32"
    ? "\\\\wsl.localhost\\Ubuntu-24.04\\home\\mhirotaka\\workspace\\plateau-city-gap"
    : "/home/mhirotaka/workspace/plateau-city-gap");
const rootSelector = ".advanced-3d-product";
const sameId = (value, id) => value === id || value === `building:${id}`;

async function advancedEvidence(page, sceneEvidence) {
  const engine = await sceneEvidence(page);
  const ui = await page.evaluate(() => ({
    url: location.href, root: { ...document.querySelector(".advanced-3d-product")?.dataset },
    root_text: document.querySelector(".advanced-3d-product")?.textContent,
    inspector: document.querySelector(".context-inspector")?.textContent,
    target: { ...document.querySelector(".advanced-target-card")?.dataset },
    target_text: document.querySelector(".advanced-target-card")?.textContent,
    target_checks: [...document.querySelectorAll(".advanced-target-card li")].map((node) => node.textContent),
    target_check_states: [...document.querySelectorAll(".advanced-target-card li")].map((node) => ({ id: node.dataset.checkId, status: node.dataset.status })),
    section: { ...document.querySelector(".urban-section[data-ui-mode='advanced']")?.dataset },
    section_text: document.querySelector(".urban-section[data-ui-mode='advanced']")?.textContent,
    upgrade: window.__cityGapFullDataUpgrade,
    overflow_pixels: Math.max(0, document.documentElement.scrollWidth - innerWidth),
    alerts: [...document.querySelectorAll(".advanced-3d-product [role='alert'], .map-engine-fallback, .error-state")].filter((node) => { const box = node.getBoundingClientRect(); return box.width > 0 && box.height > 0; }).map((node) => node.textContent),
  }));
  return { ...ui, engine };
}

async function waitAdvanced3D(page, helpers, timeout = 45_000) {
  await page.locator(`${rootSelector}[data-area-id="${area}"] .plateau-3d-shell[data-ui-mode="advanced"][data-local-presentation="true"]`).waitFor({ timeout });
  await helpers.waitForReal3D(page, timeout);
  await page.waitForFunction(() => document.documentElement.dataset.captureStrictReady === "true"
    && document.documentElement.dataset.visualReady === "true", null, { timeout });
  const evidence = await advancedEvidence(page, helpers.sceneEvidence);
  if (evidence.root.areaId !== area || evidence.upgrade?.mode !== "full" || evidence.upgrade?.settleResult !== "success" || evidence.alerts.length) throw new Error(`Advanced local 3D scope/readiness failed: ${JSON.stringify(evidence)}`);
  const buildings = evidence.engine.tilesets.find((tileset) => tileset.url?.includes("/plateau/tileset.json"));
  if (!buildings || buildings.content_ready !== 3 || buildings.loaded_features < 296) throw new Error("Required real building contents are incomplete");
  return evidence;
}

async function selectedBuilding(page, metadata, helpers) {
  const picked = await helpers.clickFeaturedBuilding(page, metadata, { click: false });
  await page.mouse.click(picked.x, picked.y);
  await page.locator(`[data-selected-building-id="${picked.id}"]`).waitFor();
  const evidence = await waitAdvanced3D(page, helpers);
  if (!sameId(evidence.root.selectedObject, picked.id)) throw new Error("Advanced root does not identify the actually picked building");
  const visibleText = `${evidence.inspector ?? ""} ${evidence.root_text ?? ""}`;
  if (![picked.usage, String(picked.measured_height_m), String(picked.storeys_above_ground)].every((value) => visibleText.includes(value))) throw new Error("Actual picked building attributes are absent from the UI");
  return { picked, evidence };
}

async function sectionVisible(page) {
  return page.locator('.urban-section[data-ui-mode="advanced"][data-transect-ready="true"]').isVisible();
}

async function setSection(page, open, helpers) {
  if (await sectionVisible(page) !== open) await page.getByRole("button", { name: "A–B断面", exact: true }).click();
  if (open) {
    await page.locator('.urban-section[data-ui-mode="advanced"][data-transect-ready="true"][data-pack-id="maizuru-533513314-plateau-2025-v1"]').waitFor();
    await page.locator('.urban-section[data-ui-mode="advanced"] [data-section-endpoint="A"]').waitFor();
    await page.locator('.urban-section[data-ui-mode="advanced"] [data-section-endpoint="B"]').waitFor();
    await page.waitForFunction(() => document.querySelector("[data-building-source][data-local-dem]")?.dataset.sectionPlaneReady === "true");
  }
  return waitAdvanced3D(page, helpers);
}

async function exactTarget(page, id, helpers) {
  await page.locator(".advanced-target-card").waitFor();
  const evidence = await waitAdvanced3D(page, helpers);
  if (!sameId(evidence.root.selectedObject, id) || evidence.root.targetResolution !== "exact"
      || !(evidence.target_text ?? "").includes("未確認") || evidence.target_checks.length < 3) throw new Error("Same picked object's exact unconfirmed target is not visible");
  if (evidence.target.targetKey !== `building:${id}` || evidence.target.objectId !== id || evidence.target.unconfirmed !== "3"
      || evidence.target_check_states.length !== 3 || evidence.target_check_states.some((check) => !check.id || check.status !== "unconfirmed")) throw new Error("Exact target card identity/check-state contract differs from picked building");
  return evidence;
}

async function realCameraMove(page, helpers, seconds = 3) {
  const box = await page.locator(`${rootSelector} .cesium-widget canvas`).boundingBox();
  const before = await page.evaluate(() => ({ heading: window.__cityGapCesiumViewer.camera.heading, pitch: window.__cityGapCesiumViewer.camera.pitch }));
  const start = helpers.monotonicMilliseconds();
  const x = box.x + box.width * 0.58;
  const y = box.y + box.height * 0.55;
  await page.mouse.move(x, y);
  await page.mouse.down({ button: "middle" });
  try {
    for (let index = 1; index <= 90; index += 1) {
      await helpers.pause(Math.max(0, start + index * seconds * 1000 / 90 - helpers.monotonicMilliseconds()));
      await page.mouse.move(x + box.width * 0.03 * index / 90, y + box.height * 0.009 * index / 90);
    }
  } finally { await page.mouse.up({ button: "middle" }); }
  const after = await page.evaluate(() => ({ heading: window.__cityGapCesiumViewer.camera.heading, pitch: window.__cityGapCesiumViewer.camera.pitch }));
  if (Math.abs(after.heading - before.heading) + Math.abs(after.pitch - before.pitch) < 0.005) throw new Error("Actual camera drag did not change the scene");
  return { before, after, input: "real middle-mouse drag", duration_seconds: (helpers.monotonicMilliseconds() - start) / 1000 };
}

export default async function run({ browser, context, page, viewport, directory, sourceUrl, sourceCommit, pagesRun, mode, errors, helpers }) {
  const rootUrl = new URL(sourceUrl);
  const localPreview = ["advanced3d-local-preview", "advanced3d-local-section-smoke"].includes(mode);
  const permittedOrigin = localPreview ? ["localhost", "127.0.0.1", "172.25.53.120"].includes(rootUrl.hostname) : rootUrl.origin === "https://catlover-bot.github.io";
  if (!permittedOrigin || rootUrl.pathname !== "/plateau-city-gap/" || !sourceCommit || !pagesRun) throw new Error("Explicit local-preview or deployed source/UI/Pages identity required");
  rootUrl.search = "";
  const dist = path.join(repository, "frontend/dist");
  const index = await (await context.request.get(rootUrl.href, { timeout: 30_000 })).body();
  if (!localPreview && !(await readFile(path.join(dist, "index.html"))).equals(index)) throw new Error("Live production index differs from local new UI build");
  const assets = [];
  for (const name of localPreview ? [] : (await readdir(path.join(dist, "assets"))).filter((value) => /\.(js|css)$/.test(value))) {
    const bytes = await (await context.request.get(new URL(`assets/${name}`, rootUrl).href, { timeout: 30_000 })).body();
    if (!(await readFile(path.join(dist, "assets", name))).equals(bytes)) throw new Error(`Live dynamic asset differs: ${name}`);
    assets.push({ path: `assets/${name}`, bytes: bytes.length, sha256: hash(bytes), matches_local_build: true });
  }
  const metadataBytes = await (await context.request.get(new URL("data/plateau/metadata.json", rootUrl).href)).body();
  const metadata = JSON.parse(metadataBytes.toString("utf8"));
  const findUrl = new URL(`?experience=guided&story=find&mapMode=map2d&selectionType=mesh&selection=${initialArea}&mesh=${initialArea}`, rootUrl).href;
  const report = { schema_version: "citygap.advanced3d-capture@1", production_url: rootUrl.href, guided_entry_url: findUrl,
    ui_source_commit: sourceCommit, pages_run: pagesRun, local_preview: localPreview, selected_area: area, initial_area: initialArea, viewport,
    live_build: { index_sha256: hash(index), assets }, metadata_featured_building: metadata.featured_building,
    dataset: { title: metadata.official_dataset, url: metadata.official_dataset_url, verified_subset_buildings: metadata.deep_dive_buildings.records, geometry_lod: metadata.deep_dive_buildings.geometry_lod },
    capture_code: { driver_sha256: hash(await readFile(fileURLToPath(import.meta.url))), native_helper_sha256: hash(await readFile(path.join(repository, "frontend/scripts/capture-judging-3d.mjs"))) },
    plateau_metadata: { url: new URL("data/plateau/metadata.json", rootUrl).href, sha256: hash(metadataBytes), bytes: metadataBytes.length },
    prewarmed: true, prewarming: "Existing Guided, Advanced full-data loader, actual local 3D content and Section are visited before the recording. Browser cache is warm; no cold-start performance claim.",
    scenes: [], files: [], tests: {}, console_errors: [] };
  page.on("console", (message) => { if (message.type() === "error") report.console_errors.push(message.text()); });
  let start;
  let recorder;
  let recordingStopped = false;
  let sampleTimer;
  let samplePending;
  const samples = [];
  const now = () => start === undefined ? undefined : (helpers.monotonicMilliseconds() - start) / 1000;
  const scene = async (key, evidence) => report.scenes.push({ key, start_seconds: now(), evidence: evidence ?? await advancedEvidence(page, helpers.sceneEvidence) });
  const holdUntil = async (seconds) => helpers.pause(Math.max(0, start + seconds * 1000 - helpers.monotonicMilliseconds()));
  const openGuided = async () => {
    await page.goto(findUrl, { waitUntil: "domcontentloaded", timeout: 45_000 });
    await page.locator(`.guided-spatial-app[data-area-id="${initialArea}"] [data-area-row="${area}"]`).waitFor();
    await page.waitForFunction(() => document.querySelector(".analytical-map-shell")?.dataset.guidedVisualReady === "true");
  };
  const guidedPlaceAnd3D = async () => {
    await page.locator(`[data-area-row="${area}"]`).click();
    await page.locator(`.guided-spatial-app[data-area-id="${area}"] [data-area-row="${area}"][aria-pressed="true"]`).waitFor();
    if (start !== undefined) {
      await scene("guided_area_selected", await helpers.sceneEvidence(page));
      await helpers.pause(900);
    }
    await page.getByRole("button", { name: "街の形を見る", exact: true }).click();
    await page.getByRole("button", { name: "PLATEAU 3D", exact: true }).click();
    const ready = await helpers.waitForReal3D(page);
    if (ready.root.areaId !== area) throw new Error("Real Guided Area selection changed context");
    return ready;
  };
  const toAdvanced3D = async () => {
    await page.getByRole("button", { name: "詳細分析", exact: true }).click();
    await page.locator('.product-app[data-experience="advanced"] .task-navigation').waitFor({ timeout: 90_000 });
    await page.waitForFunction(() => window.__cityGapFullDataUpgrade?.mode === "full" && window.__cityGapFullDataUpgrade?.settleResult === "success");
    if (new URL(page.url()).searchParams.get("mesh") !== area) throw new Error("Actual Advanced loading transition lost parent Area");
    await page.getByRole("button", { name: "PLATEAU 3D", exact: true }).click();
    return waitAdvanced3D(page, helpers);
  };
  const screenshot = async (filename, purpose) => {
    const evidence = await waitAdvanced3D(page, helpers);
    await page.mouse.move(8, viewport.height - 8);
    const bytes = await page.screenshot({ type: "png", fullPage: false, animations: "allow", caret: "hide" });
    const pixels = { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
    if (pixels.width !== 1920 || pixels.height !== 1080) throw new Error("Screenshot is not native1080 viewport");
    await writeFile(path.join(directory, filename), bytes, { flag: "wx" });
    report.files.push({ filename, purpose, bytes: bytes.length, sha256: hash(bytes), ...pixels, evidence, composited: false, cropped: false });
  };
  const zoomNearFeatured = async (deltaY) => {
    const point = await helpers.clickFeaturedBuilding(page, metadata, { click: false });
    await page.mouse.move(point.x, point.y);
    await page.mouse.wheel(0, deltaY);
    await helpers.pause(700);
    await waitAdvanced3D(page, helpers);
  };
  const restoreWideHeight = async (height) => {
    for (let index = 0; index < 8; index += 1) {
      const current = await page.evaluate(() => window.__cityGapCesiumViewer.camera.positionCartographic.height);
      if (current >= height * 0.97) break;
      await zoomNearFeatured(40);
    }
    await waitAdvanced3D(page, helpers);
  };
  const testRestorationAndMobile = async (selectionUrl, selectedId) => {
    for (const [label, size] of [["parent_mesh_reload", { width: 1920, height: 1080 }], ["mobile390", { width: 390, height: 844 }]]) {
      const testContext = await browser.newContext({ viewport: size, screen: size, deviceScaleFactor: 1, locale: "ja-JP", serviceWorkers: "block" });
      const testPage = await testContext.newPage();
      const diagnostics = [];
      testPage.on("pageerror", (error) => diagnostics.push({ kind: "page", message: error.message }));
      testPage.on("requestfailed", (request) => { if (request.failure()?.errorText !== "net::ERR_ABORTED") diagnostics.push({ kind: "request", url: request.url(), message: request.failure()?.errorText }); });
      testPage.on("response", (response) => { if (response.status() >= 400) diagnostics.push({ kind: "http", url: response.url(), status: response.status() }); });
      testPage.on("console", (message) => { if (message.type() === "error") diagnostics.push({ kind: "console", message: message.text() }); });
      try {
        await testPage.goto(selectionUrl, { waitUntil: "domcontentloaded", timeout: 45_000 });
        let evidence = await waitAdvanced3D(testPage, helpers);
        if (label === "parent_mesh_reload") { await testPage.reload({ waitUntil: "domcontentloaded" }); evidence = await waitAdvanced3D(testPage, helpers); }
        if (!sameId(evidence.root.selectedObject, selectedId) || evidence.root.areaId !== area || evidence.overflow_pixels > 1 || diagnostics.length) throw new Error(`${label} selected object/parent mesh/layout/error check failed: ${JSON.stringify({ evidence, diagnostics })}`);
        report.tests[label] = { pass: true, viewport: size, evidence, diagnostics };
      } finally { await testContext.close(); }
    }
  };
  try {
    await openGuided();
    await guidedPlaceAnd3D();
    await toAdvanced3D();
    await setSection(page, true, helpers);
    await setSection(page, false, helpers);
    report.prewarm_ready = await advancedEvidence(page, helpers.sceneEvidence);
    if (mode === "advanced3d-local-section-smoke") {
      const selected = await selectedBuilding(page, metadata, helpers);
      report.tests.actual_pick = selected;
      report.tests.section = await setSection(page, true, helpers);
      await screenshot("local-advanced3d-section.png", "Local final-CSS non-final Section layout");
      await testRestorationAndMobile(page.url(), selected.picked.id);
      if (errors.length || report.console_errors.length) throw new Error(`Unexpected local diagnostics: ${JSON.stringify({ errors, console: report.console_errors })}`);
      return;
    }
    if (localPreview) {
      const selected = await selectedBuilding(page, metadata, helpers);
      report.tests.actual_pick = selected;
      await screenshot("local-advanced3d-hero.png", "Local non-final Advanced3D layout and actual selected attributes");
      report.tests.section = await setSection(page, true, helpers);
      await screenshot("local-advanced3d-section.png", "Local non-final Advanced3D with same A–B Section");
      await setSection(page, false, helpers);
      report.tests.exact_target = await exactTarget(page, selected.picked.id, helpers);
      await page.locator(".advanced-target-card").scrollIntoViewIfNeeded();
      await screenshot("local-advanced3d-target.png", "Local non-final same exact building target and unconfirmed checks");
      return;
    }
    if (mode === "advanced3d-test") {
      const selected = await selectedBuilding(page, metadata, helpers);
      report.tests.actual_pick = selected;
      report.tests.section = await setSection(page, true, helpers);
      report.tests.exact_target = await exactTarget(page, selected.picked.id, helpers);
      await testRestorationAndMobile(page.url(), selected.picked.id);
      return;
    }
    if (mode !== "advanced3d-master") throw new Error(`Unsupported mode ${mode}`);
    await openGuided();
    recorder = await helpers.createNativeScreencast({ page, context, directory, viewport });
    report.recording_started_utc = new Date().toISOString();
    start = await recorder.start();
    await scene("guided_area", await helpers.sceneEvidence(page));
    const sample = () => {
      if (samplePending) return;
      samplePending = page.evaluate(() => {
        const viewer = window.__cityGapCesiumViewer;
        const canvas = viewer?.scene.canvas.getBoundingClientRect();
        const data = document.querySelector("[data-building-source][data-local-dem]")?.dataset;
        let selectedFeatures = 0;
        let demTiles = 0;
        for (let index = 0; index < (viewer?.scene.primitives.length ?? 0); index += 1) {
          const item = viewer.scene.primitives.get(index);
          if (!item.show || !item.statistics || !item.root) continue;
          if ((item._url ?? "").includes("plateau-terrain")) demTiles += item._selectedTiles?.length ?? 0;
          else selectedFeatures += item.statistics.numberOfFeaturesSelected ?? 0;
        }
        return { real_3d_visible: Boolean(canvas?.width > 100 && canvas?.height > 100 && selectedFeatures > 0 && demTiles > 0 && data?.roadsReady === "true"), selected_features: selectedFeatures, selected_dem_tiles: demTiles, area: document.querySelector(".advanced-3d-product, .guided-spatial-app")?.dataset.areaId };
      }).then((value) => samples.push({ at_seconds: now(), ...value })).catch((error) => report.console_errors.push(`sampling: ${error.message}`)).finally(() => { samplePending = null; });
    };
    sample();
    sampleTimer = setInterval(sample, 250);
    await holdUntil(0.8);
    const guidedReady = await guidedPlaceAnd3D();
    await scene("guided_3d", guidedReady);
    await holdUntil(6);
    await page.getByRole("button", { name: "街の断面", exact: true }).click();
    await page.locator('.guided-map-stage[data-section-expanded="true"] .urban-section').waitFor();
    await scene("guided_section", await helpers.sceneEvidence(page));
    await holdUntil(9);
    await page.getByRole("button", { name: "街の断面", exact: true }).click();
    await scene("advanced_click", await helpers.sceneEvidence(page));
    await toAdvanced3D();
    await scene("advanced_3d");
    await holdUntil(14);
    report.camera_motion_start_seconds = now();
    report.camera_motion = await realCameraMove(page, helpers);
    report.camera_motion_end_seconds = now();
    await helpers.waitForReal3D(page);
    const selected = await selectedBuilding(page, metadata, helpers);
    report.picked_building = selected.picked;
    await scene("building_selected", selected.evidence);
    await holdUntil(25);
    await scene("advanced_section", await setSection(page, true, helpers));
    await holdUntil(32);
    await setSection(page, false, helpers);
    await zoomNearFeatured(-120);
    await scene("exact_target", await exactTarget(page, selected.picked.id, helpers));
    await holdUntil(40);
    clearInterval(sampleTimer);
    if (samplePending) await samplePending;
    recordingStopped = true;
    report.recording = await recorder.stop();
    report.recording_finished_utc = new Date().toISOString();
    report.recording.visibility_samples = samples;
    report.recording.visibility_measurement = "250ms sampled visible Cesium canvas, selected actual building features, selected local DEM tile and ready roads; not continuous pixel classification";
    report.recording.measured_real_3d_seconds = samples.reduce((total, value, index) => total + (value.real_3d_visible ? Math.max(0, Math.min(report.recording.duration_seconds, samples[index + 1]?.at_seconds ?? report.recording.duration_seconds) - value.at_seconds) : 0), 0);
    report.recording.real_3d_visible_fraction = report.recording.measured_real_3d_seconds / report.recording.duration_seconds;
    if (report.recording.duration_seconds < 20 || report.recording.duration_seconds > 45) throw new Error("Master duration outside20–45s; preserve acquired record and stop");
    if (report.recording.real_3d_visible_fraction < 0.6) throw new Error("Measured real3D sample fraction is below60%; preserve master and stop");

    // All stills occur after recording; no screenshot work during camera motion.
    await page.getByRole("button", { name: "選択を解除", exact: true }).click();
    await waitAdvanced3D(page, helpers);
    const overviewHeight = report.prewarm_ready.engine.camera.height;
    await restoreWideHeight(overviewHeight);
    await screenshot("04-guided-to-advanced.png", "Actual same-Area Advanced3D connection header after Guided handoff");
    // The recorded master is already stopped. Reload the actual same-Area URL
    // to the demonstrated default camera; do not repeat the earlier -80 image
    // zoom that could not satisfy the unchanged strict visible-content gate.
    await page.reload({ waitUntil: "domcontentloaded", timeout: 45_000 });
    await waitAdvanced3D(page, helpers);
    if ((await advancedEvidence(page, helpers.sceneEvidence)).root.selectedObject) throw new Error("Hero must remain an unselected same-Area overview");
    await screenshot("01-advanced-3d-hero.png", "Unselected Advanced3D same-Area overview at its actual default ready camera after same-URL reload; Section closed");
    await selectedBuilding(page, metadata, helpers);
    await setSection(page, true, helpers);
    await screenshot("02-advanced-3d-section.png", "Same selected object and A–B Section with actual3D");
    await setSection(page, false, helpers);
    await zoomNearFeatured(-20);
    await exactTarget(page, selected.picked.id, helpers);
    await screenshot("03-advanced-3d-exact-target.png", "Actual3D and the same picked building's exact unconfirmed field target");
    await testRestorationAndMobile(page.url(), selected.picked.id);
    if (errors.length || report.console_errors.length) throw new Error(`Unexpected diagnostics: ${JSON.stringify({ errors, console: report.console_errors })}`);
  } finally {
    if (sampleTimer) clearInterval(sampleTimer);
    if (samplePending) await samplePending;
    if (recorder && !recordingStopped) report.failed_recording = await recorder.stop();
    report.diagnostics = errors;
    await writeFile(path.join(directory, "advanced3d-capture.json"), `${JSON.stringify(report, null, 2)}\n`, { flag: "wx" });
  }
}

async function captionSameMaster(sourceDirectory, outputDirectory) {
  if (process.platform === "win32") throw new Error("Run offline caption derivation using WSL Node and WSL paths");
  await mkdir(outputDirectory, { recursive: false });
  const capture = JSON.parse(await readFile(path.join(sourceDirectory, "advanced3d-capture.json"), "utf8"));
  const encode = JSON.parse(await readFile(path.join(sourceDirectory, "encode.json"), "utf8"));
  const cleanPath = path.join(sourceDirectory, encode.filename);
  if (hash(await readFile(cleanPath)) !== encode.sha256) throw new Error("Clean master differs from verified encode");
  const duration = Number(encode.probe.format.duration);
  const captionPosition = { x: Number(process.env.CITYGAP_CAPTION_X ?? 740), y: Number(process.env.CITYGAP_CAPTION_Y ?? 266) };
  if (!Number.isFinite(captionPosition.x) || !Number.isFinite(captionPosition.y) || captionPosition.x < 0 || captionPosition.x > 1920 || captionPosition.y < 0 || captionPosition.y > 1080) throw new Error("Caption position must be within native viewport");
  const timings = [
    ["guided_area", "地域を選び、街の形を確かめる"],
    ["guided_3d", "同じ範囲の建物・道路・地形をたどる"],
    ["guided_section", "同じA–B断面で、街を横から見る"],
    ["advanced_click", "選んだ地域のまま、詳細分析へ"],
    ["advanced_3d", "Advanced 3Dで、確かめる対象を選ぶ"],
    ["building_selected", "一つの建物の高さ・用途を確認"],
    ["advanced_section", "同じA–B線で、地形との関係を見る"],
    ["exact_target", "未確認の点を、現地で確かめる場所へ"],
  ].map(([key, text]) => ({ start: capture.scenes.find((scene) => scene.key === key)?.start_seconds, text }));
  if (timings.some((cue, index) => !Number.isFinite(cue.start) || (index > 0 && cue.start <= timings[index - 1].start))) throw new Error("Caption cues require actual increasing recorded scene times");
  const cues = timings.map((cue, index) => ({ ...cue, end: timings[index + 1]?.start ?? duration }));
  const stamp = (seconds, ass = false) => ass ? `0:${String(Math.floor(seconds / 60)).padStart(2, "0")}:${(seconds % 60).toFixed(2).padStart(5, "0")}` : `00:${String(Math.floor(seconds / 60)).padStart(2, "0")}:${(seconds % 60).toFixed(3).padStart(6, "0")}`;
  await writeFile(path.join(outputDirectory, "captions.vtt"), `WEBVTT\n\n${cues.map((cue) => `${stamp(cue.start)} --> ${stamp(cue.end)}\n${cue.text}\n`).join("\n")}`, { flag: "wx" });
  const assPath = path.join(outputDirectory, "captions.ass");
  if (assPath.includes("'")) throw new Error("Subtitle path cannot contain apostrophes");
  const ass = `[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Default,Noto Sans CJK JP,30,&H00FFFFFF,&H00FFFFFF,&H20292F2D,&H20292F2D,0,0,0,0,100,100,0,0,3,6,0,8,36,36,12,1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n${cues.map((cue) => `Dialogue: 0,${stamp(cue.start, true)},${stamp(cue.end, true)},Default,,0,0,0,,{\\pos(${captionPosition.x},${captionPosition.y})}${cue.text}`).join("\n")}\n`;
  await writeFile(assPath, ass, { flag: "wx" });
  const outputPath = path.join(outputDirectory, "city-gap-advanced-3d-captioned.mp4");
  execFileSync("ffmpeg", ["-n", "-hide_banner", "-loglevel", "error", "-i", cleanPath, "-vf", `ass=filename='${assPath}'`, "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", outputPath], { timeout: 180_000 });
  execFileSync("ffmpeg", ["-v", "error", "-i", outputPath, "-f", "null", "-"], { timeout: 180_000 });
  const probe = JSON.parse(execFileSync("ffprobe", ["-v", "error", "-show_streams", "-show_format", "-of", "json", outputPath], { encoding: "utf8" }));
  const video = probe.streams.find((stream) => stream.codec_type === "video");
  const originalVideo = encode.probe.streams.find((stream) => stream.codec_type === "video");
  if (video.width !== 1920 || video.height !== 1080 || video.avg_frame_rate !== "30/1" || video.nb_frames !== originalVideo.nb_frames || probe.streams.some((stream) => stream.codec_type === "audio")) throw new Error("Caption derivative changed original native master contract");
  const evidence = { filename: path.basename(outputPath), sha256: hash(await readFile(outputPath)), derived_from_sha256: encode.sha256, separately_recorded: false, cues, probe, decode: "PASS", caption_placement: { ...captionPosition, font_size: 30, treatment: "Dark box over map; final native frames require visual review for actual overlap" } };
  await writeFile(path.join(outputDirectory, "captioned.json"), `${JSON.stringify(evidence, null, 2)}\n`, { flag: "wx" });
  return evidence;
}

async function packageVerifiedAssets(sourceDirectory, captionDirectory, outputDirectory) {
  if (process.platform === "win32") throw new Error("Use WSL Node and WSL paths for offline decode/package verification");
  const repoRoot = repository;
  outputDirectory = path.resolve(outputDirectory);
  const relative = path.relative(repoRoot, outputDirectory);
  if (!relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative)) throw new Error("Final package must remain outside the repository");
  await mkdir(outputDirectory, { recursive: false });
  const json = async (directory, filename) => JSON.parse(await readFile(path.join(directory, filename), "utf8"));
  const [capture, clean, captioned, renderer] = await Promise.all([
    json(sourceDirectory, "advanced3d-capture.json"), json(sourceDirectory, "encode.json"), json(captionDirectory, "captioned.json"), json(sourceDirectory, "renderer.json"),
  ]);
  if (capture.local_preview || !capture.recording || capture.failed_recording || !capture.ui_source_commit || !capture.pages_run) throw new Error("Only completed declared production captures may be packaged");
  if (capture.tests.parent_mesh_reload?.pass !== true || capture.tests.mobile390?.pass !== true || capture.diagnostics.length || capture.console_errors.length) throw new Error("Required final capture tests/diagnostics did not pass");
  if (captioned.derived_from_sha256 !== clean.sha256 || captioned.separately_recorded !== false) throw new Error("Caption derivative is not from this unchanged clean master");
  const expected = ["01-advanced-3d-hero.png", "02-advanced-3d-section.png", "03-advanced-3d-exact-target.png", "04-guided-to-advanced.png"];
  if (capture.files.length !== 4 || expected.some((name) => !capture.files.some((file) => file.filename === name))) throw new Error("Expected exactly the four approved-composition native PNGs");
  if (capture.files.some((file) => file.evidence.root.areaId !== area || file.evidence.engine.readiness.captureStrictReady !== "true"
      || file.evidence.engine.readiness.localDemReady !== "true" || file.evidence.engine.readiness.roadsReady !== "true")) throw new Error("Final image same-Area real3D readiness evidence differs");
  const files = [];
  for (const name of expected) {
    const record = capture.files.find((file) => file.filename === name);
    const bytes = await readFile(path.join(sourceDirectory, name));
    if (hash(bytes) !== record.sha256 || bytes.readUInt32BE(16) !== 1920 || bytes.readUInt32BE(20) !== 1080) throw new Error(`PNG changed or lost native dimensions: ${name}`);
    await writeFile(path.join(outputDirectory, name), bytes, { flag: "wx" });
    files.push({ filename: name, bytes: bytes.length, sha256: hash(bytes), width: 1920, height: 1080, purpose: record.purpose });
  }
  for (const [directory, record, expectedName] of [[sourceDirectory, clean, "city-gap-advanced-3d-clean.mp4"], [captionDirectory, captioned, "city-gap-advanced-3d-captioned.mp4"]]) {
    if (record.filename !== expectedName) throw new Error("Video filename differs from intended new package");
    const source = path.join(directory, record.filename);
    const bytes = await readFile(source);
    if (hash(bytes) !== record.sha256) throw new Error(`Video changed after verification: ${record.filename}`);
    execFileSync("ffmpeg", ["-v", "error", "-i", source, "-f", "null", "-"], { timeout: 180_000 });
    const probe = JSON.parse(execFileSync("ffprobe", ["-v", "error", "-show_streams", "-show_format", "-of", "json", source], { encoding: "utf8" }));
    const video = probe.streams.find((stream) => stream.codec_type === "video");
    if (video.width !== 1920 || video.height !== 1080 || video.codec_name !== "h264" || video.pix_fmt !== "yuv420p" || video.avg_frame_rate !== "30/1"
        || Number(probe.format.duration) < 20 || Number(probe.format.duration) > 45 || probe.streams.some((stream) => stream.codec_type === "audio")) throw new Error("Video native format/duration contract failed");
    await writeFile(path.join(outputDirectory, record.filename), bytes, { flag: "wx" });
    files.push({ filename: record.filename, bytes: bytes.length, sha256: hash(bytes), width: video.width, height: video.height,
      codec: video.codec_name, pixel_format: video.pix_fmt, output_fps: video.avg_frame_rate, output_frames: Number(video.nb_frames),
      duration_seconds: Number(probe.format.duration), audio_streams: 0, full_decode: "PASS" });
  }
  const vtt = await readFile(path.join(captionDirectory, "captions.vtt"));
  await writeFile(path.join(outputDirectory, "captions.vtt"), vtt, { flag: "wx" });
  files.push({ filename: "captions.vtt", bytes: vtt.length, sha256: hash(vtt), cues: captioned.cues.length });
  const record = capture.recording;
  const motionStart = capture.camera_motion_start_seconds;
  const motionEnd = capture.camera_motion_end_seconds;
  const motionFrames = record.frames.filter((frame) => frame.offset_seconds >= motionStart && frame.offset_seconds <= motionEnd);
  const motionTimes = [motionStart, ...motionFrames.map((frame) => frame.offset_seconds), motionEnd];
  const sourceBuildings = capture.prewarm_ready.engine.tilesets.find((tileset) => tileset.url?.includes("/plateau/tileset.json"));
  const guidedSource = capture.scenes.find((scene) => scene.key === "guided_3d").evidence.root;
  const scope = { verified_3d_subset_buildings: capture.dataset.verified_subset_buildings, source_tile_catalog_records: sourceBuildings.loaded_features,
    source_building_contents: sourceBuildings.content_ready, area_building_intersections: Number(guidedSource.contextBuildings), area_road_intersections: Number(guidedSource.contextRoads) };
  if (Object.values(scope).some((value) => !Number.isFinite(value))) throw new Error("Source scope evidence is non-finite");
  const imageStates = capture.files.map(({ filename, evidence }) => ({ filename, evidence }));
  const manifest = {
    schema_version: "citygap.judging-advanced-3d@1", generated_at: new Date().toISOString(),
    source_branch: "feat/guided-spatial-storytelling-v1", captured_ui_source_commit: capture.ui_source_commit, pages_run: capture.pages_run,
    final_documentation_asset_commit: null, final_documentation_asset_commit_note: "Assigned only by the later real Git commit; this capture manifest does not invent a future final HEAD.",
    production_url: capture.production_url, actual_guided_entry_url: capture.guided_entry_url,
    actual_advanced_urls: [...new Set(imageStates.map((item) => item.evidence.url))],
    selected_area: area, initial_area_before_real_recorded_selection: capture.initial_area, dataset: capture.dataset, plateau_metadata: capture.plateau_metadata, scope,
    scope_note: "Verified subset catalog, broader source-tile records, and separate2D Area-intersection counts are distinct; none is a simultaneous-visible-building claim.",
    live_build: capture.live_build, capture_code: capture.capture_code,
    capture: { native_acquired_pixels: record.actual_capture_pixels, viewport: capture.viewport, device_pixel_ratio: 1, spatial_upscale: false,
      method: record.method, frame_cadence: record.frame_cadence, acquired_frames: record.frame_count,
      monotonic_duration_seconds: record.duration_seconds, wall_elapsed_seconds: record.wall_clock_elapsed_seconds,
      started_utc: capture.recording_started_utc, finished_utc: capture.recording_finished_utc,
      frame_offsets_seconds: record.frames.map((frame) => frame.offset_seconds),
      motion_cadence: { observation_start_seconds: motionStart, observation_end_seconds: motionEnd, acquired_frames: motionFrames.length,
        observation_duration_seconds: motionEnd - motionStart, mean_acquired_fps: motionFrames.length / (motionEnd - motionStart),
        maximum_gap_seconds: Math.max(...motionTimes.slice(1).map((value, index) => value - motionTimes[index])) },
      sampled_real_3d_fraction: record.real_3d_visible_fraction, sampled_real_3d_seconds: record.measured_real_3d_seconds,
      sampling_method: record.visibility_measurement, visibility_samples: record.visibility_samples,
      temporal_processing: clean.temporal_processing, output_fps: "30/1", static_hold_frame_duplication: clean.static_hold_frame_duplication,
      acquired_intervals_longer_than_two_output_frames: clean.acquired_intervals_longer_than_two_output_frames,
      prewarmed: true, prewarming: capture.prewarming, cold_load_performance_evidence: false, renderer,
      successful_clean_recordings: 1, browser_chrome: false, audio: false },
    picked_building: capture.picked_building,
    actual_scene_timeline: capture.scenes,
    images: imageStates,
    caption_derivation: { source_clean_sha256: clean.sha256, separately_recorded: false, cues: captioned.cues, placement: captioned.caption_placement },
    tests: capture.tests,
    diagnostics: { browser: capture.diagnostics, console: capture.console_errors },
    files,
    review: { self_visual_review: "READY_FOR_AGENT_REVIEW", user_approval: "AWAITING_USER_REVIEW", municipal_workflow_effectiveness: "UNVERIFIED" },
    limitations: ["PLATEAU LOD1 shape/use/height and local DEM are real source geometry; they do not verify current occupancy, entrances, steps, walking access or danger. Exact target checks remain unconfirmed.",
      "200 people aged65+ and distances are500m statistical/context values, not occupants of the selected building. Source years and distance semantics remain visible in the actual UI.",
      "Local verified-pack readiness does not wait for every optional global basemap tile; background refinement can continue.",
      "Variable acquired compositor frames are normalized to30fps by held-frame duplication/surplus-frame dropping, without spatial upscale or generated motion interpolation.",
      "Image04 is one actual Advanced UI state evidencing the same-Area handoff, not a fabricated split-view composite. Older completed demo/media packages remain unchanged." ],
  };
  await writeFile(path.join(outputDirectory, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, { flag: "wx" });
  return { directory: outputDirectory, payload_files: files.length, manifest_sha256: hash(await readFile(path.join(outputDirectory, "manifest.json"))), files };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url) && process.argv[2] === "--caption") {
  process.stdout.write(`${JSON.stringify(await captionSameMaster(process.argv[3], process.argv[4]), null, 2)}\n`);
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url) && process.argv[2] === "--package") {
  process.stdout.write(`${JSON.stringify(await packageVerifiedAssets(process.argv[3], process.argv[4], process.argv[5]), null, 2)}\n`);
}
