import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright-core";

process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY = "1";

const args = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const key = process.argv[index];
  if (!key.startsWith("--")) continue;
  const value = process.argv[index + 1];
  args.set(key, value && !value.startsWith("--") ? value : "true");
  if (value && !value.startsWith("--")) index += 1;
}

const rootUrl = new URL(args.get("--url") ?? "http://127.0.0.1:4173/plateau-city-gap/");
rootUrl.search = "";
rootUrl.hash = "";
const outputDirectory = path.resolve(
  process.cwd(),
  args.get("--output") ?? "../docs/assets/harbor-atlas-v2/after",
);
const repositoryRoot = path.resolve(process.cwd(), "..");
const sourceCommit = execFileSync("git", ["rev-parse", "HEAD"], { cwd: repositoryRoot, encoding: "utf8" }).trim();
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const viewport = { width: 1440, height: 900 };
const diagnostics = [];
const records = [];
const sha256 = (value) => createHash("sha256").update(value).digest("hex");

const matrices = {
  protanopia: [
    .567, .433, 0,
    .558, .442, 0,
    0, .242, .758,
  ],
  deuteranopia: [
    .625, .375, 0,
    .7, .3, 0,
    0, .3, .7,
  ],
};

function simulatedRgb(rgb, matrix) {
  return [0, 1, 2].map((row) => Math.round(
    rgb[0] * matrix[row * 3]
    + rgb[1] * matrix[row * 3 + 1]
    + rgb[2] * matrix[row * 3 + 2],
  ));
}

function rgbDistance(left, right) {
  return Number(Math.hypot(...left.map((channel, index) => channel - right[index])).toFixed(1));
}

function pageUrl(story) {
  const target = new URL(rootUrl);
  target.search = `?experience=guided&story=${story}&selectionType=mesh&selection=533513314&mesh=533513314`;
  return target.toString();
}

function watch(page, label) {
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
}

