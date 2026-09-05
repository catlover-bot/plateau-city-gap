import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright-core";

process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY = "1";

const parameters = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const key = process.argv[index];
  if (!key.startsWith("--")) continue;
  const value = process.argv[index + 1];
  parameters.set(key, value && !value.startsWith("--") ? value : "true");
  if (value && !value.startsWith("--")) index += 1;
}

const repositoryRoot = path.resolve(process.cwd(), "..");
const phase = parameters.get("--phase") ?? "before";
if (!new Set(["before", "after", "production"]).has(phase)) {
  throw new Error(`unsupported phase: ${phase}`);
}
const outputDirectory = path.resolve(
  process.cwd(),
  parameters.get("--output") ?? `../docs/assets/map-section-refinement-v1/${phase}`,
);
const rootUrl = new URL(parameters.get("--url") ?? "http://127.0.0.1:4173/plateau-city-gap/");
rootUrl.search = "";
rootUrl.hash = "";
const branch = execFileSync("git", ["branch", "--show-current"], { cwd: repositoryRoot, encoding: "utf8" }).trim();
const repositoryHead = execFileSync("git", ["rev-parse", "HEAD"], { cwd: repositoryRoot, encoding: "utf8" }).trim();
const sourceCommit = execFileSync(
  "git",
  ["rev-parse", `${parameters.get("--source-commit") ?? repositoryHead}^{commit}`],
  { cwd: repositoryRoot, encoding: "utf8" },
).trim();
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const records = [];
const diagnostics = [];

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function pageUrl(query = "") {
  const target = new URL(rootUrl);
  target.search = query ? (query.startsWith("?") ? query : `?${query}`) : "";
  return target.toString();
}

function phaseLog(message) {
  process.stderr.write(`[map-section:${phase}] ${message}\n`);
}

async function settleFrames(page) {
  await page.evaluate(async () => {
    await document.fonts?.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
}

function attachDiagnostics(page, label) {
  page.on("pageerror", (error) => diagnostics.push({ label, kind: "page", message: error.message }));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("cyberjapandata.gsi.go.jp")) {
      diagnostics.push({ label, kind: "console", message: message.text() });
    }
  });
  page.on("requestfailed", (request) => {
    const reason = request.failure()?.errorText ?? "unknown";
    if (reason !== "net::ERR_ABORTED" && !request.url().includes("cyberjapandata.gsi.go.jp")) {
      diagnostics.push({ label, kind: "request", url: request.url(), message: reason });
    }
  });
  page.on("response", (response) => {
    if (response.status() >= 500) diagnostics.push({ label, kind: "http", url: response.url(), status: response.status() });
  });
}

async function waitForMap(page, guided = true) {
  await page.locator(".analytical-map-shell").waitFor({ state: "visible", timeout: 180_000 });
  await page.waitForFunction((requireGuided) => {
    const shell = document.querySelector(".analytical-map-shell");
    return requireGuided
      ? shell?.getAttribute("data-guided-visual-ready") === "true"
      : shell?.getAttribute("data-public-cartography-ready") === "true";
  }, guided, { timeout: 180_000 });
  await settleFrames(page);
}

async function openPublic(page) {
  await page.goto(pageUrl(), { waitUntil: "domcontentloaded", timeout: 180_000 });
  await page.locator('.public-area[data-public-step="intro"]').waitFor({ timeout: 180_000 });
  await waitForMap(page, false);
}

