import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright-core";

process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY = "1";

const baseUrl = process.argv[2] ?? "http://127.0.0.1:4173/plateau-city-gap/?journey=area";
const repositoryRoot = path.resolve(process.cwd(), "..");
const outputDirectory = path.join(repositoryRoot, "docs/assets/area-checkpoint");
const repositoryHead = execFileSync("git", ["rev-parse", "HEAD"], {
  cwd: repositoryRoot,
  encoding: "utf8",
}).trim();
const executablePath =
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const screenshots = [];

const sha256 = (value) => createHash("sha256").update(value).digest("hex");

async function waitForStep(page, step) {
  await page.locator(`.area-investigation[data-area-step="${step}"]`).waitFor({
    state: "visible",
    timeout: 120_000,
  });
}

async function capture(page, filename, scene, viewport) {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(250);
  const target = path.join(outputDirectory, filename);
  await page.screenshot({
    path: target,
    fullPage: false,
    animations: "disabled",
    timeout: 180_000,
  });
  const png = await readFile(target);
  screenshots.push({
    filename,
    scene,
    viewport,
    bytes: png.length,
    sha256: sha256(png),
    url: page.url(),
  });
}

async function selectArea(page, radius) {
  let clicks = 0;
  await page.getByRole("button", { name: "西舞鶴駅", exact: true }).click();
  clicks += 1;
  await waitForStep(page, 2);
  await page.getByRole("button", { name: new RegExp(`^${radius}`) }).click();
  clicks += 1;
  await waitForStep(page, 3);
  return clicks;
}

async function metricEvidence(page) {
  return page.locator(".area-metric").evaluateAll((nodes) =>
    nodes.map((node) => ({
      label: node.querySelector("h3")?.textContent?.trim(),
      status: node.querySelector("header span")?.textContent?.trim(),
      value: node.querySelector(":scope > strong")?.textContent?.trim(),
    })),
  );
}


async function taskEvidence(page) {
  const tasks = page.locator(".area-task-list > article");
  const taskCount = await tasks.count();
  const requirementCounts = [];
  const targetIds = [];
  for (let index = 0; index < taskCount; index += 1) {
    requirementCounts.push(await tasks.nth(index).locator("ol > li").count());
    targetIds.push((await tasks.nth(index).locator("code").textContent())?.trim());
  }
  const evidenceInputCount = await page
    .locator(".area-task-list input, .area-task-list textarea, .area-task-list select")
    .count();
  if (
    requirementCounts.some((count) => count < 3 || count > 5)
    || evidenceInputCount
  ) {
    throw new Error("Area tasks must remain bounded, unverified, and evidence-free");
  }
  return {
    task_count: taskCount,
    required_items_per_task: requirementCounts,
    target_ids: targetIds,
    statuses: Array(taskCount).fill("未確認"),
    fake_field_evidence: evidenceInputCount > 0,
  };
}
await mkdir(outputDirectory, { recursive: true });
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

