import { chromium } from "playwright-core";

const parameters = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const argument = process.argv[index];
  if (!argument.startsWith("--")) continue;
  const value = process.argv[index + 1];
  parameters.set(argument, value && !value.startsWith("--") ? value : "true");
  if (value && !value.startsWith("--")) index += 1;
}

const baseUrl = parameters.get("--url") ?? "http://127.0.0.1:4173/plateau-city-gap/";
const executablePath =
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
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

async function waitForStep(page, step) {
  await page.locator(`.verification-journey[data-investigation-step="${step}"]`).waitFor({
    state: "visible",
    timeout: 120_000,
  });
}

async function touchClick(page, label, expectedStep) {
  const button = page.getByRole("button", { name: label, exact: true });
  const box = await button.boundingBox();
  if (!box || box.height < 44 || box.width < 44) {
    throw new Error(`primary action is not touch sized: ${label}`);
  }
  await button.click();
  await waitForStep(page, expectedStep);
}

async function start(page) {
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await page.getByRole("heading", { name: /地図だけでは分からないことを/ }).waitFor();
  if (await page.locator(".value-actions .investigation-primary").count() !== 1) {
    throw new Error("landing must keep exactly one primary action");
  }
  await touchClick(page, "地図から確認候補を選ぶ", 1);
}

try {
  const desktop = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  const page = await desktop.newPage();
  page.setDefaultTimeout(120_000);
  const desktopErrors = [];
  page.on("pageerror", (error) => desktopErrors.push(error.message));

  await start(page);
  const candidates = page.locator('.candidate-list [role="radio"]');
  if (await candidates.count() !== 3) throw new Error("candidate shortlist must contain three items");

  await page.getByRole("radio", { name: /二尾/ }).click();
  await touchClick(page, "まだ分からないことを見る", 2);
  await touchClick(page, "確かめる場所を見る", 3);
  if (
    await page.locator('.plateau-3d-shell[data-ui-mode="guided"]').count() !== 0
    || await page.getByText("PLATEAU詳細がないため、別地域objectで補わない").count() === 0
  ) {
    throw new Error("candidate without PLATEAU coverage must use an honest fallback");
  }

  await start(page);
  await page.getByRole("radio", { name: /常団地前周辺/ }).click();
  await touchClick(page, "まだ分からないことを見る", 2);
  if (
    await page.locator(".verification-known-facts > div").count() !== 3
    || await page.locator(".uncertainty-cards > article").count() !== 4
  ) {
    throw new Error("M3 must show three known facts and four bounded uncertainties");
  }

  await touchClick(page, "確かめる場所を見る", 3);
  await page.locator('.plateau-3d-shell[data-ui-mode="guided"]').waitFor({ state: "visible" });
  await page.locator(".plateau-3d-shell .map-engine-loading").last().waitFor({
    state: "hidden",
    timeout: 180_000,
  });
  const targetIds = await page.locator("[data-target-object-id]").evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("data-target-object-id")),
  );
  if (!targetIds.some((value) => value?.startsWith("bldg_"))
      || !targetIds.some((value) => value?.startsWith("tran_"))) {
    throw new Error("M3 must retain real PLATEAU building and road targets");
  }

  await touchClick(page, "現地確認タスクを見る", 4);
  const taskCards = page.locator(".verification-tasks > article");
  const taskCount = await taskCards.count();
  const requirementCounts = [];
  for (let index = 0; index < taskCount; index += 1) {
    const card = taskCards.nth(index);
    requirementCounts.push(await card.locator("ol > li").count());
    if ((await card.locator("header b").textContent())?.trim() !== "未確認") {
      throw new Error("a public M3 task is not unverified");
    }
  }
  if (
    taskCount !== 4
    || requirementCounts.some((count) => count < 3 || count > 5)
    || await page.locator(".verification-panel input, .verification-panel textarea, .verification-panel select").count()
  ) {
    throw new Error("M3 tasks must remain bounded and evidence-free");
  }
  await page.getByText("AWAITING_HUMAN_TEST", { exact: true }).waitFor();
  await page.getByText("AWAITING_MUNICIPAL_REVIEW", { exact: true }).waitFor();
  await page.getByRole("button", { name: "高度分析を開く", exact: true }).click();
  await page.locator('.product-app[data-experience="advanced"]').waitFor({ state: "visible" });
  if (desktopErrors.length) throw new Error(`desktop page errors: ${JSON.stringify(desktopErrors)}`);
  await desktop.close();

  const mobile = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  const mobilePage = await mobile.newPage();
  mobilePage.setDefaultTimeout(120_000);
  await start(mobilePage);
  await mobilePage.getByRole("radio", { name: /常団地前周辺/ }).click();
  await touchClick(mobilePage, "まだ分からないことを見る", 2);
  await touchClick(mobilePage, "確かめる場所を見る", 3);
  await touchClick(mobilePage, "現地確認タスクを見る", 4);
  const mobileLayout = await mobilePage.evaluate(() => ({
    viewport: innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    taskCount: document.querySelectorAll(".verification-tasks > article").length,
    touchTargets: [...document.querySelectorAll("button")]
      .filter((element) => element.getClientRects().length > 0)
      .every((element) => {
        const rect = element.getBoundingClientRect();
        return rect.height >= 44 && rect.width >= 44;
      }),
  }));
  if (
    mobileLayout.scrollWidth > mobileLayout.viewport
    || mobileLayout.taskCount !== 4
    || !mobileLayout.touchTargets
  ) {
    throw new Error(`mobile verification contract failed: ${JSON.stringify(mobileLayout)}`);
  }
  await mobile.close();

  process.stdout.write(`${JSON.stringify({
    passed: true,
    desktop: {
      candidateCount: 3,
      knownFactCount: 3,
      uncertaintyCount: 4,
      targetCount: targetIds.length,
      taskCount,
      requirementCounts,
      fieldEvidenceInputs: 0,
    },
    mobile: mobileLayout,
  }, null, 2)}\n`);
} finally {
  await browser.close();
}