async function openGuided(page, story, mesh = "533513314") {
  await page.goto(pageUrl(`experience=guided&story=${story}&selectionType=mesh&selection=${mesh}&mesh=${mesh}`), {
    waitUntil: "domcontentloaded",
    timeout: 180_000,
  });
  const contextStatus = story === "intro" || story === "find" ? "idle" : "ready";
  await page.locator(`.guided-spatial-app[data-guided-story="${story}"][data-area-id="${mesh}"][data-context-status="${contextStatus}"]`).waitFor({ timeout: 180_000 });
  await waitForMap(page);
  if (story === "understand" && mesh === "533513314") {
    await page.locator('.guided-spatial-app[data-section-pack="maizuru-533513314-plateau-2025-v1"]').waitFor({ timeout: 180_000 });
    await page.locator('.urban-section[data-terrain-samples="94"][data-direct-building-count="17"][data-direct-road-count="14"]').waitFor({ state: "attached", timeout: 180_000 });
  }
  if (story === "verify" && mesh === "533513314") {
    await page.locator('.guided-spatial-app[data-target-kind="road"][data-target-resolution="exact"]').waitFor({ timeout: 180_000 });
  }
  await settleFrames(page);
}

async function selectExactBuilding(page) {
  const select = page.locator(".guided-target-select select");
  const buildingValue = await select.locator("option").evaluateAll((options) => (
    options.map((option) => option.value).find((value) => value.startsWith("building:")) ?? null
  ));
  if (!buildingValue) throw new Error("exact building option is unavailable");
  await select.selectOption(buildingValue);
  await page.locator('.guided-spatial-app[data-target-kind="building"][data-target-resolution="exact"]').waitFor({ timeout: 180_000 });
  await waitForMap(page);
}

