import { createHash } from "node:crypto";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { chromium } from "playwright-core";

const parameters = new Map();
for (let index = 2; index < process.argv.length; index += 2) parameters.set(process.argv[index], process.argv[index + 1]);
const baseUrl = parameters.get("--url") ?? "http://127.0.0.1:4173/plateau-city-gap/";
const outputDirectory = path.resolve(process.cwd(), parameters.get("--output") ?? "../docs/assets/current");
const diagnosticDirectory = path.resolve(process.cwd(), parameters.get("--diagnostics") ?? "../analysis/outputs/real/visual-readiness-failures");
const only = parameters.get("--only") ?? null;
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
  ?? chromium.executablePath();

const deepDive = "533513314";
const featuredBuilding = "bldg_a490fb5b-d668-441e-b9af-5b35c4629006";
const featuredRoad = "tran_3dbd690e-39ee-4c61-b3d9-9419620b06fc-0";
const scenes = [
  { id: "01-city-discovery", title: "City discovery", width: 1440, height: 900, route: "?city=maizuru&scene=city_overview&resolution=city&inspector=open", mode: "map2d" },
  { id: "02-500m-finding", title: "500m finding", width: 1440, height: 900, route: "?city=maizuru&scene=gap_discovery&mesh=533512753&resolution=mesh&inspector=open", mode: "map2d" },
  { id: "03-resolution-lift", title: "PLATEAU Resolution Lift", width: 1440, height: 900, route: `?city=maizuru&scene=plateau_detail&mesh=${deepDive}&resolution=building_group&lens=urban-xray&mapMode=plateau3d&buildingSource=verified-local&inspector=open`, mode: "plateau3d", requireLocalDem: true, requireBuildings: true, requireRoads: true, requireXray: true },
  { id: "04-building-xray", title: "PLATEAU building X-Ray", width: 1440, height: 900, route: `?city=maizuru&scene=plateau_detail&building=${featuredBuilding}&resolution=building&lens=urban-xray&mapMode=plateau3d&buildingSource=verified-local&inspector=open`, mode: "plateau3d", requireLocalDem: true, requireBuildings: true, requireRoads: true, requireXray: true, requireObject: "building" },
  { id: "05-road-terrain", title: "Road and terrain investigation", width: 1440, height: 900, route: `?city=maizuru&scene=plateau_detail&road=${featuredRoad}&lng=135.3964126&lat=35.4477785&resolution=road&lens=none&mapMode=plateau3d&buildingSource=verified-local&inspector=open`, mode: "plateau3d", requireLocalDem: true, requireBuildings: true, requireRoads: true, requireObject: "road" },
  { id: "06-service-pulse", title: "Service Pulse", width: 1440, height: 900, route: `?city=maizuru&scene=network_access&mesh=${deepDive}&resolution=road&lens=service-pulse&twin=baseline&mapMode=plateau3d&inspector=open`, mode: "plateau3d", requireBuildings: true, requireRoads: true, requirePulse: true },
  { id: "07-counterfactual-twin", title: "Counterfactual Twin", width: 1440, height: 900, route: `?city=maizuru&task=try&scene=scenario_compare&mesh=${deepDive}&resolution=site&lens=changed-only&twin=scenario&mapMode=plateau3d&inspector=open`, mode: "plateau3d", requireBuildings: true, requireRoads: true, requireTwin: true },
  { id: "08-temporal-plateau-ghost", title: "Temporal PLATEAU Ghost", width: 1440, height: 900, route: "?city=fujisawa&task=validate&scene=temporal_change&resolution=building&lens=temporal-ghost&mapMode=map2d&inspector=open", mode: "map2d", requireGhost: true },
  { id: "09-investigation-evidence", title: "Investigation and evidence", width: 1440, height: 900, route: `?city=maizuru&scene=plateau_detail&building=${featuredBuilding}&resolution=building&lens=urban-xray&mapMode=plateau3d&buildingSource=verified-local&inspector=open`, mode: "plateau3d", requireLocalDem: true, requireBuildings: true, requireRoads: true, requireObjectLens: true },
  { id: "10-mobile", title: "Mobile investigation", width: 390, height: 844, route: "?city=maizuru&scene=gap_discovery&mesh=533512753&resolution=mesh&inspector=open", mode: "map2d", mobile: true },
].filter((scene) => !only || scene.id === only || scene.id.includes(only));

