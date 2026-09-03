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
const outputDirectory = path.resolve(
  process.cwd(),
  parameters.get("--output") ?? "../docs/assets/final-visual-checkpoint",
);
const rootUrl = new URL(parameters.get("--url") ?? "http://127.0.0.1:4173/plateau-city-gap/");
const captureScope = parameters.get("--scope") ?? "all";
if (!["all", "desktop", "mobile", "dpr2"].includes(captureScope)) throw new Error(`unsupported capture scope: ${captureScope}`);
rootUrl.search = "";
rootUrl.hash = "";
const repositoryHead = execFileSync("git", ["rev-parse", "HEAD"], {
  cwd: repositoryRoot,
  encoding: "utf8",
}).trim();
const sourceCommit = execFileSync(
  "git",
  ["rev-parse", `${parameters.get("--source-commit") ?? repositoryHead}^{commit}`],
  { cwd: repositoryRoot, encoding: "utf8" },
).trim();
const branch = execFileSync("git", ["branch", "--show-current"], {
  cwd: repositoryRoot,
  encoding: "utf8",
}).trim();
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const records = [];
const diagnostics = [];
const beforeEvidence = [
  "docs/assets/public-product-audit/production-landing-desktop.png",
  "docs/assets/guided-spatial-checkpoint/desktop-intro.png",
  "docs/assets/guided-spatial-checkpoint/desktop-find-tsune.png",
  "docs/assets/guided-spatial-checkpoint/desktop-understand-533513314.png",
  "docs/assets/guided-spatial-checkpoint/desktop-verify-533513314.png",
  "docs/assets/guided-spatial-checkpoint/mobile-find.png",
  "docs/assets/guided-spatial-checkpoint/mobile-understand-map.png",
  "docs/assets/guided-spatial-checkpoint/mobile-understand-section.png",
  "docs/assets/guided-spatial-checkpoint/mobile-verify.png",
];

const launchOptions = {
  executablePath,
  headless: true,
  args: [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--enable-webgl",
    "--ignore-gpu-blocklist",
    "--enable-unsafe-swiftshader",
    "--use-gl=angle",
    "--use-angle=swiftshader",
  ],
};