async function settle(page) {
  await page.evaluate(async () => {
    await document.fonts?.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
}

async function openStory(page, story) {
  await page.goto(pageUrl(story), { waitUntil: "domcontentloaded", timeout: 180_000 });
  await page.locator(`.guided-spatial-app[data-guided-story="${story}"][data-context-status="ready"]`).waitFor({ timeout: 180_000 });
  await page.waitForFunction(() => document.querySelector(".analytical-map-shell")?.getAttribute("data-guided-visual-ready") === "true", null, { timeout: 180_000 });
  if (story === "understand") {
    await page.locator('.urban-section[data-static-annotation-count="6"][data-annotation-overlap-count="0"]').waitFor({ timeout: 180_000 });
  } else {
    await page.locator('.guided-spatial-app[data-target-resolution="exact"]').waitFor({ timeout: 180_000 });
  }
  await settle(page);
}

async function applySimulation(page, simulation) {
  await page.evaluate((kind) => {
    if (kind === "grayscale") {
      document.documentElement.style.filter = "grayscale(1)";
      return;
    }
    const values = {
      protanopia: "0.567 0.433 0 0 0  0.558 0.442 0 0 0  0 0.242 0.758 0 0  0 0 0 1 0",
      deuteranopia: "0.625 0.375 0 0 0  0.7 0.3 0 0 0  0 0.3 0.7 0 0  0 0 0 1 0",
    };
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.id = "harbor-final-simulation-filter";
    svg.setAttribute("width", "0");
    svg.setAttribute("height", "0");
    svg.innerHTML = `<filter id="harbor-final-${kind}"><feColorMatrix type="matrix" values="${values[kind]}" /></filter>`;
    document.body.append(svg);
    document.documentElement.style.filter = `url(#harbor-final-${kind})`;
  }, simulation);
  await settle(page);
}

async function metrics(page) {
  return page.evaluate(() => {
    const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
    const visible = (id) => map?.getLayer(id) ? map.getLayoutProperty(id, "visibility") !== "none" : null;
    const paint = (id, property) => map?.getLayer(id) ? map.getPaintProperty(id, property) ?? null : null;
    const layout = (id, property) => map?.getLayer(id) ? map.getLayoutProperty(id, property) ?? null : null;
    const section = document.querySelector(".urban-section");
    return {
      map_initialization_count: window.__cityGapMapInitCount ?? null,
      horizontal_overflow_px: Math.max(0, document.documentElement.scrollWidth - innerWidth),
      visible_h1_count: [...document.querySelectorAll("h1")].filter((node) => node.getBoundingClientRect().height > 0).length,
      target_resolution: document.querySelector(".guided-spatial-app")?.getAttribute("data-target-resolution") ?? null,
      selected_area: {
        halo_visible: visible("guided-area-halo"),
        line_visible: visible("guided-area-line"),
        line_width: paint("guided-area-line", "line-width"),
        label_visible: visible("guided-area-label"),
      },
      transect: {
        line_visible: visible("guided-section-line"),
        line_width: paint("guided-section-line", "line-width"),
        endpoints: section?.getAttribute("data-static-annotation-count") ?? null,
      },
      exact_target: {
        halo_visible: visible("guided-target-halo"),
        line_visible: visible("guided-target-line"),
        line_width: paint("guided-target-line", "line-width"),
        label_visible: visible("guided-target-label"),
        label_size: layout("guided-target-label", "text-size"),
      },
    };
  });
}

async function capture(browser, simulation, story, filename) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1, locale: "ja-JP", reducedMotion: "reduce", serviceWorkers: "block" });
  const page = await context.newPage();
  page.setDefaultTimeout(180_000);
  watch(page, simulation);
  await openStory(page, story);
  await applySimulation(page, simulation);
  const stateMetrics = await metrics(page);
  const failures = [];
  if (stateMetrics.map_initialization_count !== 1) failures.push(`map initializations ${stateMetrics.map_initialization_count}`);
  if (stateMetrics.horizontal_overflow_px !== 0) failures.push(`overflow ${stateMetrics.horizontal_overflow_px}`);
  if (stateMetrics.visible_h1_count !== 1) failures.push(`H1 count ${stateMetrics.visible_h1_count}`);
  if (story === "understand") {
    if (!stateMetrics.selected_area.halo_visible || !stateMetrics.selected_area.line_visible || stateMetrics.selected_area.line_width < 3.5) failures.push("selected Area non-color hierarchy is incomplete");
    if (!stateMetrics.transect.line_visible || stateMetrics.transect.line_width < 3.8 || stateMetrics.transect.endpoints !== "6") failures.push("A-B non-color hierarchy is incomplete");
  } else {
    if (stateMetrics.target_resolution !== "exact") failures.push(`target resolution ${stateMetrics.target_resolution}`);
    if (!stateMetrics.exact_target.halo_visible || !stateMetrics.exact_target.line_visible || !stateMetrics.exact_target.label_visible) failures.push("exact target non-color hierarchy is incomplete");
    if (stateMetrics.exact_target.line_width <= stateMetrics.selected_area.line_width || stateMetrics.exact_target.label_size < 14) failures.push("exact target is not structurally stronger than its Area");
  }
  if (failures.length) throw new Error(`${simulation} contract failed: ${failures.join("; ")}`);
  const target = path.join(outputDirectory, filename);
  await page.screenshot({ path: target, fullPage: false, animations: "disabled", timeout: 120_000 });
  const buffer = await readFile(target);
  const matrix = matrices[simulation];
  const simulatedColors = matrix ? {
    area_outline_rgb: simulatedRgb([22, 79, 99], matrix),
    target_outline_rgb: simulatedRgb([169, 71, 54], matrix),
  } : null;
  records.push({
    simulation,
    state: story === "understand" ? "scene-2" : "scene-3-exact-road",
    filename,
    viewport,
    url: page.url(),
    bytes: buffer.length,
    sha256: sha256(buffer),
    metrics: stateMetrics,
    automated_color_separation: simulatedColors ? {
      ...simulatedColors,
      rgb_distance: rgbDistance(simulatedColors.area_outline_rgb, simulatedColors.target_outline_rgb),
      pass: rgbDistance(simulatedColors.area_outline_rgb, simulatedColors.target_outline_rgb) >= 40,
    } : {
      pass: true,
      basis: "selected Area halo/outline/label and A-B line/endpoints remain visible without hue",
    },
  });
  await context.close();
  process.stderr.write(`[harbor-simulation] saved ${filename}\n`);
}

await mkdir(outputDirectory, { recursive: true });
const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"],
});
try {
  await capture(browser, "grayscale", "understand", "21-grayscale-scene2.png");
  await capture(browser, "protanopia", "verify", "22-protanopia-scene3.png");
  await capture(browser, "deuteranopia", "verify", "23-deuteranopia-scene3.png");
} finally {
  await browser.close();
}

if (diagnostics.length) throw new Error(`simulation diagnostics are not empty: ${JSON.stringify(diagnostics, null, 2)}`);
if (records.some((record) => !record.automated_color_separation.pass)) throw new Error("simulated Area/target color separation failed");
const manifest = {
  schema_version: "citygap.harbor-atlas-simulations@1",
  generated_at: new Date().toISOString(),
  source_branch: execFileSync("git", ["branch", "--show-current"], { cwd: repositoryRoot, encoding: "utf8" }).trim(),
  source_commit: sourceCommit,
  source_url: rootUrl.toString(),
  protocol: "Playwright Chromium; final source styles; grayscale/CVD document filter; reduced motion; font and compositor readiness",
  records,
  diagnostics,
};
await writeFile(path.join(outputDirectory, "simulation-manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
process.stdout.write(`${JSON.stringify({ outputDirectory, sourceCommit, records: records.length, diagnostics: diagnostics.length }, null, 2)}\n`);
