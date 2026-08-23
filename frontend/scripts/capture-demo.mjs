import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const frontendRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const repositoryRoot = dirname(frontendRoot);
const outputDirectory = join(repositoryRoot, "docs", "assets");
const fallbackDirectory = join(outputDirectory, "demo-fallback");
const finalDirectory = join(outputDirectory, "final");
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
  ?? "/home/catlover/.cache/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-linux64/chrome-headless-shell";
const baseUrl = process.env.CITY_GAP_PREVIEW_URL
  ?? "http://127.0.0.1:4173/plateau-city-gap/";
const captureAll = process.env.CITY_GAP_CAPTURE_ALL === "1";

mkdirSync(outputDirectory, { recursive: true });
mkdirSync(fallbackDirectory, { recursive: true });
mkdirSync(finalDirectory, { recursive: true });

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
let initialPlateauAssetResponses = 0;

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
  await page.screenshot({ path: join(finalDirectory, "city-gap-overview.png"), timeout: 60_000 });
  initialPlateauAssetResponses = plateauResponses.length;
  if (initialPlateauAssetResponses !== 0) {
    localFailures.push(`PLATEAU Deep Dive assets loaded before they were requested: ${initialPlateauAssetResponses}`);
  }
  process.stdout.write("Initial map and screenshot verified.\n");

  const methodologyButton = page.locator(".methodology-button");
  await methodologyButton.focus();
  await methodologyButton.dispatchEvent("click");
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

  await page.locator(".product-intro .primary-button").dispatchEvent("click");
  await page.getByText("STEP 1 / 5", { exact: false }).waitFor();
  await page.waitForTimeout(4_200);
  await page.screenshot({ path: join(fallbackDirectory, "Step1.png"), timeout: 60_000 });
  await page.locator(".story-card .primary-button").dispatchEvent("click");
  await page.getByText("STEP 2 / 5", { exact: false }).waitFor();
  await page.waitForTimeout(1_300);
  await page.screenshot({ path: join(finalDirectory, "city-gap-discovery.png"), timeout: 60_000 });
  await page.locator(".story-card .primary-button").dispatchEvent("click");
  await page.getByText("STEP 3 / 5", { exact: false }).waitFor();
  await page.waitForTimeout(2_000);
  if (await page.locator(".building-card").isVisible()) {
    const buildingText = await page.locator(".building-card").innerText();
    buildingSelectionVerified = buildingText.includes("住宅")
      && buildingText.includes("9 m")
      && buildingText.includes("2階")
      && buildingText.includes("61.7 m²")
      && !buildingText.includes("9,999")
      && !buildingText.includes("-9,999");
  }
  const mapBox = await page.locator(".cesium-map canvas").boundingBox();
  if (mapBox && !buildingSelectionVerified) {
    const candidates = [
      [0.78, 0.28], [0.72, 0.34], [0.65, 0.31], [0.58, 0.35],
      [0.48, 0.31], [0.82, 0.42], [0.7, 0.46], [0.58, 0.45],
      [0.46, 0.43], [0.4, 0.38], [0.5, 0.5], [0.62, 0.52],
      [0.42, 0.5], [0.76, 0.52], [0.86, 0.33], [0.9, 0.45]
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
  await page.screenshot({ path: join(finalDirectory, "city-gap-deep-dive.png"), timeout: 60_000 });
  if (captureAll) {
    await page.screenshot({ path: join(outputDirectory, "city-gap-plateau.png"), timeout: 60_000 });
  }
  process.stdout.write("Story steps 1–3 and PLATEAU Deep Dive verified.\n");

  await page.locator(".story-card .primary-button").dispatchEvent("click");
  await page.getByText("STEP 4 / 5", { exact: false }).waitFor();
  await page.locator(".scenario-summary-grid").waitFor();
  await page.waitForTimeout(1_300);
  await page.screenshot({ path: join(fallbackDirectory, "Step4.png"), timeout: 60_000 });
  await page.screenshot({ path: join(finalDirectory, "city-gap-what-if.png"), timeout: 60_000 });
  if (captureAll) {
    await page.screenshot({ path: join(outputDirectory, "city-gap-what-if.png"), timeout: 60_000 });
  }
  process.stdout.write("Story step 4 and road-anchored deterministic scenario verified.\n");

  const scenarioText = await page.locator(".scenario-panel").innerText();
  const loadedB3dm = plateauResponses.filter((response) => response.url.endsWith(".b3dm") && response.status === 200);
  if (loadedB3dm.length === 0) localFailures.push("No official PLATEAU b3dm response completed with HTTP 200");
  if (!buildingSelectionVerified) localFailures.push("No official PLATEAU building could be selected on the reference view");
  if (!scenarioText.includes("5") || !scenarioText.includes("241人")) {
    localFailures.push("Primary candidate did not render the verified 5 mesh / 241 elderly-person result");
  }

  await page.locator(".story-card .primary-button").dispatchEvent("click");
  await page.getByText("STEP 5 / 5", { exact: false }).waitFor();
  await page.locator(".story-card .text-button").dispatchEvent("click");
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.getByRole("button", { name: /藤沢市/ }).dispatchEvent("click");
  await page.locator(".map-loading").waitFor({ state: "hidden", timeout: 60_000 });
  await page.getByText("同じCITY GAP Engineを実データへ適用", { exact: true }).waitFor();
  if (await page.getByRole("tab", { name: /施策を試す/ }).count() !== 0) {
    localFailures.push("Fujisawa validation mode exposed the Maizuru What-if tab");
  }
  await page.screenshot({ path: join(finalDirectory, "city-gap-cross-city.png"), timeout: 60_000 });

  await page.getByRole("button", { name: /舞鶴市/ }).dispatchEvent("click");
  await page.locator(".map-loading").waitFor({ state: "hidden", timeout: 60_000 });
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
  await page.screenshot({ path: join(finalDirectory, "city-gap-mobile.png"), timeout: 60_000 });

  const degradedPage = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const degradedPageErrors = [];
  degradedPage.on("pageerror", (error) => degradedPageErrors.push(error.message));
  await degradedPage.route("**/data/plateau/tileset.json", (route) => route.abort("failed"));
  await degradedPage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await degradedPage.locator(".map-loading").waitFor({ state: "hidden", timeout: 60_000 });
  await degradedPage.locator(".product-intro .primary-button").dispatchEvent("click");
  await degradedPage.getByText("STEP 1 / 5", { exact: false }).waitFor();
  await degradedPage.getByRole("button", { name: "次へ", exact: true }).click();
  await degradedPage.getByText("STEP 2 / 5", { exact: false }).waitFor();
  await degradedPage.getByRole("button", { name: "次へ", exact: true }).click();
  await degradedPage.getByText("STEP 3 / 5", { exact: false }).waitFor();
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
    await fallbackPage.locator(".detail-panel").waitFor({ timeout: 60_000 });
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
    screenshots: [
      "final/city-gap-overview.png",
      "final/city-gap-discovery.png",
      "final/city-gap-deep-dive.png",
      "final/city-gap-what-if.png",
      "final/city-gap-cross-city.png",
      "final/city-gap-mobile.png"
    ],
    plateauResponses: plateauResponses.length,
    initialPlateauAssetResponses,
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
