import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const frontendRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const repositoryRoot = dirname(frontendRoot);
const output = join(repositoryRoot, "docs", "assets", "urban-futures-workspace.png");
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
  ?? "/home/catlover/.cache/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-linux64/chrome-headless-shell";
const baseUrl = process.env.CITY_GAP_PREVIEW_URL
  ?? "http://127.0.0.1:4173/plateau-city-gap/";

mkdirSync(dirname(output), { recursive: true });
const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--use-gl=swiftshader"]
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const consoleErrors = [];
page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text());
});
page.on("pageerror", (error) => consoleErrors.push(error.message));

try {
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await page.getByRole("button", { name: "時間・レジリエンス" }).click();
  await page.getByRole("heading", { name: "時間状態とサービス継続性" }).waitFor();
  await page.getByLabel("Stress test").selectOption("flood");
  await page.getByText("これは災害時の実通行可否を予測したものではありません。").waitFor();
  const panelText = await page.locator(".futures-workspace").innerText();
  const checks = {
    three_state_comparison: panelText.toLowerCase().includes("3 state comparison") && panelText.includes("2040"),
    explicit_assumption: panelText.includes("明示的な道路利用不可仮定"),
    criticality_boundary: panelText.includes("危険道路") && panelText.includes("レビュー候補"),
    offline_conflict: panelText.includes("自動上書きせず自治体が解決"),
    no_prediction: panelText.includes("実通行可否を予測したものではありません"),
    aggregated_only: panelText.includes("集約済み実データ")
  };
  await page.screenshot({ path: output, timeout: 60_000 });
  process.stdout.write(`${JSON.stringify({ baseUrl, output, checks, consoleErrors }, null, 2)}\n`);
  if (consoleErrors.length > 0 || Object.values(checks).some((value) => !value)) process.exitCode = 1;
} finally {
  await browser.close();
}
