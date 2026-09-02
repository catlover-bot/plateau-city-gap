import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { chromium } from "playwright-core";

const parameters = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const key = process.argv[index];
  if (!key.startsWith("--")) continue;
  const value = process.argv[index + 1];
  parameters.set(key, value && !value.startsWith("--") ? value : "true");
  if (value && !value.startsWith("--")) index += 1;
}

const baseUrl = parameters.get("--url") ?? "http://127.0.0.1:4173/plateau-city-gap/?experience=guided&story=intro";
const sampleCount = Number.parseInt(parameters.get("--samples") ?? "5", 10);
const outputPath = resolve(
  process.cwd(),
  parameters.get("--output") ?? "../analysis/outputs/real/guided-spatial-performance.json",
);
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();

const browser = await chromium.launch({
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
});

const samples = [];
const median = (values) => [...values].sort((left, right) => left - right)[Math.floor(values.length / 2)];

async function browserNow(page) {
  return page.evaluate(() => performance.now());
}

async function compositorTimestamp(page) {
  return page.evaluate(() => new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve(performance.now())));
  }));
}

async function waitForVisual(page, story) {
  await page.locator(`.guided-spatial-app[data-guided-story="${story}"][data-context-status="${story === "intro" || story === "find" ? "idle" : "ready"}"]`).waitFor({ timeout: 120_000 });
  await page.waitForFunction(
    () => document.querySelector(".analytical-map-shell")?.getAttribute("data-guided-visual-ready") === "true",
    null,
    { timeout: 120_000 },
  );
}

try {
  for (let index = 0; index < sampleCount; index += 1) {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
      reducedMotion: "reduce",
      serviceWorkers: "block",
    });
    await context.route("https://cyberjapandata.gsi.go.jp/**", (route) => route.abort("blockedbyclient"));
    const page = await context.newPage();
    page.setDefaultTimeout(120_000);
    page.on("pageerror", (error) => process.stderr.write(`[guided-profile] pageerror: ${error.message}\n`));
    page.on("console", (message) => {
      if (message.type() === "error" && !message.text().includes("cyberjapandata.gsi.go.jp")) {
        process.stderr.write(`[guided-profile] console: ${message.text()}\n`);
      }
    });

    await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 120_000 });
    await page.locator('.guided-spatial-app[data-guided-story="intro"]').waitFor({ timeout: 120_000 });
    const firstMeaningfulRenderMs = Number((await compositorTimestamp(page)).toFixed(1));

    await page.getByRole("button", { name: "デモを始める", exact: true }).click();
    await waitForVisual(page, "find");

    const contextStarted = await browserNow(page);
    await page.getByRole("button", { name: "街の形を見る", exact: true }).click();
    await waitForVisual(page, "understand");
    const areaContextColdMs = Number(((await compositorTimestamp(page)) - contextStarted).toFixed(1));

    const roadStarted = await browserNow(page);
    await page.getByRole("button", { name: "確認場所を見る", exact: true }).click();
    await waitForVisual(page, "verify");
    await page.locator('.guided-spatial-app[data-target-kind="road"][data-target-resolution="exact"]').waitFor();
    const exactRoadWarmMs = Number(((await compositorTimestamp(page)) - roadStarted).toFixed(1));

    const buildingValue = await page.locator('.guided-target-select option[value^="building:"]').first().getAttribute("value");
    if (!buildingValue) throw new Error("Exact building target is unavailable");
    const buildingStarted = await browserNow(page);
    await page.locator(".guided-target-select select").selectOption(buildingValue);
    await page.locator('.guided-spatial-app[data-target-kind="building"][data-target-resolution="exact"]').waitFor();
    await page.waitForFunction(
      () => document.querySelector(".analytical-map-shell")?.getAttribute("data-guided-visual-ready") === "true",
    );
    const exactBuildingWarmMs = Number(((await compositorTimestamp(page)) - buildingStarted).toFixed(1));

    const returnStarted = await browserNow(page);
    await page.getByRole("button", { name: "街の形へ戻る", exact: true }).click();
    await waitForVisual(page, "understand");
    const buildingStoryWarmMs = Number(((await compositorTimestamp(page)) - returnStarted).toFixed(1));

    samples.push({
      sample: index + 1,
      first_meaningful_render_ms: firstMeaningfulRenderMs,
      area_context_cold_ms: areaContextColdMs,
      exact_road_warm_ms: exactRoadWarmMs,
      exact_building_warm_ms: exactBuildingWarmMs,
      building_story_warm_ms: buildingStoryWarmMs,
    });
    process.stderr.write(`[guided-profile] ${index + 1}/${sampleCount} ${JSON.stringify(samples.at(-1))}\n`);
    await context.close();
  }
} finally {
  await browser.close();
}

const medians = {
  first_meaningful_render_ms: median(samples.map((sample) => sample.first_meaningful_render_ms)),
  area_context_cold_ms: median(samples.map((sample) => sample.area_context_cold_ms)),
  exact_road_warm_ms: median(samples.map((sample) => sample.exact_road_warm_ms)),
  exact_building_warm_ms: median(samples.map((sample) => sample.exact_building_warm_ms)),
  building_story_warm_ms: median(samples.map((sample) => sample.building_story_warm_ms)),
};
const gates = {
  first_meaningful_render: { target_ms: 2000, pass: medians.first_meaningful_render_ms <= 2000 },
  exact_road_warm: { target_ms: 1800, pass: medians.exact_road_warm_ms <= 1800 },
  exact_building_warm: { target_ms: 2500, pass: medians.exact_building_warm_ms <= 2500 },
  building_story_warm: { target_ms: 2000, pass: medians.building_story_warm_ms <= 2000 },
};
const report = {
  schema_version: "citygap.guided-spatial-performance@1",
  generated_at: new Date().toISOString(),
  branch: execFileSync("git", ["branch", "--show-current"], { encoding: "utf8" }).trim(),
  commit: execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).trim(),
  protocol: "production-preview; 1440x900; DPR1; reduced motion; five fresh browser contexts",
  url: baseUrl,
  samples,
  medians,
  gates,
};

mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`);
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
if (Object.values(gates).some((gate) => !gate.pass)) process.exitCode = 1;
