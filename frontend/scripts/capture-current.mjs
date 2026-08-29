import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

// Readiness already requires document.fonts.status === "loaded". Avoid a second,
// non-stalling utility-world wait after SwiftShader has entered screenshot mode.
process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY = "1";

const CAPTURE_SCRIPT_VERSION = "urban-anatomy-capture@2.0.0";
const TARGET_BUILDINGS = 296;
const MINIMUM_TARGET_COVERAGE = 0.95;
const PACK_ID = "maizuru-533513314-plateau-2025-v1";
const parameters = new Map();
for (let index = 2; index < process.argv.length; index += 2) {
  parameters.set(process.argv[index], process.argv[index + 1]);
}
const repositoryRoot = path.resolve(process.cwd(), "..");
const baseUrl = parameters.get("--url") ?? "http://127.0.0.1:4173/plateau-city-gap/";
const outputDirectory = path.resolve(process.cwd(), parameters.get("--output") ?? "../docs/assets/current");
const diagnosticDirectory = path.resolve(process.cwd(), parameters.get("--diagnostics") ?? "../analysis/outputs/real/visual-readiness-failures");
const only = parameters.get("--only") ?? null;
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const repositoryHead = execFileSync("git", ["rev-parse", "HEAD"], { cwd: repositoryRoot, encoding: "utf8" }).trim();
const renderSourceCommit = process.env.CITYGAP_RENDER_SOURCE_COMMIT ?? repositoryHead;
const captureAssetCommit = process.env.CITYGAP_CAPTURE_ASSET_COMMIT ?? repositoryHead;
const scriptPath = fileURLToPath(import.meta.url);

const deepDive = "533513314";
const featuredBuilding = "bldg_a490fb5b-d668-441e-b9af-5b35c4629006";
const scenes = [
  { id: "01-city-finding", title: "City Finding", width: 1440, height: 900, route: `?city=maizuru&scene=gap_discovery&mesh=${deepDive}&resolution=mesh&inspector=open`, mode: "map2d" },
  { id: "02-resolution-lift", title: "Resolution Lift · 296 buildings", width: 1440, height: 900, route: `?city=maizuru&scene=plateau_detail&mesh=${deepDive}&resolution=building_group&lens=urban-xray&mapMode=plateau3d&buildingSource=spatial-pack&section=closed&inspector=open`, mode: "plateau3d", requirePack: true, requireXray: true },
  { id: "03-urban-section", title: "PLATEAU Urban Section", width: 1440, height: 900, route: `?city=maizuru&scene=plateau_detail&mesh=${deepDive}&resolution=building_group&lens=urban-xray&mapMode=plateau3d&buildingSource=spatial-pack&section=open&inspector=open`, mode: "plateau3d", requirePack: true, requireSection: true },
  { id: "04-building-xray", title: "Building X-Ray V2", width: 1440, height: 900, route: `?city=maizuru&scene=plateau_detail&building=${featuredBuilding}&resolution=building&lens=urban-xray&mapMode=plateau3d&buildingSource=spatial-pack&section=open&inspector=open`, mode: "plateau3d", requirePack: true, requireSection: true, requireXray: true, requireObject: "building" },
  { id: "05-service-pulse-section", title: "Service Pulse V2 × Section", width: 1440, height: 900, route: `?city=maizuru&scene=network_access&mesh=${deepDive}&resolution=road&lens=service-pulse&twin=baseline&mapMode=plateau3d&buildingSource=spatial-pack&section=open&inspector=open`, mode: "plateau3d", requirePack: true, requireSection: true, requirePulse: true },
  { id: "06-counterfactual-section", title: "Counterfactual Section", width: 1440, height: 900, route: `?city=maizuru&task=try&scene=scenario_compare&mesh=${deepDive}&resolution=site&lens=changed-only&twin=scenario&mapMode=plateau3d&buildingSource=spatial-pack&section=open&inspector=open`, mode: "plateau3d", requirePack: true, requireSection: true, requireTwin: true },
  { id: "07-object-evidence", title: "Object Lens × Evidence", width: 1440, height: 900, route: `?city=maizuru&scene=plateau_detail&building=${featuredBuilding}&resolution=building&lens=urban-xray&mapMode=plateau3d&buildingSource=spatial-pack&section=closed&inspector=open`, mode: "plateau3d", requirePack: true, requireXray: true, requireObject: "building", requireObjectLens: true },
  { id: "08-investigation-report", title: "Investigation Report", width: 1440, height: 900, route: `?city=maizuru&task=operate&scene=gap_discovery&mesh=${deepDive}&resolution=mesh&mapMode=map2d&inspector=open`, mode: "map2d", requireReport: true },
  { id: "09-mobile", title: "Mobile Investigation", width: 390, height: 844, route: `?city=maizuru&scene=gap_discovery&mesh=${deepDive}&resolution=mesh&mapMode=map2d&inspector=open`, mode: "map2d", mobile: true },
].filter((scene) => !only || scene.id === only || scene.id.includes(only));

