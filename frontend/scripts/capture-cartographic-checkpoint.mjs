import { createHash } from "node:crypto";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright-core";

process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY = "1";

const baseUrl = process.argv[2] ?? "http://127.0.0.1:4175/plateau-city-gap/";
const repositoryRoot = path.resolve(process.cwd(), "..");
const outputDirectoryName = process.argv[3] ?? "cartographic-checkpoint";
const outputDirectory = path.join(repositoryRoot, "docs/assets", outputDirectoryName);
const performanceCheckpoint = outputDirectoryName === "cartographic-performance-checkpoint";
const baselineCommit = "946534c32a965654ee429af01e213cf980b8bac7";
const repositoryHead = execFileSync("git", ["rev-parse", "HEAD"], {
  cwd: repositoryRoot,
  encoding: "utf8",
}).trim();
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const screenshots = [];
const diagnostics = [];
const stateEvidence = {};
const prohibitedCopy = [
  "徒歩10分圏",
  "10分以内に歩ける",
  "walking isochrone",
  "実際に徒歩で到達できる",
  "道路ネットワーク上の徒歩圏",
  "ボーリング",
  "Ground X-Ray",
];
const isHeadlessShaderWarning = (message) => message.startsWith("Could not compile fragment shader:");
const isExpectedCartographyAbort = (item) => item.error === "net::ERR_ABORTED"
  && item.url.includes("/data/cartography/");

const sha256 = (value) => createHash("sha256").update(value).digest("hex");
const round = (value) => Math.round(value * 10) / 10;

function launchCaptureBrowser() {
  return chromium.launch({
    executablePath,
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist", "--use-gl=swiftshader"],
  });
}

async function waitForStep(page, step) {
  await page.locator(`.public-area[data-public-step="${step}"]`).waitFor({
    state: "visible",
    timeout: 120_000,
  });
}

