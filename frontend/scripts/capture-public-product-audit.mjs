import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright-core";

process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY = "1";

const repositoryRoot = path.resolve(process.cwd(), "..");
const outputDirectory = path.join(repositoryRoot, "docs/assets/public-product-audit");
const featureUrl = process.argv[2] ?? "http://127.0.0.1:4180/plateau-city-gap/";
const productionUrl = "https://catlover-bot.github.io/plateau-city-gap/";
const repositoryHead = execFileSync("git", ["rev-parse", "HEAD"], {
  cwd: repositoryRoot,
  encoding: "utf8",
}).trim();
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const records = [];

const benchmarks = [
  {
    id: "field-maps",
    product: "ArcGIS Field Maps",
    url: "https://doc.arcgis.com/en/field-maps/android/use-maps/quick-reference.htm",
    evidenceStatus: "PARTIALLY_OBSERVED",
  },
  {
    id: "survey123",
    product: "ArcGIS Survey123",
    url: "https://doc.arcgis.com/en/survey123/capture/field-app/quickreferencegetanswers.htm",
    evidenceStatus: "PARTIALLY_OBSERVED",
  },
  {
    id: "arcgis-urban",
    product: "ArcGIS Urban",
    url: "https://doc.arcgis.com/en/urban/12.1/help/help-intro.htm",
    evidenceStatus: "PARTIALLY_OBSERVED",
  },
  {
    id: "maptionnaire",
    product: "Maptionnaire",
    url: "https://www.maptionnaire.com/",
    evidenceStatus: "TEXT_ONLY",
  },
  {
    id: "my-city-report",
    product: "My City Report",
    url: "https://web.mycityreport.jp/",
    evidenceStatus: "OBSERVED",
  },
  {
    id: "storymaps",
    product: "ArcGIS StoryMaps",
    url: "https://doc.arcgis.com/en/arcgis-storymaps/author-and-share/add-guided-tours.htm",
    evidenceStatus: "PARTIALLY_OBSERVED",
  },
  { id: "felt", product: "Felt", url: "https://felt.com/", evidenceStatus: "TEXT_ONLY" },
  { id: "carto", product: "CARTO", url: "https://carto.com/", evidenceStatus: "TEXT_ONLY" },
  { id: "mapbox", product: "Mapbox", url: "https://www.mapbox.com/", evidenceStatus: "TEXT_ONLY" },
];

const sha256 = (value) => createHash("sha256").update(value).digest("hex");

async function saveScreenshot(page, filename, metadata) {
  await page.evaluate(() => document.fonts?.ready).catch(() => undefined);
  const target = path.join(outputDirectory, filename);
  await page.screenshot({ path: target, fullPage: false, animations: "disabled", timeout: 90_000 });
  const buffer = await readFile(target);
  records.push({
    filename,
    ...metadata,
    final_url: page.url(),
    title: await page.title(),
    captured_at: new Date().toISOString(),
    bytes: buffer.length,
    sha256: sha256(buffer),
  });
}

async function captureProductBaseline(browser, id, url) {
  for (const viewport of [
    { name: "desktop", width: 1440, height: 900 },
    { name: "mobile", width: 390, height: 844 },
  ]) {
    const context = await browser.newContext({ viewport, deviceScaleFactor: 1, locale: "ja-JP" });
    const page = await context.newPage();
    let status = "OBSERVED";
    let error = null;
    try {
      const response = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 90_000 });
      if (!response?.ok()) status = "PARTIALLY_OBSERVED";
      await page.waitForTimeout(4_000);
      await saveScreenshot(page, `${id}-landing-${viewport.name}.png`, {
        kind: "product-baseline",
        product: id,
        requested_url: url,
        viewport,
        access_status: status,
        http_status: response?.status() ?? null,
      });

      if (id === "feature") {
        await page.getByRole("button", { name: "地図で場所を調べる", exact: true }).click();
        await page.locator('.public-area[data-public-step="place"]').waitFor();
        await saveScreenshot(page, `${id}-place-${viewport.name}.png`, {
          kind: "product-baseline",
          product: id,
          requested_url: url,
          viewport,
          access_status: status,
        });
        await page.getByRole("button", { name: "選んだ駅を起点にする", exact: true }).click();
        await page.locator('.public-area[data-public-step="radius"]').waitFor();
        await saveScreenshot(page, `${id}-radius-${viewport.name}.png`, {
          kind: "product-baseline",
          product: id,
          requested_url: url,
          viewport,
          access_status: status,
        });
        await page.getByRole("button", { name: "この範囲を調べる", exact: true }).click();
        await page.locator('.public-area[data-public-step="result"]').waitFor({ timeout: 120_000 });
        await page.waitForTimeout(2_000);
        await saveScreenshot(page, `${id}-result-${viewport.name}.png`, {
          kind: "product-baseline",
          product: id,
          requested_url: url,
          viewport,
          access_status: status,
        });
        await page.getByRole("button", { name: "確認場所を見る", exact: true }).click();
        await page.locator('.public-area[data-public-step="target"]').waitFor({ timeout: 120_000 });
        await page.waitForTimeout(1_000);
        await saveScreenshot(page, `${id}-target-${viewport.name}.png`, {
          kind: "product-baseline",
          product: id,
          requested_url: url,
          viewport,
          access_status: status,
        });
      }
    } catch (captureError) {
      status = "ACCESS_UNAVAILABLE";
      error = captureError instanceof Error ? captureError.message : String(captureError);
      records.push({
        kind: "product-baseline",
        product: id,
        requested_url: url,
        viewport,
        access_status: status,
        error,
        captured_at: new Date().toISOString(),
      });
    } finally {
      await context.close();
    }
  }
}

