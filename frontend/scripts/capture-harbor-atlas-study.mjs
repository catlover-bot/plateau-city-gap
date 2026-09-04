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
const repositoryRoot = path.resolve(process.cwd(), "..");
const outputDirectory = path.resolve(
  process.cwd(),
  args.get("--output") ?? "../docs/assets/harbor-atlas-v2/palette-study",
);
const sourceCommit = execFileSync("git", ["rev-parse", "HEAD"], {
  cwd: repositoryRoot,
  encoding: "utf8",
}).trim();
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();

const palettes = {
  "harbor-atlas": {
    label: "Harbor Atlas",
    ink: "#15242B",
    inkSoft: "#526269",
    paper: "#F5F5F1",
    surface: "#FCFCF9",
    muted: "#EEF1EF",
    line: "#D7DDDA",
    lineStrong: "#87959A",
    harborStrong: "#164F63",
    harbor: "#26758A",
    harborSoft: "#77AEB6",
    seaGlass: "#C9E1DE",
    seaGlassPale: "#E8F2EF",
    targetStrong: "#A94736",
    target: "#D9664D",
    targetPale: "#F7E4DE",
    building: "#9BA9AD",
    buildingOutline: "#596970",
    road: "#E5DDD1",
    roadOutline: "#667279",
    terrain: "#5D7476",
    focus: "#F0B84B",
  },
  "civic-graphite": {
    label: "Civic Graphite",
    ink: "#202B30",
    inkSoft: "#5C686C",
    paper: "#F3F4F2",
    surface: "#FFFFFF",
    muted: "#ECEFEE",
    line: "#D4D9D8",
    lineStrong: "#7F8B8F",
    harborStrong: "#285D66",
    harbor: "#3D7D86",
    harborSoft: "#86ADB2",
    seaGlass: "#D0E2E2",
    seaGlassPale: "#EAF1F1",
    targetStrong: "#8B6515",
    target: "#C08B24",
    targetPale: "#F4E9CF",
    building: "#A5ADB0",
    buildingOutline: "#59656A",
    road: "#DDD9D0",
    roadOutline: "#697176",
    terrain: "#68797D",
    focus: "#D49A2D",
  },
  "paper-map": {
    label: "Paper Map",
    ink: "#183447",
    inkSoft: "#59666C",
    paper: "#F3EFE5",
    surface: "#FBF8F0",
    muted: "#ECE8DD",
    line: "#D9D1C3",
    lineStrong: "#8D918D",
    harborStrong: "#334E68",
    harbor: "#536B8E",
    harborSoft: "#8D9DB5",
    seaGlass: "#D7DDD5",
    seaGlassPale: "#ECEEE8",
    targetStrong: "#963F31",
    target: "#C5533D",
    targetPale: "#F3DDD4",
    building: "#AAA9A3",
    buildingOutline: "#5E6568",
    road: "#E4D8C7",
    roadOutline: "#686C6B",
    terrain: "#667B7D",
    focus: "#D79D31",
  },
};

const records = [];
const diagnostics = [];
const sha256 = (value) => createHash("sha256").update(value).digest("hex");

