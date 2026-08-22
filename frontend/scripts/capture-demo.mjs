import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const frontendRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const repositoryRoot = dirname(frontendRoot);
const outputDirectory = join(repositoryRoot, "docs", "assets");
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
  ?? "/home/catlover/.cache/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-linux64/chrome-headless-shell";
const baseUrl = process.env.CITY_GAP_PREVIEW_URL
  ?? "http://127.0.0.1:4173/plateau-city-gap/";
const captureAll = process.env.CITY_GAP_CAPTURE_ALL === "1";

mkdirSync(outputDirectory, { recursive: true });

const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--enable-webgl",
    "--ignore-gpu-blocklist",
    "--use-gl=swiftshader"
  ]
});

const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
page.setDefaultTimeout(15_000);
const consoleErrors = [];
const localFailures = [];
const plateauResponses = [];
let buildingSelectionVerified = false;
let modalFocusVerified = false;
let optionalPlateauFallbackVerified = false;
let webglFallbackVerified = false;

page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text());
});
page.on("pageerror", (error) => consoleErrors.push(error.message));
page.on("requestfailed", (request) => {
  if (request.url().startsWith(baseUrl)) {
    localFailures.push(`${request.url()}: ${request.failure()?.errorText ?? "request failed"}`);
  }
});
page.on("response", (response) => {
  if (response.url().includes("/data/plateau/")) {
    plateauResponses.push({ url: response.url(), status: response.status() });
  }
  if (response.url().startsWith(baseUrl) && response.status() >= 400) {
    localFailures.push(`${response.url()}: HTTP ${response.status()}`);
  }
});