async function captureProductionRoutes(browser) {
  const routes = [
    { id: "production-guided-section", query: "?experience=guided&guide=3" },
    { id: "production-guided-task", query: "?experience=guided&guide=4" },
    {
      id: "production-advanced-section",
      query: "?experience=advanced&city=maizuru&scene=plateau_detail&mesh=533513314&resolution=building_group&lens=urban-xray&mapMode=plateau3d&buildingSource=spatial-pack&section=open&inspector=open",
    },
  ];
  for (const route of routes) {
    const viewport = { width: 1440, height: 900 };
    const context = await browser.newContext({ viewport, locale: "ja-JP" });
    const page = await context.newPage();
    try {
      const requestedUrl = new URL(route.query, productionUrl).toString();
      const response = await page.goto(requestedUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
      await page.waitForTimeout(8_000);
      await saveScreenshot(page, `${route.id}.png`, {
        kind: "product-baseline",
        product: "production",
        requested_url: requestedUrl,
        viewport,
        access_status: response?.ok() ? "OBSERVED" : "PARTIALLY_OBSERVED",
        http_status: response?.status() ?? null,
      });
    } catch (captureError) {
      records.push({
        kind: "product-baseline",
        product: "production",
        requested_url: new URL(route.query, productionUrl).toString(),
        viewport,
        access_status: "ACCESS_UNAVAILABLE",
        error: captureError instanceof Error ? captureError.message : String(captureError),
        captured_at: new Date().toISOString(),
      });
    } finally {
      await context.close();
    }
  }
}

async function captureBenchmarks(browser) {
  for (const benchmark of benchmarks) {
    const viewport = { width: 1440, height: 900 };
    const context = await browser.newContext({ viewport, locale: "ja-JP" });
    const page = await context.newPage();
    let status = "OBSERVED";
    let error = null;
    try {
      const response = await page.goto(benchmark.url, { waitUntil: "domcontentloaded", timeout: 90_000 });
      await page.waitForTimeout(5_000);
      const bodyText = await page.locator("body").innerText({ timeout: 10_000 }).catch(() => "");
      status = benchmark.evidenceStatus;
      if (!response?.ok() || bodyText.trim().length < 120) status = "PARTIALLY_OBSERVED";
      await saveScreenshot(page, `benchmark-${benchmark.id}.png`, {
        kind: "benchmark",
        product: benchmark.product,
        requested_url: benchmark.url,
        viewport,
        access_status: status,
        http_status: response?.status() ?? null,
        first_heading: await page.locator("h1").first().innerText().catch(() => null),
        visible_text_sample: bodyText.replace(/\s+/g, " ").trim().slice(0, 600),
      });
    } catch (captureError) {
      status = "ACCESS_UNAVAILABLE";
      error = captureError instanceof Error ? captureError.message : String(captureError);
      records.push({
        kind: "benchmark",
        product: benchmark.product,
        requested_url: benchmark.url,
        viewport,
        access_status: status,
        error,
        captured_at: new Date().toISOString(),
      });
    } finally {
      await context.close();
    }
  }
}

await mkdir(outputDirectory, { recursive: true });
const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--ignore-gpu-blocklist", "--use-gl=swiftshader"],
});
try {
  await captureProductBaseline(browser, "production", productionUrl);
  await captureProductionRoutes(browser);
  await captureProductBaseline(browser, "feature", featureUrl);
  await captureBenchmarks(browser);
} finally {
  await browser.close();
}

await writeFile(path.join(outputDirectory, "manifest.json"), `${JSON.stringify({
  schema_version: "citygap.public-product-audit@1",
  repository_head: repositoryHead,
  production_url: productionUrl,
  feature_url: featureUrl,
  records,
}, null, 2)}\n`);

console.log(JSON.stringify({ outputDirectory, records: records.length }, null, 2));
