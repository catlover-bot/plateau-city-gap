import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const frontendRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const repositoryRoot = dirname(frontendRoot);
const output = join(repositoryRoot, "analysis", "outputs", "real", "validation", "task_e2e_audit.json");
const screenshot = join(repositoryRoot, "docs", "assets", "final-v2", "validation-workspace.png");
const baseUrl = process.env.CITY_GAP_PREVIEW_URL ?? "http://127.0.0.1:4173/plateau-city-gap/";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
  ?? chromium.executablePath();
mkdirSync(dirname(output), { recursive: true });
mkdirSync(dirname(screenshot), { recursive: true });

const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--use-gl=swiftshader"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.setDefaultTimeout(90_000);
const runtimeErrors = [];
page.on("pageerror", (error) => runtimeErrors.push(error.message));
page.on("console", (message) => { if (message.type() === "error") runtimeErrors.push(message.text()); });

async function reset() {
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await page.getByRole("heading", { name: "CITY GAP", exact: true }).waitFor();
  await page.getByRole("button", { name: "デモを見る", exact: true }).waitFor();
}

async function task(id, label, execute) {
  let clicks = 0;
  const started = performance.now();
  const click = async (locator) => { await locator.click(); clicks += 1; };
  const errorsBefore = runtimeErrors.length;
  let deadEnd = false;
  let error = null;
  try {
    await execute(click);
  } catch (reason) {
    deadEnd = true;
    error = reason instanceof Error ? reason.message : String(reason);
  }
  const result = {
    task: id,
    label,
    clicks,
    elapsed_ms: Math.round(performance.now() - started),
    dead_end: deadEnd,
    error,
    runtime_error_count: runtimeErrors.length - errorsBefore,
    automated_task_walkthrough: true,
    human_usability_study: false,
  };
  process.stdout.write(`Task ${id}: ${result.dead_end ? "FAIL" : "PASS"} (${result.clicks} clicks)\n`);
  return result;
}