try {
  process.stdout.write("Opening production preview…\n");
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await page.getByRole("heading", { name: "CITY GAP", exact: true }).waitFor({ timeout: 60_000 });
  await page.locator(".map-loading").waitFor({ state: "hidden", timeout: 60_000 });
  await page.waitForTimeout(4_000);
  await page.screenshot({ path: join(outputDirectory, "city-gap-demo.png"), timeout: 60_000 });
  process.stdout.write("Initial map and screenshot verified.\n");

  const methodologyButton = page.locator(".methodology-button");
  await methodologyButton.click();
  await page.locator(".methodology-modal").waitFor();
  const closeInitiallyFocused = await page.evaluate(
    () => document.activeElement?.getAttribute("aria-label") === "閉じる"
  );
  await page.keyboard.press("Shift+Tab");
  const focusStayedInModal = await page.evaluate(
    () => document.activeElement?.closest(".methodology-modal") !== null
  );
  await page.keyboard.press("Escape");
  await page.locator(".methodology-modal").waitFor({ state: "hidden" });
  const focusRestored = await methodologyButton.evaluate(
    (button) => document.activeElement === button
  );
  modalFocusVerified = closeInitiallyFocused && focusStayedInModal && focusRestored;
  if (!modalFocusVerified) localFailures.push("Methodology dialog focus trap/restore failed");

  await page.locator(".story-start-button").dispatchEvent("click");
  await page.getByText("STEP 1 / 4", { exact: false }).waitFor();
  await page.locator(".story-card .primary-button").dispatchEvent("click");
  await page.getByText("STEP 2 / 4", { exact: false }).waitFor();
  await page.locator(".story-card .primary-button").dispatchEvent("click");
  await page.getByText("STEP 3 / 4", { exact: false }).waitFor();
  await page.waitForTimeout(2_000);
  const mapBox = await page.locator(".cesium-map canvas").boundingBox();
  if (mapBox) {
    const candidates = [
      [0.5, 0.5], [0.45, 0.52], [0.55, 0.52], [0.5, 0.58],
      [0.4, 0.48], [0.6, 0.48], [0.45, 0.62], [0.55, 0.62]
    ];
    for (const [x, y] of candidates) {
      await page.mouse.click(mapBox.x + mapBox.width * x, mapBox.y + mapBox.height * y);
      await page.waitForTimeout(250);
      if (await page.locator(".building-card").isVisible()) {
        buildingSelectionVerified = true;
        break;
      }
    }
  }
  if (captureAll) {
    await page.screenshot({ path: join(outputDirectory, "city-gap-plateau.png"), timeout: 60_000 });
  }
  process.stdout.write("Story steps 1–3 and PLATEAU view verified.\n");

  await page.locator(".story-card .primary-button").dispatchEvent("click");
  await page.getByText("STEP 4 / 4", { exact: false }).waitFor();
  await page.locator(".scenario-summary-grid").waitFor();
  if (captureAll) {
    await page.screenshot({ path: join(outputDirectory, "city-gap-what-if.png"), timeout: 60_000 });
  }
  process.stdout.write("Story step 4 and deterministic scenario verified.\n");

  const scenarioText = await page.locator(".scenario-panel").innerText();
  const loadedB3dm = plateauResponses.filter((response) => response.url.endsWith(".b3dm") && response.status === 200);
  if (loadedB3dm.length === 0) localFailures.push("No official PLATEAU b3dm response completed with HTTP 200");
  if (!buildingSelectionVerified) localFailures.push("No official PLATEAU building could be selected on the reference view");
  if (!scenarioText.includes("2") || !scenarioText.includes("64人")) {
    localFailures.push("Rank 1 scenario did not render the verified 2 mesh / 64 elderly-person result");
  }

  await page.locator(".story-card .text-button").dispatchEvent("click");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(500);
  const mobileLayout = await page.evaluate(() => ({
    innerWidth: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    mapWidth: document.querySelector(".map-stage")?.getBoundingClientRect().width ?? 0,
    panelWidth: document.querySelector(".side-panel")?.getBoundingClientRect().width ?? 0
  }));
  if (
    mobileLayout.scrollWidth > mobileLayout.innerWidth
    || mobileLayout.mapWidth > mobileLayout.innerWidth + 1
    || mobileLayout.panelWidth > mobileLayout.innerWidth + 1
  ) {
    localFailures.push(`Mobile layout overflowed: ${JSON.stringify(mobileLayout)}`);
  }
  if (captureAll) {
    await page.screenshot({ path: join(outputDirectory, "city-gap-mobile.png"), timeout: 60_000 });
  }

  const degradedPage = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const degradedPageErrors = [];
  degradedPage.on("pageerror", (error) => degradedPageErrors.push(error.message));
  await degradedPage.route("**/data/plateau/tileset.json", (route) => route.abort("failed"));
  await degradedPage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await degradedPage.locator(".map-loading").waitFor({ state: "hidden", timeout: 60_000 });
  await degradedPage.locator(".map-warning").waitFor({ timeout: 60_000 });
  optionalPlateauFallbackVerified = await degradedPage.locator(".side-panel").isVisible()
    && !await degradedPage.locator(".map-error-fallback").isVisible()
    && degradedPageErrors.length === 0;
  if (!optionalPlateauFallbackVerified) {
    localFailures.push(`Optional PLATEAU failure did not preserve the core map: ${JSON.stringify(degradedPageErrors)}`);
  }
  await degradedPage.close();

  const fallbackBrowser = await chromium.launch({
    executablePath,
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--disable-webgl", "--disable-webgl2"]
  });
  try {
    const fallbackPage = await fallbackBrowser.newPage({ viewport: { width: 1280, height: 800 } });
    const fallbackPageErrors = [];
    fallbackPage.on("pageerror", (error) => fallbackPageErrors.push(error.message));
    await fallbackPage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await fallbackPage.getByRole("heading", { name: "CITY GAP", exact: true }).waitFor({ timeout: 60_000 });
    await fallbackPage.locator(".map-error-fallback").waitFor({ timeout: 60_000 });
    await fallbackPage.locator(".ranking-list").waitFor({ timeout: 60_000 });
    webglFallbackVerified = fallbackPageErrors.length === 0
      && await fallbackPage.locator(".side-panel").isVisible();
    if (!webglFallbackVerified) {
      localFailures.push(`WebGL fallback did not preserve the numeric UI: ${JSON.stringify(fallbackPageErrors)}`);
    }
  } finally {
    await fallbackBrowser.close();
  }

  process.stdout.write(`${JSON.stringify({
    baseUrl,
    screenshots: captureAll
      ? ["city-gap-demo.png", "city-gap-plateau.png", "city-gap-what-if.png", "city-gap-mobile.png"]
      : ["city-gap-demo.png"],
    plateauResponses: plateauResponses.length,
    loadedB3dm: loadedB3dm.length,
    buildingSelectionVerified,
    modalFocusVerified,
    optionalPlateauFallbackVerified,
    webglFallbackVerified,
    mobileLayout,
    consoleErrors,
    localFailures
  }, null, 2)}\n`);

  if (consoleErrors.length > 0 || localFailures.length > 0) process.exitCode = 1;
} finally {
  await browser.close();
}