async function visualMetrics(page) {
  return page.evaluate(() => {
    const visible = (node) => {
      if (!(node instanceof Element)) return false;
      const rect = node.getBoundingClientRect();
      const style = getComputedStyle(node);
      return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none" && Number(style.opacity) !== 0;
    };
    const rectOf = (selector) => document.querySelector(selector)?.getBoundingClientRect() ?? null;
    const map = rectOf(".guided-map-stage, .public-map-stage");
    const panel = rectOf(".guided-story-panel, .public-area-panel");
    const workspace = rectOf(".guided-spatial-workspace, .public-area-body");
    const actionables = [...document.querySelectorAll('button, a[href], select, input, [role="button"]')].filter(visible);
    const svg = document.querySelector(".urban-section svg");
    const plotRect = svg?.getBoundingClientRect() ?? null;
    const staticLabels = svg
      ? [...svg.querySelectorAll("[data-section-static-annotation], .section-services text")].filter(visible)
      : [];
    const endpoints = svg ? [...svg.querySelectorAll("[data-section-endpoint]")].filter(visible) : [];
    const axisTicks = svg ? [...svg.querySelectorAll("[data-section-axis-tick]")].filter(visible) : [];
    const focusNames = svg ? [...svg.querySelectorAll(".section-focus-callout .focus-name")].filter(visible) : [];
    const focusMeta = svg ? [...svg.querySelectorAll(".section-focus-callout .focus-meta")].filter(visible) : [];
    const minimumFontSize = (nodes) => nodes.length
      ? Math.min(...nodes.map((node) => Number.parseFloat(getComputedStyle(node).fontSize)))
      : null;
    const styleValue = (selector, property) => {
      const node = document.querySelector(selector);
      return node ? getComputedStyle(node)[property] ?? null : null;
    };
    const labelRects = staticLabels.map((node) => ({ node, rect: node.getBoundingClientRect() }));
    const pairOverlaps = [];
    for (let index = 0; index < labelRects.length; index += 1) {
      for (let other = index + 1; other < labelRects.length; other += 1) {
        const first = labelRects[index].rect;
        const second = labelRects[other].rect;
        if (first.left < second.right - 0.5 && first.right > second.left + 0.5 && first.top < second.bottom - 0.5 && first.bottom > second.top + 0.5) {
          pairOverlaps.push([index, other]);
        }
      }
    }
    const overlapsAny = (rect, nodes) => nodes.some((node) => {
      const other = node.getBoundingClientRect();
      return rect.left < other.right - 0.5 && rect.right > other.left + 0.5 && rect.top < other.bottom - 0.5 && rect.bottom > other.top + 0.5;
    });
    const outsidePlot = plotRect
      ? labelRects.filter(({ rect }) => rect.left < plotRect.left - 0.5 || rect.right > plotRect.right + 0.5 || rect.top < plotRect.top - 0.5 || rect.bottom > plotRect.bottom + 0.5).length
      : 0;
    const legend = document.querySelector(".section-visual-legend");
    const legendRect = visible(legend) ? legend.getBoundingClientRect() : null;
    const selectedAnnotation = svg?.querySelector('[data-section-annotation-selected="true"]') ?? null;
    const root = document.querySelector(".guided-spatial-app");
    const mapShell = document.querySelector(".analytical-map-shell");
    const mapCanvas = document.querySelector(".analytical-map-canvas");
    const mapInstance = mapCanvas?.__cityGapMap ?? null;
    const layerVisible = (id) => mapInstance?.getLayer(id)
      ? mapInstance.getLayoutProperty(id, "visibility") !== "none"
      : null;
    const paint = (id, property) => mapInstance?.getLayer(id)
      ? mapInstance.getPaintProperty(id, property) ?? null
      : null;
    const layout = (id, property) => mapInstance?.getLayer(id)
      ? mapInstance.getLayoutProperty(id, property) ?? null
      : null;
    const metrics = window.__cityGapSectionAnnotationMetrics ?? null;
    const accentFamilies = new Set();
    const classifyAccent = (value) => {
      const normalized = String(value ?? "").toLowerCase().replaceAll(" ", "");
      if (["#164f63", "#26758a", "#77aeb6", "rgb(22,79,99)", "rgb(38,117,138)", "rgb(119,174,182)"].includes(normalized)) accentFamilies.add("Harbor");
      if (["#a94736", "#d9664d", "#f1a085", "rgb(169,71,54)", "rgb(217,102,77)", "rgb(241,160,133)"].includes(normalized)) accentFamilies.add("Signal");
    };
    [...document.querySelectorAll("body *")].filter(visible).forEach((node) => {
      const style = getComputedStyle(node);
      [style.color, style.backgroundColor, style.borderTopColor, style.borderRightColor, style.fill, style.stroke].forEach(classifyAccent);
    });
    [
      paint("guided-area-fill", "fill-color"), paint("guided-area-line", "line-color"),
      paint("mesh-top-fill", "fill-color"), paint("guided-section-line", "line-color"),
      paint("guided-target-fill", "fill-color"), paint("guided-target-line", "line-color"),
    ].forEach(classifyAccent);
    return {
      viewport: { width: innerWidth, height: innerHeight },
      orientation: innerWidth > 900 ? "horizontal" : "vertical",
      map_share_percent: map && workspace ? Number(((innerWidth > 900 ? map.width / workspace.width : map.height / workspace.height) * 100).toFixed(1)) : null,
      panel_share_percent: panel && workspace ? Number(((innerWidth > 900 ? panel.width / workspace.width : panel.height / workspace.height) * 100).toFixed(1)) : null,
      section_height_px: rectOf(".guided-section-dock svg")?.height ?? null,
      annotation_count: staticLabels.length + endpoints.length,
      road_annotation_count: staticLabels.filter((node) => node.getAttribute("data-section-annotation-kind") === "road").length,
      hidden_low_priority_annotations: metrics?.hiddenCount ?? null,
      annotation_calculation_ms: metrics?.calculationMs ?? null,
      static_annotation_labels: staticLabels.map((node) => node.textContent?.trim() ?? ""),
      endpoint_labels: endpoints.map((node) => node.textContent?.trim() ?? ""),
      static_annotation_min_font_px: minimumFontSize(staticLabels),
      axis_tick_min_font_px: minimumFontSize(axisTicks),
      endpoint_min_font_px: minimumFontSize(endpoints),
      focus_name_min_font_px: minimumFontSize(focusNames),
      focus_meta_min_font_px: minimumFontSize(focusMeta),
      label_overlap_count: pairOverlaps.length,
      labels_outside_plot: outsidePlot,
      labels_covering_endpoints: labelRects.filter(({ rect }) => overlapsAny(rect, endpoints)).length,
      labels_covering_axis_ticks: labelRects.filter(({ rect }) => overlapsAny(rect, axisTicks)).length,
      legend_overlap_count: legendRect && plotRect && legendRect.top < plotRect.bottom && legendRect.bottom > plotRect.top ? 1 : 0,
      selected_annotation_visible: selectedAnnotation ? visible(selectedAnnotation) : null,
      section_palette: svg ? {
        terrain_stroke: styleValue(".section-terrain path", "stroke"),
        building_fill: styleValue(".urban-section.guided .section-buildings rect.direct:not(.focused)", "fill"),
        building_outline: styleValue(".urban-section.guided .section-buildings rect.direct:not(.focused)", "stroke"),
        road_fill: styleValue(".urban-section.guided .section-roads path:not(.focused)", "fill"),
        road_outline: styleValue(".urban-section.guided .section-roads path:not(.focused)", "stroke"),
        endpoint_fill: styleValue(".urban-section.guided .section-axis text.endpoint", "fill"),
        focus_fill: styleValue(".urban-section.guided .section-buildings rect.focused, .urban-section.guided .section-roads path.focused", "fill"),
        focus_outline: styleValue(".urban-section.guided .section-buildings rect.focused, .urban-section.guided .section-roads path.focused", "stroke"),
        callout_outline: styleValue(".section-focus-callout > rect", "stroke"),
      } : null,
      visible_controls: actionables.length,
      map_initialization_count: window.__cityGapMapInitCount ?? null,
      map_render_state: mapShell?.getAttribute("data-map-render-state") ?? null,
      map_hierarchy: mapInstance ? {
        basemap_opacity: paint("gsi-pale", "raster-opacity"),
        selected_area_fill_visible: layerVisible("guided-area-fill"),
        selected_area_halo_visible: layerVisible("guided-area-halo"),
        selected_area_line_visible: layerVisible("guided-area-line"),
        selected_area_line_width: paint("guided-area-line", "line-width"),
        selected_area_fill_color: paint("guided-area-fill", "fill-color"),
        selected_area_line_color: paint("guided-area-line", "line-color"),
        selected_area_label_visible: layerVisible("guided-area-label"),
        selected_area_label_size: layout("guided-area-label", "text-size"),
        candidate_fill_visible: layerVisible("mesh-top-fill"),
        candidate_fill_color: paint("mesh-top-fill", "fill-color"),
        candidate_label_visible: layerVisible("mesh-top-label"),
        candidate_label_size: layout("mesh-top-label", "text-size"),
        buildings_visible: layerVisible("guided-buildings-fill"),
        buildings_fill_color: paint("guided-buildings-fill", "fill-color"),
        roads_visible: layerVisible("guided-roads-line"),
        roads_fill_color: paint("guided-roads-fill", "fill-color"),
        roads_line_color: paint("guided-roads-line", "line-color"),
        planning_visible: layerVisible("guided-planning-line"),
        section_line_visible: layerVisible("guided-section-line"),
        section_line_width: paint("guided-section-line", "line-width"),
        section_line_color: paint("guided-section-line", "line-color"),
        target_fill_visible: layerVisible("guided-target-fill"),
        target_fill_color: paint("guided-target-fill", "fill-color"),
        target_halo_visible: layerVisible("guided-target-halo"),
        target_line_visible: layerVisible("guided-target-line"),
        target_line_width: paint("guided-target-line", "line-width"),
        target_line_color: paint("guided-target-line", "line-color"),
        target_label_visible: layerVisible("guided-target-label"),
        target_label_size: layout("guided-target-label", "text-size"),
      } : null,
      target_kind: root?.getAttribute("data-target-kind") ?? null,
      target_resolution: root?.getAttribute("data-target-resolution") ?? null,
      horizontal_overflow_px: Math.max(0, document.documentElement.scrollWidth - innerWidth),
      visible_h1_count: [...document.querySelectorAll("h1")].filter(visible).length,
      strong_accent_family_count: accentFamilies.size,
      strong_accent_families: [...accentFamilies].sort(),
    };
  });
}

