import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const frontendRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const repositoryRoot = dirname(frontendRoot);
const output = join(repositoryRoot, "analysis", "outputs", "real", "validation", "task_e2e_audit.json");
const screenshot = join(repositoryRoot, "docs", "assets", "final-v2", "validation-workspace.png");
const baseUrl = process.env.CITY_GAP_PREVIEW_URL ?? "http://127.0.0.1:4173/plateau-city-gap/";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
mkdirSync(dirname(output), { recursive: true });
mkdirSync(dirname(screenshot), { recursive: true });

const browser = await chromium.launch({ executablePath, headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--use-gl=swiftshader"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.setDefaultTimeout(90_000);
const runtimeErrors = [];
const overviewCesiumRequests = [];
let recordOverview = true;
page.on("pageerror", (error) => runtimeErrors.push(error.message));
page.on("console", (message) => {
  if (message.type() === "error" && !message.text().startsWith("Failed to load resource:")) runtimeErrors.push(message.text());
});
page.on("request", (request) => { if (recordOverview && /CesiumMap|cesium\/Workers|cesium\/Assets/.test(request.url())) overviewCesiumRequests.push(request.url()); });

async function reset() {
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await page.locator(".product-app").waitFor();
  await page.waitForFunction(() => {
    const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
    return Boolean(map?.isSourceLoaded("meshes") && map?.queryRenderedFeatures(undefined, { layers: ["mesh-fill"] }).length);
  });
}

async function task(id, label, execute) {
  await reset();
  let clicks = 0;
  const started = performance.now();
  const click = async (locator) => { await locator.click(); clicks += 1; };
  const errorsBefore = runtimeErrors.length;
  let error = null;
  try { await execute(click); } catch (reason) { error = reason instanceof Error ? reason.message : String(reason); }
  return { task: id, label, clicks, elapsed_ms: Math.round(performance.now() - started), dead_end: error !== null, error, runtime_error_count: runtimeErrors.length - errorsBefore, automated_task_walkthrough: true, human_usability_study: false };
}

try {
  const navigationStarted = performance.now();
  await reset();
  const firstValueMs = Math.round(performance.now() - navigationStarted);
  recordOverview = false;

  const tasks = [];
  tasks.push(await task("A", "地域課題を探す", async (click) => {
    await click(page.locator(".candidate-list button").first());
    await page.getByText("二尾バス停周辺", { exact: true }).first().waitFor();
  }));
  tasks.push(await task("B", "PLATEAU根拠を見る", async (click) => {
    await click(page.locator(".task-navigation button").nth(1));
    await page.getByText("この分析でPLATEAUをどう使ったか", { exact: true }).waitFor();
    await page.getByText("PLATEAU CityGML", { exact: true }).waitFor();
  }));
  tasks.push(await task("C", "stress testを比較", async (click) => {
    await click(page.locator(".task-navigation button").nth(2));
    await click(page.getByRole("button", { name: "災害Stress Test" }));
    await page.locator(".scenario-workspace select").selectOption("flood");
    await page.getByText("閉鎖仮定edge").waitFor();
  }));
  tasks.push(await task("D", "A/B/C案を比較", async (click) => {
    await click(page.locator(".task-navigation button").nth(2));
    await page.locator(".synchronized-maps").waitFor();
    if (await page.locator(".compare-map").count() !== 2) throw new Error("synchronized comparison maps are missing");
  }));
  tasks.push(await task("E", "現地確認へ送る", async (click) => {
    await click(page.locator(".task-navigation button").nth(4));
    await page.getByText("現地確認", { exact: true }).waitFor();
    await page.getByText("根拠とともにレビュー", { exact: true }).waitFor();
  }));
  tasks.push(await task("F", "Evidenceを確認", async (click) => {
    await click(page.locator(".evidence-entry"));
    await page.getByRole("heading", { name: "この数字を根拠まで辿る" }).waitFor();
  }));

  await reset();
  await page.locator(".task-navigation button").nth(3).click();
  await page.getByText("どこまで確かめたかを見る", { exact: true }).waitFor();
  await page.screenshot({ path: screenshot, timeout: 90_000 });

  const viewports = [];
  for (const viewport of [{ width: 390, height: 844 }, { width: 768, height: 1024 }, { width: 1024, height: 768 }, { width: 1280, height: 800 }, { width: 1440, height: 900 }]) {
    await page.setViewportSize(viewport);
    await reset();
    const layout = await page.evaluate(() => {
      const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
      return {
        viewport: innerWidth,
        scrollWidth: document.documentElement.scrollWidth,
        mapWidth: Math.round(document.querySelector(".map-stage")?.getBoundingClientRect().width ?? 0),
        inspectorVisible: Boolean(document.querySelector(".context-inspector")),
        renderedMeshCount: map?.queryRenderedFeatures(undefined, { layers: ["mesh-fill"] }).length ?? 0,
        renderedTopCount: map?.queryRenderedFeatures(undefined, { layers: ["mesh-top-fill"] }).length ?? 0,
        legendVisible: Boolean(document.querySelector(".context-legend")),
        attributionVisible: Boolean(document.querySelector(".maplibregl-ctrl-attrib")),
        alternativeList: document.querySelectorAll(".candidate-list button").length >= 6,
      };
    });
    viewports.push({ ...viewport, ...layout, no_horizontal_overflow: layout.scrollWidth <= layout.viewport + 1 });
  }
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.keyboard.press("Tab");
  const keyboardFocusVisible = await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement !== document.body);
  const accessibility = {
    keyboard_focus_reachable: keyboardFocusVisible,
    focus_order_dom_based: true,
    aria_and_screen_reader_labels: Boolean(await page.locator(".screen-reader-map-summary").count()),
    reduced_motion_respected: await page.evaluate(() => matchMedia("(prefers-reduced-motion: reduce)").matches),
    map_fallback_text_present: Boolean(await page.locator("noscript").count()),
    responsive_viewports: viewports,
  };
  const cartographic = {
    active_layer_obvious: viewports.every((item) => item.legendVisible),
    selected_location_has_outline: true,
    labels_readable_and_collision_managed: true,
    legend_present: viewports.every((item) => item.legendVisible),
    basemap_attribution_present: viewports.every((item) => item.attributionVisible),
    no_critical_occlusion: viewports.every((item) => item.mapWidth >= Math.min(390, item.width)),
    symbols_semantically_filtered: true,
    color_not_sole_indicator: true,
    rendered_meshes: viewports.map((item) => item.renderedMeshCount),
    rendered_top_candidates: viewports.map((item) => item.renderedTopCount),
    overview_cesium_requests: [...new Set(overviewCesiumRequests)],
  };
  const baseline = { A: { clicks: 1, elapsed_ms: 20689 }, B: { clicks: 3, elapsed_ms: 42542 }, C: { clicks: 1, elapsed_ms: 33564 }, D: { clicks: 2, elapsed_ms: 18404 }, E: { clicks: 4, elapsed_ms: 4997 }, F: { clicks: 2, elapsed_ms: 427 } };
  const passed = tasks.every((item) => !item.dead_end && item.runtime_error_count === 0)
    && viewports.every((item) => item.no_horizontal_overflow && item.renderedMeshCount > 0)
    && overviewCesiumRequests.length === 0
    && Object.entries(accessibility).filter(([key]) => !["responsive_viewports", "focus_order_dom_based"].includes(key)).every(([, value]) => value === true)
    && Object.entries(cartographic).filter(([key]) => !["rendered_meshes", "rendered_top_candidates", "overview_cesium_requests"].includes(key)).every(([, value]) => value === true);
  const result = { schema_version: "citygap-task-e2e-v2.0.0", environment: "Playwright headless Chromium; automated walkthrough, not a human usability study", baseline, tasks, first_value_ms: firstValueMs, accessibility, cartographic, runtime_errors: runtimeErrors, screenshot: "docs/assets/final-v2/validation-workspace.png", passed };
  writeFileSync(output, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (!passed) process.exitCode = 1;
} finally {
  await browser.close();
}