function phase(message) {
  process.stderr.write(`[final-visual] ${message}\n`);
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function pageUrl(query = "") {
  const target = new URL(rootUrl);
  target.search = query.startsWith("?") ? query : `?${query}`;
  return target.toString();
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

async function waitForMap(page, requireGuidedReady = true) {
  await page.locator(".analytical-map-shell").waitFor({ state: "visible", timeout: 180_000 });
  await page.waitForFunction((guidedReady) => {
    const shell = document.querySelector(".analytical-map-shell");
    return guidedReady
      ? shell?.getAttribute("data-guided-visual-ready") === "true"
      : shell?.getAttribute("data-public-cartography-ready") === "true";
  }, requireGuidedReady, { timeout: 180_000 });
  await settleFrames(page);
}

async function openPublic(page) {
  await page.goto(pageUrl(), { waitUntil: "domcontentloaded", timeout: 180_000 });
  await page.locator('.public-area[data-public-step="intro"]').waitFor({ timeout: 180_000 });
  await waitForMap(page, false);
}

async function openGuided(page, story, mesh = "533513314") {
  phase(`open guided ${story} ${mesh}`);
  await page.goto(pageUrl(`experience=guided&story=${story}&mesh=${mesh}`), {
    waitUntil: "domcontentloaded",
    timeout: 180_000,
  });
  const contextStatus = story === "intro" || story === "find" ? "idle" : "ready";
  await page.locator(`.guided-spatial-app[data-guided-story="${story}"][data-area-id="${mesh}"][data-context-status="${contextStatus}"]`).waitFor({ timeout: 180_000 });
  phase(`context ready ${story} ${mesh}`);
  await waitForMap(page);
  phase(`map ready ${story} ${mesh}`);
  if (story === "understand" && mesh === "533513314") {
    await page.locator('.guided-spatial-app[data-section-pack="maizuru-533513314-plateau-2025-v1"]').waitFor({ timeout: 180_000 });
    await page.locator('.urban-section[data-terrain-samples="94"][data-direct-building-count="17"][data-direct-road-count="14"]').waitFor({ state: "attached", timeout: 180_000 });
  }
  if (story === "verify" && mesh === "533513314") {
    await page.locator('.guided-spatial-app[data-target-kind="road"][data-target-resolution="exact"]').waitFor({ timeout: 180_000 });
  }
  await settleFrames(page);
}

async function visualMetrics(page) {
  return page.evaluate(() => {
    const visible = (node) => {
      if (!(node instanceof HTMLElement)) return false;
      const rect = node.getBoundingClientRect();
      const style = getComputedStyle(node);
      return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
    };
    const rectOf = (selector) => document.querySelector(selector)?.getBoundingClientRect() ?? null;
    const map = rectOf(".guided-map-stage, .public-map-stage");
    const panel = rectOf(".guided-story-panel, .public-area-panel");
    const workspace = rectOf(".guided-spatial-workspace, .public-area-body");
    const overlays = [...document.querySelectorAll([
      ".guided-map-caption",
      ".guided-context-legend",
      ".public-map-caption",
      ".public-map-legend",
      ".public-map-area-badge",
      ".public-map-target-label",
      ".maplibregl-control-container .maplibregl-ctrl",
    ].join(","))].filter(visible);
    const occluded = map ? overlays.reduce((total, node) => {
      const rect = node.getBoundingClientRect();
      const width = Math.max(0, Math.min(map.right, rect.right) - Math.max(map.left, rect.left));
      const height = Math.max(0, Math.min(map.bottom, rect.bottom) - Math.max(map.top, rect.top));
      return total + width * height;
    }, 0) : 0;
    const actionables = [...document.querySelectorAll('button, a[href], select, input, [role="button"]')].filter(visible);
    const primary = [...document.querySelectorAll(".guided-primary, .public-primary")].filter(visible);
    const root = document.querySelector(".guided-spatial-app");
    const mapInstance = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
    const targetFeature = mapInstance?.getSource("guided-target")?.serialize?.().data?.features?.[0];
    const sectionFeature = mapInstance?.getSource("guided-section")?.serialize?.().data?.features?.[0];
    const bodyText = document.body.innerText;
    const mapShell = document.querySelector(".analytical-map-shell");
    return {
      viewport: { width: innerWidth, height: innerHeight },
      orientation: innerWidth > 900 ? "horizontal" : "vertical",
      map_share_percent: map && workspace
        ? Number(((innerWidth > 900 ? map.width / workspace.width : map.height / workspace.height) * 100).toFixed(1))
        : null,
      panel_share_percent: panel && workspace
        ? Number(((innerWidth > 900 ? panel.width / workspace.width : panel.height / workspace.height) * 100).toFixed(1))
        : null,
      map_occlusion_percent: map ? Number(((occluded / (map.width * map.height)) * 100).toFixed(1)) : null,
      visible_actionable_controls: actionables.length,
      primary_cta_count: primary.length,
      visible_h1_count: [...document.querySelectorAll("h1")].filter(visible).length,
      page_horizontal_overflow_px: Math.max(0, document.documentElement.scrollWidth - innerWidth),
      page_vertical_overflow_px: Math.max(0, document.documentElement.scrollHeight - innerHeight),
      section_plot_height_px: rectOf(".guided-section-dock svg")?.height ?? null,
      section_line_coordinates: sectionFeature?.geometry?.coordinates ?? null,
      target_kind: root?.getAttribute("data-target-kind") ?? null,
      target_resolution: root?.getAttribute("data-target-resolution") ?? null,
      target_source_id: targetFeature?.properties?.source_id ?? targetFeature?.properties?.source_object_id ?? null,
      target_geometry_type: targetFeature?.geometry?.type ?? null,
      map_initialization_count: window.__cityGapMapInitCount ?? null,
      map_render_state: mapShell?.getAttribute("data-map-render-state") ?? null,
      forbidden_internal_copy: /AWAITING_|BASELINE_NOT_COLLECTED|SUPPORTED|GUIDED STORY|validation_status/.test(bodyText),
      fake_field_evidence_copy: /GPS|写真を撮影|回答済み|レビュー済み/.test(bodyText),
    };
  });
}

async function saveScreenshot(page, filename, metadata, locator = null) {
  phase(`capture ${filename}`);
  const target = path.join(outputDirectory, filename);
  const options = { path: target, animations: "disabled", timeout: 120_000 };
  if (locator) await locator.screenshot(options);
  else await page.screenshot({ ...options, fullPage: false });
  const buffer = await readFile(target);
  const metrics = await visualMetrics(page);
  if (metrics.visible_h1_count !== 1 || metrics.primary_cta_count > 1 || metrics.page_horizontal_overflow_px > 0 || metrics.forbidden_internal_copy || metrics.fake_field_evidence_copy) {
    throw new Error(`visual contract failed for ${filename}: ${JSON.stringify(metrics)}`);
  }
  records.push({
    filename,
    ...metadata,
    final_url: page.url(),
    bytes: buffer.length,
    sha256: sha256(buffer),
    metrics,
  });
  phase(`saved ${filename}`);
}

async function captureDesktop(browser) {
  phase("desktop sequence");
  const viewport = { width: 1440, height: 900 };
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1, locale: "ja-JP", reducedMotion: "reduce" });
  const page = await context.newPage();
  attachDiagnostics(page, "desktop");

  await openPublic(page);
  await saveScreenshot(page, "01-public-landing-desktop.png", { state: "public-landing", viewport, dpr: 1 });
  await openGuided(page, "intro");
  await saveScreenshot(page, "02-guided-intro-desktop.png", { state: "guided-intro", viewport, dpr: 1 });
  await openGuided(page, "find");
  await saveScreenshot(page, "03-scene1-find-desktop.png", { state: "scene-1-find", viewport, dpr: 1 });
  await openGuided(page, "understand");
  await saveScreenshot(page, "04-scene2-hero-desktop.png", { state: "scene-2-understand", viewport, dpr: 1 });
  await saveScreenshot(
    page,
    "05-scene2-section-closeup.png",
    { state: "scene-2-section-closeup", viewport, dpr: 1 },
    page.locator(".guided-section-dock"),
  );
  await openGuided(page, "verify");
  await saveScreenshot(page, "06-scene3-exact-road.png", { state: "scene-3-exact-road", viewport, dpr: 1 });
  await openGuided(page, "understand", "533522274");
  await saveScreenshot(page, "07-another-area.png", { state: "another-area", area: "533522274", viewport, dpr: 1 });
  await openGuided(page, "verify", "533512753");
  await saveScreenshot(page, "08-fallback-area.png", { state: "fallback-area", area: "533512753", viewport, dpr: 1 });

  await context.close();
}