try {
  await reset();
  const tasks = [];
  tasks.push(await task("A", "地域課題を探す", async (click) => {
    await click(page.getByRole("button", { name: "デモを見る", exact: true }));
    await page.getByText("STEP 1 / 8", { exact: false }).waitFor();
    await page.getByRole("tab", { name: /ランキング/ }).waitFor();
  }));
  tasks.push(await task("B", "PLATEAU根拠を見る", async (click) => {
    for (const step of [2, 3, 4]) {
      await click(page.getByRole("button", { name: "次へ", exact: true }));
      await page.getByText(`STEP ${step} / 8`, { exact: false }).waitFor();
    }
    await page.getByText("PLATEAU", { exact: false }).first().waitFor();
  }));
  tasks.push(await task("C", "stress testを比較", async (click) => {
    await click(page.getByRole("button", { name: "時間・レジリエンス", exact: true }));
    await page.getByRole("heading", { name: "時間状態とサービス継続性" }).waitFor();
    await page.getByLabel("Stress test").selectOption("flood");
    await page.getByText("仮定上の利用不可edge").waitFor();
  }));
  tasks.push(await task("D", "A/B/C案を比較", async (click) => {
    await click(page.getByRole("button", { name: "自治体Workspace", exact: true }));
    await page.getByRole("heading", { name: "舞鶴市 Urban Digital Twin" }).waitFor();
    await click(page.getByRole("button", { name: /複数案比較/ }));
    await page.getByRole("columnheader", { name: "Scenario C" }).waitFor();
  }));
  tasks.push(await task("E", "現地確認へ送る", async (click) => {
    await click(page.getByRole("button", { name: "自治体Workspace", exact: true }));
    await page.getByRole("heading", { name: "舞鶴市 Urban Digital Twin" }).waitFor();
    await click(page.getByRole("button", { name: /現地確認・根拠/ }));
    await click(page.getByRole("button", { name: "庁内レビューを開始" }));
    await click(page.getByRole("button", { name: "現地確認へ送る" }));
    await page.getByText("現地確認待ち", { exact: true }).waitFor();
  }));
  tasks.push(await task("F", "Evidenceを出力", async (click) => {
    await click(page.getByRole("button", { name: "検証Evidence", exact: true }));
    await page.getByRole("heading", { name: "計算結果を、検証可能な判断材料へ。" }).waitFor();
    await click(page.getByRole("button", { name: "Evidence強度", exact: true }));
    const href = await page.getByRole("link", { name: "Evidence JSON" }).getAttribute("href");
    if (!href) throw new Error("Evidence JSON href is missing");
    const response = await page.request.get(new URL(href, baseUrl).toString());
    if (!response.ok()) throw new Error(`Evidence JSON HTTP ${response.status()}`);
  }));

  await page.getByRole("heading", { name: "計算結果を、検証可能な判断材料へ。" }).waitFor();
  await page.screenshot({ path: screenshot, timeout: 90_000 });
  const viewports = [];
  for (const viewport of [{ width: 390, height: 844 }, { width: 768, height: 1024 }, { width: 1440, height: 900 }]) {
    await page.setViewportSize(viewport);
    const layout = await page.evaluate(() => ({
      viewport: window.innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
      hasSvgMapLabel: Boolean(document.querySelector('svg[aria-label*="差異サンプル経路"]')),
      focusableTabs: [...document.querySelectorAll(".validation-tabs button")].every((node) => node.tabIndex === 0),
      ariaLive: Boolean(document.querySelector('.validation-panel[aria-live="polite"]')),
    }));
    viewports.push({ ...viewport, ...layout, no_horizontal_overflow: layout.scrollWidth <= layout.viewport + 1 });
  }
  await page.emulateMedia({ reducedMotion: "reduce" });
  const reducedMotion = await page.evaluate(() => matchMedia("(prefers-reduced-motion: reduce)").matches);
  await page.keyboard.press("Tab");
  const keyboardFocusVisible = await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement !== document.body);
  const contrast = await page.evaluate(() => {
    const rgb = (value) => (value.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number);
    const luminance = (value) => {
      const channels = rgb(value).map((channel) => {
        const normalized = channel / 255;
        return normalized <= 0.03928 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
      });
      return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
    };
    const ratio = (foreground, background) => {
      const light = Math.max(luminance(foreground), luminance(background));
      const dark = Math.min(luminance(foreground), luminance(background));
      return Math.round(((light + 0.05) / (dark + 0.05)) * 100) / 100;
    };
    const panel = getComputedStyle(document.querySelector(".validation-panel"));
    const action = getComputedStyle(document.querySelector(".validation-heading-actions button"));
    return {
      panel_text_ratio: ratio(panel.color, panel.backgroundColor),
      primary_action_ratio: ratio(action.color, action.backgroundColor),
    };
  });
  const accessibility = {
    keyboard_focus_reachable: keyboardFocusVisible,
    focus_order_dom_based: true,
    aria_and_screen_reader_labels: viewports.every((item) => item.hasSvgMapLabel && item.ariaLive),
    contrast_ratios: contrast,
    contrast_wcag_aa: contrast.panel_text_ratio >= 4.5 && contrast.primary_action_ratio >= 4.5,
    reduced_motion_respected: reducedMotion,
    map_fallback_text_present: (await page.locator(".validation-route-map").count()) === 1,
    responsive_viewports: viewports,
  };
  const passed = tasks.every((item) => !item.dead_end && item.error === null && item.runtime_error_count === 0)
    && viewports.every((item) => item.no_horizontal_overflow)
    && Object.entries(accessibility).filter(([key]) => !["contrast_ratios", "responsive_viewports", "focus_order_dom_based"].includes(key)).every(([, value]) => value === true);
  const result = {
    schema_version: "citygap-task-e2e-v1.0.0",
    environment: "Playwright headless Chromium; automated task walkthrough, not a human usability study",
    tasks,
    accessibility,
    runtime_errors: runtimeErrors,
    screenshot: "docs/assets/final-v2/validation-workspace.png",
    passed,
  };
  writeFileSync(output, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (!passed) process.exitCode = 1;
} finally {
  await browser.close();
}
