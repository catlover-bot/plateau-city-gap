import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const frontendRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const repositoryRoot = dirname(frontendRoot);
const screenshot = join(repositoryRoot, "docs", "assets", "final-v2", "municipal-workspace.png");
const auditOutput = join(
  repositoryRoot,
  "analysis",
  "outputs",
  "real",
  "municipal_workspace_browser_audit.json",
);
const baseUrl = process.env.CITY_GAP_PREVIEW_URL
  ?? "http://127.0.0.1:4173/plateau-city-gap/";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
  ?? "/home/catlover/.cache/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-linux64/chrome-headless-shell";
mkdirSync(dirname(screenshot), { recursive: true });
mkdirSync(dirname(auditOutput), { recursive: true });

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
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
page.setDefaultTimeout(90_000);
const errors = [];
const failures = [];
page.on("console", (message) => {
  if (message.type() === "error") errors.push(message.text());
});
page.on("pageerror", (error) => errors.push(error.message));
page.on("requestfailed", (request) => {
  failures.push(`${request.url()}: ${request.failure()?.errorText ?? "failed"}`);
});

try {
  const started = Date.now();
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await page.locator(".map-loading").waitFor({ state: "hidden" });
  const demoReadyMs = Date.now() - started;
  await page.getByRole("button", { name: "自治体Workspace", exact: true }).click();
  await page.getByRole("heading", { name: "舞鶴市 Urban Digital Twin" }).waitFor();
  await page.getByRole("button", { name: "Scenario A", exact: true }).click();
  await page.getByRole("checkbox", { name: "改善対象建物" }).check();
  await page.locator('.cesium-map[data-workspace-points="ready"]').waitFor();
  const workspaceReadyMs = Date.now() - started;

  const scenarioC = page.getByRole("button", { name: "Scenario C", exact: true });
  if (!(await scenarioC.isEnabled())) failures.push("Scenario C is disabled");
  await page.getByRole("checkbox", { name: "改善対象建物" }).uncheck();
  await scenarioC.click();
  if ((await scenarioC.getAttribute("aria-pressed")) !== "true") {
    failures.push("Scenario C did not activate");
  }
  await page.getByRole("button", { name: "Scenario A", exact: true }).click();
  await page.getByRole("checkbox", { name: "改善対象建物" }).check();
  await page.locator('.cesium-map[data-workspace-points="ready"]').waitFor();
  await page.getByRole("button", { name: /シナリオ作成/ }).click();
  await page.getByRole("heading", { name: "Scenario A" }).waitFor();
  await page.locator(".map-loading").waitFor({ state: "hidden" });
  await page.waitForTimeout(1_000);

  const applicationText = await page.locator(".app-shell").innerText();
  if (!applicationText.includes("建物別人数と厳密な改善値は表示しません")) {
    failures.push("Privacy disclosure is missing");
  }
  if (applicationText.includes("推奨案")) failures.push("Workspace contains recommendation wording");
  await page.screenshot({ path: screenshot, timeout: 90_000 });

  const resources = await page.evaluate(() => performance.getEntriesByType("resource")
    .filter((entry) => entry.name.includes("municipal_workspace")
      || entry.name.includes("network_scenario_map")
      || entry.name.includes("network_scenario_building"))
    .map((entry) => ({
      name: entry.name.split("/").pop(),
      duration_ms: Math.round(entry.duration),
      transfer_bytes: "transferSize" in entry ? entry.transferSize : null,
    })));
  const result = {
    schema_version: "1.0.0",
    environment: "Playwright headless Chromium with SwiftShader",
    viewport: { width: 1440, height: 900 },
    demo_ready_ms: demoReadyMs,
    scenario_a_points_ready_ms_from_navigation: workspaceReadyMs,
    resource_timings: resources,
    console_errors: errors,
    request_or_ui_failures: failures,
    checks: {
      initial_demo_ready: demoReadyMs > 0,
      scenario_a_points_rendered: workspaceReadyMs > demoReadyMs,
      scenario_c_selectable: !failures.includes("Scenario C is disabled"),
      privacy_disclosure_visible: !failures.includes("Privacy disclosure is missing"),
      no_console_errors: errors.length === 0,
      no_request_or_ui_failures: failures.length === 0,
    },
    screenshot: "docs/assets/final-v2/municipal-workspace.png",
    note: "Headless SwiftShader timing is a regression observation, not a production-browser SLA.",
  };
  result.passed = Object.values(result.checks).every(Boolean);
  writeFileSync(auditOutput, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (!result.passed) process.exitCode = 1;
} finally {
  await browser.close();
}