async function captureMobile(browser) {
  phase("mobile sequence");
  const viewport = { width: 390, height: 844 };
  const storyContext = await browser.newContext({ viewport, deviceScaleFactor: 1, locale: "ja-JP", reducedMotion: "reduce" });
  const page = await storyContext.newPage();
  attachDiagnostics(page, "mobile-understand-verify");
  await openGuided(page, "understand");
  await saveScreenshot(page, "10-mobile-scene2-map.png", { state: "mobile-scene-2-map", viewport, dpr: 1 });
  await page.getByRole("button", { name: "街の断面", exact: true }).click();
  await page.locator(".guided-section-dock.mobile-visible").waitFor({ state: "visible" });
  await page.waitForFunction(() => (document.querySelector(".guided-section-dock svg")?.getBoundingClientRect().height ?? 0) >= 300);
  await settleFrames(page);
  await saveScreenshot(page, "11-mobile-scene2-section.png", { state: "mobile-scene-2-section", viewport, dpr: 1 });
  await page.getByRole("button", { name: "地図", exact: true }).click();
  await page.getByRole("button", { name: "確認場所を見る", exact: true }).click();
  await page.locator('.guided-spatial-app[data-guided-story="verify"][data-target-kind="road"][data-target-resolution="exact"]').waitFor({ timeout: 180_000 });
  await waitForMap(page);
  await saveScreenshot(page, "12-mobile-scene3.png", { state: "mobile-scene-3", viewport, dpr: 1 });

  await storyContext.close();

  const findContext = await browser.newContext({ viewport, deviceScaleFactor: 1, locale: "ja-JP", reducedMotion: "reduce" });
  const findPage = await findContext.newPage();
  attachDiagnostics(findPage, "mobile-find");
  await openGuided(findPage, "find");
  await saveScreenshot(findPage, "09-mobile-scene1.png", { state: "mobile-scene-1", viewport, dpr: 1 });
  await findContext.close();
}

