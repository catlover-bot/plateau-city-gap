import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright-core";

process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY = "1";

const parameters = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const argument = process.argv[index];
  if (!argument.startsWith("--")) continue;
  const value = process.argv[index + 1];
  parameters.set(argument, value && !value.startsWith("--") ? value : "true");
  if (value && !value.startsWith("--")) index += 1;
}

const beforeUrl = parameters.get("--before-url") ?? "http://127.0.0.1:4182/plateau-city-gap/";
const afterUrl = parameters.get("--after-url") ?? "http://127.0.0.1:4180/plateau-city-gap/";
const repositoryRoot = path.resolve(process.cwd(), "..");
const outputDirectory = path.resolve(
  repositoryRoot,
  parameters.get("--output") ?? "docs/assets/public-product-language-checkpoint",
);
const baselineCommit = "a365dc04ccbcfad020d8f6ff2cd63db6e7865d60";
const currentCommit = execFileSync("git", ["rev-parse", "HEAD"], {
  cwd: repositoryRoot,
  encoding: "utf8",
}).trim();
const branch = execFileSync("git", ["branch", "--show-current"], {
  cwd: repositoryRoot,
  encoding: "utf8",
}).trim();
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();

const viewportDefinitions = {
  desktop: { width: 1440, height: 900, dpr: 1 },
  compact: { width: 1280, height: 720, dpr: 1 },
  mobile: { width: 390, height: 844, dpr: 1 },
  dpr2: { width: 1440, height: 900, dpr: 2 },
};
const screenshots = [];
const inventories = { before: {}, after: {} };
const diagnostics = [];
const journey = {};

const sha256 = (value) => createHash("sha256").update(value).digest("hex");
const round = (value) => Math.round(value * 10) / 10;

function attachDiagnostics(page, label, baseUrl) {
  const record = { label, page_errors: [], failed_same_origin_requests: [], error_responses: [] };
  page.on("pageerror", (error) => record.page_errors.push(error.message));
  page.on("requestfailed", (request) => {
    try {
      if (new URL(request.url()).origin === new URL(baseUrl).origin) {
        record.failed_same_origin_requests.push({
          url: request.url(),
          error: request.failure()?.errorText ?? "unknown",
        });
      }
    } catch {
      record.failed_same_origin_requests.push({ url: request.url(), error: "invalid-url" });
    }
  });
  page.on("response", (response) => {
    if (response.status() >= 400 && response.url().startsWith(new URL(baseUrl).origin)) {
      record.error_responses.push({ url: response.url(), status: response.status() });
    }
  });
  diagnostics.push(record);
}

async function waitForStep(page, step) {
  await page.locator(`.public-area[data-public-step="${step}"]`).waitFor({
    state: "visible",
    timeout: 120_000,
  });
}

async function waitForCartography(page) {
  await page.locator('.public-area[data-cartography-state="ready"]').waitFor({
    state: "visible",
    timeout: 120_000,
  });
}

async function waitForMap(page, expected = {}) {
  await page.waitForFunction((expectation) => {
    const nodes = [...document.querySelectorAll("[data-public-cartography-ready]")];
    const node = nodes.at(-1);
    if (!node || node.getAttribute("data-public-cartography-ready") !== "true") return false;
    if (node.getAttribute("data-public-pending-sources")) return false;
    if (expectation.story && node.getAttribute("data-public-story") !== expectation.story) return false;
    if (expectation.target && node.getAttribute("data-target-resolution") !== expectation.target) return false;
    if (expectation.radius && node.getAttribute("data-public-area-radius-m") !== String(expectation.radius)) return false;
    return true;
  }, expected, { timeout: 120_000 });
  await page.waitForTimeout(80);
}

async function openPublic(context, baseUrl, label) {
  const page = await context.newPage();
  attachDiagnostics(page, label, baseUrl);
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await waitForStep(page, "intro");
  return page;
}

