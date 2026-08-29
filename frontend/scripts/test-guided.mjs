import { chromium } from "playwright-core";
import {
  advanceGuided,
  COPY,
  assertLanding,
  assertMobileGuidedLayout,
  assertNoCriticalBrowserErrors,
  attachBrowserDiagnostics,
  startGuided,
  reviewEvidenceAndOpenAdvanced,
} from "./guided-browser.mjs";

const parameters = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const argument = process.argv[index];
  if (!argument.startsWith("--")) continue;
  const value = process.argv[index + 1];
  parameters.set(argument, value && !value.startsWith("--") ? value : "true");
  if (value && !value.startsWith("--")) index += 1;
}

const baseUrl = parameters.get("--url") ?? "http://127.0.0.1:4173/plateau-city-gap/";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist", "--use-gl=swiftshader"],
});
const suiteStartedAt = Date.now();

try {
  const desktop = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  const page = await desktop.newPage();
  const diagnostics = attachBrowserDiagnostics(page);
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await assertLanding(page);
  await startGuided(page);
  for (let step = 1; step <= 4; step += 1) await advanceGuided(page, step);
  await reviewEvidenceAndOpenAdvanced(page);
  assertNoCriticalBrowserErrors(diagnostics);
  await desktop.close();

  const mobile = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  const mobilePage = await mobile.newPage();
  const mobileDiagnostics = attachBrowserDiagnostics(mobilePage);
  await mobilePage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await assertLanding(mobilePage);
  const landingAction = await mobilePage.getByRole("button", { name: "\u821e\u9db4\u306e\u4f8b\u30921\u5206\u3067\u898b\u308b", exact: true }).boundingBox();
  if (!landingAction || landingAction.height < 44 || landingAction.y + landingAction.height > 844) {
    throw new Error("mobile landing CTA is not visible and touch sized: " + JSON.stringify(landingAction));
  }
  await startGuided(mobilePage);
  await advanceGuided(mobilePage, 1);
  await advanceGuided(mobilePage, 2);
  await assertMobileGuidedLayout(mobilePage);
  assertNoCriticalBrowserErrors(mobileDiagnostics);
  await mobile.close();

  const normalMotionStartedAt = Date.now();
  const normalMotion = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    reducedMotion: "no-preference",
  });
  const normalPage = await normalMotion.newPage();
  normalPage.setDefaultTimeout(120_000);
  const normalDiagnostics = attachBrowserDiagnostics(normalPage);
  await normalPage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await assertLanding(normalPage);
  await startGuided(normalPage);
  await advanceGuided(normalPage, 1);
  await advanceGuided(normalPage, 2);
  const threeDRenderer = normalPage.locator('.plateau-3d-shell[data-ui-mode="guided"][data-map-engine="cesium"]');
  await threeDRenderer.waitFor({ state: "visible", timeout: 120_000 });
  if (await threeDRenderer.count() !== 1) throw new Error("normal-motion Guided step 3 must mount exactly one shared Plateau3D renderer");
  if (await normalPage.locator('.guided-static-map[data-render-source="verified-section"]').count() !== 0) {
    throw new Error("normal-motion Guided step 3 unexpectedly used the reduced-motion static fallback");
  }
  const section = normalPage.locator('.urban-section[data-ui-mode="guided"][data-transect-ready="true"]');
  await section.waitFor({ state: "attached", timeout: 120_000 });
  const sectionState = await section.evaluate((element) => ({
    buildings: Number(element.getAttribute("data-building-count") ?? 0),
    roads: Number(element.getAttribute("data-road-count") ?? 0),
    terrain_covered: Number(element.getAttribute("data-terrain-covered") ?? 0),
  }));
  if (sectionState.buildings <= 0 || sectionState.roads <= 0 || sectionState.terrain_covered <= 0) {
    throw new Error("normal-motion Guided UrbanSection is empty: " + JSON.stringify(sectionState));
  }
  const next = normalPage.getByRole("button", { name: COPY.next[2], exact: true });
  const nextBox = await next.boundingBox();
  const nextUsable = await next.evaluate((element) => {
    const box = element.getBoundingClientRect();
    const hit = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
    return !element.disabled && (hit === element || element.contains(hit));
  });
  if (!nextBox || nextBox.height < 44 || !nextUsable) throw new Error("normal-motion Guided step 3 Next CTA is not usable");
  assertNoCriticalBrowserErrors(normalDiagnostics);
  await normalMotion.close();
  const normalMotionRuntimeMs = Date.now() - normalMotionStartedAt;

  process.stdout.write(JSON.stringify({
    result: "passed",
    desktop: "landing -> guided 1..5 -> evidence -> advanced",
    mobile: "390x844 landing -> guided step 3",
    normal_motion: "1440x900 landing -> shared Plateau3D guided step 3",
    normal_motion_runtime_ms: normalMotionRuntimeMs,
    runtime_ms: Date.now() - suiteStartedAt,
  }) + "\n");
} finally {
  await browser.close();
}