if (scenes.length === 0) throw new Error(`Unknown scene: ${only}`);
const commit = execFileSync("git", ["rev-parse", "HEAD"], { cwd: path.resolve(process.cwd(), ".."), encoding: "utf8" }).trim();
const browser = await chromium.launch({ executablePath, headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist", "--use-gl=swiftshader"] });
const captures = [];
let failed = false;

await mkdir(diagnosticDirectory, { recursive: true });
await mkdir(outputDirectory, { recursive: true });
if (!only) {
  await rm(outputDirectory, { recursive: true, force: true });
  await mkdir(outputDirectory, { recursive: true });
}

for (const specification of scenes) {
  const captureStartedAt = Date.now();
  const page = await browser.newPage({ viewport: { width: specification.width, height: specification.height }, deviceScaleFactor: 1, reducedMotion: "reduce" });
  const consoleErrors = [];
  const requestFailures = [];
  const responses = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      const entry = { text: message.text(), location: message.location(), arguments: [] };
      consoleErrors.push(entry);
      void Promise.all(message.args().map((argument) => argument.jsonValue().catch(() => "[unserializable]"))).then((values) => { entry.arguments = values; });
    }
  });
  page.on("pageerror", (error) => consoleErrors.push({ text: error.message, location: null }));
  page.on("requestfailed", (request) => requestFailures.push({ url: request.url(), failure: request.failure()?.errorText ?? "unknown" }));
  page.on("response", (response) => { if (response.status() >= 400) responses.push({ url: response.url(), status: response.status() }); });
  const route = `${baseUrl}${specification.route}`;
  try {
    await page.goto(route, { waitUntil: "domcontentloaded", timeout: 90_000 });
    await page.waitForSelector(".product-app", { timeout: 90_000 });
    const readinessTimeout = specification.mode === "plateau3d" && !specification.route.includes("buildingSource=verified-local") ? 240_000 : 120_000;
    await page.waitForFunction(() => document.documentElement.dataset.visualReady === "true", null, { timeout: readinessTimeout });
    if (specification.requireObjectLens) await page.locator(".object-lens").scrollIntoViewIfNeeded();
    const readiness = await page.evaluate((scene) => {
      const cesium = document.querySelector(".cesium-map");
      const map2d = document.querySelector(".analytical-map-shell");
      const viewer = window.__cityGapCesiumViewer;
      const camera = viewer ? {
        longitude: viewer.camera.positionCartographic.longitude * 180 / Math.PI,
        latitude: viewer.camera.positionCartographic.latitude * 180 / Math.PI,
        height: viewer.camera.positionCartographic.height,
        heading: viewer.camera.heading * 180 / Math.PI,
        pitch: viewer.camera.pitch * 180 / Math.PI,
      } : null;
      const visibleTemporal = viewer ? 0 : (() => {
        const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
        return map?.getLayer("temporal-point") && map.getLayoutProperty("temporal-point", "visibility") !== "none" ? 1 : 0;
      })();
      const actual = {
        rootReady: document.documentElement.dataset.visualReady === "true",
        visualUnmet: document.documentElement.dataset.visualUnmet ?? "",
        camera,
        terrainSource: cesium?.dataset.terrainSource ?? "none",
        terrainReady: scene.mode === "map2d" ? true : cesium?.dataset.terrainReady === "true",
        terrainTileCount: Number(cesium?.dataset.terrainTileCount ?? 0),
        localDemReady: cesium?.dataset.localDemReady === "true",
        buildingSource: cesium?.dataset.buildingSource ?? "none",
        buildingReady: scene.mode === "map2d" ? true : cesium?.dataset.buildingFeatureCount !== "0" && Boolean(cesium?.dataset.buildingFeatureCount),
        buildingFeatureCount: Number(cesium?.dataset.buildingFeatureCount ?? 0),
        roadsReady: scene.mode === "map2d" ? true : cesium?.dataset.roadsReady === "true",
        imageryReady: scene.mode === "map2d" ? map2d?.dataset.visualReady === "true" : cesium?.dataset.visualReady === "true",
        analysisReady: scene.mode === "map2d" ? map2d?.dataset.visualReady === "true" : cesium?.dataset.analysis === "ready",
        overlayReady: scene.mode === "map2d" ? true : cesium?.dataset.overlay === "ready",
        fontReady: document.fonts.status === "loaded",
        cameraSettled: scene.mode === "map2d" ? true : cesium?.dataset.cameraSettled === "true",
        canvasSizeReady: scene.mode === "map2d" ? true : cesium?.dataset.canvasSizeReady === "true",
        canvasCssSize: cesium?.dataset.canvasCssSize ?? null,
        drawingBufferSize: cesium?.dataset.drawingBufferSize ?? null,
        stableFrames: Number(cesium?.dataset.stableFrames ?? map2d?.dataset.stableFrames ?? 0),
        outstandingCriticalRequests: Number(cesium?.dataset.criticalRequests ?? 0),
        optionalGlobeRequests: Number(cesium?.dataset.optionalGlobeRequests ?? 0),
        optionalBuildingRequests: Number(cesium?.dataset.optionalBuildingRequests ?? 0),
        pulseMarkers: Number(cesium?.dataset.pulseMarkers ?? 0),
        pulseSemantics: cesium?.dataset.pulseSemantics ?? "",
        lens: cesium?.dataset.analysisLens ?? document.querySelector(".analysis-lens-rail")?.dataset.lens ?? "none",
        selectionType: new URLSearchParams(location.search).get("selectionType") ?? (new URLSearchParams(location.search).has("building") ? "building" : new URLSearchParams(location.search).has("road") ? "road" : new URLSearchParams(location.search).has("mesh") ? "mesh" : "none"),
        objectLensVisible: Boolean(document.querySelector(".object-lens")),
        temporalVisible: visibleTemporal,
        counterfactual: new URLSearchParams(location.search).get("twin") ?? "baseline",
      };
      const checks = [actual.rootReady, actual.fontReady, actual.stableFrames >= 3];
      if (scene.mode === "plateau3d") checks.push(actual.terrainReady, actual.terrainTileCount > 0, actual.cameraSettled, actual.canvasSizeReady, actual.imageryReady, actual.analysisReady, actual.overlayReady, actual.outstandingCriticalRequests === 0);
      if (scene.requireLocalDem) checks.push(actual.localDemReady);
      if (scene.requireBuildings) checks.push(actual.buildingReady, actual.buildingFeatureCount > 0);
      if (scene.requireRoads) checks.push(actual.roadsReady);
      if (scene.requirePulse) checks.push(actual.pulseMarkers > 0, actual.pulseSemantics === "network-distance-only");
      if (scene.requireXray) checks.push(actual.lens === "urban-xray");
      if (scene.requireTwin) checks.push(actual.lens === "changed-only", actual.counterfactual === "scenario");
      if (scene.requireGhost) checks.push(actual.temporalVisible > 0);
      if (scene.requireObjectLens) checks.push(actual.objectLensVisible);
      if (scene.requireObject) checks.push(actual.selectionType === scene.requireObject);
      return { actual, complete: checks.every(Boolean), checks };
    }, specification);
    const optionalLodCancellations = requestFailures.filter((item) => item.failure.includes("ERR_ABORTED") && item.url.endsWith(".b3dm"));
    const optionalBasemapCancellations = requestFailures.filter((item) => item.failure.includes("ERR_ABORTED") && item.url.includes("cyberjapandata.gsi.go.jp/xyz/"));
    const optionalRequestCancellations = [...optionalLodCancellations, ...optionalBasemapCancellations];
    const criticalRequestFailures = [...requestFailures.filter((item) => !optionalRequestCancellations.includes(item)), ...responses]
      .filter((item) => item.url.startsWith(baseUrl) || item.url.includes("cyberjapandata.gsi.go.jp"));
    if (!readiness.complete || criticalRequestFailures.length || consoleErrors.length) {
      throw new Error(`Visual readiness incomplete: ${JSON.stringify({ readiness, criticalRequestFailures, consoleErrors })}`);
    }
    const target = path.join(outputDirectory, `${specification.id}.png`);
    await page.screenshot({ path: target, fullPage: false, animations: "disabled", timeout: 90_000 });
    const runtimeMetrics = await page.evaluate(() => {
      const resources = performance.getEntriesByType("resource");
      const memory = performance.memory;
      return {
        ready_ms: Date.now() - performance.timeOrigin,
        resource_count: resources.length,
        transfer_bytes: resources.reduce((sum, entry) => sum + (entry.transferSize ?? 0), 0),
        decoded_body_bytes: resources.reduce((sum, entry) => sum + (entry.decodedBodySize ?? 0), 0),
        js_heap_used_bytes: memory?.usedJSHeapSize ?? null,
        js_heap_limit_bytes: memory?.jsHeapSizeLimit ?? null,
      };
    });
    const bytes = await readFile(target);
    captures.push({
      schema_version: "citygap.visual-capture@1",
      capture_id: specification.id,
      generated_at: new Date().toISOString(),
      production_url: baseUrl,
      commit,
      browser: "chromium",
      viewport: { width: specification.width, height: specification.height },
      device_scale_factor: 1,
      scene_name: specification.title,
      route: specification.route,
      city: specification.route.includes("city=fujisawa") ? "fujisawa" : "maizuru",
      map_mode: specification.mode,
      camera: readiness.actual.camera,
      required_resources: { terrain: specification.mode === "plateau3d", local_dem: Boolean(specification.requireLocalDem), buildings: Boolean(specification.requireBuildings), roads: Boolean(specification.requireRoads), overlay: true },
      terrain_source: readiness.actual.terrainSource,
      terrain_ready: readiness.actual.terrainReady,
      terrain_tile_count: readiness.actual.terrainTileCount,
      building_source: readiness.actual.buildingSource,
      building_ready: readiness.actual.buildingReady,
      building_feature_count: readiness.actual.buildingFeatureCount,
      roads_ready: readiness.actual.roadsReady,
      imagery_ready: readiness.actual.imageryReady,
      analysis_source: readiness.actual.lens === "urban-xray" ? "existing CITY GAP exploratory_score_c" : readiness.actual.lens === "service-pulse" ? "precomputed network distance" : readiness.actual.lens === "changed-only" ? "existing scenario mesh results" : readiness.actual.lens === "temporal-ghost" ? "published PLATEAU temporal samples" : "none",
      analysis_ready: readiness.actual.analysisReady,
      overlay_ready: readiness.actual.overlayReady,
      font_ready: readiness.actual.fontReady,
      camera_settled: readiness.actual.cameraSettled,
      canvas_size_ready: readiness.actual.canvasSizeReady,
      canvas_css_size: readiness.actual.canvasCssSize,
      drawing_buffer_size: readiness.actual.drawingBufferSize,
      stable_frames: readiness.actual.stableFrames,
      outstanding_critical_requests: readiness.actual.outstandingCriticalRequests,
      optional_globe_refinement_requests: readiness.actual.optionalGlobeRequests,
      optional_building_stream_requests: readiness.actual.optionalBuildingRequests,
      request_failures: criticalRequestFailures,
      optional_lod_cancellations: optionalLodCancellations.length,
      optional_basemap_cancellations: optionalBasemapCancellations.length,
      console_errors: consoleErrors,
      capture_wall_time_ms: Date.now() - captureStartedAt,
      runtime_metrics: runtimeMetrics,
      capture_sha256: createHash("sha256").update(bytes).digest("hex"),
      capture_bytes: bytes.byteLength,
      source_data_ids: [
        specification.route.includes("city=fujisawa") ? "fujisawa-validation-data" : "maizuru-mesh-metrics",
        specification.requireGhost ? "plateau-temporal-validation" : specification.mode === "plateau3d" ? "plateau-26202-2025" : null,
        specification.requirePulse || specification.requireTwin ? "maizuru-network-scenarios" : null,
      ].filter(Boolean),
      capture_status: "complete",
      visual_ready: readiness.complete,
    });
  } catch (error) {
    failed = true;
    const diagnostic = {
      schema_version: "citygap.visual-readiness-diagnostic@1",
      generated_at: new Date().toISOString(),
      scene: specification,
      route,
      error: error instanceof Error ? error.message : String(error),
      root: await page.evaluate(() => ({ html: { ...document.documentElement.dataset }, cesium: document.querySelector(".cesium-map") ? { ...document.querySelector(".cesium-map").dataset } : null, body: document.body.innerText.slice(0, 4000) })).catch(() => null),
      console_errors: consoleErrors,
      request_failures: requestFailures,
      error_responses: responses,
    };
    await writeFile(path.join(diagnosticDirectory, `${specification.id}.json`), `${JSON.stringify(diagnostic, null, 2)}\n`, "utf8");
    process.stderr.write(`${specification.id}: ${diagnostic.error}\n`);
  } finally {
    await page.close();
  }
}

await browser.close();
if (failed) {
  if (!only) await rm(outputDirectory, { recursive: true, force: true });
  process.exitCode = 1;
} else {
  await mkdir(outputDirectory, { recursive: true });
  const manifestPath = path.join(outputDirectory, "manifest.json");
  let manifestCaptures = captures;
  if (only) {
    const existing = await readFile(manifestPath, "utf8").then(JSON.parse).catch(() => ({ captures: [] }));
    const replaced = new Set(captures.map((capture) => capture.capture_id));
    manifestCaptures = [...(existing.captures ?? []).filter((capture) => !replaced.has(capture.capture_id)), ...captures]
      .sort((left, right) => String(left.capture_id).localeCompare(String(right.capture_id)));
  }
  await writeFile(manifestPath, `${JSON.stringify({ schema_version: "citygap.visual-capture-manifest@1", generated_at: new Date().toISOString(), commit, captures: manifestCaptures }, null, 2)}\n`, "utf8");
  process.stdout.write(`${captures.length} complete production captures written to ${outputDirectory}\n`);
}