async function settle(page) {
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(async () => {
    for (const canvas of document.querySelectorAll(".analytical-map-canvas")) {
      canvas.__cityGapMap?.triggerRepaint();
    }
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  await page.waitForTimeout(160);
}

async function capture(page, filename, scene, viewport, dpr, source) {
  await settle(page);
  const target = path.join(outputDirectory, filename);
  await page.screenshot({ path: target, fullPage: false, animations: "disabled", timeout: 180_000 });
  const png = await readFile(target);
  const physicalDimensions = execFileSync("identify", ["-format", "%wx%h", target], { encoding: "utf8" }).trim();
  const record = {
    filename,
    source,
    scene,
    viewport,
    device_scale_factor: dpr,
    physical_dimensions: physicalDimensions,
    bytes: png.length,
    sha256: sha256(png),
    url: page.url(),
    commit: source === "before" ? baselineCommit : currentCommit,
  };
  screenshots.push(record);
  return record;
}

async function inventory(page) {
  return page.evaluate(() => {
    const root = document.querySelector(".public-area");
    if (!root) throw new Error("Public root is missing");
    const roundValue = (value) => Math.round(value * 10) / 10;
    const visible = (element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity) !== 0
        && rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.right > 0
        && rect.top < innerHeight && rect.left < innerWidth;
    };
    const rectOf = (element) => {
      const rect = element.getBoundingClientRect();
      return { x: rect.x, y: rect.y, width: rect.width, height: rect.height, right: rect.right, bottom: rect.bottom };
    };
    const all = [...root.querySelectorAll("*")].filter(visible);
    const controls = all.filter((element) => element.matches("button:not([disabled]), select:not([disabled]), input:not([disabled]), a[href], summary"));
    const primary = all.filter((element) => element.matches(".public-primary"));
    const panel = root.querySelector(".public-area-panel");
    const panelElements = panel ? [...panel.querySelectorAll("*")].filter(visible) : [];
    const surfaceCandidates = panelElements.filter((element) => {
      if (element.matches("button, input, select, a, summary, svg, path, text")) return false;
      const rect = element.getBoundingClientRect();
      if (rect.width < 64 || rect.height < 24) return false;
      const style = getComputedStyle(element);
      const parentStyle = element.parentElement ? getComputedStyle(element.parentElement) : null;
      const border = [style.borderTopWidth, style.borderRightWidth, style.borderBottomWidth, style.borderLeftWidth]
        .some((width) => Number.parseFloat(width) > 0 && style.borderStyle !== "none");
      const shadow = style.boxShadow !== "none";
      const background = style.backgroundColor !== "rgba(0, 0, 0, 0)"
        && style.backgroundColor !== "transparent"
        && style.backgroundColor !== parentStyle?.backgroundColor;
      return border || shadow || background;
    });
    const surfaceSet = new Set(surfaceCandidates);
    const nestedSurfaces = surfaceCandidates.filter((surface) => {
      let ancestor = surface.parentElement;
      while (ancestor && ancestor !== panel) {
        if (surfaceSet.has(ancestor)) return true;
        ancestor = ancestor.parentElement;
      }
      return false;
    });
    const cardSelector = [
      "article",
      "[class*='card']",
      ".public-origin-grid > div",
      ".area-metric-group",
      ".area-unknown-list > li",
      ".area-task-list > li",
    ].join(",");
    const cards = [...new Set(panelElements.filter((element) => element.matches(cardSelector)))];
    const pills = panelElements.filter((element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      const radius = Math.max(...style.borderRadius.split(/\s+/).map(Number.parseFloat).filter(Number.isFinite));
      return element.matches("[class*='badge'], [class*='pill'], [class*='status'], .public-area-label")
        || (rect.height >= 16 && rect.height <= 44 && radius >= rect.height / 2 - 1 && rect.width < 260);
    });
    const shadows = panelElements.filter((element) => getComputedStyle(element).boxShadow !== "none");
    const roundedContainers = panelElements.filter((element) => {
      if (element.matches("button, input, select, a, summary")) return false;
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      const radius = Math.max(...style.borderRadius.split(/\s+/).map(Number.parseFloat).filter(Number.isFinite));
      return rect.width >= 64 && rect.height >= 24 && radius >= 6;
    });
    const bordered = panelElements.filter((element) => {
      if (element.matches("button, input, select, a, summary")) return false;
      const style = getComputedStyle(element);
      return [style.borderTopWidth, style.borderRightWidth, style.borderBottomWidth, style.borderLeftWidth]
        .some((width) => Number.parseFloat(width) > 0 && style.borderStyle !== "none");
    });
    const headings = all.filter((element) => element.matches("h1, h2, h3, h4, h5, h6"));
    const paragraphs = panelElements.filter((element) => element.matches("p"));
    const visibleText = all.map((element) => {
      if (element.children.length > 0) return "";
      return element.textContent?.trim() ?? "";
    }).filter(Boolean).join("\n");
    const technicalTerms = [
      "KNOWN", "UNKNOWN", "EVIDENCE", "TARGET", "VERIFICATION", "Finding", "task",
      "coverage", "version", "rule", "object", "analysis run", "起点", "任意地点",
    ].filter((term) => visibleText.includes(term));
    const map = root.querySelector(".public-map-stage");
    const body = root.querySelector(".public-area-body");
    const mapRect = map ? rectOf(map) : null;
    const bodyRect = body ? rectOf(body) : null;
    const panelRect = panel ? rectOf(panel) : null;
    let covered = 0;
    const columns = 80;
    const rows = 80;
    if (mapRect) {
      for (let column = 0; column < columns; column += 1) {
        for (let row = 0; row < rows; row += 1) {
          const x = mapRect.x + (column + .5) * mapRect.width / columns;
          const y = mapRect.y + (row + .5) * mapRect.height / rows;
          const element = document.elementFromPoint(x, y);
          if (element?.closest(".public-map-caption, .public-map-area-badge, .public-map-legend, .public-map-target-label, .maplibregl-ctrl-group, .map-mode-switch")) covered += 1;
        }
      }
    }
    const mobile = innerWidth <= 900;
    const overlapWidth = mapRect && panelRect ? Math.max(0, Math.min(mapRect.right, panelRect.right) - Math.max(mapRect.x, panelRect.x)) : 0;
    const overlapHeight = mapRect && panelRect ? Math.max(0, Math.min(mapRect.bottom, panelRect.bottom) - Math.max(mapRect.y, panelRect.y)) : 0;
    const section = all.filter((element) => element.matches(".urban-section, [data-urban-section]"));
    const sectionLabels = all.filter((element) => element.matches(".urban-section text, [data-urban-section] text"));
    const sectionLegendItems = all.filter((element) => element.matches(".urban-section [class*='legend'] li, .urban-section [class*='legend'] span, [data-urban-section] [class*='legend'] li"));
    const touchTargetsUnder44 = controls.filter((element) => {
      const rect = element.getBoundingClientRect();
      return (element.matches("button, input, select, summary") || element.classList.contains("public-primary"))
        && (rect.width < 44 || rect.height < 44);
    });
    return {
      viewport: { width: innerWidth, height: innerHeight, device_pixel_ratio: devicePixelRatio },
      step: root.getAttribute("data-public-step"),
      visible_controls: controls.length,
      cards: cards.length,
      measured_surfaces: surfaceCandidates.length,
      nested_surfaces: nestedSurfaces.length,
      pills_badges: pills.length,
      shadows: shadows.length,
      rounded_containers: roundedContainers.length,
      bordered_containers: bordered.length,
      headings: headings.length,
      explanatory_paragraphs: paragraphs.length,
      technical_terms: technicalTerms,
      primary_ctas: primary.length,
      primary_cta_labels: primary.map((element) => element.textContent?.trim() ?? ""),
      map_share_percent: mapRect && bodyRect ? roundValue((mobile ? mapRect.height / bodyRect.height : mapRect.width / bodyRect.width) * 100) : null,
      panel_share_percent: panelRect && bodyRect ? roundValue((mobile ? panelRect.height / bodyRect.height : panelRect.width / bodyRect.width) * 100) : null,
      map_occlusion_percent: mapRect ? roundValue(covered / (columns * rows) * 100) : null,
      map_panel_overlap_px2: roundValue(overlapWidth * overlapHeight),
      horizontal_overflow_px: Math.max(0, document.documentElement.scrollWidth - innerWidth),
      section_count: section.length,
      section_labels: sectionLabels.length,
      section_legend_items: sectionLegendItems.length,
      touch_targets_under_44px: touchTargetsUnder44.length,
    };
  });
}

async function record(page, source, key) {
  inventories[source][key] = await inventory(page);
}

async function clickStation(page, source) {
  const label = source === "before" ? "選んだ駅を起点にする" : "この駅を選ぶ";
  await page.getByRole("button", { name: label, exact: true }).click();
  await waitForStep(page, "radius");
  await waitForMap(page);
}

async function selectRadiusAndOpenResult(page, source) {
  await page.getByRole("button", { name: "800m", exact: true }).click();
  await waitForMap(page, { radius: 800 });
  const label = source === "before" ? "この範囲を調べる" : "この範囲を見る";
  await page.getByRole("button", { name: label, exact: true }).click();
  await waitForStep(page, "result");
  await waitForCartography(page);
  await waitForMap(page, { story: "population-age" });
}

async function advanceToResult(page, source) {
  let clicks = 0;
  await page.getByRole("button", { name: "地図で場所を調べる", exact: true }).click();
  clicks += 1;
  await waitForStep(page, "place");
  await clickStation(page, source);
  clicks += 1;
  await page.getByRole("button", { name: "800m", exact: true }).click();
  clicks += 1;
  await waitForMap(page, { radius: 800 });
  const label = source === "before" ? "この範囲を調べる" : "この範囲を見る";
  await page.getByRole("button", { name: label, exact: true }).click();
  clicks += 1;
  await waitForStep(page, "result");
  await waitForCartography(page);
  await waitForMap(page, { story: "population-age" });
  return clicks;
}

async function selectStory(page, label, story) {
  const group = page.locator(".area-metric-group").filter({ hasText: label }).first();
  await group.locator(".area-story-action").click();
  await page.locator(`.public-area[data-active-story="${story}"]`).waitFor({ timeout: 30_000 });
  await waitForMap(page, { story });
}

async function selectUnknown(page, label) {
  const button = page.locator(".area-unknown-list").getByRole("button", { name: label, exact: true });
  await button.click();
  await page.waitForFunction((name) => [...document.querySelectorAll(".area-unknown-list button")]
    .some((candidate) => candidate.textContent?.trim() === name && candidate.getAttribute("aria-pressed") === "true"), label);
}

async function openTarget(page, source, expectedResolution, expectedKind) {
  const label = source === "before" ? "確認場所を見る" : "確認する場所を見る";
  await page.getByRole("button", { name: label, exact: true }).click();
  await waitForStep(page, "target");
  await page.locator(`.public-map-target-label[data-target-resolution="${expectedResolution}"]`).waitFor({ timeout: 120_000 });
  await waitForMap(page, { target: expectedResolution });
  if (expectedResolution === "exact") {
    await page.waitForFunction((kind) => {
      const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
      const data = map?.getSource("public-target")?._data?.geojson;
      if (!data?.features?.length || data.features.some((feature) => feature.properties?.object_type !== kind)) return false;
      return ["public-target-fill", "public-target-halo", "public-target-line", "public-target-point"]
        .filter((id) => map.getLayer(id))
        .some((id) => map.queryRenderedFeatures(undefined, { layers: [id] }).length > 0);
    }, expectedKind, { timeout: 120_000 });
  }
}

async function advanceMapPointToResult(page, source) {
  await page.getByRole("button", { name: "地図で場所を調べる", exact: true }).click();
  await waitForStep(page, "place");
  const mapPointLabel = source === "before" ? "地図中心を起点にする" : "この場所を選ぶ";
  await page.getByRole("button", { name: mapPointLabel, exact: true }).click();
  await waitForStep(page, "radius");
  await page.getByRole("button", { name: "800m", exact: true }).click();
  const resultLabel = source === "before" ? "この範囲を調べる" : "この範囲を見る";
  await page.getByRole("button", { name: resultLabel, exact: true }).click();
  await waitForStep(page, "result");
  await waitForCartography(page);
  await waitForMap(page);
}

async function captureCore(browser, source, baseUrl, definition, options = {}) {
  const viewport = { width: definition.width, height: definition.height };
  const context = await browser.newContext({ viewport, deviceScaleFactor: definition.dpr, reducedMotion: "reduce" });
  try {
    const page = await openPublic(context, baseUrl, `${source}-${options.prefix ?? "core"}`);
    const suffix = options.suffix ?? "desktop";
    if (options.captureIntro !== false) {
      await record(page, source, `${suffix}.intro`);
      await capture(page, `${source}-01-landing-${suffix}.png`, "landing", viewport, definition.dpr, source);
    }
    await page.getByRole("button", { name: "地図で場所を調べる", exact: true }).click();
    await waitForStep(page, "place");
    await record(page, source, `${suffix}.place`);
    if (options.fullSteps !== false) await capture(page, `${source}-02-place-${suffix}.png`, "place", viewport, definition.dpr, source);
    await clickStation(page, source);
    await record(page, source, `${suffix}.radius`);
    if (options.fullSteps !== false) await capture(page, `${source}-03-radius-${suffix}.png`, "radius", viewport, definition.dpr, source);
    await selectRadiusAndOpenResult(page, source);
    await record(page, source, `${suffix}.result`);
    await capture(page, `${source}-04-population-${suffix}.png`, "population-story", viewport, definition.dpr, source);
    if (options.captureBuilding) {
      await selectStory(page, "建物の使われ方", "building-use");
      await record(page, source, `${suffix}.building-story`);
      await capture(page, `${source}-05-building-${suffix}.png`, "building-story", viewport, definition.dpr, source);
    }
    await selectUnknown(page, "駅から周辺へ実際に歩いて通れる経路");
    await record(page, source, `${suffix}.unknown`);
    await capture(page, `${source}-06-unknown-${suffix}.png`, "unknown", viewport, definition.dpr, source);
    await openTarget(page, source, "exact", "road");
    await record(page, source, `${suffix}.road-target`);
    await capture(page, `${source}-07-road-target-${suffix}.png`, "road-target", viewport, definition.dpr, source);
  } finally {
    await context.close();
  }
}

async function captureTarget(browser, source, baseUrl, definition, config) {
  const viewport = { width: definition.width, height: definition.height };
  const context = await browser.newContext({ viewport, deviceScaleFactor: definition.dpr, reducedMotion: "reduce" });
  try {
    const page = await openPublic(context, baseUrl, `${source}-${config.key}`);
    await advanceToResult(page, source);
    await selectUnknown(page, config.unknown);
    await openTarget(page, source, config.resolution, config.kind);
    await record(page, source, `${config.inventoryKey ?? "desktop"}.${config.key}`);
    await capture(page, `${source}-${config.filename}`, config.key, viewport, definition.dpr, source);
  } finally {
    await context.close();
  }
}

async function captureFallback(browser, source, baseUrl, definition) {
  const viewport = { width: definition.width, height: definition.height };
  const context = await browser.newContext({ viewport, deviceScaleFactor: definition.dpr, reducedMotion: "reduce" });
  try {
    const page = await openPublic(context, baseUrl, `${source}-fallback`);
    await advanceMapPointToResult(page, source);
    await openTarget(page, source, "area_fallback");
    await record(page, source, "desktop.fallback");
    await capture(page, `${source}-10-area-fallback-desktop.png`, "area-fallback", viewport, definition.dpr, source);
  } finally {
    await context.close();
  }
}

async function primaryJourneyClicks(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
  try {
    const page = await openPublic(context, afterUrl, "after-click-count");
    let clicks = await advanceToResult(page, "after");
    await selectUnknown(page, "駅から周辺へ実際に歩いて通れる経路");
    await openTarget(page, "after", "exact", "road");
    clicks += 1;
    return clicks;
  } finally {
    await context.close();
  }
}

await mkdir(outputDirectory, { recursive: true });
const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist", "--use-gl=swiftshader"],
});

