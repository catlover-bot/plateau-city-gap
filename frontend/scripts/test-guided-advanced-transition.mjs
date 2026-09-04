import { chromium } from "playwright-core";

const parameters = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const key = process.argv[index];
  if (!key.startsWith("--")) continue;
  const value = process.argv[index + 1];
  parameters.set(key, value && !value.startsWith("--") ? value : "true");
  if (value && !value.startsWith("--")) index += 1;
}

const baseUrl = parameters.get("--url") ?? "http://127.0.0.1:4173/plateau-city-gap/";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const FULL_DATA_FILES = [
  "top10.json",
  "final_demo.json",
  "robustness.json",
  "intervention_scenarios.json",
  "evidence.json",
  "stations.geojson",
  "bus_stops.geojson",
  "medical_facilities.geojson",
  "maizuru_boundary.geojson",
  "plateau_buildings.geojson",
  "plateau_roads.geojson",
  "plateau_metadata.json",
];
const ANCILLARY_OPERATE_FILES = [
  "urban_futures_resilience.json",
  "municipal_workspace_story.json",
  "network_scenario_map.geojson",
  "network_scenario_building_points.json",
  "platform_registry.json",
];

function invariant(condition, message, detail) {
  if (!condition) throw new Error(`${message}${detail === undefined ? "" : `: ${JSON.stringify(detail)}`}`);
}

function queryUrl(query) {
  const url = new URL(baseUrl);
  url.search = query;
  return url.href;
}

function installDiagnostics(context, label, expectedError = () => false, expectedConsoleFragments = []) {
  const result = { label, console: [], page: [], request: [], response: [], unhandled: [] };
  context.addInitScript(() => {
    window.__cityGapUnhandledRejections = [];
    window.addEventListener("unhandledrejection", (event) => {
      window.__cityGapUnhandledRejections.push(String(event.reason));
    });
  });
  const attach = (page) => {
    page.on("console", (message) => {
      const expectedConsole = expectedConsoleFragments.some((fragment) => message.text().includes(fragment));
      if (message.type() === "error" && !message.text().includes("cyberjapandata.gsi.go.jp") && !expectedConsole) {
        result.console.push(message.text());
      }
    });
    page.on("pageerror", (error) => result.page.push(error.message));
    page.on("requestfailed", (request) => {
      const error = request.failure()?.errorText ?? "unknown";
      if (request.url().startsWith(new URL(baseUrl).origin) && !expectedError(request.url()) && error !== "net::ERR_ABORTED") {
        result.request.push({ url: request.url(), error });
      }
    });
    page.on("response", (response) => {
      if (response.status() >= 400 && !expectedError(response.url())) {
        result.response.push({ url: response.url(), status: response.status() });
      }
    });
  };
  return { result, attach };
}

async function readUpgrade(page) {
  return page.evaluate(() => window.__cityGapFullDataUpgrade ?? null);
}

async function readUnhandled(page) {
  return page.evaluate(() => window.__cityGapUnhandledRejections ?? []);
}

async function waitForGuided(page, story = "intro") {
  await page.locator(`.guided-spatial-app[data-guided-story="${story}"]`).waitFor({ timeout: 90_000 });
}

async function waitForAdvanced(page) {
  await page.locator('.product-app[data-experience="advanced"]').waitFor({ timeout: 90_000 });
  await page.locator(".task-navigation").waitFor({ timeout: 90_000 });
  await page.locator(".map-stage").waitFor({ timeout: 90_000 });
}