function pageUrl(query) {
  const target = new URL(rootUrl);
  target.search = query ? `?${query}` : "";
  return target.toString();
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

async function settle(page) {
  await page.evaluate(async () => {
    await document.fonts?.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
}

async function waitForMap(page, guided = true) {
  await page.locator(".analytical-map-shell").waitFor({ state: "visible", timeout: 180_000 });
  await page.waitForFunction((isGuided) => {
    const shell = document.querySelector(".analytical-map-shell");
    return isGuided
      ? shell?.getAttribute("data-guided-visual-ready") === "true"
      : shell?.getAttribute("data-public-cartography-ready") === "true";
  }, guided, { timeout: 180_000 });
  await settle(page);
}

async function openState(page, state) {
  const query = state === "public"
    ? ""
    : `experience=guided&story=${state}&selectionType=mesh&selection=533513314&mesh=533513314`;
  await page.goto(pageUrl(query), { waitUntil: "domcontentloaded", timeout: 180_000 });
  if (state === "public") {
    await page.locator('.public-area[data-public-step="intro"]').waitFor({ timeout: 180_000 });
    await waitForMap(page, false);
    return;
  }
  const contextStatus = state === "intro" || state === "find" ? "idle" : "ready";
  await page.locator(`.guided-spatial-app[data-guided-story="${state}"][data-context-status="${contextStatus}"]`).waitFor({ timeout: 180_000 });
  await waitForMap(page);
  if (state === "understand") {
    await page.locator('.guided-spatial-app[data-section-pack="maizuru-533513314-plateau-2025-v1"]').waitFor({ timeout: 180_000 });
  }
  if (state === "verify") {
    await page.locator('.guided-spatial-app[data-target-kind="road"][data-target-resolution="exact"]').waitFor({ timeout: 180_000 });
  }
  await settle(page);
}

function paletteCss(palette) {
  return `
    :root {
      --cg-ink: ${palette.ink}; --cg-ink-soft: ${palette.inkSoft};
      --cg-paper: ${palette.paper}; --cg-panel: ${palette.surface};
      --cg-canvas: ${palette.muted}; --cg-surface: ${palette.surface};
      --cg-surface-muted: ${palette.muted}; --cg-line: ${palette.line};
      --cg-line-strong: ${palette.lineStrong}; --cg-teal-dark: ${palette.harborStrong};
      --cg-teal: ${palette.harbor}; --cg-teal-pale: ${palette.seaGlassPale};
      --cg-selected: ${palette.harborStrong}; --cg-context: ${palette.terrain};
      --cg-target: ${palette.target}; --cg-target-pale: ${palette.targetPale};
      --cg-section: ${palette.harbor}; --cg-focus: ${palette.focus};
    }
    .guided-context-legend .symbol-area { border-color: ${palette.harborStrong}; background: ${palette.seaGlass}; }
    .guided-context-legend .symbol-candidate { border-color: ${palette.harbor}; background: ${palette.seaGlassPale}; }
    .guided-context-legend .symbol-building { border-color: ${palette.buildingOutline}; background: ${palette.building}; }
    .guided-context-legend .symbol-road { border-color: ${palette.roadOutline}; }
    .guided-context-legend .symbol-target { border-color: ${palette.targetStrong}; background: ${palette.targetPale}; }
    .section-terrain path { stroke: ${palette.terrain}; }
    .section-terrain-area path { fill: color-mix(in srgb, ${palette.terrain} 10%, transparent); }
    .urban-section.guided .section-buildings rect { fill: ${palette.building}; stroke: ${palette.buildingOutline}; }
    .urban-section.guided .section-roads path { fill: ${palette.road}; stroke: ${palette.roadOutline}; }
    .urban-section.guided .section-buildings rect.selected,
    .urban-section.guided .section-buildings rect.focused,
    .urban-section.guided .section-roads path.focused { fill: ${palette.target}; stroke: ${palette.targetStrong}; }
    .urban-section.guided .section-axis text.endpoint { fill: ${palette.harborStrong}; }
    .urban-section.guided .section-axis .endpoint-dot { fill: ${palette.harbor}; }
  `;
}

async function applyPalette(page, palette) {
  await page.addStyleTag({ content: paletteCss(palette) });
  await page.evaluate((colors) => {
    const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
    if (!map) return;
    const set = (id, property, value) => {
      if (map.getLayer(id)) map.setPaintProperty(id, property, value);
    };
    set("guided-area-fill", "fill-color", colors.seaGlass);
    set("guided-area-halo", "line-color", colors.surface);
    set("guided-area-line", "line-color", colors.harborStrong);
    set("guided-area-label", "text-color", colors.harborStrong);
    set("mesh-top-fill", "fill-color", colors.seaGlass);
    set("mesh-top-line", "line-color", colors.harbor);
    set("mesh-top-label", "text-color", colors.harborStrong);
    set("guided-buildings-fill", "fill-color", colors.building);
    set("guided-buildings-line", "line-color", colors.buildingOutline);
    set("guided-roads-fill", "fill-color", colors.road);
    set("guided-roads-line", "line-color", colors.roadOutline);
    set("guided-section-halo", "line-color", colors.surface);
    set("guided-section-line", "line-color", colors.harbor);
    set("guided-section-points", "circle-color", colors.harbor);
    set("guided-target-fill", "fill-color", colors.target);
    set("guided-target-halo", "line-color", colors.surface);
    set("guided-target-line", "line-color", colors.targetStrong);
    set("guided-target-point", "circle-color", colors.target);
    set("guided-target-label", "text-color", colors.targetStrong);
  }, palette);
  await settle(page);
}

async function addSimulation(page, simulation) {
  await page.evaluate((kind) => {
    document.getElementById("harbor-simulation-filter")?.remove();
    const matrices = {
      protanopia: "0.567 0.433 0 0 0  0.558 0.442 0 0 0  0 0.242 0.758 0 0  0 0 0 1 0",
      deuteranopia: "0.625 0.375 0 0 0  0.7 0.3 0 0 0  0 0.3 0.7 0 0  0 0 0 1 0",
    };
    if (kind === "grayscale") {
      document.documentElement.style.filter = "grayscale(1)";
      return;
    }
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.id = "harbor-simulation-filter";
    svg.setAttribute("width", "0");
    svg.setAttribute("height", "0");
    svg.innerHTML = `<filter id="harbor-${kind}"><feColorMatrix type="matrix" values="${matrices[kind]}" /></filter>`;
    document.body.append(svg);
    document.documentElement.style.filter = `url(#harbor-${kind})`;
  }, simulation);
  await settle(page);
}

async function save(page, paletteId, state, viewport, locator = null, simulation = null) {
  const suffix = simulation ? `-${simulation}` : "";
  const filename = `${paletteId}-${state}-${viewport.width}x${viewport.height}${suffix}.png`;
  const target = path.join(outputDirectory, filename);
  const screenshotOptions = { path: target, animations: "disabled", timeout: 120_000 };
  if (locator) await locator.screenshot(screenshotOptions);
  else await page.screenshot({ ...screenshotOptions, fullPage: false });
  const buffer = await readFile(target);
  const metrics = await page.evaluate(() => ({
    horizontal_overflow_px: Math.max(0, document.documentElement.scrollWidth - innerWidth),
    visible_h1_count: [...document.querySelectorAll("h1")].filter((node) => {
      const rect = node.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    }).length,
    map_initialization_count: window.__cityGapMapInitCount ?? null,
    target_kind: document.querySelector(".guided-spatial-app")?.getAttribute("data-target-kind") ?? null,
    target_resolution: document.querySelector(".guided-spatial-app")?.getAttribute("data-target-resolution") ?? null,
  }));
  if (metrics.horizontal_overflow_px !== 0 || metrics.visible_h1_count !== 1 || metrics.map_initialization_count !== 1) {
    throw new Error(`palette capture contract failed for ${filename}: ${JSON.stringify(metrics)}`);
  }
  records.push({ palette: paletteId, state, simulation, filename, viewport, url: page.url(), bytes: buffer.length, sha256: sha256(buffer), metrics });
  process.stderr.write(`[harbor-palette] saved ${filename}\n`);
}

await mkdir(outputDirectory, { recursive: true });
const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"],
});

try {
  for (const [paletteId, palette] of Object.entries(palettes)) {
    const desktop = { width: 1440, height: 900 };
    const context = await browser.newContext({ viewport: desktop, deviceScaleFactor: 1, locale: "ja-JP", reducedMotion: "reduce", serviceWorkers: "block" });
    const page = await context.newPage();
    attachDiagnostics(page, paletteId);
    for (const state of ["public", "find", "understand", "verify"]) {
      await openState(page, state);
      await applyPalette(page, palette);
      await save(page, paletteId, state === "find" ? "scene1" : state === "understand" ? "scene2" : state === "verify" ? "scene3" : state, desktop);
      if (state === "understand") {
        await save(page, paletteId, "section", desktop, page.locator(".guided-section-dock"));
      }
    }
    await context.close();

    const mobile = { width: 390, height: 844 };
    const mobileContext = await browser.newContext({ viewport: mobile, deviceScaleFactor: 1, locale: "ja-JP", reducedMotion: "reduce", serviceWorkers: "block" });
    const mobilePage = await mobileContext.newPage();
    attachDiagnostics(mobilePage, `${paletteId}-mobile`);
    await openState(mobilePage, "understand");
    await applyPalette(mobilePage, palette);
    await mobilePage.locator(".guided-mobile-surface-switch button").nth(1).click();
    await mobilePage.locator(".guided-section-dock.mobile-visible").waitFor({ state: "visible" });
    await settle(mobilePage);
    await save(mobilePage, paletteId, "mobile-section", mobile);
    await mobileContext.close();
  }

  const simulationViewport = { width: 1440, height: 900 };
  for (const simulation of ["grayscale", "protanopia", "deuteranopia"]) {
    const context = await browser.newContext({ viewport: simulationViewport, deviceScaleFactor: 1, locale: "ja-JP", reducedMotion: "reduce", serviceWorkers: "block" });
    const page = await context.newPage();
    attachDiagnostics(page, `harbor-atlas-${simulation}`);
    await openState(page, simulation === "grayscale" ? "understand" : "verify");
    await applyPalette(page, palettes["harbor-atlas"]);
    await addSimulation(page, simulation);
    await save(page, "harbor-atlas", simulation === "grayscale" ? "scene2" : "scene3", simulationViewport, null, simulation);
    await context.close();
  }
} finally {
  await browser.close();
}

if (diagnostics.length) throw new Error(`palette capture diagnostics are not empty: ${JSON.stringify(diagnostics, null, 2)}`);

const manifest = {
  schema_version: "citygap.harbor-atlas-palette-study@1",
  generated_at: new Date().toISOString(),
  source_branch: execFileSync("git", ["branch", "--show-current"], { cwd: repositoryRoot, encoding: "utf8" }).trim(),
  source_commit: sourceCommit,
  source_url: rootUrl.toString(),
  protocol: "Playwright Chromium; production build; identical state URLs; CSS/runtime map overrides for capture only; reduced motion; font and compositor readiness",
  product_theme_selector_added: false,
  candidates: palettes,
  decision: "harbor-atlas",
  records,
  diagnostics,
};
await writeFile(path.join(outputDirectory, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
process.stdout.write(`${JSON.stringify({ outputDirectory, sourceCommit, candidates: Object.keys(palettes).length, records: records.length, diagnostics: diagnostics.length }, null, 2)}\n`);