function assertAfterCaptureContract(filename, state, viewport, metrics) {
  if (phase === "before") return;

  const failures = [];
  const color = (value) => String(value ?? "").toLowerCase();
  const expect = (condition, message) => {
    if (!condition) failures.push(message);
  };
  const sectionVisible = Number(metrics.section_height_px ?? 0) > 0;
  expect(metrics.strong_accent_family_count <= 2, `strong accent families ${metrics.strong_accent_families.join(", ")}`);
  if (sectionVisible) {
    const mobile = viewport.width <= 600;
    expect(metrics.annotation_count <= (mobile ? 4 : 6), `annotation budget ${metrics.annotation_count}`);
    expect(metrics.road_annotation_count <= (mobile ? 2 : 4), `road annotation budget ${metrics.road_annotation_count}`);
    expect(new Set(metrics.static_annotation_labels).size === metrics.static_annotation_labels.length, "duplicate static annotation");
    expect(JSON.stringify(metrics.endpoint_labels) === JSON.stringify(["A", "B"]), `endpoint labels ${JSON.stringify(metrics.endpoint_labels)}`);
    expect(metrics.label_overlap_count === 0, `label overlaps ${metrics.label_overlap_count}`);
    expect(metrics.labels_outside_plot === 0, `outside labels ${metrics.labels_outside_plot}`);
    expect(metrics.labels_covering_endpoints === 0, `endpoint conflicts ${metrics.labels_covering_endpoints}`);
    expect(metrics.labels_covering_axis_ticks === 0, `axis conflicts ${metrics.labels_covering_axis_ticks}`);
    expect(metrics.legend_overlap_count === 0, `legend conflicts ${metrics.legend_overlap_count}`);
    expect(metrics.annotation_calculation_ms <= 50, `annotation calculation ${metrics.annotation_calculation_ms}ms`);
    expect(metrics.static_annotation_min_font_px >= 12, `road annotation font ${metrics.static_annotation_min_font_px}px`);
    expect(metrics.axis_tick_min_font_px >= 11, `axis tick font ${metrics.axis_tick_min_font_px}px`);
    expect(metrics.endpoint_min_font_px >= 14 && metrics.endpoint_min_font_px <= 16, `endpoint font ${metrics.endpoint_min_font_px}px`);
    expect(metrics.section_palette?.terrain_stroke === "rgb(93, 116, 118)", `terrain color ${metrics.section_palette?.terrain_stroke}`);
    expect(metrics.section_palette?.building_fill === "rgb(155, 169, 173)", `building color ${metrics.section_palette?.building_fill}`);
    expect(metrics.section_palette?.building_outline === "rgb(89, 105, 112)", `building outline ${metrics.section_palette?.building_outline}`);
    expect(metrics.section_palette?.road_fill === "rgb(229, 221, 209)", `road color ${metrics.section_palette?.road_fill}`);
    expect(metrics.section_palette?.road_outline === "rgb(102, 114, 121)", `road outline ${metrics.section_palette?.road_outline}`);
    expect(metrics.section_palette?.endpoint_fill === "rgb(22, 79, 99)", `endpoint color ${metrics.section_palette?.endpoint_fill}`);
    if (mobile) {
      expect(metrics.section_height_px >= 300 && metrics.section_height_px <= 340, `mobile section height ${metrics.section_height_px}px`);
    } else if (viewport.width === 1440) {
      expect(metrics.section_height_px >= 360 && metrics.section_height_px <= 410, `desktop section height ${metrics.section_height_px}px`);
    } else {
      expect(metrics.section_height_px >= 300, `compact section height ${metrics.section_height_px}px`);
    }
    if (state === "scene-2-section") {
      expect(metrics.selected_annotation_visible === true, "focused annotation is not visible");
      expect(metrics.focus_name_min_font_px >= 13, `focus name font ${metrics.focus_name_min_font_px}px`);
      expect(metrics.focus_meta_min_font_px >= 12, `focus metadata font ${metrics.focus_meta_min_font_px}px`);
      expect(metrics.section_palette?.focus_fill === "rgb(217, 102, 77)", `focus fill ${metrics.section_palette?.focus_fill}`);
      expect(metrics.section_palette?.focus_outline === "rgb(169, 71, 54)", `focus outline ${metrics.section_palette?.focus_outline}`);
      expect(metrics.section_palette?.callout_outline === "rgb(169, 71, 54)", `callout outline ${metrics.section_palette?.callout_outline}`);
    }
  }

  const hierarchy = metrics.map_hierarchy;
  if (state === "guided-intro") {
    expect(hierarchy?.basemap_opacity === 0.68, `intro basemap opacity ${hierarchy?.basemap_opacity}`);
  }
  if (state === "scene-1-find" || state === "mobile-scene-1") {
    expect(hierarchy?.basemap_opacity === 0.58, `find basemap opacity ${hierarchy?.basemap_opacity}`);
    expect(hierarchy?.selected_area_line_visible === true && hierarchy?.selected_area_halo_visible === true, "selected Area hierarchy is hidden");
    expect(hierarchy?.selected_area_label_visible === true && hierarchy?.selected_area_label_size === 15, "selected Area label hierarchy is missing");
    expect(hierarchy?.candidate_fill_visible === true && hierarchy?.candidate_label_visible === true, "candidate hierarchy is hidden");
    expect(hierarchy?.selected_area_line_width > 3, `selected Area line width ${hierarchy?.selected_area_line_width}`);
    expect(color(hierarchy?.selected_area_fill_color) === "#c9e1de" && color(hierarchy?.selected_area_line_color) === "#164f63", "selected Area does not use Harbor hierarchy");
    expect(color(hierarchy?.candidate_fill_color) === "#e8f2ef", `candidate fill ${hierarchy?.candidate_fill_color}`);
  }
  if (state === "scene-2-map" || state === "scene-2-combined" || state === "scene-2-section" || state === "mobile-scene-2-map" || state === "mobile-scene-2-section" || state === "dpr2-section") {
    expect(hierarchy?.basemap_opacity === 0.5, `understand basemap opacity ${hierarchy?.basemap_opacity}`);
    expect(hierarchy?.buildings_visible === true && hierarchy?.roads_visible === true, "PLATEAU context is hidden");
    expect(hierarchy?.section_line_visible === true && hierarchy?.section_line_width >= 3.8, "A–B hierarchy is missing");
    expect(hierarchy?.target_line_visible === false, "target should not compete in Scene 2");
    expect(color(hierarchy?.buildings_fill_color) === "#9ba9ad", `building fill ${hierarchy?.buildings_fill_color}`);
    expect(color(hierarchy?.roads_fill_color) === "#e5ddd1" && color(hierarchy?.roads_line_color) === "#667279", "road material hierarchy is wrong");
    expect(color(hierarchy?.section_line_color) === "#26758a", `A–B color ${hierarchy?.section_line_color}`);
  }
  if (state === "scene-3-exact-road" || state === "scene-3-exact-building" || state === "mobile-scene-3") {
    expect(hierarchy?.basemap_opacity === 0.42, `verify basemap opacity ${hierarchy?.basemap_opacity}`);
    expect(metrics.target_resolution === "exact", `target resolution ${metrics.target_resolution}`);
    expect(hierarchy?.target_fill_visible === true && hierarchy?.target_halo_visible === true && hierarchy?.target_line_visible === true, "exact target hierarchy is incomplete");
    expect(hierarchy?.target_label_visible === true && hierarchy?.target_label_size === 14, "exact target label is missing");
    expect(hierarchy?.target_line_width > hierarchy?.selected_area_line_width, "exact target is not stronger than its Area");
    expect(color(hierarchy?.target_fill_color) === "#d9664d" && color(hierarchy?.target_line_color) === "#a94736", "exact target does not use Signal hierarchy");
  }
  if (state === "fallback-area") {
    expect(metrics.target_resolution === "area_fallback", `fallback resolution ${metrics.target_resolution}`);
    expect(hierarchy?.target_line_visible === true && hierarchy?.target_halo_visible === false && hierarchy?.target_label_visible === false, "fallback is presented as an exact target");
    expect(color(hierarchy?.target_line_color) === "#164f63", `fallback line is not Harbor ${hierarchy?.target_line_color}`);
  }

  if (failures.length) throw new Error(`after contract failed for ${filename}: ${failures.join("; ")}`);
}