async function waitForCartographyData(page) {
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

function attachDiagnostics(page, label) {
  const record = { label, page_errors: [], failed_same_origin_requests: [], error_responses: [] };
  page.on("pageerror", (error) => record.page_errors.push(error.message));
  page.on("requestfailed", (request) => {
    try {
      if (new URL(request.url()).origin === new URL(baseUrl).origin) {
        record.failed_same_origin_requests.push({ url: request.url(), error: request.failure()?.errorText ?? "unknown" });
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
  return record;
}

async function capture(page, filename, scene, viewport, dpr = 1) {
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(async () => {
    for (const canvas of document.querySelectorAll(".analytical-map-canvas")) {
      canvas.__cityGapMap?.triggerRepaint();
    }
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  });
  await page.waitForTimeout(180);
  const target = path.join(outputDirectory, filename);
  await page.screenshot({ path: target, fullPage: false, animations: "disabled", timeout: 180_000 });
  const png = await readFile(target);
  const dimensions = execFileSync("identify", ["-format", "%wx%h", target], { encoding: "utf8" }).trim();
  const record = {
    filename,
    scene,
    viewport,
    device_scale_factor: dpr,
    physical_dimensions: dimensions,
    bytes: png.length,
    sha256: sha256(png),
    url: page.url(),
  };
  const existing = screenshots.findIndex((item) => item.filename === filename);
  if (existing >= 0) screenshots[existing] = record;
  else screenshots.push(record);
  return record;
}

function mapPixelStandardDeviation(filename, mapRect, dpr = 1) {
  const target = path.join(outputDirectory, filename);
  const crop = `${Math.round(mapRect.width * dpr)}x${Math.round(mapRect.height * dpr)}+${Math.round(mapRect.x * dpr)}+${Math.round(mapRect.y * dpr)}`;
  return Number(execFileSync("convert", [
    target,
    "-crop", crop,
    "-colorspace", "Gray",
    "-format", "%[fx:standard_deviation]",
    "info:",
  ], { encoding: "utf8" }).trim());
}

function targetColorPixelCount(filename, mapRect, dpr = 1) {
  const target = path.join(outputDirectory, filename);
  const cropX = Math.round((mapRect.x + mapRect.width * .3) * dpr);
  const cropY = Math.round((mapRect.y + mapRect.height * .24) * dpr);
  const cropWidth = Math.round(mapRect.width * .4 * dpr);
  const cropHeight = Math.round(mapRect.height * .38 * dpr);
  const histogram = execFileSync("convert", [
    target,
    "-crop", `${cropWidth}x${cropHeight}+${cropX}+${cropY}`,
    "-format", "%c",
    "histogram:info:-",
  ], { encoding: "utf8" });
  return [...histogram.matchAll(/^\s*(\d+):.*#6B4C7D/gim)]
    .reduce((sum, match) => sum + Number(match[1]), 0);
}

async function stateMetrics(page) {
  return page.evaluate(() => {
    const visible = (element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden"
        && rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.right > 0
        && rect.top < innerHeight && rect.left < innerWidth;
    };
    const rectOf = (selector) => {
      const element = document.querySelector(selector);
      if (!element) return null;
      const rect = element.getBoundingClientRect();
      return { x: rect.x, y: rect.y, width: rect.width, height: rect.height, right: rect.right, bottom: rect.bottom };
    };
    const body = rectOf(".public-area-body");
    const map = rectOf(".public-map-stage");
    const panel = rectOf(".public-area-panel");
    if (!body || !map || !panel) throw new Error("Public layout regions are missing");
    const mobile = innerWidth <= 900;
    let covered = 0;
    const columns = 80;
    const rows = 80;
    for (let column = 0; column < columns; column += 1) {
      for (let row = 0; row < rows; row += 1) {
        const x = map.x + (column + 0.5) * map.width / columns;
        const y = map.y + (row + 0.5) * map.height / rows;
        const element = document.elementFromPoint(x, y);
        if (element?.closest(".public-map-caption, .public-map-area-badge, .public-map-legend, .public-map-target-label, .maplibregl-ctrl-group, .map-mode-switch")) covered += 1;
      }
    }
    const mapStates = [...document.querySelectorAll("[data-public-cartography-ready]")];
    const mapState = mapStates.at(-1) ?? null;
    const controls = [...document.querySelectorAll("button:not([disabled]), select:not([disabled]), input:not([disabled]), a[href], summary")].filter(visible);
    const productControls = controls.filter((element) => !element.closest(".maplibregl-ctrl-attrib"));
    const attributionLinks = controls.filter((element) => element.closest(".maplibregl-ctrl-attrib"));
    const activeStories = [...document.querySelectorAll('.area-story-action[aria-pressed="true"]')].filter(visible);
    const overlapWidth = Math.max(0, Math.min(map.right, panel.right) - Math.max(map.x, panel.x));
    const overlapHeight = Math.max(0, Math.min(map.bottom, panel.bottom) - Math.max(map.y, panel.y));
    const legend = document.querySelector(".public-map-legend");
    const targetLabel = document.querySelector(".public-map-target-label");
    return {
      viewport: { width: innerWidth, height: innerHeight },
      step: document.querySelector(".public-area")?.getAttribute("data-public-step"),
      cartography_state: document.querySelector(".public-area")?.getAttribute("data-cartography-state"),
      active_story: document.querySelector(".public-area")?.getAttribute("data-active-story"),
      map_render_ready: mapState?.getAttribute("data-public-cartography-ready"),
      map_render_state: mapState?.getAttribute("data-map-render-state"),
      basemap_error: Boolean(mapState?.getAttribute("data-basemap-error")),
      area_visible: mapState?.getAttribute("data-public-area-visible"),
      area_radius_m: mapState?.getAttribute("data-public-area-radius-m"),
      target_resolution: mapState?.getAttribute("data-target-resolution"),
      pending_sources: mapState?.getAttribute("data-public-pending-sources") ?? null,
      map_share_percent: Math.round((mobile ? map.height / body.height : map.width / body.width) * 1000) / 10,
      panel_share_percent: Math.round((mobile ? panel.height / body.height : panel.width / body.width) * 1000) / 10,
      map_occlusion_percent: Math.round(covered / (columns * rows) * 1000) / 10,
      map_panel_overlap_px2: Math.round(overlapWidth * overlapHeight * 10) / 10,
      horizontal_overflow_px: Math.max(0, document.documentElement.scrollWidth - innerWidth),
      visible_actionable_controls: productControls.length,
      visible_attribution_links: attributionLinks.length,
      active_story_action_count: activeStories.length,
      legend: legend ? {
        title: legend.querySelector(":scope > strong")?.textContent?.trim() ?? "",
        item_count: legend.querySelectorAll(":scope > span").length,
        note: legend.querySelector(":scope > small")?.textContent?.trim() ?? "",
      } : null,
      target_label: targetLabel?.querySelector("strong")?.textContent?.trim() ?? null,
      target_label_resolution: targetLabel?.getAttribute("data-target-resolution") ?? null,
      three_d_button_count: [...document.querySelectorAll("button")].filter((button) => button.textContent?.includes("3Dで周辺を見る") && visible(button)).length,
      reduced_motion: matchMedia("(prefers-reduced-motion: reduce)").matches,
      map,
      panel,
    };
  });
}

async function accessibilityAudit(page) {
  return page.evaluate(() => {
    const visible = (element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
    };
    const accessibleName = (element) => {
      const aria = element.getAttribute("aria-label");
      if (aria?.trim()) return aria.trim();
      const labelledBy = element.getAttribute("aria-labelledby");
      if (labelledBy) {
        const text = labelledBy.split(/\s+/).map((id) => document.getElementById(id)?.textContent ?? "").join(" ").trim();
        if (text) return text;
      }
      if (element instanceof HTMLInputElement || element instanceof HTMLSelectElement) {
        const label = element.id ? document.querySelector(`label[for="${CSS.escape(element.id)}"]`) : null;
        if (label?.textContent?.trim()) return label.textContent.trim();
      }
      return element.textContent?.trim() ?? "";
    };
    const interactive = [...document.querySelectorAll("button, select, input, a[href], summary")].filter(visible);
    const unnamed = interactive.filter((element) => !accessibleName(element));
    const ids = [...document.querySelectorAll("[id]")].map((element) => element.id);
    const duplicateIds = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
    const critical = [];
    if (!document.querySelector("header")) critical.push("header landmark missing");
    if (!document.querySelector("main")) critical.push("main landmark missing");
    if ([...document.querySelectorAll("h1")].filter(visible).length !== 1) critical.push("visible h1 count is not one");
    if (unnamed.length) critical.push(`unnamed controls ${unnamed.length}`);
    if (duplicateIds.length) critical.push(`duplicate ids ${duplicateIds.join(",")}`);
    if ([...document.querySelectorAll("img")].some((image) => !image.hasAttribute("alt"))) critical.push("image without alt");
    return {
      critical,
      visible_interactive_count: interactive.length,
      unnamed_control_count: unnamed.length,
      duplicate_ids: duplicateIds,
      visible_h1_count: [...document.querySelectorAll("h1")].filter(visible).length,
    };
  });
}

async function keyboardAudit(page) {
  await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
  const order = [];
  const failures = [];
  for (let index = 0; index < 36; index += 1) {
    await page.keyboard.press("Tab");
    const focused = await page.evaluate(() => {
      const element = document.activeElement;
      if (!(element instanceof HTMLElement)) return null;
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return {
        label: element.getAttribute("aria-label") || element.textContent?.trim() || element.tagName,
        interactive: element.matches("button, select, input, a[href], summary, [tabindex]:not([tabindex='-1'])"),
        visible: rect.width > 0 && rect.height > 0 && rect.top < innerHeight && rect.bottom > 0,
        focus_visible: style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0,
      };
    });
    if (!focused) continue;
    if (!focused.interactive) continue;
    order.push(focused.label);
    if (!focused.visible || !focused.focus_visible) failures.push(focused);
  }
  return { order, failures };
}

async function openPublic(context, label, { degradeBasemap = false } = {}) {
  const page = await context.newPage();
  attachDiagnostics(page, label);
  if (degradeBasemap) {
    await page.route("**/*", async (route) => {
      if (route.request().url().includes("cyberjapandata.gsi.go.jp")) await route.abort("failed");
      else await route.continue();
    });
  }
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await waitForStep(page, "intro");
  return page;
}

async function startStationArea(page, radiusLabel) {
  let clicks = 0;
  await page.getByRole("button", { name: "地図で場所を調べる", exact: true }).click();
  clicks += 1;
  await waitForStep(page, "place");
  await page.getByRole("button", { name: "この駅を選ぶ", exact: true }).click();
  clicks += 1;
  await waitForStep(page, "radius");
  await waitForMap(page);
  const startedAt = Date.now();
  await page.getByRole("button", { name: radiusLabel, exact: true }).click();
  clicks += 1;
  const radiusM = radiusLabel === "1km" ? 1_000 : Number.parseInt(radiusLabel, 10);
  await waitForMap(page, { radius: radiusM });
  const areaRecognitionMs = Date.now() - startedAt;
  await page.getByRole("button", { name: "この範囲を見る", exact: true }).click();
  clicks += 1;
  await waitForStep(page, "result");
  return { clicks, areaRecognitionMs };
}

async function startMapPointArea(page, radiusLabel = "800m") {
  await page.getByRole("button", { name: "地図で場所を調べる", exact: true }).click();
  await waitForStep(page, "place");
  await page.getByRole("button", { name: "地図中心を起点にする", exact: true }).click();
  await waitForStep(page, "radius");
  await page.getByRole("button", { name: radiusLabel, exact: true }).click();
  await page.getByRole("button", { name: "この範囲を見る", exact: true }).click();
  await waitForStep(page, "result");
}

async function selectStory(page, label, expectedId) {
  const section = page.locator(".area-metric-group").filter({ hasText: label }).first();
  const button = section.locator(".area-story-action");
  const startedAt = Date.now();
  await button.click();
  await page.locator(`.public-area[data-active-story="${expectedId}"]`).waitFor({ timeout: 30_000 });
  await waitForMap(page, { story: expectedId });
  const renderedLayer = expectedId === "building-use"
    ? { source: "public-buildings", layer: "public-buildings-fill" }
    : expectedId === "urban-planning"
      ? { source: "public-planning", layer: "public-planning-fill" }
      : null;
  if (renderedLayer) {
    await page.waitForFunction((expected) => {
      const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
      if (!map?.getLayer(expected.layer) || !map.isSourceLoaded(expected.source)) return false;
      return map.queryRenderedFeatures(undefined, { layers: [expected.layer] }).length > 0;
    }, renderedLayer, { timeout: 120_000 });
    await waitForMap(page, { story: expectedId });
  }
  return Date.now() - startedAt;
}

async function selectUnknown(page, name) {
  const button = page.locator(".area-unknown-list").getByRole("button", { name, exact: true });
  await button.click();
  await page.waitForFunction((label) => [...document.querySelectorAll(".area-unknown-list button")]
    .some((candidate) => candidate.textContent?.trim() === label && candidate.getAttribute("aria-pressed") === "true"), name, { timeout: 30_000 });
}

async function openTarget(page, resolution, expectedKind) {
  const startedAt = Date.now();
  await page.getByRole("button", { name: "確認する場所を見る", exact: true }).click();
  await waitForStep(page, "target");
  await page.locator(`.public-map-target-label[data-target-resolution="${resolution}"]`).waitFor({ timeout: 120_000 });
  await waitForMap(page, { target: resolution });
  let readyMs = Date.now() - startedAt;
  if (resolution !== "area_fallback") {
    await page.waitForFunction((kind) => {
      const canvas = document.querySelector(".analytical-map-canvas");
      const map = canvas?.__cityGapMap;
      if (!map) return false;
      const data = map.getSource("public-target")?._data?.geojson;
      if (!data?.features?.length || data.features.some((feature) => feature.properties?.object_type !== kind)) return false;
      return ["public-target-fill", "public-target-halo", "public-target-line", "public-target-point"]
        .filter((id) => map.getLayer(id))
        .some((id) => map.queryRenderedFeatures(undefined, { layers: [id] }).length > 0);
    }, expectedKind, { timeout: 120_000 });
    readyMs = Date.now() - startedAt;
  }
  return readyMs;
}

async function captureIsolatedTarget({
  label,
  viewport,
  unknownName,
  resolution,
  kind,
  filename,
  scene,
  minimumMapDeviation,
  dpr = 1,
}) {
  const attempts = [];
  for (let attempt = 1; attempt <= 5; attempt += 1) {
    const isolatedBrowser = await launchCaptureBrowser();
    try {
      const context = await isolatedBrowser.newContext({ viewport, deviceScaleFactor: dpr, reducedMotion: "reduce" });
      const page = await openPublic(context, `${label}-attempt-${attempt}`);
      await startStationArea(page, "800m");
      await waitForCartographyData(page);
      await selectUnknown(page, unknownName);
      await openTarget(page, resolution, kind);
      const state = await stateMetrics(page);
      await capture(page, filename, scene, viewport, dpr);
      const mapStandardDeviation = mapPixelStandardDeviation(filename, state.map, dpr);
      const targetColorPixels = targetColorPixelCount(filename, state.map, dpr);
      const diagnostic = diagnostics.at(-1);
      const headlessShaderWarningCount = diagnostic?.page_errors.filter(isHeadlessShaderWarning).length ?? 0;
      const diagnosticCount = (diagnostic?.page_errors.filter((message) => !isHeadlessShaderWarning(message)).length ?? 0)
        + (diagnostic?.failed_same_origin_requests.filter((item) => !isExpectedCartographyAbort(item)).length ?? 0)
        + (diagnostic?.error_responses.length ?? 0);
      attempts.push({
        attempt,
        map_standard_deviation: mapStandardDeviation,
        target_color_pixels: targetColorPixels,
        map_render_state: state.map_render_state,
        basemap_error: state.basemap_error,
        diagnostic_count: diagnosticCount,
        headless_shader_warning_count: headlessShaderWarningCount,
      });
      await context.close();
      if (mapStandardDeviation >= minimumMapDeviation && targetColorPixels >= 100 * dpr * dpr && diagnosticCount === 0) {
        return { attempts, map_standard_deviation: mapStandardDeviation, target_color_pixels: targetColorPixels };
      }
      diagnostics.pop();
    } finally {
      await isolatedBrowser.close();
    }
  }
  throw new Error(`${label} remained visually blank after ${attempts.length} isolated attempts: ${JSON.stringify(attempts)}`);
}

async function returnToResult(page) {
  await page.locator(".public-area-actions").getByRole("button", { name: "戻る", exact: true }).click();
  await waitForStep(page, "result");
  await waitForMap(page);
}

async function publicBoundaryAudit(page) {
  const bodyText = await page.locator("body").innerText();
  return {
    prohibited_copy: prohibitedCopy.filter((copy) => bodyText.includes(copy)),
    field_evidence_inputs: await page.locator(".area-task-flow input, .area-task-flow textarea, .area-task-flow select").count(),
    visible_internal_ids: await page.locator(".area-target-source code:visible").count(),
    photo_copy: bodyText.includes("写真"),
    gps_copy: bodyText.includes("GPS"),
    review_copy: bodyText.includes("レビュー結果"),
  };
}

async function validateProvenance() {
  const manifestPath = path.join(repositoryRoot, "frontend/public/data/cartography/manifest.json");
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  const artifacts = {};
  for (const [name, artifact] of Object.entries(manifest.artifacts)) {
    const artifactPath = path.join(repositoryRoot, "frontend/public/data/cartography", artifact.path);
    const content = await readFile(artifactPath);
    const collection = JSON.parse(content.toString("utf8"));
    artifacts[name] = {
      expected_sha256: artifact.sha256,
      actual_sha256: sha256(content),
      expected_feature_count: artifact.feature_count,
      actual_feature_count: collection.features.length,
      geometry_types: [...new Set(collection.features.map((feature) => feature.geometry?.type).filter(Boolean))].sort(),
    };
  }
  const valid = manifest.artifact_kind === "display_derivative"
    && manifest.source?.version && manifest.source?.path && manifest.source?.sha256
    && manifest.rule_version && manifest.scope?.area_content_sha256
    && Object.values(artifacts).every((artifact) => artifact.expected_sha256 === artifact.actual_sha256
      && artifact.expected_feature_count === artifact.actual_feature_count)
    && manifest.target_ids.every((id) => [
      ...(manifest.resolved_target_ids.buildings ?? []),
      ...(manifest.resolved_target_ids.roads ?? []),
    ].includes(id));
  return {
    valid: Boolean(valid),
    source: manifest.source,
    rule_version: manifest.rule_version,
    scope: manifest.scope,
    target_ids: manifest.target_ids,
    resolved_target_ids: manifest.resolved_target_ids,
    prohibitions: manifest.prohibitions,
    artifacts,
  };
}

function pixelDifference(beforePath, afterPath, width, height) {
  const result = spawnSync("compare", ["-metric", "AE", beforePath, afterPath, "null:"], { encoding: "utf8" });
  const pixels = Number((result.stderr || result.stdout).trim().split(/\s+/).at(-1));
  return {
    absolute_error_pixels: pixels,
    total_pixels: width * height,
    changed_pixel_percent: round(pixels / (width * height) * 100),
  };
}

await mkdir(outputDirectory, { recursive: true });
const baselineDesktop = execFileSync("git", ["show", `${baselineCommit}:docs/assets/public-first-run-ux/03-known-unknown-desktop.png`], { cwd: repositoryRoot });
const baselineMobile = execFileSync("git", ["show", `${baselineCommit}:docs/assets/public-first-run-ux/08-known-unknown-mobile.png`], { cwd: repositoryRoot });
await writeFile(path.join(outputDirectory, "00-before-known-unknown-desktop.png"), baselineDesktop);
await writeFile(path.join(outputDirectory, "00-before-known-unknown-mobile.png"), baselineMobile);
screenshots.push({ filename: "00-before-known-unknown-desktop.png", scene: "before-desktop", viewport: { width: 1440, height: 900 }, device_scale_factor: 1, physical_dimensions: "1440x900", bytes: baselineDesktop.length, sha256: sha256(baselineDesktop), source_commit: baselineCommit });
screenshots.push({ filename: "00-before-known-unknown-mobile.png", scene: "before-mobile", viewport: { width: 390, height: 844 }, device_scale_factor: 1, physical_dimensions: "390x844", bytes: baselineMobile.length, sha256: sha256(baselineMobile), source_commit: baselineCommit });

const browser = await launchCaptureBrowser();

try {
  const fmrSamples = [];
  for (let index = 0; index < 5; index += 1) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
    await waitForStep(page, "intro");
    fmrSamples.push(await page.evaluate(() => Math.round(performance.now())));
    await context.close();
  }
  const sortedFmr = [...fmrSamples].sort((left, right) => left - right);
  const fmrMedian = sortedFmr[Math.floor(sortedFmr.length / 2)];

  const desktopViewport = { width: 1440, height: 900 };
  const desktop = await browser.newContext({ viewport: desktopViewport, reducedMotion: "reduce" });
  const page = await openPublic(desktop, "desktop-main");
  stateEvidence.landing = await stateMetrics(page);
  await capture(page, "01-landing-desktop.png", "landing", desktopViewport);
  const keyboard = await keyboardAudit(page);
  const journey = await startStationArea(page, "800m");
  const loadingStateAfterJourney = await page.locator(".public-area").getAttribute("data-cartography-state");
  await waitForCartographyData(page);
  await waitForMap(page);
  stateEvidence.population_age = { ...(await stateMetrics(page)), switch_ms: 0 };
  await capture(page, "02-area-800m-population-age.png", "area-800m-population-age", desktopViewport);

  const buildingUseSwitchMs = await selectStory(page, "建物の使われ方", "building-use");
  stateEvidence.building_use = { ...(await stateMetrics(page)), switch_ms: buildingUseSwitchMs };
  await capture(page, "03-story-building-use.png", "story-building-use", desktopViewport);
  const establishmentsSwitchMs = await selectStory(page, "事業所", "establishments");
  stateEvidence.establishments = { ...(await stateMetrics(page)), switch_ms: establishmentsSwitchMs };
  await capture(page, "04-story-establishments-aggregate.png", "story-establishments-aggregate", desktopViewport);
  const urbanPlanningSwitchMs = await selectStory(page, "都市計画", "urban-planning");
  stateEvidence.urban_planning = { ...(await stateMetrics(page)), switch_ms: urbanPlanningSwitchMs };
  await capture(page, "05-story-urban-planning.png", "story-urban-planning", desktopViewport);
  const transportSwitchMs = await selectStory(page, "交通", "transport");
  stateEvidence.transport = { ...(await stateMetrics(page)), switch_ms: transportSwitchMs };
  await capture(page, "06-story-transport.png", "story-transport", desktopViewport);

  await selectUnknown(page, "駅から周辺へ実際に歩いて通れる経路");
  stateEvidence.unknown_road = await stateMetrics(page);
  await capture(page, "07-unknown-road-highlight.png", "unknown-road-highlight", desktopViewport);
  const roadCameraMs = await openTarget(page, "exact", "road");
  stateEvidence.exact_road_target = { ...(await stateMetrics(page)), camera_ms: roadCameraMs };
  await capture(page, "08-target-road-exact.png", "target-road-exact", desktopViewport);

  await returnToResult(page);
  await selectUnknown(page, "PLATEAU建物の現在の使われ方");
  const buildingCameraMs = await openTarget(page, "exact", "building");
  stateEvidence.exact_building_target = { ...(await stateMetrics(page)), camera_ms: buildingCameraMs };
  await capture(page, "09-target-building-exact.png", "target-building-exact", desktopViewport);

  await returnToResult(page);
  await selectUnknown(page, "登録施設が現在も利用できるか");
  const facilityCameraMs = await openTarget(page, "reference_position", "facility");
  stateEvidence.facility_reference = { ...(await stateMetrics(page)), camera_ms: facilityCameraMs };
  await capture(page, "10-target-facility-reference.png", "target-facility-reference", desktopViewport);
  const boundaryAudit = await publicBoundaryAudit(page);
  const accessibility = await accessibilityAudit(page);
  await desktop.close();

  const targetVisualSignals = {
    road: await captureIsolatedTarget({
      label: "isolated-road-target",
      viewport: desktopViewport,
      unknownName: "駅から周辺へ実際に歩いて通れる経路",
      resolution: "exact",
      kind: "road",
      filename: "08-target-road-exact.png",
      scene: "target-road-exact",
      minimumMapDeviation: .04,
    }),
    building: await captureIsolatedTarget({
      label: "isolated-building-target",
      viewport: desktopViewport,
      unknownName: "PLATEAU建物の現在の使われ方",
      resolution: "exact",
      kind: "building",
      filename: "09-target-building-exact.png",
      scene: "target-building-exact",
      minimumMapDeviation: .04,
    }),
    facility: await captureIsolatedTarget({
      label: "isolated-facility-target",
      viewport: desktopViewport,
      unknownName: "登録施設が現在も利用できるか",
      resolution: "reference_position",
      kind: "facility",
      filename: "10-target-facility-reference.png",
      scene: "target-facility-reference",
      minimumMapDeviation: .04,
    }),
  };

  const radius500Browser = await launchCaptureBrowser();
  let journey500;
  try {
    const radius500 = await radius500Browser.newContext({ viewport: desktopViewport, reducedMotion: "reduce" });
    const radius500Page = await openPublic(radius500, "radius-500");
    journey500 = await startStationArea(radius500Page, "500m");
    await waitForCartographyData(radius500Page);
    await waitForMap(radius500Page);
    stateEvidence.area_500m = await stateMetrics(radius500Page);
    await capture(radius500Page, "11-area-500m.png", "area-500m", desktopViewport);
    await radius500.close();
  } finally {
    await radius500Browser.close();
  }

  const radius1kmBrowser = await launchCaptureBrowser();
  let journey1km;
  try {
    const radius1km = await radius1kmBrowser.newContext({ viewport: desktopViewport, reducedMotion: "reduce" });
    const radius1kmPage = await openPublic(radius1km, "radius-1km");
    journey1km = await startStationArea(radius1kmPage, "1km");
    await waitForCartographyData(radius1kmPage);
    await waitForMap(radius1kmPage);
    stateEvidence.area_1km = await stateMetrics(radius1kmPage);
    await capture(radius1kmPage, "12-area-1km.png", "area-1km", desktopViewport);
    await radius1km.close();
  } finally {
    await radius1kmBrowser.close();
  }

  const fallbackBrowser = await launchCaptureBrowser();
  try {
    const fallback = await fallbackBrowser.newContext({ viewport: desktopViewport, reducedMotion: "reduce" });
    const fallbackPage = await openPublic(fallback, "area-fallback");
    await startMapPointArea(fallbackPage);
    await waitForCartographyData(fallbackPage);
    await waitForMap(fallbackPage);
    await openTarget(fallbackPage, "area_fallback");
    stateEvidence.area_fallback = await stateMetrics(fallbackPage);
    await capture(fallbackPage, "13-target-area-fallback.png", "target-area-fallback", desktopViewport);
    await fallback.close();
  } finally {
    await fallbackBrowser.close();
  }

  const degradedBrowser = await launchCaptureBrowser();
  try {
    const degraded = await degradedBrowser.newContext({ viewport: desktopViewport, reducedMotion: "reduce" });
    const degradedPage = await openPublic(degraded, "basemap-degraded", { degradeBasemap: true });
    await startStationArea(degradedPage, "800m");
    await waitForCartographyData(degradedPage);
    await selectStory(degradedPage, "建物の使われ方", "building-use");
    stateEvidence.basemap_degraded = await stateMetrics(degradedPage);
    await capture(degradedPage, "14-basemap-degraded-local-vectors.png", "basemap-degraded", desktopViewport);
    await degraded.close();
  } finally {
    await degradedBrowser.close();
  }

  const mobileViewport = { width: 390, height: 844 };
  const mobileBrowser = await launchCaptureBrowser();
  let mobileAccessibility;
  try {
    const mobile = await mobileBrowser.newContext({ viewport: mobileViewport, reducedMotion: "reduce" });
    const mobilePage = await openPublic(mobile, "mobile");
    await startStationArea(mobilePage, "800m");
    await waitForCartographyData(mobilePage);
    await selectStory(mobilePage, "建物の使われ方", "building-use");
    stateEvidence.mobile_result = await stateMetrics(mobilePage);
    await capture(mobilePage, "15-mobile-result.png", "mobile-result", mobileViewport);
    await selectUnknown(mobilePage, "駅から周辺へ実際に歩いて通れる経路");
    await openTarget(mobilePage, "exact", "road");
    stateEvidence.mobile_target = await stateMetrics(mobilePage);
    await capture(mobilePage, "16-mobile-target-road-exact.png", "mobile-target-road-exact", mobileViewport);
    mobileAccessibility = await accessibilityAudit(mobilePage);
    await mobile.close();
  } finally {
    await mobileBrowser.close();
  }
  targetVisualSignals.mobile_road = await captureIsolatedTarget({
    label: "isolated-mobile-road-target",
    viewport: mobileViewport,
    unknownName: "駅から周辺へ実際に歩いて通れる経路",
    resolution: "exact",
    kind: "road",
    filename: "16-mobile-target-road-exact.png",
    scene: "mobile-target-road-exact",
    minimumMapDeviation: .04,
    dpr: 2,
  });

  const retinaViewport = { width: 1280, height: 720 };
  const retinaBrowser = await launchCaptureBrowser();
  try {
    const retina = await retinaBrowser.newContext({ viewport: retinaViewport, deviceScaleFactor: 2, reducedMotion: "reduce" });
    const retinaPage = await openPublic(retina, "retina-dpr2");
    await startStationArea(retinaPage, "800m");
    await waitForCartographyData(retinaPage);
    await openTarget(retinaPage, "exact", "road");
    stateEvidence.retina_target = await stateMetrics(retinaPage);
    await capture(retinaPage, "17-retina-dpr2-target-road.png", "retina-dpr2-target-road", retinaViewport, 2);
    await retina.close();
  } finally {
    await retinaBrowser.close();
  }

  const routeBrowser = await launchCaptureBrowser();
  let legacyM3;
  let advanced;
  try {
    const routeContext = await routeBrowser.newContext({ viewport: { width: 1280, height: 720 } });
    const routePage = await routeContext.newPage();
    await routePage.goto(`${baseUrl}?journey=m3`, { waitUntil: "domcontentloaded", timeout: 90_000 });
    await routePage.locator('.investigation-landing[data-experience="landing"]').waitFor({ timeout: 120_000 });
    legacyM3 = true;
    await routePage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
    await waitForStep(routePage, "intro");
    await routePage.getByRole("button", { name: "詳細分析", exact: true }).click();
    await routePage.locator('[data-experience="advanced"]').waitFor({ timeout: 120_000 });
    advanced = true;
    await routeContext.close();
  } finally {
    await routeBrowser.close();
  }

  const provenance = await validateProvenance();
  const baselineDesktopPath = path.join(outputDirectory, "00-before-known-unknown-desktop.png");
  const baselineMobilePath = path.join(outputDirectory, "00-before-known-unknown-mobile.png");
  const afterDesktopPath = path.join(outputDirectory, "02-area-800m-population-age.png");
  const afterMobilePath = path.join(outputDirectory, "15-mobile-result.png");
  const beforeAfter = {
    desktop: pixelDifference(baselineDesktopPath, afterDesktopPath, 1440, 900),
    mobile: pixelDifference(baselineMobilePath, afterMobilePath, 390, 844),
    baseline_commit: baselineCommit,
  };
  const c5Directory = path.join(repositoryRoot, "docs/assets/cartographic-checkpoint");
  const c5VisualRegression = [];
  if (performanceCheckpoint) {
    for (const screenshot of screenshots.filter((item) => !item.filename.startsWith("00-before-"))) {
      const beforePath = path.join(c5Directory, screenshot.filename);
      const afterPath = path.join(outputDirectory, screenshot.filename);
      try {
        const dimensions = execFileSync("identify", ["-format", "%w %h", afterPath], { encoding: "utf8" })
          .trim().split(/\s+/).map(Number);
        await readFile(beforePath);
        c5VisualRegression.push({
          scene: screenshot.scene,
          c5_path: path.relative(repositoryRoot, beforePath),
          after_path: path.relative(repositoryRoot, afterPath),
          ...pixelDifference(beforePath, afterPath, dimensions[0], dimensions[1]),
        });
      } catch {
        c5VisualRegression.push({ scene: screenshot.scene, comparison: "unavailable" });
      }
    }
  }

  const criticalDiagnostics = diagnostics.flatMap((entry) => [
    ...entry.page_errors.filter((message) => !isHeadlessShaderWarning(message)),
    ...entry.failed_same_origin_requests
      .filter((item) => !isExpectedCartographyAbort(item))
      .map((item) => `${entry.label}: ${JSON.stringify(item)}`),
    ...entry.error_responses.map((item) => `${entry.label}: ${JSON.stringify(item)}`),
  ]);
  const headlessShaderWarnings = diagnostics.flatMap((entry) => entry.page_errors
    .filter(isHeadlessShaderWarning)
    .map((message) => ({ label: entry.label, message })));
  const expectedRequestCancellations = diagnostics.flatMap((entry) => entry.failed_same_origin_requests
    .filter(isExpectedCartographyAbort)
    .map((item) => ({ label: entry.label, ...item })));
  const allStates = Object.values(stateEvidence);
  const storyStates = ["population_age", "building_use", "establishments", "urban_planning", "transport"].map((key) => stateEvidence[key]);
  const expectedStories = ["population-age", "building-use", "establishments", "urban-planning", "transport"];
  const gateFailures = [];
  if (fmrMedian > 3_000) gateFailures.push(`FMR median ${fmrMedian}ms`);
  if (stateEvidence.area_500m.area_radius_m !== "500" || stateEvidence.population_age.area_radius_m !== "800" || stateEvidence.area_1km.area_radius_m !== "1000") gateFailures.push("Area radius render state failed");
  if ([stateEvidence.area_500m, stateEvidence.population_age, stateEvidence.area_1km].some((state) => state.area_visible !== "true")) gateFailures.push("Area visibility state failed");
  if (storyStates.some((state) => state.active_story_action_count !== 1 || state.legend?.item_count > 5)) gateFailures.push("Story or legend contract failed");
  if (storyStates.some((state, index) => state.active_story !== expectedStories[index])) gateFailures.push("Story state synchronization failed");
  if (stateEvidence.exact_road_target.target_resolution !== "exact" || stateEvidence.exact_building_target.target_resolution !== "exact") gateFailures.push("Exact target resolution failed");
  if (stateEvidence.facility_reference.target_label_resolution !== "reference_position") gateFailures.push("Facility reference resolution failed");
  if (stateEvidence.area_fallback.target_resolution !== "area_fallback") gateFailures.push("Area fallback resolution failed");
  if (allStates.some((state) => state.three_d_button_count !== 0)) gateFailures.push("3D button was displayed");
  if (allStates.some((state) => state.visible_actionable_controls > 12 || state.horizontal_overflow_px > 0 || state.map_panel_overlap_px2 > 0)) gateFailures.push("Control/overflow/overlap gate failed");
  if (allStates.some((state) => state.map_render_ready === "true" && state.pending_sources)) gateFailures.push("Ready state retained pending sources");
  if ([...storyStates, stateEvidence.mobile_result].some((state) => state.map_render_ready !== "true" || state.pending_sources)) gateFailures.push("Story semantic-ready state failed");
  if (stateEvidence.population_age.map_share_percent < 65 || stateEvidence.population_age.map_share_percent > 72) gateFailures.push("Desktop map share failed");
  if (stateEvidence.mobile_result.map_share_percent < 28 || stateEvidence.mobile_result.map_share_percent > 32) gateFailures.push("Mobile result map share failed");
  if (stateEvidence.population_age.map_occlusion_percent > 8 || stateEvidence.mobile_result.map_occlusion_percent > 15) gateFailures.push("Map occlusion failed");
  if (stateEvidence.basemap_degraded.area_visible !== "true" || stateEvidence.basemap_degraded.map_render_ready !== "true") gateFailures.push("Degraded basemap local-vector readiness failed");
  if (!provenance.valid) gateFailures.push("Display derivative provenance failed");
  if (accessibility.critical.length || mobileAccessibility.critical.length || keyboard.failures.length) gateFailures.push("Accessibility gate failed");
  if (criticalDiagnostics.length) gateFailures.push("Browser diagnostics failed");
  if (Object.values(targetVisualSignals).some((signal) => !signal || signal.map_standard_deviation < .04 || signal.target_color_pixels < 100)) gateFailures.push("Target screenshot visual-signal gate failed");
  if (boundaryAudit.prohibited_copy.length || boundaryAudit.field_evidence_inputs || boundaryAudit.visible_internal_ids || boundaryAudit.review_copy) gateFailures.push("Public privacy/copy boundary failed");
  if (screenshots.find((item) => item.filename === "17-retina-dpr2-target-road.png")?.physical_dimensions !== "2560x1440") gateFailures.push("DPR2 capture dimensions failed");
  if (!advanced || !legacyM3) gateFailures.push("Route regression failed");

  const manifest = {
    schema_version: performanceCheckpoint
      ? "citygap.cartographic-performance-checkpoint@1"
      : "citygap.cartographic-checkpoint@1",
    generated_at: new Date().toISOString(),
    repository_head_before_c5_commit: repositoryHead,
    base_url: baseUrl,
    baseline_commit: baselineCommit,
    load_resume: {
      trigger: "500ms after Area confirmation; no pre-confirmation prefetch",
      initial_state_after_fast_journey: loadingStateAfterJourney,
      final_state: stateEvidence.population_age.cartography_state,
      honest_loading_fallback: "reference_position or area_fallback; no invented geometry",
    },
    performance: {
      fmr_samples_ms: fmrSamples,
      fmr_median_ms: fmrMedian,
      area_map_ready_ms: { "500m": journey500.areaRecognitionMs, "800m": journey.areaRecognitionMs, "1km": journey1km.areaRecognitionMs },
      area_three_second_recognition: "READY_FOR_VISUAL_REVIEW; automated state and screenshots recorded, not substituted for a human judgment",
      story_switch_ms: Object.fromEntries(["building_use", "establishments", "urban_planning", "transport"].map((key) => [key, stateEvidence[key].switch_ms])),
      target_camera_ms: { road: roadCameraMs, building: buildingCameraMs, facility: facilityCameraMs },
    },
    states: stateEvidence,
    provenance,
    accessibility: { desktop: accessibility, mobile: mobileAccessibility, keyboard, critical_or_serious_count: accessibility.critical.length + mobileAccessibility.critical.length + keyboard.failures.length },
    public_boundary: boundaryAudit,
    routes: { advanced, legacy_m3: legacyM3, municipal_surface: "validated by separate municipal production build" },
    before_after: beforeAfter,
    c5_visual_regression: c5VisualRegression,
    diagnostics,
    headless_shader_warnings: headlessShaderWarnings,
    expected_request_cancellations: expectedRequestCancellations,
    target_visual_signals: targetVisualSignals,
    screenshots,
    gate_failures: gateFailures,
    status: gateFailures.length ? [performanceCheckpoint ? "P4_INCOMPLETE" : "C5_INCOMPLETE"] : [
      performanceCheckpoint
        ? "AUTOMATED_CARTOGRAPHIC_PERFORMANCE_CHECKPOINT_COMPLETE"
        : "AUTOMATED_CARTOGRAPHIC_CHECKPOINT_COMPLETE",
      performanceCheckpoint ? "READY_FOR_SELF_VISUAL_REVIEW" : "READY_FOR_VISUAL_REVIEW",
      "READY_FOR_HUMAN_TEST",
      "AWAITING_HUMAN_TEST",
      "AWAITING_MUNICIPAL_WORKFLOW_REVIEW",
      "HOLD_MAIN_PROMOTION",
      "HOLD_P1_M4_M6",
      ...(performanceCheckpoint ? [] : ["BOREHOLE_INTEGRATE_RESEARCH_ONLY"]),
    ],
  };
  await writeFile(path.join(outputDirectory, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify({
    performance: manifest.performance,
    target_resolution: {
      road: stateEvidence.exact_road_target.target_resolution,
      building: stateEvidence.exact_building_target.target_resolution,
      facility: stateEvidence.facility_reference.target_label_resolution,
      fallback: stateEvidence.area_fallback.target_resolution,
    },
    story_count: storyStates.length,
    provenance_valid: provenance.valid,
    accessibility_critical: manifest.accessibility.critical_or_serious_count,
    diagnostic_count: criticalDiagnostics.length,
    screenshot_count: screenshots.length,
    gate_failures: gateFailures,
    status: manifest.status,
  }, null, 2)}\n`);
  if (gateFailures.length) process.exitCode = 1;
} finally {
  await browser.close();
}
