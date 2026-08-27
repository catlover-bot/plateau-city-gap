import { chromium } from "playwright-core";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const baseUrl = process.argv[2] ?? "http://127.0.0.1:5173/plateau-city-gap/";
const outDir = path.resolve(process.cwd(), "../docs/assets/product-v2");
await mkdir(outDir, { recursive: true });
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
  ?? "/home/catlover/.cache/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-linux64/chrome-headless-shell";
const browser = await chromium.launch({ headless: true, executablePath, args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist", "--use-gl=swiftshader"] });
const debugMode = process.argv.includes("--debug-only");
const debug3dMode = process.argv.includes("--debug-3d");
const report = { baseUrl, generatedAt: new Date().toISOString(), overviewCesiumRequests: [], consoleErrors: [], consoleMessages: [], gsiRequests: [], plateauRequests: [], screenshots: [], viewports: [] };

async function waitForProduct(page) {
  await page.waitForSelector(".product-app", { timeout: 90_000 });
  await page.waitForSelector(".analytical-map-canvas canvas", { timeout: 90_000 });
  await page.waitForTimeout(2_000);
}

async function shot(page, name) {
  await page.screenshot({ path: path.join(outDir, name), fullPage: true });
  report.screenshots.push(name);
}

async function openFresh(viewport = { width: 1440, height: 900 }, search = "", captureOverview = false) {
  const page = await browser.newPage({ viewport });
  page.on("console", (message) => { if (message.type() === "error") report.consoleErrors.push(message.text()); });
  if (debugMode || debug3dMode) page.on("console", (message) => report.consoleMessages.push(`${message.type()}: ${message.text()}`));
  if (debugMode || debug3dMode) page.on("worker", (worker) => report.consoleMessages.push(`worker: ${worker.url()}`));
  page.on("pageerror", (error) => report.consoleErrors.push(error.message));
  page.on("request", (request) => { if (captureOverview && /CesiumMap|cesium\/Workers|cesium\/Assets/.test(request.url())) report.overviewCesiumRequests.push(request.url()); });
  if (debug3dMode) page.on("response", (response) => { if (response.url().includes("cyberjapandata.gsi.go.jp")) report.gsiRequests.push(`${response.status()} ${response.url()}`); });
  if (debug3dMode) page.on("response", (response) => { if (/plateauview|plateau.reearth|plateau-terrain/.test(response.url())) report.plateauRequests.push(`${response.status()} ${response.url()}`); });
  await page.goto(`${baseUrl}${search}`, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await waitForProduct(page);
  return page;
}

if (process.argv.includes("--debug-3d")) {
  const page = await openFresh();
  await page.locator(".candidate-list button").nth(2).click();
  await page.locator(".task-navigation button").nth(1).click();
  await page.getByRole("button", { name: /PLATEAU 3D/ }).first().click();
  await page.waitForTimeout(Number(process.env.CITY_GAP_3D_WAIT_MS ?? 8_000));
  const debug = await page.evaluate(() => {
    const viewer = window.__cityGapCesiumViewer;
    const cartographic = viewer?.camera.positionCartographic;
    const center = viewer
      ? viewer.camera.pickEllipsoid({ x: viewer.canvas.width / 2, y: viewer.canvas.height / 2 }, viewer.scene.globe.ellipsoid)
      : undefined;
    const centerCartographic = center && viewer ? viewer.scene.globe.ellipsoid.cartesianToCartographic(center) : undefined;
    return {
      destroyed: viewer?.isDestroyed(),
      longitude: cartographic?.longitude,
      latitude: cartographic?.latitude,
      height: cartographic?.height,
      heading: viewer?.camera.heading,
      pitch: viewer?.camera.pitch,
      roll: viewer?.camera.roll,
      direction: viewer?.camera.directionWC,
      globeShow: viewer?.scene.globe.show,
      globeTilesLoaded: viewer?.scene.globe.tilesLoaded,
      globeBaseColor: viewer?.scene.globe.baseColor,
      globeTranslucency: viewer?.scene.globe.translucency.enabled,
      tilesToRender: viewer?.scene.globe._surface?._tilesToRender?.length,
      renderTileLevels: viewer?.scene.globe._surface?._tilesToRender?.slice(0, 12).map((tile) => tile.level),
      imageryCount: viewer?.imageryLayers.length,
      dataSourceCount: viewer?.dataSources.length,
      primitives: viewer?.scene.primitives._primitives?.map((primitive) => ({
        type: primitive.constructor?.name,
        url: primitive._resource?.url,
        show: primitive.show,
        ready: primitive.ready,
        tilesLoaded: primitive.tilesLoaded,
        selectedTiles: primitive._selectedTiles?.length,
        commands: primitive._statistics?.numberOfCommands,
        visited: primitive._statistics?.visited,
        pendingRequests: primitive._statistics?.numberOfPendingRequests,
        processing: primitive._statistics?.numberOfTilesProcessing,
        featuresSelected: primitive._statistics?.numberOfFeaturesSelected,
        rootRadius: primitive.root?.boundingSphere?.radius,
        rootCenter: primitive.root?.boundingSphere?.center,
        rootCartographic: primitive.root?.boundingSphere?.center
          ? viewer.scene.globe.ellipsoid.cartesianToCartographic(primitive.root.boundingSphere.center)
          : undefined,
        rootState: primitive.root && {
          visible: primitive.root._visible,
          inRequestVolume: primitive.root._inRequestVolume,
          contentState: primitive.root._contentState,
          distanceToCamera: primitive.root._distanceToCamera,
          screenSpaceError: primitive.root._screenSpaceError,
          finalResolution: primitive.root._finalResolution,
          depth: primitive.root._depth,
        },
      })),
      canvas: viewer ? [viewer.canvas.width, viewer.canvas.height] : null,
      pickedCenter: centerCartographic && { longitude: centerCartographic.longitude, latitude: centerCartographic.latitude, height: centerCartographic.height },
      sourceStages: viewer?.container?.dataset,
      ready: document.querySelector(".plateau-3d-shell")?.getAttribute("data-ready")
    };
  });
  debug.messages = report.consoleMessages;
  debug.gsiRequests = report.gsiRequests;
  debug.plateauRequests = report.plateauRequests;
  await page.screenshot({ path: "/tmp/city-gap-debug-3d.png" });
  console.log(JSON.stringify(debug, null, 2));
  await page.close(); await browser.close(); process.exit(0);
}

if (debugMode) {
  const page = await openFresh();
  await page.waitForTimeout(8_000);
  const debug = await page.locator(".analytical-map-canvas").evaluate((node) => {
    const map = node.__cityGapMap;
    return {
      zoom: map?.getZoom(),
      initCount: window.__cityGapMapInitCount,
      loaded: map?.loaded(),
      styleLoaded: map?.isStyleLoaded(),
      layers: map?.getStyle().layers.map((layer) => layer.id),
      meshSourceType: map?.getSource("meshes")?.type,
      meshSourceLoaded: map?.isSourceLoaded("meshes"),
      sourceFeatures: map?.querySourceFeatures("meshes").length,
      boundaryFeatures: map?.querySourceFeatures("boundary").length,
      center: map?.getCenter().toArray(),
      renderedMeshes: map?.queryRenderedFeatures(undefined, { layers: ["mesh-fill"] }).length,
      renderedTop: map?.queryRenderedFeatures(undefined, { layers: ["mesh-top-fill"] }).length,
      meshVisibility: map?.getLayoutProperty("mesh-fill", "visibility"),
      meshOpacity: map?.getPaintProperty("mesh-fill", "fill-opacity")
    };
  });
  console.log(JSON.stringify({ ...debug, messages: report.consoleMessages }, null, 2));
  await page.close();
  await browser.close();
  process.exit(0);
}

let page = await openFresh({ width: 1440, height: 900 }, "", true);
await shot(page, "01-discovery-2d.png");
// Requests after this point belong to an explicit PLATEAU 3D action.
report.overviewCesiumRequests = [...new Set(report.overviewCesiumRequests)];
await page.close();
page = await openFresh();
await page.locator(".candidate-list button").first().click();
await page.waitForTimeout(700);
await shot(page, "02-selected-mesh.png");
await page.locator(".candidate-list button").nth(2).click();
await page.locator(".task-navigation button").nth(1).click();
await page.getByRole("button", { name: /PLATEAU 3D/ }).first().click();
await page.waitForSelector(".plateau-3d-shell", { timeout: 90_000 });
await page.waitForFunction(() => document.querySelector(".plateau-3d-shell")?.getAttribute("data-ready") === "true", { timeout: 90_000 });
await page.waitForTimeout(3_000);
await shot(page, "03-plateau-3d.png");
await page.close();

page = await openFresh();
await page.getByRole("button", { name: "交通を見る" }).click();
await page.waitForTimeout(700);
await shot(page, "04-network.png");
await page.locator(".task-navigation button").nth(2).click();
await page.getByRole("button", { name: "災害Stress Test" }).click();
await page.locator(".scenario-workspace select").selectOption("flood");
await page.waitForTimeout(700);
await shot(page, "05-hazard.png");
await page.getByRole("button", { name: "施策案比較" }).click();
await page.waitForTimeout(700);
await shot(page, "06-scenario-compare.png");
await page.close();

page = await openFresh();
await page.locator(".task-navigation button").nth(3).click();
await page.waitForTimeout(2_000);
await shot(page, "07-validation.png");
await page.getByRole("button", { name: "年次差分" }).click();
await page.waitForTimeout(700);
await shot(page, "08-temporal.png");
await page.locator(".task-navigation button").nth(4).click();
await page.waitForTimeout(1_500);
await shot(page, "09-municipal.png");
await page.close();

page = await openFresh({ width: 390, height: 844 });
await shot(page, "10-mobile.png");
await page.close();

for (const viewport of [{ width: 1440, height: 900 }, { width: 1280, height: 800 }, { width: 1024, height: 768 }, { width: 768, height: 1024 }, { width: 390, height: 844 }]) {
  const auditPage = await openFresh(viewport);
  report.viewports.push({
    ...viewport,
    horizontalOverflow: await auditPage.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
    mapWidth: await auditPage.locator(".map-stage").evaluate((node) => Math.round(node.getBoundingClientRect().width)),
    inspectorVisible: await auditPage.locator(".context-inspector").isVisible(),
    activePrimary: await auditPage.locator(".context-legend strong").textContent(),
    mapAttributionVisible: await auditPage.locator(".maplibregl-ctrl-attrib").isVisible()
  });
  await auditPage.close();
}

report.overviewCesiumRequests = [...new Set(report.overviewCesiumRequests)];
report.consoleErrors = [...new Set(report.consoleErrors)].filter((message) => !message.includes("favicon"));
await writeFile(path.join(outDir, "audit.json"), `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify(report, null, 2));
await browser.close();
