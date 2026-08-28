import { mkdir, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { chromium } from "playwright-core";

const parameters = new Map();
for (let index = 2; index < process.argv.length; index += 2) parameters.set(process.argv[index], process.argv[index + 1]);
const baseUrl = parameters.get("--url") ?? process.env.CITY_GAP_PREVIEW_URL ?? "http://127.0.0.1:4173/plateau-city-gap/";
const output = path.resolve(process.cwd(), parameters.get("--output") ?? "../analysis/outputs/real/plateau-native-browser-audit.json");
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const commit = execFileSync("git", ["rev-parse", "HEAD"], { cwd: path.resolve(process.cwd(), ".."), encoding: "utf8" }).trim();
const browser = await chromium.launch({ executablePath, headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--use-gl=swiftshader"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
const consoleErrors = [];
const criticalRequestFailures = [];
const cesiumRequestsDuringInitial2d = [];
let recordInitialRequests = true;

page.on("pageerror", (error) => consoleErrors.push(error.message));
page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
page.on("request", (request) => {
  if (recordInitialRequests && /CesiumMap|cesium\/Workers|cesium\/Assets/.test(request.url())) cesiumRequestsDuringInitial2d.push(request.url());
});
page.on("requestfailed", (request) => {
  if (request.url().startsWith(baseUrl) || request.url().includes("cyberjapandata.gsi.go.jp")) {
    criticalRequestFailures.push({ url: request.url(), error: request.failure()?.errorText ?? "unknown" });
  }
});

async function visit(route, viewport = { width: 1440, height: 900 }) {
  await page.setViewportSize(viewport);
  await page.goto(`${baseUrl}${route}`, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await page.locator(".product-app").waitFor({ timeout: 90_000 });
  await page.waitForFunction(() => document.documentElement.dataset.visualReady === "true", null, { timeout: 120_000 });
}

function check(condition, message) {
  if (!condition) throw new Error(message);
  return true;
}

const checks = {};
try {
  await visit("?city=maizuru&scene=city_overview&resolution=city&inspector=open");
  checks.city_discovery_ready = check(await page.locator(".analytical-map-shell").count() === 1, "2D discovery map is missing");
  checks.resolution_has_seven_levels = check(await page.locator(".resolution-rail button").count() === 7, "Resolution rail must expose seven levels");
  checks.initial_2d_lazy_loads_cesium = check(cesiumRequestsDuringInitial2d.length === 0, "Cesium was loaded during initial 2D discovery");
  checks.no_legacy_demo_ui = check(await page.locator(".story-mode, .presentation-guide").count() === 0 && !(await page.locator("body").innerText()).includes("4分デモ"), "Legacy demo UI remains visible");
  recordInitialRequests = false;

  await visit("?city=maizuru&scene=plateau_detail&mesh=533513314&resolution=city&mapMode=map2d&inspector=open");
  checks.scene_resolution_independent = check((await page.locator('.resolution-rail button[aria-current="step"] strong').innerText()) === "都市", "Scene changed the requested resolution");

  await visit("?city=maizuru&scene=gap_discovery&mesh=533512753&resolution=mesh&mapMode=map2d&inspector=open");
  const findingText = await page.locator(".object-lens").innerText();
  checks.object_lens_present = check(findingText.includes("PLATEAU OBJECT LENS"), "Object Lens is missing");
  checks.finding_bidirectional_trace = check(findingText.includes("Finding ↔ PLATEAU 追跡"), "Finding trace is missing");
  checks.plateau_off_audit = check(findingText.includes("PLATEAUを外すと失われるもの"), "PLATEAU OFF audit is missing");

  await visit("?city=maizuru&scene=plateau_detail&building=bldg_a490fb5b-d668-441e-b9af-5b35c4629006&resolution=building&mapMode=map2d&inspector=open");
  const buildingText = await page.locator(".context-inspector").innerText();
  checks.public_building_population_boundary = check(buildingText.includes("モデル推計配分（実居住者数ではない）"), "Building population claim boundary is missing");

  await visit("?city=maizuru&scene=plateau_detail&road=tran_3dbd690e-39ee-4c61-b3d9-9419620b06fc-0&lng=135.3964126&lat=35.4477785&resolution=road&mapMode=map2d&inspector=open");
  const roadText = await page.locator(".object-lens").innerText();
  checks.road_claim_boundary = check(roadText.includes("road-surface adjacency") && !roadText.includes("徒歩時間"), "Road semantics are overstated or missing");
  checks.road_to_finding_trace = check(roadText.includes("Finding ↔ PLATEAU 追跡"), "Road Finding reverse trace is missing");

  await visit("?city=fujisawa&task=validate&scene=temporal_change&resolution=building&lens=temporal-ghost&mapMode=map2d&inspector=open");
  checks.temporal_actual_points_visible = check(await page.evaluate(() => {
    const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
    return Boolean(map?.getLayer("temporal-point") && map.getLayoutProperty("temporal-point", "visibility") !== "none");
  }), "Temporal actual Point layer is not visible");

  await visit("?city=maizuru&scene=gap_discovery&mesh=533512753&resolution=mesh&inspector=open", { width: 390, height: 844 });
  const mobile = await page.evaluate(() => ({
    viewport: innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    mapWidth: Math.round(document.querySelector(".analytical-map-shell")?.getBoundingClientRect().width ?? 0),
    touchTargets: [...document.querySelectorAll("button")]
      .filter((element) => element.getClientRects().length > 0)
      .every((element) => {
        const rect = element.getBoundingClientRect();
        return rect.height >= 44 && rect.width >= 44;
      }),
  }));
  checks.mobile_no_horizontal_overflow = check(mobile.scrollWidth <= mobile.viewport + 1, "Mobile layout overflows horizontally");
  checks.mobile_map_retained = check(mobile.mapWidth >= 380, "Mobile map was replaced or collapsed");
  checks.mobile_touch_targets = check(mobile.touchTargets, "A visible mobile button is smaller than 44×44px");
  checks.reduced_motion_active = check(await page.evaluate(() => matchMedia("(prefers-reduced-motion: reduce)").matches), "Reduced motion is not active");

  await page.keyboard.press("Tab");
  checks.keyboard_focus_reachable = check(await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement !== document.body), "Keyboard focus is not reachable");
  checks.critical_requests_clean = check(criticalRequestFailures.length === 0, "Critical browser requests failed");
  checks.console_clean = check(consoleErrors.length === 0, "Browser console contains errors");

  const result = {
    schema_version: "citygap.plateau-native-browser-audit@1",
    generated_at: new Date().toISOString(),
    commit,
    production_url: baseUrl,
    automated_browser_walkthrough: true,
    human_usability_study: false,
    checks,
    mobile,
    initial_2d_cesium_requests: cesiumRequestsDuringInitial2d,
    critical_request_failures: criticalRequestFailures,
    console_errors: consoleErrors,
    passed: Object.values(checks).every(Boolean),
  };
  await mkdir(path.dirname(output), { recursive: true });
  await writeFile(output, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
} catch (error) {
  await mkdir(path.dirname(output), { recursive: true });
  const result = { schema_version: "citygap.plateau-native-browser-audit@1", generated_at: new Date().toISOString(), commit, production_url: baseUrl, checks, console_errors: consoleErrors, critical_request_failures: criticalRequestFailures, error: error instanceof Error ? error.message : String(error), passed: false };
  await writeFile(output, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  process.stderr.write(`${JSON.stringify(result, null, 2)}\n`);
  process.exitCode = 1;
} finally {
  await browser.close();
}