if (!scenes.length) throw new Error(`Unknown scene: ${only}`);

function sha256(buffer) {
  return createHash("sha256").update(buffer).digest("hex");
}

async function sha256File(filename) {
  return sha256(await readFile(filename));
}

async function filesBelow(directory) {
  const entries = await readdir(directory, { withFileTypes: true }).catch(() => []);
  const nested = await Promise.all(entries.map((entry) => {
    const target = path.join(directory, entry.name);
    return entry.isDirectory() ? filesBelow(target) : [target];
  }));
  return nested.flat().sort();
}

async function aggregateAssetHash(directory) {
  const files = (await filesBelow(directory)).filter((file) => /\.(css|js)$/.test(file));
  const digest = createHash("sha256");
  for (const file of files) {
    digest.update(path.relative(directory, file).replaceAll(path.sep, "/"));
    digest.update("\0");
    digest.update(await readFile(file));
    digest.update("\0");
  }
  return digest.digest("hex");
}

const dataManifestPath = path.join(process.cwd(), "public/data/manifest.json");
const packManifestPath = path.join(process.cwd(), `public/data/spatial-packs/${PACK_ID}/manifest.json`);
const packManifest = JSON.parse(await readFile(packManifestPath, "utf8"));
const sourceDataIds = [
  `plateau-building-2025:${packManifest.source_versions.buildings.sha256}`,
  `plateau-dem-2025:${packManifest.source_versions.terrain.source_archive_sha256}`,
  "plateau-road-lod1-maizuru-2025",
  "ksj-p04-medical-2020",
  "ksj-p11-transport-2022",
  "citygap-mesh-analysis-2025",
];
const provenance = {
  repository_head: repositoryHead,
  render_source_commit: renderSourceCommit,
  capture_asset_commit: captureAssetCommit,
  frontend_asset_sha256: await aggregateAssetHash(path.join(process.cwd(), "dist/assets")),
  capture_script_version: CAPTURE_SCRIPT_VERSION,
  capture_script_sha256: await sha256File(scriptPath),
  data_manifest_sha256: await sha256File(dataManifestPath),
  pack_manifest_sha256: packManifest.pack_manifest_sha256,
  pack_manifest_file_sha256: await sha256File(packManifestPath),
  difference_reasons: [
    ...(repositoryHead !== renderSourceCommit ? [{ fields: ["repository_head", "render_source_commit"], reason: "capture metadata or assets were committed after the rendered source" }] : []),
    ...(captureAssetCommit !== renderSourceCommit ? [{ fields: ["capture_asset_commit", "render_source_commit"], reason: "capture PNG assets are stored in a later immutable commit than rendered source" }] : []),
  ],
};