try {
  await captureCore(browser, "before", beforeUrl, viewportDefinitions.desktop, { captureBuilding: true });
  await captureCore(browser, "after", afterUrl, viewportDefinitions.desktop, { captureBuilding: true });
  await captureCore(browser, "after", afterUrl, viewportDefinitions.compact, {
    prefix: "compact",
    suffix: "compact",
    captureIntro: false,
    fullSteps: false,
  });
  await captureCore(browser, "after", afterUrl, viewportDefinitions.mobile, {
    prefix: "mobile",
    suffix: "mobile",
    captureIntro: true,
    fullSteps: true,
  });
  await captureCore(browser, "after", afterUrl, viewportDefinitions.dpr2, {
    prefix: "dpr2",
    suffix: "dpr2",
    captureIntro: false,
    fullSteps: false,
  });
  await captureTarget(browser, "after", afterUrl, viewportDefinitions.desktop, {
    key: "building-target",
    filename: "08-building-target-desktop.png",
    unknown: "PLATEAU建物の現在の使われ方",
    resolution: "exact",
    kind: "building",
  });
  await captureTarget(browser, "after", afterUrl, viewportDefinitions.desktop, {
    key: "facility-target",
    filename: "09-facility-reference-desktop.png",
    unknown: "登録施設が現在も利用できるか",
    resolution: "reference_position",
    kind: "facility",
  });
  await captureFallback(browser, "after", afterUrl, viewportDefinitions.desktop);
  journey.primary_clicks = await primaryJourneyClicks(browser);
} finally {
  await browser.close();
}

