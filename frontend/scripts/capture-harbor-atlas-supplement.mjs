import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright-core";

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
const phase = args.get("--phase") ?? "before";
const repositoryRoot = path.resolve(process.cwd(), "..");
const outputDirectory = path.resolve(
  process.cwd(),
  args.get("--output") ?? `../docs/assets/harbor-atlas-v2/${phase}`,
);
const commit = execFileSync("git", ["rev-parse", "HEAD"], { cwd: repositoryRoot, encoding: "utf8" }).trim();
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const records = [];
const diagnostics = [];
const sha256 = (value) => createHash("sha256").update(value).digest("hex");

function pageUrl(query = "") {
  const target = new URL(rootUrl);
  target.search = query ? `?${query}` : "";
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

async function waitForGuidedMap(page) {
  await page.locator(".analytical-map-shell").waitFor({ state: "visible", timeout: 180_000 });
  await page.waitForFunction(() => document.querySelector(".analytical-map-shell")?.getAttribute("data-guided-visual-ready") === "true", null, { timeout: 180_000 });
  await settle(page);
}

async function openGuided(page, story, mesh = "533513314") {
  await page.goto(pageUrl(`experience=guided&story=${story}&selectionType=mesh&selection=${mesh}&mesh=${mesh}`), { waitUntil: "domcontentloaded", timeout: 180_000 });
  const status = story === "find" ? "idle" : "ready";
  await page.locator(`.guided-spatial-app[data-guided-story="${story}"][data-context-status="${status}"]`).waitFor({ timeout: 180_000 });
  await waitForGuidedMap(page);
}

async function metrics(page) {
  return page.evaluate(() => {
    const visible = (node) => {
      if (!(node instanceof Element)) return false;
      const style = getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity) !== 0;
    };
    const map = document.querySelector(".guided-map-stage, .public-map-stage, .map-stage")?.getBoundingClientRect() ?? null;
    const panel = document.querySelector(".guided-story-panel, .public-area-panel, .context-inspector")?.getBoundingClientRect() ?? null;
    const actionables = [...document.querySelectorAll('button, a[href], select, input, [role="button"]')].filter(visible);
    const primary = [...document.querySelectorAll(".guided-primary, .public-primary, .primary-action")].filter(visible);
    const all = [...document.querySelectorAll("body *")].filter(visible);
    const cards = all.filter((node) => /(^|[-_ ])(card|tile)([-_ ]|$)/i.test(node.className?.toString() ?? ""));
    const pills = all.filter((node) => {
      const style = getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      return rect.height >= 18 && rect.width > rect.height * 1.15 && Number.parseFloat(style.borderTopLeftRadius) >= rect.height * .4;
    });
    const shadows = all.filter((node) => getComputedStyle(node).boxShadow !== "none");
    const borders = all.filter((node) => ["Top", "Right", "Bottom", "Left"].some((side) => Number.parseFloat(getComputedStyle(node)[`border${side}Width`]) > 0));
    return {
      viewport: { width: innerWidth, height: innerHeight },
      map_share_percent: map ? Number((map.width / innerWidth * 100).toFixed(1)) : null,
      panel_share_percent: panel ? Number((panel.width / innerWidth * 100).toFixed(1)) : null,
      visible_controls: actionables.length,
      primary_actions: primary.length,
      card_count: cards.length,
      pill_count: pills.length,
      shadow_count: shadows.length,
      border_count: borders.length,
      heading_count: [...document.querySelectorAll("h1, h2, h3, h4")].filter(visible).length,
      paragraph_count: [...document.querySelectorAll("p")].filter(visible).length,
      map_label_count: [...document.querySelectorAll(".maplibregl-marker")].filter(visible).length,
      legend_item_count: [...document.querySelectorAll(".guided-context-legend span, .section-visual-legend span")].filter(visible).length,
      section_annotation_count: [...document.querySelectorAll("[data-section-static-annotation], [data-section-endpoint]")].filter(visible).length,
      map_initialization_count: window.__cityGapMapInitCount ?? null,
      horizontal_overflow_px: Math.max(0, document.documentElement.scrollWidth - innerWidth),
      visible_h1_count: [...document.querySelectorAll("h1")].filter(visible).length,
      experience: document.querySelector(".product-app")?.getAttribute("data-experience") ?? (document.querySelector(".guided-spatial-app") ? "guided" : document.querySelector(".public-area") ? "public" : "loading"),
      target_kind: document.querySelector(".guided-spatial-app")?.getAttribute("data-target-kind") ?? null,
      target_resolution: document.querySelector(".guided-spatial-app")?.getAttribute("data-target-resolution") ?? null,
    };
  });
}

