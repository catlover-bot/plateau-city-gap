import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const frontendRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const repositoryRoot = dirname(frontendRoot);
const finalDirectory = join(repositoryRoot, "docs", "assets", "final-v2");
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
  ?? "/home/catlover/.cache/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-linux64/chrome-headless-shell";
const baseUrl = process.env.CITY_GAP_PREVIEW_URL
  ?? "http://127.0.0.1:4173/plateau-city-gap/";

mkdirSync(finalDirectory, { recursive: true });

const launchArgs = [
  "--no-sandbox",
  "--disable-dev-shm-usage",
  "--enable-webgl",
  "--ignore-gpu-blocklist",
  "--use-gl=swiftshader"
];
const browser = await chromium.launch({ executablePath, headless: true, args: launchArgs });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
page.setDefaultTimeout(20_000);
const consoleErrors = [];
const localFailures = [];
const plateauResponses = [];

page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text());
});
page.on("pageerror", (error) => consoleErrors.push(error.stack ?? error.message));
page.on("requestfailed", (request) => {
  if (request.url().startsWith(baseUrl)) localFailures.push(`${request.url()}: ${request.failure()?.errorText ?? "failed"}`);
});
page.on("response", (response) => {
  if (response.url().includes("/data/plateau/")) plateauResponses.push({ url: response.url(), status: response.status() });
  if (response.url().startsWith(baseUrl) && response.status() >= 400) localFailures.push(`${response.url()}: HTTP ${response.status()}`);
});

async function nextStep(expected) {
  await page.locator(".story-card .primary-button").dispatchEvent("click");
  await page.getByText(`STEP ${expected} / 8`, { exact: false }).waitFor();
  await page.waitForTimeout(expected >= 4 && expected <= 7 ? 2_400 : 900);
}

async function shot(name) {
  await page.screenshot({ path: join(finalDirectory, name), timeout: 60_000 });
}