const ignoredShader = (message) => message.startsWith("Could not compile fragment shader:");
const normalizedDiagnostics = diagnostics.map((record) => ({
  ...record,
  page_errors: record.page_errors.filter((message) => !ignoredShader(message)),
  headless_shader_warning_count: record.page_errors.filter(ignoredShader).length,
  failed_same_origin_requests: record.failed_same_origin_requests.filter((item) => item.error !== "net::ERR_ABORTED"),
}));
const failures = [];
for (const [source, states] of Object.entries(inventories)) {
  for (const [state, value] of Object.entries(states)) {
    if (value.horizontal_overflow_px !== 0) failures.push(`${source}.${state}: horizontal overflow ${value.horizontal_overflow_px}`);
    if (value.map_panel_overlap_px2 !== 0) failures.push(`${source}.${state}: map/panel overlap ${value.map_panel_overlap_px2}`);
    if (source === "after" && value.technical_terms.length) failures.push(`${source}.${state}: technical terms ${value.technical_terms.join(", ")}`);
    if (source === "after" && value.primary_ctas > 1) failures.push(`${source}.${state}: ${value.primary_ctas} primary CTAs`);
  }
}
if (journey.primary_clicks > 5) failures.push(`primary journey requires ${journey.primary_clicks} clicks`);
for (const record of normalizedDiagnostics) {
  if (record.page_errors.length || record.failed_same_origin_requests.length || record.error_responses.length) {
    failures.push(`${record.label}: browser diagnostics are not empty`);
  }
}