async function captureDpr2(browser) {
  phase("DPR2 sequence");
  const viewport = { width: 1440, height: 900 };
  const context = await browser.newContext({ viewport, deviceScaleFactor: 2, locale: "ja-JP", reducedMotion: "reduce" });
  const page = await context.newPage();
  attachDiagnostics(page, "dpr2");
  await openGuided(page, "understand");
  await saveScreenshot(page, "13-dpr2-scene2.png", { state: "dpr2-scene-2", viewport, dpr: 2 });
  await context.close();
}

await mkdir(outputDirectory, { recursive: true });
let runtime;
let browser = await chromium.launch(launchOptions);
try {
  const probe = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  runtime = await probe.evaluate(() => ({
    user_agent: navigator.userAgent,
    playwright: navigator.webdriver,
  }));
  await probe.close();
  if (captureScope === "all" || captureScope === "desktop") await captureDesktop(browser);
} finally {
  await browser.close();
}
if (captureScope === "all" || captureScope === "mobile") {
  browser = await chromium.launch(launchOptions);
  try {
    await captureMobile(browser);
  } finally {
    await browser.close();
  }
}
if (captureScope === "all" || captureScope === "dpr2") {
  browser = await chromium.launch(launchOptions);
  try {
    await captureDpr2(browser);
  } finally {
    await browser.close();
  }
}

if (diagnostics.length) throw new Error(`browser diagnostics are not empty: ${JSON.stringify(diagnostics, null, 2)}`);

const before = [];
for (const relative of beforeEvidence) {
  const buffer = await readFile(path.join(repositoryRoot, relative));
  before.push({ path: relative, bytes: buffer.length, sha256: sha256(buffer) });
}

const manifest = {
  schema_version: "citygap.final-visual-checkpoint@1",
  generated_at: new Date().toISOString(),
  environment: rootUrl.hostname === "catlover-bot.github.io" ? "production" : "production-preview",
  source_url: rootUrl.toString(),
  source_branch: branch,
  source_commit: sourceCommit,
  pages_run_id: parameters.get("--pages-run-id") ?? null,
  capture_protocol: "Playwright Chromium; readiness attributes + fonts + compositor frames; reduced motion",
  capture_scope: captureScope,
  runtime,
  click_count_to_exact_task: 4,
  before_evidence: before,
  records: records.sort((left, right) => left.filename.localeCompare(right.filename)),
  diagnostics,
};
await writeFile(path.join(outputDirectory, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
process.stdout.write(`${JSON.stringify({ outputDirectory, records: records.length, sourceCommit, diagnostics: diagnostics.length }, null, 2)}\n`);