const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist", "--use-gl=swiftshader"],
});
const context = await browser.newContext({
  deviceScaleFactor: 1,
  reducedMotion: "reduce",
});
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
  const page = await context.newPage();
  await page.setViewportSize({ width: specification.width, height: specification.height });
  const consoleErrors = [];
  const requestFailures = [];
  const errorResponses = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push({ text: message.text(), location: message.location() });
  });
  page.on("pageerror", (error) => consoleErrors.push({ text: error.message, location: null }));
  page.on("requestfailed", (request) => requestFailures.push({ url: request.url(), failure: request.failure()?.errorText ?? "unknown" }));
  page.on("response", (response) => {
    if (response.status() >= 400) errorResponses.push({ url: response.url(), status: response.status() });
  });
  const route = `${baseUrl}${specification.route}`;
  try {
    await page.goto(route, { waitUntil: "domcontentloaded", timeout: 90_000 });
    await page.waitForSelector(".product-app", { timeout: 90_000 });
    await page.waitForFunction(
      (scene) => {
        const rootReady = document.documentElement.dataset.captureStrictReady === "true";
        const sectionReady = !scene.requireSection || (
          document.querySelector(".urban-section")?.getAttribute("data-transect-ready") === "true"
          && document.querySelector(".cesium-map")?.getAttribute("data-section-plane-ready") === "true"
        );
        return rootReady && sectionReady;
      },
      specification,
      { timeout: specification.mode === "plateau3d" ? 300_000 : 60_000 },
    );
    if (specification.requireObjectLens) {
      await page.locator(".object-lens").scrollIntoViewIfNeeded();
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    }
    const readiness = await page.evaluate((scene) => {
      const root = document.documentElement;
      const cesium = document.querySelector(".cesium-map");
      const viewer = window.__cityGapCesiumViewer;
      const section = document.querySelector(".urban-section");
      const actual = {
        interactionReady: root.dataset.interactionReady === "true",
        visualComplete: root.dataset.visualComplete === "true",
        captureStrictReady: root.dataset.captureStrictReady === "true",
        camera: viewer ? {
          longitude: viewer.camera.positionCartographic.longitude * 180 / Math.PI,
          latitude: viewer.camera.positionCartographic.latitude * 180 / Math.PI,
          height: viewer.camera.positionCartographic.height,
          heading: viewer.camera.heading,
          pitch: viewer.camera.pitch,
          roll: viewer.camera.roll,
        } : null,
        buildingSource: cesium?.dataset.buildingSource ?? "none",
        packId: cesium?.dataset.packId ?? "none",
        buildingFeatureCount: Number(cesium?.dataset.buildingFeatureCount ?? 0),
        targetBuildingCount: Number(cesium?.dataset.targetBuildingCount ?? 0),
        loadedTargetBuildingCount: Number(cesium?.dataset.loadedTargetBuildingCount ?? 0),
        visibleTargetBuildingCount: Number(cesium?.dataset.visibleTargetBuildingCount ?? 0),
        targetCoverageRatio: Number(cesium?.dataset.targetCoverageRatio ?? 0),
        packArtifactsReady: cesium?.dataset.packArtifactsReady === "true",
        packArtifactBytes: Number(cesium?.dataset.packArtifactBytes ?? 0),
        terrainSource: cesium?.dataset.terrainSource ?? "none",
        terrainTileCount: Number(cesium?.dataset.terrainTileCount ?? 0),
        localDemReady: cesium?.dataset.localDemReady === "true",
        roadsReady: cesium?.dataset.roadsReady === "true",
        cameraSettled: cesium?.dataset.cameraSettled === "true",
        canvasSizeReady: cesium?.dataset.canvasSizeReady === "true",
        stableFrames: Number(cesium?.dataset.stableFrames ?? (scene.mode === "map2d" ? 3 : 0)),
        criticalRequests: Number(cesium?.dataset.criticalRequests ?? 0),
        optionalGlobeRequests: Number(cesium?.dataset.optionalGlobeRequests ?? 0),
        optionalBuildingRequests: Number(cesium?.dataset.optionalBuildingRequests ?? 0),
        lens: new URLSearchParams(location.search).get("lens") ?? "none",
        counterfactual: new URLSearchParams(location.search).get("twin") ?? "baseline",
        selectionType: new URLSearchParams(location.search).has("building") ? "building" : new URLSearchParams(location.search).has("road") ? "road" : new URLSearchParams(location.search).has("mesh") ? "mesh" : "none",
        pulseMarkers: Number(cesium?.dataset.pulseMarkers ?? 0),
        pulseSemantics: cesium?.dataset.pulseSemantics ?? "none",
        sectionReady: section?.getAttribute("data-transect-ready") === "true",
        sectionPlaneReady: cesium?.dataset.sectionPlaneReady === "true",
        sectionBuildingCount: Number(section?.getAttribute("data-building-count") ?? 0),
        sectionRoadCount: Number(section?.getAttribute("data-road-count") ?? 0),
        sectionTerrainSamples: Number(section?.getAttribute("data-terrain-samples") ?? 0),
        sectionTerrainCovered: Number(section?.getAttribute("data-terrain-covered") ?? 0),
        objectLensVisible: Boolean(document.querySelector(".object-lens")),
        reportVisible: Boolean(document.querySelector(".operations-workspace, .decision-record, .evidence-center")),
      };
      const checks = [actual.interactionReady, actual.visualComplete, actual.captureStrictReady, document.fonts.status === "loaded"];
      if (scene.mode === "plateau3d") checks.push(
        actual.localDemReady,
        actual.terrainSource === "plateau-local-dem",
        actual.terrainTileCount > 0,
        actual.roadsReady,
        actual.cameraSettled,
        actual.canvasSizeReady,
        actual.stableFrames >= 3,
        actual.criticalRequests === 0,
      );
      if (scene.requirePack) checks.push(
        actual.buildingSource === "spatial-evidence-pack",
        actual.packId === "maizuru-533513314-plateau-2025-v1",
        actual.targetBuildingCount === 296,
        actual.loadedTargetBuildingCount >= Math.ceil(296 * 0.95),
        actual.targetCoverageRatio >= 0.95,
        actual.packArtifactsReady,
        actual.packArtifactBytes > 4_000_000,
      );
      if (scene.requireSection) checks.push(
        actual.sectionReady,
        actual.sectionPlaneReady,
        actual.sectionBuildingCount > 0,
        actual.sectionRoadCount > 0,
        actual.sectionTerrainSamples > 0,
        actual.sectionTerrainCovered > 0,
      );
      if (scene.requirePulse) checks.push(actual.pulseMarkers > 0, actual.pulseSemantics === "network-distance-only");
      if (scene.requireXray) checks.push(actual.lens === "urban-xray");
      if (scene.requireTwin) checks.push(actual.lens === "changed-only", actual.counterfactual === "scenario");
      if (scene.requireObject) checks.push(actual.selectionType === scene.requireObject);
      if (scene.requireObjectLens) checks.push(actual.objectLensVisible);
      if (scene.requireReport) checks.push(actual.reportVisible);
      return { actual, checks, complete: checks.every(Boolean) };
    }, specification);

    const cancelledOptional = requestFailures.filter((item) => item.failure.includes("ERR_ABORTED") && (
      item.url.endsWith(".b3dm") || item.url.includes("cyberjapandata.gsi.go.jp/xyz/")
    ));
    const criticalNetworkFailures = [
      ...requestFailures.filter((item) => !cancelledOptional.includes(item)),
      ...errorResponses,
    ];
    if (!readiness.complete || criticalNetworkFailures.length || consoleErrors.length) {
      throw new Error(`Strict capture rejected: ${JSON.stringify({ readiness, criticalNetworkFailures, consoleErrors })}`);
    }
    const captureStabilization = specification.mode === "plateau3d"
      ? await page.evaluate(async () => {
        const hook = window.__cityGapStabilizeCapture;
        if (typeof hook !== "function") throw new Error("3D capture stabilization hook is unavailable");
        return hook();
      })
      : { globeHidden: false, incompleteFallbackHidden: false, fastStartVisible: false };
    const target = path.join(outputDirectory, `${specification.id}.png`);
    await page.screenshot({ path: target, fullPage: false, animations: "disabled", timeout: 180_000 });
    const captureBytes = await readFile(target);
    const runtimeMetrics = await page.evaluate(() => {
      const resources = performance.getEntriesByType("resource");
      const b3dm = resources.filter((entry) => entry.name.endsWith(".b3dm"));
      const transferred = b3dm.reduce((total, entry) => total + (entry.transferSize ?? 0), 0);
      return {
        app_shell_ms: Number(document.documentElement.dataset.perfAppShellMs ?? 0),
        map_2d_interaction_ms: Number(document.documentElement.dataset.perfMap2dInteractionMs ?? 0),
        three_d_first_meaningful_ms: Number(document.documentElement.dataset.perfThreeDFirstMeaningfulMs ?? 0),
        pack_interaction_ms: Number(document.documentElement.dataset.perfPackInteractionMs ?? 0),
        visual_complete_ms: Number(document.documentElement.dataset.perfVisualCompleteMs ?? 0),
        capture_strict_ms: Number(document.documentElement.dataset.perfCaptureStrictMs ?? 0),
        resource_count: resources.length,
        js_heap_used_bytes: performance.memory?.usedJSHeapSize ?? null,
        pack_cache: {
          b3dm_resource_entries: b3dm.length,
          transfer_size_bytes: transferred,
          result: b3dm.length > 0 && transferred === 0 ? "warm-http-cache" : "cold-or-revalidated",
        },
      };
    });
    captures.push({
      schema_version: "citygap.visual-capture@2",
      capture_id: specification.id,
      generated_at: new Date().toISOString(),
      production_url: baseUrl,
      ...provenance,
      browser: "chromium",
      renderer_class: "swiftshader",
      viewport: { width: specification.width, height: specification.height },
      device_scale_factor: 1,
      scene_name: specification.title,
      route: specification.route,
      city: "maizuru",
      map_mode: specification.mode,
      urban_state: packManifest.urban_state,
      camera: readiness.actual.camera,
      pack_id: readiness.actual.packId,
      target_building_count: readiness.actual.targetBuildingCount,
      loaded_target_building_count: readiness.actual.loadedTargetBuildingCount,
      visible_target_building_count: readiness.actual.visibleTargetBuildingCount,
      target_coverage_ratio: readiness.actual.targetCoverageRatio,
      pack_artifacts_ready: readiness.actual.packArtifactsReady,
      pack_artifact_bytes: readiness.actual.packArtifactBytes,
      terrain_triangle_count: packManifest.objects.terrain_source_triangles,
      road_object_count: packManifest.objects.roads,
      section_sample_count: specification.requireSection ? readiness.actual.sectionTerrainSamples : 0,
      source_data_ids: sourceDataIds,
      building_source: readiness.actual.buildingSource,
      building_feature_count: readiness.actual.buildingFeatureCount,
      terrain_source: readiness.actual.terrainSource,
      terrain_tile_count: readiness.actual.terrainTileCount,
      road_objects_ready: readiness.actual.roadsReady,
      transect: specification.requireSection ? {
        id: `${PACK_ID}-default-section`,
        terrain_samples: readiness.actual.sectionTerrainSamples,
        terrain_samples_with_coverage: readiness.actual.sectionTerrainCovered,
        building_relations: readiness.actual.sectionBuildingCount,
        road_intersections: readiness.actual.sectionRoadCount,
        plane_ready: readiness.actual.sectionPlaneReady,
      } : null,
      readiness: {
        interaction_ready: readiness.actual.interactionReady,
        visual_complete: readiness.actual.visualComplete,
        capture_strict_ready: readiness.actual.captureStrictReady,
        stable_frames: readiness.actual.stableFrames,
        outstanding_critical_requests: readiness.actual.criticalRequests,
        optional_globe_requests: readiness.actual.optionalGlobeRequests,
        optional_building_requests: readiness.actual.optionalBuildingRequests,
      },
      reduced_motion: true,
      console_errors: consoleErrors,
      network_failures: criticalNetworkFailures,
      runtime_metrics: runtimeMetrics,
      capture_wall_time_ms: Date.now() - captureStartedAt,
      capture_stabilization: captureStabilization,
      capture_sha256: sha256(captureBytes),
      capture_bytes: captureBytes.byteLength,
      incomplete_capture_rejection: {
        fast_start_15_rejected: specification.requirePack,
        terrain_fallback_rejected: specification.mode === "plateau3d",
        empty_section_rejected: Boolean(specification.requireSection),
        external_stream_timeout_nonblocking: specification.mode === "plateau3d",
      },
      capture_status: "complete",
    });
  } catch (error) {
    failed = true;
    const diagnostic = {
      schema_version: "citygap.visual-readiness-diagnostic@2",
      generated_at: new Date().toISOString(),
      scene: specification,
      route,
      error: error instanceof Error ? error.message : String(error),
      root: await page.evaluate(() => ({
        html: { ...document.documentElement.dataset },
        cesium: document.querySelector(".cesium-map") ? { ...document.querySelector(".cesium-map").dataset } : null,
        section: document.querySelector(".urban-section") ? { ...document.querySelector(".urban-section").dataset } : null,
        body: document.body.innerText.slice(0, 5000),
      })).catch(() => null),
      console_errors: consoleErrors,
      request_failures: requestFailures,
      error_responses: errorResponses,
    };
    await writeFile(path.join(diagnosticDirectory, `${specification.id}.json`), `${JSON.stringify(diagnostic, null, 2)}\n`, "utf8");
    process.stderr.write(`${specification.id}: ${diagnostic.error}\n`);
  } finally {
    await page.close();
  }
}

await context.close();
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
  const manifest = {
    schema_version: "citygap.visual-capture-manifest@2",
    generated_at: new Date().toISOString(),
    ...provenance,
    capture_count: manifestCaptures.length,
    required_capture_ids: scenes.map((scene) => scene.id),
    strict_contract: {
      target_buildings: TARGET_BUILDINGS,
      minimum_target_coverage_ratio: MINIMUM_TARGET_COVERAGE,
      terrain_source: "plateau-local-dem",
      stable_frames: 3,
      console_errors: 0,
      network_failures: 0,
    },
    captures: manifestCaptures,
  };
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  const pngFiles = (await readdir(outputDirectory)).filter((name) => name.endsWith(".png"));
  if (pngFiles.length !== manifestCaptures.length) throw new Error("Current screenshot directory contains stale or missing PNG files");
  for (const capture of manifestCaptures) {
    const filename = path.join(outputDirectory, `${capture.capture_id}.png`);
    if ((await stat(filename)).size !== capture.capture_bytes || await sha256File(filename) !== capture.capture_sha256) {
      throw new Error(`Screenshot integrity mismatch: ${capture.capture_id}`);
    }
  }
  process.stdout.write(`${captures.length} strict current captures written to ${outputDirectory}\n`);
}