const comparableStates = ["desktop.intro", "desktop.place", "desktop.radius", "desktop.result", "desktop.building-story", "desktop.unknown", "desktop.road-target"];
const comparisons = Object.fromEntries(comparableStates.map((state) => {
  const before = inventories.before[state];
  const after = inventories.after[state];
  if (!before || !after) return [state, null];
  const fields = [
    "visible_controls", "cards", "measured_surfaces", "nested_surfaces", "pills_badges", "shadows",
    "rounded_containers", "bordered_containers", "headings", "explanatory_paragraphs", "primary_ctas",
    "map_share_percent", "map_occlusion_percent", "horizontal_overflow_px", "section_labels", "section_legend_items",
  ];
  return [state, Object.fromEntries(fields.map((field) => [field, {
    before: before[field],
    after: after[field],
    delta: typeof before[field] === "number" && typeof after[field] === "number" ? round(after[field] - before[field]) : null,
  }]))];
}));

const manifest = {
  schema_version: "citygap.public-product-language-checkpoint@1",
  generated_at: new Date().toISOString(),
  branch,
  baseline_commit: baselineCommit,
  current_commit: currentCommit,
  urls: { before: beforeUrl, after: afterUrl },
  conditions: {
    browser: "Playwright Chromium",
    reduced_motion: true,
    screenshots_are_production_build_previews: true,
    human_aesthetic_judgment: "not performed; counts are diagnostic evidence only",
    urban_section_decision: "C / advanced_only; Public section screenshots are not applicable",
  },
  viewports: viewportDefinitions,
  journey,
  screenshots,
  inventories,
  comparisons,
  diagnostics: normalizedDiagnostics,
  failures,
  passed: failures.length === 0,
};
await writeFile(path.join(outputDirectory, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");

if (failures.length) {
  throw new Error(`Public product language checkpoint failed:\n${failures.join("\n")}`);
}
process.stdout.write(`${JSON.stringify({ output: outputDirectory, screenshots: screenshots.length, journey, comparisons }, null, 2)}\n`);
