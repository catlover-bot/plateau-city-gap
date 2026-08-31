import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright-core";

process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY = "1";

const baseUrl = process.argv[2] ?? "http://127.0.0.1:4173/plateau-city-gap/";
const repositoryRoot = path.resolve(process.cwd(), "..");
const outputDirectory = path.join(repositoryRoot, "docs/assets/m3-checkpoint");
const executablePath =
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const repositoryHead = execFileSync("git", ["rev-parse", "HEAD"], {
  cwd: repositoryRoot,
  encoding: "utf8",
}).trim();
const screenshots = [];
let clickCount = 0;

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

async function waitForStep(page, step) {
  await page.locator(
    `.verification-journey[data-investigation-step="${step}"]`,
  ).waitFor({ state: "visible", timeout: 120_000 });
}

async function click(page, locator) {
  await locator.click();
  clickCount += 1;
}

async function next(page, label, step) {
  await click(page, page.getByRole("button", { name: label, exact: true }));
  await waitForStep(page, step);
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
  await page.getByRole("heading", {
    name: /地図だけでは分からないことを/,
  }).waitFor();
  const firstMeaningfulRenderMs = await page.evaluate(() => Math.round(performance.now()));
  await capture(page, "01-landing.png", "landing", desktopViewport);

  await click(
    page,
    page.getByRole("button", { name: "地図から確認候補を選ぶ", exact: true }),
  );
  await waitForStep(page, 1);
  await click(page, page.getByRole("radio", { name: /常団地前周辺/ }));
  await next(page, "まだ分からないことを見る", 2);

  const uncertaintyCount = await page.locator(".uncertainty-cards > article").count();
  if (uncertaintyCount !== 4) {
    throw new Error(`expected four uncertainties, received ${uncertaintyCount}`);
  }
  await capture(page, "02-uncertainties.png", "uncertainties", desktopViewport);

  await next(page, "確かめる場所を見る", 3);
  await page.locator('[data-target-object-id="tran_05dbefba-6a77-40ea-88ac-a568a63a2f05-0"]').waitFor();
  await page.locator('.plateau-3d-shell[data-ui-mode="guided"]').waitFor({
    state: "visible",
  });
  await page.locator(".plateau-3d-shell .map-engine-loading").last().waitFor({
    state: "hidden",
    timeout: 180_000,
  });
  await capture(page, "03-object-targets.png", "object-targets", desktopViewport);
  const objectIds = await page.locator("[data-target-object-id]").evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("data-target-object-id")),
  );

  await next(page, "現地確認タスクを見る", 4);
  const taskCards = page.locator(".verification-tasks > article");
  const taskCount = await taskCards.count();
  const requirementCounts = [];
  const statuses = [];
  for (let index = 0; index < taskCount; index += 1) {
    requirementCounts.push(await taskCards.nth(index).locator("ol > li").count());
    statuses.push((await taskCards.nth(index).locator("header b").textContent())?.trim());
  }
  if (
    taskCount !== 4 ||
    requirementCounts.some((count) => count < 3 || count > 5) ||
    statuses.some((status) => status !== "未確認")
  ) {
    throw new Error("M3 task contract is not bounded and unverified");
  }
  const publicInputs = await page.locator(
    ".verification-panel input, .verification-panel textarea, .verification-panel select",
  ).count();
  if (publicInputs !== 0) throw new Error("M3 public slice must not collect field evidence");
  await capture(page, "04-unverified-tasks.png", "unverified-tasks", desktopViewport);

  if (pageErrors.length) throw new Error(JSON.stringify(pageErrors));
  await desktop.close();

  const mobileViewport = { width: 390, height: 844 };
  const mobile = await browser.newContext({
    viewport: mobileViewport,
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  const mobilePage = await mobile.newPage();
  mobilePage.setDefaultTimeout(120_000);
  await mobilePage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await mobilePage.getByRole("heading", {
    name: /地図だけでは分からないことを/,
  }).waitFor();
  await mobilePage.getByRole("button", {
    name: "地図から確認候補を選ぶ",
    exact: true,
  }).click();
  await waitForStep(mobilePage, 1);
  await mobilePage.getByRole("radio", { name: /常団地前周辺/ }).click();
  await next(mobilePage, "まだ分からないことを見る", 2);
  await next(mobilePage, "確かめる場所を見る", 3);
  await next(mobilePage, "現地確認タスクを見る", 4);
  await capture(mobilePage, "05-mobile-unverified-tasks.png", "mobile-tasks", mobileViewport);
  await mobile.close();

  const evidence = {
    schema_version: "citygap.m3-validation-checkpoint@1",
    generated_at: new Date().toISOString(),
    repository_head: repositoryHead,
    base_url: baseUrl,
    public_walkthrough: {
      desktop_click_count: clickCount - 3,
      first_meaningful_render_ms: firstMeaningfulRenderMs,
      candidate: {
        name: "常団地前周辺",
        mesh_code: "533513314",
      },
      uncertainty_count: uncertaintyCount,
      object_ids: objectIds,
      task_count: taskCount,
      required_items_per_task: requirementCounts,
      statuses,
      evidence_inputs_rendered: publicInputs,
    },
    validation_status: {
      human: "AWAITING_HUMAN_TEST",
      municipal: "AWAITING_MUNICIPAL_REVIEW",
    },
    screenshots,
  };
  await writeFile(
    path.join(outputDirectory, "manifest.json"),
    JSON.stringify(evidence, null, 2) + "\n",
    "utf8",
  );
  process.stdout.write(JSON.stringify(evidence.public_walkthrough, null, 2) + "\n");
} finally {
  await browser.close();
}