async function save(page, filename, state) {
  const target = path.join(outputDirectory, filename);
  await page.screenshot({ path: target, fullPage: false, animations: "disabled", timeout: 120_000 });
  const buffer = await readFile(target);
  records.push({ filename, state, url: page.url(), bytes: buffer.length, sha256: sha256(buffer), metrics: await metrics(page) });
  process.stderr.write(`[harbor-supplement:${phase}] saved ${filename}\n`);
}

await mkdir(outputDirectory, { recursive: true });
const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"],
});

try {
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "ja-JP", reducedMotion: "reduce", serviceWorkers: "block" });
    const page = await context.newPage();
    watch(page, "guided-supplement");
    await openGuided(page, "find");
    const rows = page.locator(".guided-area-list button");
    await rows.nth(1).hover();
    await settle(page);
    await save(page, "16-scene1-hover-area.png", "scene-1-hover");

    await openGuided(page, "verify", "533513611");
    const select = page.locator(".guided-target-select select");
    await page.waitForFunction(() => [...document.querySelectorAll(".guided-target-select option")].some((option) => option.value.startsWith("facility:")), null, { timeout: 180_000 });
    const facilityValue = await select.locator("option").evaluateAll((options) => options.map((option) => option.value).find((value) => value.startsWith("facility:")) ?? null);
    if (!facilityValue) throw new Error("facility target is unavailable");
    await select.selectOption(facilityValue);
    await page.locator('.guided-spatial-app[data-target-kind="facility"][data-target-resolution="exact"]').waitFor({ timeout: 180_000 });
    await waitForGuidedMap(page);
    await save(page, "17-facility-reference.png", "facility-reference");
    await context.close();
  }

  {
    const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, locale: "ja-JP", reducedMotion: "reduce", serviceWorkers: "block" });
    const page = await context.newPage();
    watch(page, "public-1920");
    await page.goto(pageUrl(), { waitUntil: "domcontentloaded", timeout: 180_000 });
    await page.locator('.public-area[data-public-step="intro"]').waitFor({ timeout: 180_000 });
    await page.waitForFunction(() => document.querySelector(".analytical-map-shell")?.getAttribute("data-public-cartography-ready") === "true", null, { timeout: 180_000 });
    await settle(page);
    await save(page, "18-public-landing-1920.png", "public-landing-1920");
    await context.close();
  }

  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "ja-JP", reducedMotion: "reduce", serviceWorkers: "block" });
    let releaseMarker;
    let markerSeen;
    const markerPromise = new Promise((resolve) => { markerSeen = resolve; });
    const releasePromise = new Promise((resolve) => { releaseMarker = resolve; });
    await context.route("**/data/robustness.json", async (route) => {
      markerSeen();
      await releasePromise;
      await route.continue();
    });
    const page = await context.newPage();
    watch(page, "advanced");
    await page.goto(pageUrl("experience=advanced&city=maizuru&task=operate"), { waitUntil: "domcontentloaded", timeout: 180_000 });
    await markerPromise;
    await page.locator(".state-screen:not(.error-state)").waitFor({ state: "visible", timeout: 180_000 });
    await settle(page);
    await save(page, "19-advanced-loading.png", "advanced-loading");
    releaseMarker();
    await page.locator('.product-app[data-experience="advanced"] .map-stage').waitFor({ state: "visible", timeout: 180_000 });
    await settle(page);
    await save(page, "20-advanced-ready.png", "advanced-ready");
    await context.close();
  }
} finally {
  await browser.close();
}

if (diagnostics.length) throw new Error(`supplement diagnostics are not empty: ${JSON.stringify(diagnostics, null, 2)}`);
const manifest = {
  schema_version: "citygap.harbor-atlas-supplement@1",
  generated_at: new Date().toISOString(),
  phase,
  source_branch: execFileSync("git", ["branch", "--show-current"], { cwd: repositoryRoot, encoding: "utf8" }).trim(),
  source_commit: commit,
  source_url: rootUrl.toString(),
  records,
  diagnostics,
};
await writeFile(path.join(outputDirectory, "supplement-manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
process.stdout.write(`${JSON.stringify({ outputDirectory, phase, records: records.length, diagnostics: diagnostics.length }, null, 2)}\n`);