try {
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await page.getByRole("heading", { name: "CITY GAP", exact: true }).waitFor({ timeout: 60_000 });
  await page.locator(".map-loading").waitFor({ state: "hidden", timeout: 60_000 });
  await page.waitForTimeout(2_000);
  if (plateauResponses.length !== 0) localFailures.push("PLATEAU assets loaded before the 3D step");

  const methodologyButton = page.locator(".methodology-button");
  await methodologyButton.focus();
  await methodologyButton.dispatchEvent("click");
  await page.locator(".methodology-modal").waitFor();
  const closeFocused = await page.evaluate(() => document.activeElement?.getAttribute("aria-label") === "閉じる");
  await page.keyboard.press("Escape");
  await page.locator(".methodology-modal").waitFor({ state: "hidden" });
  const focusRestored = await methodologyButton.evaluate((button) => document.activeElement === button);
  if (!closeFocused || !focusRestored) localFailures.push("Methodology modal focus/restore failed");

  await page.locator(".product-intro .primary-button").dispatchEvent("click");
  await page.getByText("STEP 1 / 8", { exact: false }).waitFor();
  await page.waitForTimeout(4_200);
  await shot("01-discovery.png");

  await nextStep(2);
  await nextStep(3);
  const robustText = await page.locator(".robustness-section").innerText();
  if (!robustText.includes("9条件") || !robustText.includes("確率や信頼度ではありません")) {
    localFailures.push("Robustness UI did not expose 9 conditions and non-probability wording");
  }
  await page.locator(".robustness-section").scrollIntoViewIfNeeded();
  await shot("02-robustness.png");

  await nextStep(4);
  await shot("03-3d-context.png");
  const loadedB3dm = plateauResponses.filter((response) => response.url.endsWith(".b3dm") && response.status === 200);
  if (loadedB3dm.length === 0) localFailures.push("No PLATEAU b3dm loaded with HTTP 200");

  await nextStep(5);
  const oneText = await page.locator(".scenario-panel").innerText();
  if (!oneText.includes("5") || !oneText.includes("241")) localFailures.push("1-site verified result is missing");
  await shot("04-one-site.png");

  await nextStep(6);
  const twoText = await page.locator(".scenario-panel").innerText();
  if (!twoText.includes("2地点") || !twoText.includes("377")) localFailures.push("2-site verified result is missing");
  await shot("05-two-site.png");

  await nextStep(7);
  const fairnessText = await page.locator(".scenario-panel").innerText();
  if (!fairnessText.includes("取り残し重視") || !fairnessText.includes("trade-off")) localFailures.push("Fairness trade-off is missing");
  await shot("06-fairness.png");

  await page.getByRole("button", { name: "施策前", exact: true }).dispatchEvent("click");
  await page.waitForTimeout(400);
  await page.getByRole("button", { name: "施策後", exact: true }).dispatchEvent("click");
  await page.waitForTimeout(500);
  await shot("07-before-after.png");

  const evidenceButton = page.locator(".scenario-heading .evidence-link");
  await evidenceButton.dispatchEvent("click");
  await page.getByRole("heading", { name: "この数字を根拠まで辿る" }).waitFor();
  const evidenceText = await page.locator(".evidence-modal").innerText();
  if (!evidenceText.includes("2321.655608906") || !evidenceText.includes("国土数値情報 P11 2022")) {
    localFailures.push("Evidence Chain raw value/source is missing");
  }
  await shot("08-evidence.png");
  await page.keyboard.press("Escape");

  await nextStep(8);
  await shot("10-presentation-mode.png");
  await page.locator(".story-card .primary-button").dispatchEvent("click");
  await page.locator(".map-loading").waitFor({ state: "hidden", timeout: 60_000 });
  await page.getByText("同じCITY GAP Engineを実データへ適用", { exact: true }).waitFor();
  if (await page.getByRole("tab", { name: /施策配置/ }).count() !== 0) localFailures.push("Fujisawa exposed Maizuru Decision tab");
  await shot("09-cross-city.png");

  await page.getByRole("button", { name: /舞鶴市/ }).dispatchEvent("click");
  await page.locator(".map-loading").waitFor({ state: "hidden", timeout: 60_000 });
  await page.setViewportSize({ width: 390, height: 844 });
  const mobileLayout = await page.evaluate(() => ({
    innerWidth: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    mapWidth: document.querySelector(".map-stage")?.getBoundingClientRect().width ?? 0,
    panelWidth: document.querySelector(".side-panel")?.getBoundingClientRect().width ?? 0
  }));
  if (mobileLayout.scrollWidth > mobileLayout.innerWidth
    || mobileLayout.mapWidth > mobileLayout.innerWidth + 1
    || mobileLayout.panelWidth > mobileLayout.innerWidth + 1) {
    localFailures.push(`Mobile layout overflowed: ${JSON.stringify(mobileLayout)}`);
  }

  const degradedPage = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const degradedErrors = [];
  degradedPage.on("pageerror", (error) => degradedErrors.push(error.message));
  await degradedPage.route("**/data/plateau/tileset.json", (route) => route.abort("failed"));
  await degradedPage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await degradedPage.locator(".map-loading").waitFor({ state: "hidden", timeout: 60_000 });
  await degradedPage.locator(".product-intro .primary-button").dispatchEvent("click");
  await degradedPage.getByText("STEP 1 / 8", { exact: false }).waitFor();
  for (const expected of [2, 3, 4]) {
    await degradedPage.waitForTimeout(650);
    await degradedPage.getByRole("button", { name: "次へ", exact: true }).click();
    await degradedPage.getByText(`STEP ${expected} / 8`, { exact: false }).waitFor();
  }
  await degradedPage.locator(".map-warning").waitFor({ timeout: 60_000 });
  if (!await degradedPage.locator(".side-panel").isVisible()
    || await degradedPage.locator(".map-error-fallback").isVisible()
    || degradedErrors.length > 0) localFailures.push(`Optional PLATEAU fallback failed: ${degradedErrors.join("; ")}`);
  await degradedPage.close();

  process.stdout.write(`${JSON.stringify({
    baseUrl,
    screenshots: [
      "01-discovery.png", "02-robustness.png", "03-3d-context.png", "04-one-site.png",
      "05-two-site.png", "06-fairness.png", "07-before-after.png", "08-evidence.png",
      "09-cross-city.png", "10-presentation-mode.png"
    ],
    loadedB3dm: loadedB3dm.length,
    mobileLayout,
    consoleErrors,
    localFailures
  }, null, 2)}\n`);
  if (consoleErrors.length > 0 || localFailures.length > 0) process.exitCode = 1;
} finally {
  await browser.close();
}
