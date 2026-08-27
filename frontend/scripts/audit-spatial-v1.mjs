import { chromium } from "playwright-core";
import { copyFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const baseUrl = process.argv[2] ?? "http://127.0.0.1:4173/plateau-city-gap/";
const outDir = path.resolve(process.cwd(), "../docs/assets/spatial-v1");
const beforeDir = path.join(outDir, "before");
await mkdir(beforeDir, { recursive: true });
for (const name of ["1440x900.png", "1280x800.png", "1024x768.png", "768x1024.png", "390x844.png"]) {
  await copyFile(path.resolve(process.cwd(), `../docs/assets/product-v2/baseline/${name}`), path.join(beforeDir, name));
}

const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
  ?? "/home/catlover/.cache/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-linux64/chrome-headless-shell";
const browser = await chromium.launch({
  headless: true,
  executablePath,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist", "--use-gl=swiftshader"],
});

const report = {
  schemaVersion: "1.0.0",
  baseUrl,
  generatedAt: new Date().toISOString(),
  screenshots: [],
  viewports: [],
  workflows: [],
  consoleErrors: [],
  localNetworkFailures: [],
  externalNetworkFailures: [],
  threeD: {},
  performance: {},
  accessibility: {},
};

function target(search = "") {
  return `${baseUrl}${search}`;
}

function observe(page, label) {
  page.on("console", (message) => {
    if (message.type() === "error") report.consoleErrors.push({ label, text: message.text() });
  });
  page.on("pageerror", (error) => report.consoleErrors.push({ label, text: error.message }));
  page.on("response", (response) => {
    if (response.status() < 400) return;
    const entry = { label, status: response.status(), url: response.url() };
    if (response.url().startsWith(baseUrl)) report.localNetworkFailures.push(entry);
    else report.externalNetworkFailures.push(entry);
  });
}

async function openPage(search = "", viewport = { width: 1440, height: 900 }, label = "page") {
  const page = await browser.newPage({ viewport });
  observe(page, label);
  const started = Date.now();
  await page.goto(target(search), { waitUntil: "domcontentloaded", timeout: 90_000 });
  await page.waitForSelector(".product-app", { timeout: 90_000 });
  const is3d = await page.locator(".product-app").getAttribute("data-map-state") === "detail3d";
  if (is3d) await page.waitForSelector(".plateau-3d-shell", { timeout: 90_000 });
  else await page.waitForSelector(".analytical-map-canvas canvas", { timeout: 90_000 });
  await page.waitForTimeout(1_000);
  return { page, productReadyMs: Date.now() - started };
}

async function shot(page, name) {
  await page.screenshot({ path: path.join(outDir, name), fullPage: false });
  report.screenshots.push(name);
}

async function waitFor3d(page, timeout = 30_000) {
  const started = Date.now();
  await page.waitForSelector('.plateau-3d-shell[data-ready="true"]', { timeout: 90_000 });
  await page.waitForFunction(() => {
    const viewer = window.__cityGapCesiumViewer;
    if (!viewer || viewer.isDestroyed()) return false;
    const primitives = viewer.scene.primitives?._primitives ?? [];
    const hasBuilding = primitives.some((item) => /plateau-fast|\/plateau\/|26202-bldg/.test(item?._resource?.url ?? "") && ((item?._selectedTiles?.length ?? 0) > 0 || item?.tilesLoaded));
    const localDem = viewer.container?.dataset?.localDem;
    return hasBuilding && (localDem === "ready" || localDem === "fallback");
  }, { timeout }).catch(() => undefined);
  await page.waitForTimeout(1_500);
  return Date.now() - started;
}

async function waitForOfficialBuildings(page, timeout = 40_000) {
  await page.waitForFunction(() => {
    const viewer = window.__cityGapCesiumViewer;
    if (!viewer || viewer.isDestroyed()) return false;
    return (viewer.scene.primitives?._primitives ?? []).some((item) => /26202-bldg/.test(item?._resource?.url ?? "") && (item?._selectedTiles?.length ?? 0) >= 5 && (item?._statistics?.numberOfCommands ?? 0) >= 5);
  }, { timeout }).catch(() => undefined);
  await page.waitForTimeout(700);
}

async function threeDStats(page) {
  return page.evaluate(async () => {
    const viewer = window.__cityGapCesiumViewer;
    if (!viewer || viewer.isDestroyed()) return null;
    let frames = 0;
    const count = () => { frames += 1; };
    viewer.scene.postRender.addEventListener(count);
    const started = performance.now();
    while (performance.now() - started < 1_500) {
      viewer.render();
      await new Promise((resolve) => requestAnimationFrame(resolve));
    }
    viewer.scene.postRender.removeEventListener(count);
    const primitives = (viewer.scene.primitives?._primitives ?? []).filter((item) => item?._resource?.url).map((item) => ({
      url: item._resource.url,
      show: item.show,
      ready: item.ready,
      tilesLoaded: item.tilesLoaded,
      selectedTiles: item._selectedTiles?.length ?? 0,
      pendingRequests: item._statistics?.numberOfPendingRequests ?? 0,
      processing: item._statistics?.numberOfTilesProcessing ?? 0,
      commands: item._statistics?.numberOfCommands ?? 0,
      featuresSelected: item._statistics?.numberOfFeaturesSelected ?? 0,
      cacheBytes: item.cacheBytes,
      maximumScreenSpaceError: item.maximumScreenSpaceError,
    }));
    const camera = viewer.camera.positionCartographic;
    return {
      forcedRenderFps: Number((frames / 1.5).toFixed(1)),
      frameCount: frames,
      canvas: { width: viewer.canvas.width, height: viewer.canvas.height },
      camera: { longitudeRadians: camera.longitude, latitudeRadians: camera.latitude, heightM: camera.height, pitchRadians: viewer.camera.pitch },
      globeTilesLoaded: viewer.scene.globe.tilesLoaded,
      sourceStages: { ...viewer.container.dataset },
      primitives,
    };
  });
}

async function selectVisibleBuilding(page) {
  const point = await page.evaluate(() => {
    const viewer = window.__cityGapCesiumViewer;
    if (!viewer || viewer.isDestroyed()) return null;
    viewer.scene.render();
    const canvas = viewer.canvas;
    for (let y = Math.round(canvas.clientHeight * 0.18); y < canvas.clientHeight * 0.82; y += 28) {
      for (let x = Math.round(canvas.clientWidth * 0.12); x < canvas.clientWidth * 0.88; x += 28) {
        const hits = viewer.scene.drillPick({ x, y }, 12) ?? [];
        const feature = hits.find((item) => typeof item?.getProperty === "function" && (item.getProperty("gml_id") || item.getProperty("_gml_id")));
        if (feature) {
          const rect = canvas.getBoundingClientRect();
          return { x: rect.left + x, y: rect.top + y };
        }
      }
    }
    return null;
  });
  if (!point) return false;
  await page.mouse.click(point.x, point.y);
  await page.waitForFunction(() => new URLSearchParams(location.search).get("selectionType") === "building", { timeout: 10_000 }).catch(() => undefined);
  return new URLSearchParams(new URL(page.url()).search).get("selectionType") === "building";
}

async function runWorkflow(name, search, action) {
  const { page } = await openPage(search, { width: 1440, height: 900 }, `workflow:${name}`);
  const started = Date.now();
  let clicks = 0;
  let deadEnd = null;
  const click = async (locator) => { await locator.click({ timeout: 20_000 }); clicks += 1; };
  try {
    await action(page, click);
  } catch (error) {
    deadEnd = error instanceof Error ? error.message : String(error);
  }
  report.workflows.push({ name, durationMs: Date.now() - started, clicks, deadEnd, finalUrl: page.url(), finalScene: await page.locator(".product-app").getAttribute("data-scene-preset") });
  await page.close();
}

let opened = await openPage("?city=maizuru&scene=city_overview", { width: 1440, height: 900 }, "01-city-overview");
report.performance.twoDProductReadyMs = opened.productReadyMs;
await shot(opened.page, "01-city-overview.png");
await opened.page.close();

opened = await openPage("?city=maizuru&scene=gap_discovery", { width: 1440, height: 900 }, "02-gap-candidate");
await opened.page.locator(".candidate-list button").first().click();
await opened.page.waitForTimeout(700);
await shot(opened.page, "02-gap-candidate.png");
await opened.page.close();

opened = await openPage("?city=maizuru&scene=plateau_detail&mesh=533513314", { width: 1440, height: 900 }, "03-plateau-3d");
report.performance.threeDMeaningfulMs = await waitFor3d(opened.page);
await waitForOfficialBuildings(opened.page);
await shot(opened.page, "03-plateau-3d-overview.png");
report.threeD.plateauDetail = await threeDStats(opened.page);
report.threeD.buildingSelected = await selectVisibleBuilding(opened.page);
await opened.page.waitForTimeout(600);
await shot(opened.page, "04-plateau-building-detail.png");
await opened.page.close();

opened = await openPage("?city=maizuru&scene=network_access&mesh=533513314", { width: 1440, height: 900 }, "05-road-terrain");
await waitFor3d(opened.page);
await shot(opened.page, "05-road-terrain.png");
report.threeD.networkAccess = await threeDStats(opened.page);
await opened.page.close();

opened = await openPage("?city=maizuru&scene=scenario_compare&mapMode=plateau3d&mesh=533513314", { width: 1440, height: 900 }, "06-scenario-3d");
await waitFor3d(opened.page);
await opened.page.waitForTimeout(1_000);
await shot(opened.page, "06-scenario-3d.png");
report.threeD.scenario = await threeDStats(opened.page);
await opened.page.close();

opened = await openPage("?city=maizuru&scene=hazard_stress&mesh=533513314", { width: 1440, height: 900 }, "07-hazard-stress-3d");
await opened.page.getByRole("button", { name: "災害Stress Test" }).click();
await opened.page.locator(".scenario-workspace select").selectOption("flood");
await waitFor3d(opened.page);
await opened.page.waitForTimeout(800);
await shot(opened.page, "07-hazard-stress-3d.png");
report.threeD.hazardStress = await threeDStats(opened.page);
await opened.page.close();

opened = await openPage("?city=maizuru&scene=validation_disagreement", { width: 1440, height: 900 }, "08-validation");
await opened.page.waitForSelector(".validation-summary", { timeout: 30_000 });
await shot(opened.page, "08-validation-disagreement.png");
await opened.page.getByRole("button", { name: "年次差分" }).click();
await opened.page.waitForTimeout(1_000);
await shot(opened.page, "09-temporal-change.png");
await opened.page.close();

opened = await openPage("?city=maizuru&scene=gap_discovery", { width: 390, height: 844 }, "10-mobile");
await opened.page.locator(".candidate-list button").first().click();
await opened.page.waitForTimeout(500);
await shot(opened.page, "10-mobile-selected.png");
await opened.page.close();

for (const viewport of [{ width: 1440, height: 900 }, { width: 1280, height: 800 }, { width: 1024, height: 768 }, { width: 768, height: 1024 }, { width: 390, height: 844 }]) {
  const { page } = await openPage("?city=maizuru&scene=gap_discovery", viewport, `viewport:${viewport.width}x${viewport.height}`);
  report.viewports.push({
    ...viewport,
    horizontalOverflow: await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
    mapWidth: await page.locator(".map-stage").evaluate((node) => Math.round(node.getBoundingClientRect().width)),
    mapHeight: await page.locator(".map-stage").evaluate((node) => Math.round(node.getBoundingClientRect().height)),
    mapWidthPercent: await page.locator(".map-stage").evaluate((node) => Number((node.getBoundingClientRect().width / window.innerWidth * 100).toFixed(1))),
    inspectorMode: await page.locator(".context-inspector").evaluate((node) => getComputedStyle(node).position),
    attributionVisible: await page.locator(".maplibregl-ctrl-attrib").isVisible(),
    resolutionRailVisible: await page.locator(".resolution-rail").isVisible(),
  });
  await page.close();
}

await runWorkflow("discover-to-plateau-detail", "?city=maizuru&scene=gap_discovery", async (page, click) => {
  await click(page.locator(".candidate-list button").first());
  await click(page.getByRole("button", { name: /建物.*PLATEAU 3D/ }));
  await waitFor3d(page);
});
await runWorkflow("scenario-a-b-c", "?city=maizuru&scene=scenario_compare", async (page) => {
  const select = page.locator(".scenario-workspace select");
  await select.selectOption("1");
  await select.selectOption("2");
  await select.selectOption("3");
  await page.waitForSelector(".synchronized-maps");
});
await runWorkflow("resilience-normal-to-flood", "?city=maizuru&scene=scenario_compare", async (page, click) => {
  await click(page.getByRole("button", { name: "災害Stress Test" }));
  await page.locator(".scenario-workspace select").selectOption("flood");
  await page.waitForSelector('.product-app[data-scene-preset="hazard_stress"]');
});
await runWorkflow("validation-to-temporal", "?city=maizuru&scene=validation_disagreement", async (page, click) => {
  await page.waitForSelector(".validation-summary");
  await click(page.getByRole("button", { name: "年次差分" }));
  await page.waitForSelector('.product-app[data-scene-preset="temporal_change"]');
});
await runWorkflow("guided-presentation", "?city=maizuru&scene=city_overview", async (page, click) => {
  await click(page.getByRole("button", { name: "4分デモ" }));
  await click(page.locator(".presentation-guide ol button").nth(1));
  await click(page.locator(".presentation-guide ol button").nth(2));
  await waitFor3d(page);
});

opened = await openPage("?city=maizuru&scene=gap_discovery", { width: 1440, height: 900 }, "accessibility");
report.accessibility = await opened.page.evaluate(async () => {
  const visible = (node) => {
    const rect = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  };
  const focusables = [...document.querySelectorAll('button,a[href],select,input,[tabindex]:not([tabindex="-1"])')].filter(visible);
  const duplicateIds = [...document.querySelectorAll("[id]")].map((node) => node.id).filter((id, index, ids) => ids.indexOf(id) !== index);
  const unnamedButtons = [...document.querySelectorAll("button")].filter(visible).filter((node) => !(node.getAttribute("aria-label") || node.textContent?.trim())).length;
  const missingImageAlt = [...document.querySelectorAll("img")].filter((node) => !node.hasAttribute("alt")).length;
  const tabOrder = [];
  document.body.focus();
  for (let index = 0; index < Math.min(20, focusables.length); index += 1) {
    focusables[index].focus();
    tabOrder.push({ tag: document.activeElement?.tagName, label: document.activeElement?.getAttribute("aria-label") || document.activeElement?.textContent?.trim().slice(0, 50) });
  }
  return {
    mainLandmark: Boolean(document.querySelector("main")),
    navigationLandmarks: document.querySelectorAll("nav").length,
    liveRegion: Boolean(document.querySelector('[aria-live="polite"]')),
    mapAccessibleName: document.querySelector(".map-stage")?.getAttribute("aria-label"),
    focusableCount: focusables.length,
    unnamedButtons,
    missingImageAlt,
    duplicateIds: [...new Set(duplicateIds)],
    keyboardFocusSequence: tabOrder,
  };
});
await opened.page.close();

report.consoleErrors = report.consoleErrors.filter((entry, index, entries) => entries.findIndex((item) => item.text === entry.text) === index);
report.localNetworkFailures = report.localNetworkFailures.filter((entry, index, entries) => entries.findIndex((item) => item.status === entry.status && item.url === entry.url) === index);
report.externalNetworkFailures = report.externalNetworkFailures.filter((entry, index, entries) => entries.findIndex((item) => item.status === entry.status && item.url === entry.url) === index);
await writeFile(path.join(outDir, "audit.json"), `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify(report, null, 2));
await browser.close();
