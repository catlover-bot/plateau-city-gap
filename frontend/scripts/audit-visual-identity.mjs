import { gzipSync } from "node:zlib";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, readdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright-core";

const args = new Map();
for (let index = 2; index < process.argv.length; index += 2) {
  args.set(process.argv[index], process.argv[index + 1]);
}

const baseUrl = args.get("--url") ?? "http://127.0.0.1:4173/plateau-city-gap/";
const label = args.get("--label") ?? "current";
const output = path.resolve(
  process.cwd(),
  args.get("--output") ?? `../analysis/outputs/real/visual-identity/${label}.json`,
);
const screenshotDirectory = args.has("--screenshots")
  ? path.resolve(process.cwd(), args.get("--screenshots"))
  : null;
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
  ?? chromium.executablePath();
const viewports = [
  { width: 1440, height: 900 },
  { width: 1280, height: 800 },
  { width: 1024, height: 768 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
];
const commit = execFileSync("git", ["rev-parse", "HEAD"], { cwd: path.resolve(process.cwd(), ".."), encoding: "utf8" }).trim();

async function filesBelow(directory) {
  const entries = await readdir(directory, { withFileTypes: true }).catch(() => []);
  const nested = await Promise.all(entries.map(async (entry) => {
    const target = path.join(directory, entry.name);
    return entry.isDirectory() ? filesBelow(target) : [target];
  }));
  return nested.flat();
}

async function fileInventory() {
  const frontendRoot = process.cwd();
  const repositoryRoot = path.dirname(frontendRoot);
  const cssSources = (await filesBelow(path.join(frontendRoot, "src")))
    .filter((file) => file.endsWith(".css"));
  const buildAssets = (await filesBelow(path.join(frontendRoot, "dist", "assets")))
    .filter((file) => /\.(css|js)$/.test(file) && !file.includes("worker"));
  const screenshots = (await filesBelow(path.join(repositoryRoot, "docs", "assets")))
    .filter((file) => /\.(png|webp|jpe?g)$/i.test(file));
  const describe = async (file) => {
    const content = await readFile(file);
    return {
      path: path.relative(repositoryRoot, file).replaceAll(path.sep, "/"),
      bytes: content.byteLength,
      gzipBytes: gzipSync(content).byteLength,
    };
  };
  const css = await Promise.all(cssSources.map(describe));
  const assets = await Promise.all(buildAssets.map(describe));
  const screenshotSizes = await Promise.all(screenshots.map((file) => stat(file).then((item) => item.size)));
  return {
    sourceCss: css.sort((left, right) => left.path.localeCompare(right.path)),
    sourceCssBytes: css.reduce((sum, item) => sum + item.bytes, 0),
    buildAssets: assets.sort((left, right) => left.path.localeCompare(right.path)),
    screenshotCount: screenshots.length,
    screenshotBytes: screenshotSizes.reduce((sum, size) => sum + size, 0),
  };
}

const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--enable-webgl",
    "--ignore-gpu-blocklist",
    "--use-gl=swiftshader",
  ],
});

const report = {
  schemaVersion: "citygap.visual-identity-audit@1",
  label,
  commit,
  baseUrl,
  generatedAt: new Date().toISOString(),
  viewports: [],
  consoleErrors: [],
  localHttpFailures: [],
  files: await fileInventory(),
};

if (screenshotDirectory) await mkdir(screenshotDirectory, { recursive: true });

function observe(page, viewport) {
  const key = `${viewport.width}x${viewport.height}`;
  page.on("console", (message) => {
    if (message.type() === "error") report.consoleErrors.push({ viewport: key, text: message.text() });
  });
  page.on("pageerror", (error) => report.consoleErrors.push({ viewport: key, text: error.message }));
  page.on("response", (response) => {
    if (response.url().startsWith(baseUrl) && response.status() >= 400) {
      report.localHttpFailures.push({ viewport: key, status: response.status(), url: response.url() });
    }
  });
}