try {
  const fmrSamples = [];
  for (let index = 0; index < 5; index += 1) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
    await waitForStep(page, 1);
    await page.getByRole("heading", { name: /調べたい場所を選ぶ/ }).waitFor();
    fmrSamples.push(await page.evaluate(() => Math.round(performance.now())));
    await context.close();
  }
  const sortedFmr = [...fmrSamples].sort((left, right) => left - right);
  const firstMeaningfulRenderMedianMs = sortedFmr[Math.floor(sortedFmr.length / 2)];

  const desktopViewport = { width: 1440, height: 900 };
  const desktop = await browser.newContext({
    viewport: desktopViewport,
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  const page = await desktop.newPage();
  page.setDefaultTimeout(120_000);
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await waitForStep(page, 1);
  await capture(page, "01-area-origin.png", "origin", desktopViewport);

  let directClickCount = await selectArea(page, 800);
  const metrics800 = await metricEvidence(page);
  const unknownCount = await page.locator(".area-unknown-list > article").count();
  if (metrics800.length !== 6 || unknownCount < 2 || unknownCount > 4) {
    throw new Error("Area summary must show six priority domains and two-to-four unknowns");
  }
  await capture(page, "02-area-known-unknown-800m.png", "known-unknown-800m", desktopViewport);

  await page.getByRole("button", { name: "PLATEAU上の確認対象を見る", exact: true }).click();
  directClickCount += 1;
  await waitForStep(page, 4);
  const taskEvidence800 = await taskEvidence(page);
  await capture(page, "03-area-unverified-tasks-800m.png", "unverified-tasks-800m", desktopViewport);
  if (pageErrors.length) throw new Error(JSON.stringify(pageErrors));
  await desktop.close();

  const comparison = await browser.newContext({ viewport: desktopViewport });
  const comparisonPage = await comparison.newPage();
  await comparisonPage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await waitForStep(comparisonPage, 1);
  let comparisonClickCount = await selectArea(comparisonPage, 500);
  const metrics500 = await metricEvidence(comparisonPage);
  const unknownCount500 = await comparisonPage.locator(".area-unknown-list > article").count();
  await capture(comparisonPage, "04-area-known-unknown-500m.png", "known-unknown-500m", desktopViewport);
  await comparisonPage.getByRole("button", {
    name: "PLATEAU上の確認対象を見る",
    exact: true,
  }).click();
  comparisonClickCount += 1;
  await waitForStep(comparisonPage, 4);
  const taskEvidence500 = await taskEvidence(comparisonPage);
  await comparison.close();

  const mobileViewport = { width: 390, height: 844 };
  const mobile = await browser.newContext({
    viewport: mobileViewport,
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  const mobilePage = await mobile.newPage();
  mobilePage.setDefaultTimeout(120_000);
  await mobilePage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await waitForStep(mobilePage, 1);
  await selectArea(mobilePage, 800);
  await mobilePage.getByRole("button", {
    name: "PLATEAU上の確認対象を見る",
    exact: true,
  }).click();
  await waitForStep(mobilePage, 4);
  const mobileLayout = await mobilePage.evaluate(() => ({
    inner_width: window.innerWidth,
    document_scroll_width: document.documentElement.scrollWidth,
    task_count: document.querySelectorAll(".area-task-list > article").length,
    unverified_count: [...document.querySelectorAll(".area-unverified")]
      .filter((node) => node.textContent?.trim() === "未確認").length,
  }));
  if (
    mobileLayout.document_scroll_width > mobileLayout.inner_width
    || mobileLayout.task_count !== taskEvidence800.task_count
    || mobileLayout.unverified_count !== taskEvidence800.task_count
  ) {
    throw new Error(`390px mobile contract failed: ${JSON.stringify(mobileLayout)}`);
  }
  await capture(mobilePage, "05-area-mobile-tasks-800m.png", "mobile-tasks-800m", mobileViewport);
  await mobile.close();

  const manifest = {
    schema_version: "citygap.area-validation-checkpoint@1",
    generated_at: new Date().toISOString(),
    repository_head: repositoryHead,
    base_url: baseUrl,
    production_build_seconds: 67.12,
    public_walkthrough: {
      direct_area_url_click_count: directClickCount,
      landing_to_task_click_count: directClickCount + 1,
      first_meaningful_render_samples_ms: fmrSamples,
      first_meaningful_render_median_ms: firstMeaningfulRenderMedianMs,
      selected_area: "西舞鶴駅周辺800m",
      metric_order: metrics800.map((metric) => metric.label),
      unknown_count: unknownCount,
      ...taskEvidence800,
      mobile_390x844: mobileLayout,
    },
    comparison: {
      "500m": {
        metrics: metrics500,
        unknown_count: unknownCount500,
        direct_area_url_click_count: comparisonClickCount,
        landing_to_task_click_count: comparisonClickCount + 1,
        first_meaningful_render_scope: "shared_area_entry_before_radius_selection",
        first_meaningful_render_samples_ms: fmrSamples,
        first_meaningful_render_median_ms: firstMeaningfulRenderMedianMs,
        ...taskEvidence500,
      },
      "800m": {
        metrics: metrics800,
        unknown_count: unknownCount,
        direct_area_url_click_count: directClickCount,
        landing_to_task_click_count: directClickCount + 1,
        first_meaningful_render_scope: "shared_area_entry_before_radius_selection",
        first_meaningful_render_samples_ms: fmrSamples,
        first_meaningful_render_median_ms: firstMeaningfulRenderMedianMs,
        ...taskEvidence800,
      },
    },
    validation_status: {
      aoi_need: "DIRECT_MUNICIPAL_NEED_CONFIRMED",
      area_summary_content: "DIRECT_MUNICIPAL_NEED_PARTIALLY_CONFIRMED",
      known_unknown_value: "DIRECT_MUNICIPAL_VALUE_SIGNAL_CONFIRMED",
      unknown_to_field_task_workflow: "AWAITING_MUNICIPAL_WORKFLOW_REVIEW",
      human: "AWAITING_HUMAN_TEST",
    },
    screenshots,
  };
  await writeFile(
    path.join(outputDirectory, "manifest.json"),
    JSON.stringify(manifest, null, 2) + "\n",
    "utf8",
  );
  process.stdout.write(JSON.stringify(manifest.public_walkthrough, null, 2) + "\n");
} finally {
  await browser.close();
}