async function saveScreenshot(page, filename, state, viewport, dpr, locator = null) {
  const target = path.join(outputDirectory, filename);
  const options = { path: target, animations: "disabled", timeout: 120_000 };
  if (locator) await locator.screenshot(options);
  else await page.screenshot({ ...options, fullPage: false });
  const buffer = await readFile(target);
  const metrics = await visualMetrics(page);
  if (metrics.visible_h1_count !== 1 || metrics.horizontal_overflow_px > 0 || metrics.map_initialization_count !== 1) {
    throw new Error(`capture contract failed for ${filename}: ${JSON.stringify(metrics)}`);
  }
  assertAfterCaptureContract(filename, state, viewport, metrics);
  records.push({ filename, state, viewport, dpr, url: page.url(), bytes: buffer.length, sha256: sha256(buffer), metrics });
  phaseLog(`saved ${filename}`);
}

async function newPage(browser, viewport, dpr, label) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: dpr, locale: "ja-JP", reducedMotion: "reduce", serviceWorkers: "block" });
  const page = await context.newPage();
  page.setDefaultTimeout(180_000);
  attachDiagnostics(page, label);
  return { context, page };
}

async function captureDesktop(browser) {
  const viewport = { width: 1440, height: 900 };
  const { context, page } = await newPage(browser, viewport, 1, "desktop");
  await openPublic(page);
  await saveScreenshot(page, "01-public-landing-desktop.png", "public-landing", viewport, 1);
  await openGuided(page, "intro");
  await saveScreenshot(page, "02-guided-intro-desktop.png", "guided-intro", viewport, 1);
  await openGuided(page, "find");
  await saveScreenshot(page, "03-scene1-find-desktop.png", "scene-1-find", viewport, 1);
  await openGuided(page, "understand");
  await saveScreenshot(page, "04-scene2-map-desktop.png", "scene-2-map", viewport, 1, page.locator(".guided-map-stage"));
  await saveScreenshot(page, "05-scene2-combined-desktop.png", "scene-2-combined", viewport, 1);
  const sectionSvg = page.locator(".guided-section-dock svg");
  await sectionSvg.hover({ position: { x: 620, y: 150 } });
  await settleFrames(page);
  await saveScreenshot(page, "06-scene2-section-closeup.png", "scene-2-section", viewport, 1, page.locator(".guided-section-dock"));
  await openGuided(page, "verify");
  await saveScreenshot(page, "07-scene3-exact-road.png", "scene-3-exact-road", viewport, 1);
  await selectExactBuilding(page);
  await saveScreenshot(page, "08-scene3-exact-building.png", "scene-3-exact-building", viewport, 1);
  await openGuided(page, "understand", "533522274");
  await saveScreenshot(page, "09-another-area.png", "another-area", viewport, 1);
  await openGuided(page, "verify", "533512753");
  await saveScreenshot(page, "10-fallback-area.png", "fallback-area", viewport, 1);
  await context.close();
}