for (const viewport of viewports) {
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1 });
  observe(page, viewport);
  const started = Date.now();
  await page.goto(`${baseUrl}?experience=advanced&city=maizuru&scene=gap_discovery`, {
    waitUntil: "domcontentloaded",
    timeout: 90_000,
  });
  await page.waitForSelector(".product-app", { timeout: 90_000 });
  await page.waitForSelector(".analytical-map-canvas canvas", { timeout: 90_000 });
  await page.waitForFunction(() => document.fonts.status === "loaded", { timeout: 30_000 });
  await page.waitForFunction(() => {
    const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
    return Boolean(map?.loaded() && map?.isStyleLoaded());
  }, { timeout: 30_000 });

  const metrics = await page.evaluate(() => {
    const visible = (element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
    };
    const elements = [...document.querySelectorAll("body *")].filter(visible);
    const parseRadius = (style) => Number.parseFloat(style.borderTopLeftRadius) || 0;
    const isSurface = (style) => style.backgroundColor !== "rgba(0, 0, 0, 0)"
      && style.backgroundColor !== "transparent";
    const colors = new Set();
    const saturated = (value) => {
      const channels = value.match(/[\d.]+/g)?.slice(0, 3).map(Number) ?? [];
      return channels.length === 3 && Math.max(...channels) - Math.min(...channels) >= 36;
    };
    let roundedSurfaceCount = 0;
    let pillCount = 0;
    let gradientCount = 0;
    let shadowCount = 0;
    let floatingPanelCount = 0;
    const floatingPanels = [];
    let borderedSurfaceCount = 0;
    let maximumRadiusPx = 0;
    for (const element of elements) {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      const radius = parseRadius(style);
      maximumRadiusPx = Math.max(maximumRadiusPx, radius);
      if (isSurface(style) && radius > 4 && rect.width >= 32 && rect.height >= 20) roundedSurfaceCount += 1;
      if (isSurface(style) && radius >= rect.height * 0.4 && rect.width > rect.height * 1.15) pillCount += 1;
      if (style.backgroundImage.includes("gradient")) gradientCount += 1;
      if (style.boxShadow !== "none") shadowCount += 1;
      if ((style.position === "absolute" || style.position === "fixed") && isSurface(style) && rect.width >= 120) {
        floatingPanelCount += 1;
        floatingPanels.push({
          tag: element.tagName.toLowerCase(),
          className: element.className?.toString() ?? "",
          width: Math.round(rect.width),
          height: Math.round(rect.height),
        });
      }
      if (isSurface(style) && [style.borderTopWidth, style.borderRightWidth, style.borderBottomWidth, style.borderLeftWidth].some((width) => Number.parseFloat(width) > 0)) borderedSurfaceCount += 1;
      for (const color of [style.color, style.backgroundColor, style.borderTopColor]) {
        if (saturated(color)) colors.add(color);
      }
    }
    const map = document.querySelector(".map-stage")?.getBoundingClientRect();
    const bodyText = document.body.innerText;
    const classCardCount = elements.filter((element) => /(^|\s|[-_])(card|tile)([-_]|\s|$)/i.test(element.className?.toString() ?? "")).length;
    return {
      visibleElementCount: elements.length,
      classCardCount,
      roundedSurfaceCount,
      pillCount,
      gradientCount,
      shadowCount,
      floatingPanelCount,
      floatingPanels,
      persistentMajorSurfaceCount: [
        document.querySelector(".task-navigation"),
        document.querySelector(".context-inspector:not(.closed)"),
        document.querySelector(".urban-section"),
      ].filter((element) => element && visible(element)).length,
      borderedSurfaceCount,
      maximumRadiusPx,
      accentColorCount: colors.size,
      accentColors: [...colors].sort(),
      horizontalOverflow: document.documentElement.scrollWidth > innerWidth,
      mapWidthPx: map ? Math.round(map.width) : 0,
      mapHeightPx: map ? Math.round(map.height) : 0,
      mapWidthPercent: map ? Number((map.width / innerWidth * 100).toFixed(1)) : 0,
      mapAreaPercent: map ? Number((map.width * map.height / (innerWidth * innerHeight) * 100).toFixed(1)) : 0,
      marketingWordCount: (bodyText.match(/革新的|スマート|高度|AI|未来|最適/g) ?? []).length,
      navigationLandmarks: document.querySelectorAll("nav").length,
      mainLandmarks: document.querySelectorAll("main").length,
      unnamedButtons: elements.filter((element) => element.tagName === "BUTTON" && !(element.getAttribute("aria-label") || element.textContent?.trim())).length,
    };
  });

  report.viewports.push({
    ...viewport,
    productReadyMs: Date.now() - started,
    ...metrics,
  });
  if (screenshotDirectory) {
    await page.screenshot({
      path: path.join(screenshotDirectory, `${label}-${viewport.width}x${viewport.height}.png`),
      fullPage: false,
    });
  }
  await page.close();
}

report.consoleErrors = report.consoleErrors.filter((entry, index, entries) => (
  entries.findIndex((candidate) => candidate.viewport === entry.viewport && candidate.text === entry.text) === index
));
report.localHttpFailures = report.localHttpFailures.filter((entry, index, entries) => (
  entries.findIndex((candidate) => candidate.status === entry.status && candidate.url === entry.url) === index
));

await mkdir(path.dirname(output), { recursive: true });
await writeFile(output, `${JSON.stringify(report, null, 2)}\n`, "utf8");
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
await browser.close();

if (
  report.consoleErrors.length
  || report.localHttpFailures.length
  || report.viewports.some((item) => item.horizontalOverflow || item.persistentMajorSurfaceCount > 3)
) {
  process.exitCode = 1;
}