async function transitionUrlInPlace(page, experience, story) {
  await page.evaluate(({ nextExperience, nextStory }) => {
    const url = new URL(window.location.href);
    url.searchParams.set("experience", nextExperience);
    url.searchParams.set("story", nextStory);
    window.history.pushState({}, "", url);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, { nextExperience: experience, nextStory: story });
}

async function assertCleanDiagnostics(page, diagnostics) {
  diagnostics.result.unhandled.push(...await readUnhandled(page));
  invariant(diagnostics.result.console.length === 0, "console errors", diagnostics.result.console);
  invariant(diagnostics.result.page.length === 0, "page errors", diagnostics.result.page);
  invariant(diagnostics.result.request.length === 0, "required same-origin request failures", diagnostics.result.request);
  invariant(diagnostics.result.response.length === 0, "unexpected HTTP errors", diagnostics.result.response);
  invariant(diagnostics.result.unhandled.length === 0, "unhandled rejections", diagnostics.result.unhandled);
}

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

const report = {
  schema_version: "citygap.guided-advanced-transition@1",
  base_url: baseUrl,
  flows: {},
  diagnostics: [],
};

try {
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, serviceWorkers: "block" });
    const diagnostics = installDiagnostics(context, "direct-advanced");
    const page = await context.newPage();
    diagnostics.attach(page);
    const requests = [];
    page.on("request", (request) => {
      const filename = FULL_DATA_FILES.find((item) => request.url().endsWith(`/data/${item}`));
      if (filename) requests.push(filename);
    });
    await page.goto(queryUrl("?experience=advanced&city=maizuru&task=operate"), { waitUntil: "domcontentloaded" });
    await waitForAdvanced(page);
    const upgrade = await readUpgrade(page);
    invariant(upgrade?.mode === "full" && upgrade.fullLoadStartCount === 1 && upgrade.settleResult === "success", "direct Advanced did not settle full", upgrade);
    invariant(new Set(requests).size === FULL_DATA_FILES.length, "direct Advanced did not request the complete dataset", requests);
    await assertCleanDiagnostics(page, diagnostics);
    report.flows.direct_advanced = { pass: true, upgrade, full_data_requests: requests.length };
    report.diagnostics.push(diagnostics.result);
    await context.close();
  }

  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, serviceWorkers: "block" });
    const diagnostics = installDiagnostics(
      context,
      "guided-upgrade",
      (url) => ANCILLARY_OPERATE_FILES.some((filename) => url.endsWith(`/data/${filename}`)),
      ["net::ERR_BLOCKED_BY_CLIENT"],
    );
    let fullMarkerStarts = 0;
    let ancillaryStarts = 0;
    await context.route("**/data/*", async (route) => {
      const url = route.request().url();
      if (url.endsWith("/data/robustness.json")) {
        fullMarkerStarts += 1;
        await new Promise((resolve) => setTimeout(resolve, 350));
      }
      if (ANCILLARY_OPERATE_FILES.some((filename) => url.endsWith(`/data/${filename}`))) {
        ancillaryStarts += 1;
        await route.abort("blockedbyclient");
        return;
      }
      await route.continue();
    });
    const page = await context.newPage();
    diagnostics.attach(page);
    await page.goto(queryUrl("?experience=guided&story=intro"), { waitUntil: "domcontentloaded" });
    await waitForGuided(page);
    await page.getByRole("button", { name: "詳細分析", exact: true }).click();
    await page.locator(".state-screen:not(.error-state)").waitFor();
    await waitForAdvanced(page);
    const firstUpgrade = await readUpgrade(page);
    invariant(firstUpgrade?.mode === "full" && firstUpgrade.fullLoadStartCount === 1 && firstUpgrade.settleResult === "success", "Guided upgrade did not settle full", firstUpgrade);
    invariant(fullMarkerStarts === 1, "Guided upgrade was not single-flight", { fullMarkerStarts });
    invariant(ancillaryStarts === ANCILLARY_OPERATE_FILES.length, "operate ancillary requests were not exercised", { ancillaryStarts });

    await transitionUrlInPlace(page, "guided", "intro");
    await waitForGuided(page);
    await page.goBack();
    await waitForAdvanced(page);
    await page.goForward();
    await waitForGuided(page);
    await page.getByRole("button", { name: "詳細分析", exact: true }).click();
    await waitForAdvanced(page);
    const cachedUpgrade = await readUpgrade(page);
    invariant(fullMarkerStarts === 1 && cachedUpgrade?.fullLoadStartCount === 1, "cached full data was fetched again", { fullMarkerStarts, cachedUpgrade });
    await assertCleanDiagnostics(page, diagnostics);
    report.flows.guided_upgrade = {
      pass: true,
      loading_state_seen: true,
      first_upgrade: firstUpgrade,
      cached_upgrade: cachedUpgrade,
      full_marker_starts: fullMarkerStarts,
      ancillary_requests_aborted_without_blocking: ancillaryStarts,
      back_forward: true,
    };
    report.diagnostics.push(diagnostics.result);
    await context.close();
  }

  {
    const longQuery = "?experience=advanced&city=maizuru&task=operate&workspace=workspace&urbanState=2025&mapMode=map2d&intent=inspect&resolution=mesh&scene=gap_discovery&preset=discovery&layer=analysis-city-gap&lens=none&twin=baseline&lng=135.39829&lat=35.44790&z=18.68&selectionType=mesh&selection=533513314&mesh=533513314&selectionLng=135.3968750&selectionLat=35.4479167";
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, serviceWorkers: "block" });
    const diagnostics = installDiagnostics(context, "long-url");
    const page = await context.newPage();
    diagnostics.attach(page);
    await page.goto(queryUrl(longQuery), { waitUntil: "domcontentloaded" });
    await waitForAdvanced(page);
    const upgrade = await readUpgrade(page);
    invariant(upgrade?.mode === "full" && upgrade.settleResult === "success", "long Advanced URL did not load", upgrade);
    invariant(new URL(page.url()).searchParams.get("selection") === "533513314", "long URL lost its selected mesh", page.url());
    await page.reload({ waitUntil: "domcontentloaded" });
    await waitForAdvanced(page);
    await assertCleanDiagnostics(page, diagnostics);
    report.flows.long_url_and_reload = { pass: true, upgrade, selection: "533513314" };
    report.diagnostics.push(diagnostics.result);
    await context.close();
  }

  {
    const legacy = [];
    for (const guide of ["5", "6"]) {
      const context = await browser.newContext({ viewport: { width: 1280, height: 720 }, serviceWorkers: "block" });
      const diagnostics = installDiagnostics(context, `legacy-guide-${guide}`);
      const page = await context.newPage();
      diagnostics.attach(page);
      await page.goto(queryUrl(`?guide=${guide}`), { waitUntil: "domcontentloaded" });
      await waitForAdvanced(page);
      const upgrade = await readUpgrade(page);
      invariant(upgrade?.mode === "full" && upgrade.fullLoadStartCount === 1, `legacy guide=${guide} did not load Advanced`, upgrade);
      await assertCleanDiagnostics(page, diagnostics);
      legacy.push({ guide, pass: true, final_url: page.url(), upgrade });
      report.diagnostics.push(diagnostics.result);
      await context.close();
    }
    report.flows.legacy_routes = legacy;
  }

  {
    const expectedFailure = (url) => url.endsWith("/data/robustness.json");
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, serviceWorkers: "block" });
    const diagnostics = installDiagnostics(
      context,
      "failure-retry",
      expectedFailure,
      ["status of 503"],
    );
    let robustnessAttempts = 0;
    await context.route("**/data/robustness.json", async (route) => {
      robustnessAttempts += 1;
      if (robustnessAttempts === 1) {
        await route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
        return;
      }
      await route.continue();
    });
    const page = await context.newPage();
    diagnostics.attach(page);
    await page.goto(queryUrl("?experience=guided&story=intro"), { waitUntil: "domcontentloaded" });
    await waitForGuided(page);
    await page.getByRole("button", { name: "詳細分析", exact: true }).click();
    await page.locator(".error-state").waitFor({ timeout: 90_000 });
    const failedUpgrade = await readUpgrade(page);
    invariant(failedUpgrade?.mode === "full-error" && failedUpgrade.settleResult === "error" && failedUpgrade.fullLoadStartCount === 1, "failure did not settle to retryable full-error", failedUpgrade);
    await page.getByRole("button", { name: "もう一度試す", exact: true }).click();
    await waitForAdvanced(page);
    const retriedUpgrade = await readUpgrade(page);
    invariant(retriedUpgrade?.mode === "full" && retriedUpgrade.settleResult === "success" && retriedUpgrade.requestGeneration === 2 && retriedUpgrade.fullLoadStartCount === 2, "retry did not settle full", retriedUpgrade);
    invariant(robustnessAttempts === 2, "retry request count mismatch", { robustnessAttempts });
    await assertCleanDiagnostics(page, diagnostics);
    report.flows.failure_retry = { pass: true, failed_upgrade: failedUpgrade, retried_upgrade: retriedUpgrade, robustness_attempts: robustnessAttempts };
    report.diagnostics.push(diagnostics.result);
    await context.close();
  }

  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
} finally {
  await browser.close();
}