async function captureViewportEvidence(browser) {
  for (const viewport of [{ width: 1280, height: 720 }, { width: 1920, height: 1080 }]) {
    const { context, page } = await newPage(browser, viewport, 1, `${viewport.width}x${viewport.height}`);
    await openGuided(page, "understand");
    await saveScreenshot(page, `${viewport.width}-scene2-combined.png`, "scene-2-combined", viewport, 1);
    await context.close();
  }
}

async function captureMobile(browser) {
  const viewport = { width: 390, height: 844 };
  const { context, page } = await newPage(browser, viewport, 1, "mobile");
  await openGuided(page, "find");
  await saveScreenshot(page, "11-mobile-scene1.png", "mobile-scene-1", viewport, 1);
  await openGuided(page, "understand");
  await saveScreenshot(page, "12-mobile-scene2-map.png", "mobile-scene-2-map", viewport, 1);
  await page.getByRole("button", { name: "街の断面", exact: true }).click();
  await page.locator(".guided-section-dock.mobile-visible").waitFor({ state: "visible" });
  await page.waitForFunction(() => (document.querySelector(".guided-section-dock svg")?.getBoundingClientRect().height ?? 0) >= 300);
  await settleFrames(page);
  await saveScreenshot(page, "13-mobile-scene2-section.png", "mobile-scene-2-section", viewport, 1);
  await page.getByRole("button", { name: "地図", exact: true }).click();
  await page.getByRole("button", { name: "確認場所を見る", exact: true }).click();
  await page.locator('.guided-spatial-app[data-guided-story="verify"][data-target-kind="road"]').waitFor({ timeout: 180_000 });
  await waitForMap(page);
  await saveScreenshot(page, "14-mobile-scene3.png", "mobile-scene-3", viewport, 1);
  await context.close();
}

async function captureDpr2(browser) {
  const viewport = { width: 1440, height: 900 };
  const { context, page } = await newPage(browser, viewport, 2, "dpr2");
  await openGuided(page, "understand");
  await saveScreenshot(page, "15-dpr2-section.png", "dpr2-section", viewport, 2, page.locator(".guided-section-dock"));
  await context.close();
}

await mkdir(outputDirectory, { recursive: true });
const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"],
});
let runtime;
try {
  const probe = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  runtime = await probe.evaluate(() => ({ userAgent: navigator.userAgent, playwright: navigator.webdriver }));
  await probe.close();
  await captureDesktop(browser);
  await captureViewportEvidence(browser);
  await captureMobile(browser);
  await captureDpr2(browser);
} finally {
  await browser.close();
}

if (diagnostics.length) throw new Error(`browser diagnostics are not empty: ${JSON.stringify(diagnostics, null, 2)}`);
const sectionCalculationSamples = records
  .map((record) => record.metrics.annotation_calculation_ms)
  .filter((value) => Number.isFinite(value) && value > 0);
const sortedSectionSamples = [...sectionCalculationSamples].sort((left, right) => left - right);
const sectionPerformance = {
  samples_ms: sectionCalculationSamples,
  median_ms: sortedSectionSamples[Math.floor(sortedSectionSamples.length / 2)] ?? null,
  maximum_ms: sortedSectionSamples.at(-1) ?? null,
  gates: {
    median: { target_ms: 16, pass: (sortedSectionSamples[Math.floor(sortedSectionSamples.length / 2)] ?? Number.POSITIVE_INFINITY) <= 16 },
    hard_maximum: { target_ms: 50, pass: (sortedSectionSamples.at(-1) ?? Number.POSITIVE_INFINITY) <= 50 },
  },
};
if (phase !== "before" && Object.values(sectionPerformance.gates).some((gate) => !gate.pass)) {
  throw new Error(`Section performance contract failed: ${JSON.stringify(sectionPerformance)}`);
}
const manifest = {
  schema_version: "citygap.map-section-refinement-capture@1",
  generated_at: new Date().toISOString(),
  phase,
  environment: rootUrl.hostname === "catlover-bot.github.io" ? "production" : "production-preview",
  source_url: rootUrl.toString(),
  source_branch: branch,
  source_commit: sourceCommit,
  pages_run_id: parameters.get("--pages-run-id") ?? null,
  protocol: "Playwright Chromium; production build; fonts and four compositor frames; reduced motion; identical before/after state matrix",
  runtime,
  records,
  section_performance: sectionPerformance,
  diagnostics,
};
await writeFile(path.join(outputDirectory, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
process.stdout.write(`${JSON.stringify({ outputDirectory, phase, records: records.length, sourceCommit, diagnostics: diagnostics.length }, null, 2)}\n`);
