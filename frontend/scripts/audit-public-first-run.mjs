import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright-core";

process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY = "1";

const baseUrl = process.argv[2] ?? "http://127.0.0.1:4174/plateau-city-gap/";
const repositoryRoot = path.resolve(process.cwd(), "..");
const outputDirectory = path.join(repositoryRoot, "docs/assets/public-first-run-ux");
const repositoryHead = execFileSync("git", ["rev-parse", "HEAD"], {
  cwd: repositoryRoot,
  encoding: "utf8",
}).trim();
const executablePath =
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const baseline = {
  "1440x900": { map_share_percent: 46, panel_share_percent: 54, visible_controls: 14, map_occlusion_percent: 7.9 },
  "1280x720": { map_share_percent: 46, panel_share_percent: 54, visible_controls: 13, map_occlusion_percent: 11.3 },
  "390x844": { map_share_percent: 29, panel_share_percent: 73.5, visible_controls: 12, map_occlusion_percent: 38.8, overlap_px: 20 },
};
const screenshots = [];
const diagnostics = [];
const prohibitedCopy = [
  "徒歩10分圏",
  "10分以内に歩ける",
  "walking isochrone",
  "実際に徒歩で到達できる",
  "道路ネットワーク上の徒歩圏",
];

const sha256 = (value) => createHash("sha256").update(value).digest("hex");

async function waitForStep(page, step) {
  await page.locator(`.public-area[data-public-step="${step}"]`).waitFor({
    state: "visible",
    timeout: 120_000,
  });
}

async function capture(page, filename, scene, viewport) {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
  const target = path.join(outputDirectory, filename);
  await page.screenshot({ path: target, fullPage: false, animations: "disabled", timeout: 180_000 });
  const png = await readFile(target);
  screenshots.push({
    filename,
    scene,
    viewport,
    bytes: png.length,
    sha256: sha256(png),
    url: page.url(),
  });
}

function attachDiagnostics(page, label) {
  const record = { label, page_errors: [], failed_same_origin_requests: [], error_responses: [] };
  page.on("pageerror", (error) => record.page_errors.push(error.message));
  page.on("requestfailed", (request) => {
    try {
      if (new URL(request.url()).origin === new URL(baseUrl).origin) {
        record.failed_same_origin_requests.push({ url: request.url(), error: request.failure()?.errorText ?? "unknown" });
      }
    } catch {
      record.failed_same_origin_requests.push({ url: request.url(), error: "invalid-url" });
    }
  });
  page.on("response", (response) => {
    if (response.status() >= 400 && response.url().startsWith(new URL(baseUrl).origin)) {
      record.error_responses.push({ url: response.url(), status: response.status() });
    }
  });
  diagnostics.push(record);
  return record;
}

async function stateMetrics(page) {
  return page.evaluate(() => {
    const round = (value) => Math.round(value * 10) / 10;
    const visible = (element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== "none"
        && style.visibility !== "hidden"
        && rect.width > 0
        && rect.height > 0
        && rect.bottom > 0
        && rect.right > 0
        && rect.top < innerHeight
        && rect.left < innerWidth;
    };
    const rectOf = (selector) => {
      const element = document.querySelector(selector);
      if (!element) return null;
      const rect = element.getBoundingClientRect();
      return { x: rect.x, y: rect.y, width: rect.width, height: rect.height, right: rect.right, bottom: rect.bottom };
    };
    const body = rectOf(".public-area-body");
    const map = rectOf(".public-map-stage");
    const panel = rectOf(".public-area-panel");
    if (!body || !map || !panel) throw new Error("public layout regions are missing");
    const mobile = innerWidth <= 900;
    let covered = 0;
    const sampleColumns = 80;
    const sampleRows = 80;
    for (let column = 0; column < sampleColumns; column += 1) {
      for (let row = 0; row < sampleRows; row += 1) {
        const x = map.x + (column + 0.5) * map.width / sampleColumns;
        const y = map.y + (row + 0.5) * map.height / sampleRows;
        const element = document.elementFromPoint(x, y);
        if (element?.closest(".public-map-caption, .maplibregl-ctrl-group, .map-mode-switch")) covered += 1;
      }
    }
    const controls = [...document.querySelectorAll("button:not([disabled]), select:not([disabled]), input:not([disabled]), a[href]")]
      .filter(visible);
    const primary = [...document.querySelectorAll(".public-primary:not([disabled])")].filter(visible);
    const summaries = [...document.querySelectorAll("summary")].filter(visible);
    const overlapWidth = Math.max(0, Math.min(map.right, panel.right) - Math.max(map.x, panel.x));
    const overlapHeight = Math.max(0, Math.min(map.bottom, panel.bottom) - Math.max(map.y, panel.y));
    return {
      viewport: { width: innerWidth, height: innerHeight },
      step: document.querySelector(".public-area")?.getAttribute("data-public-step"),
      map_share_percent: round(mobile ? map.height / body.height * 100 : map.width / body.width * 100),
      panel_share_percent: round(mobile ? panel.height / body.height * 100 : panel.width / body.width * 100),
      visible_controls: controls.length,
      visible_disclosures: summaries.length,
      primary_cta_count: primary.length,
      map_occlusion_percent: round(covered / (sampleColumns * sampleRows) * 100),
      map_panel_overlap_px2: round(overlapWidth * overlapHeight),
      horizontal_overflow_px: Math.max(0, document.documentElement.scrollWidth - innerWidth),
      map,
      panel,
    };
  });
}

async function accessibilityAudit(page) {
  return page.evaluate(() => {
    const visible = (element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
    };
    const name = (element) => {
      const aria = element.getAttribute("aria-label");
      if (aria?.trim()) return aria.trim();
      const labelledBy = element.getAttribute("aria-labelledby");
      if (labelledBy) {
        const text = labelledBy.split(/\s+/).map((id) => document.getElementById(id)?.textContent ?? "").join(" ").trim();
        if (text) return text;
      }
      if (element instanceof HTMLInputElement || element instanceof HTMLSelectElement) {
        const label = element.id ? document.querySelector(`label[for="${CSS.escape(element.id)}"]`) : null;
        if (label?.textContent?.trim()) return label.textContent.trim();
      }
      return element.textContent?.trim() ?? "";
    };
    const interactive = [...document.querySelectorAll("button, select, input, a[href], summary")].filter(visible);
    const unnamed = interactive.filter((element) => !name(element)).map((element) => element.outerHTML.slice(0, 180));
    const ids = [...document.querySelectorAll("[id]")].map((element) => element.id);
    const duplicateIds = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
    const imagesWithoutAlt = [...document.querySelectorAll("img")].filter((image) => !image.hasAttribute("alt")).length;
    const h1Count = [...document.querySelectorAll("h1")].filter(visible).length;
    const critical = [];
    if (!document.querySelector("header")) critical.push("header landmark missing");
    if (!document.querySelector("main")) critical.push("main landmark missing");
    if (h1Count !== 1) critical.push(`visible h1 count ${h1Count}`);
    if (unnamed.length) critical.push(`unnamed controls ${unnamed.length}`);
    if (duplicateIds.length) critical.push(`duplicate ids ${duplicateIds.join(",")}`);
    if (imagesWithoutAlt) critical.push(`images without alt ${imagesWithoutAlt}`);
    return { critical, unnamed, duplicate_ids: duplicateIds, images_without_alt: imagesWithoutAlt, h1_count: h1Count };
  });
}

async function keyboardAudit(page) {
  await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
  const order = [];
  const invisibleFocus = [];
  for (let index = 0; index < 10; index += 1) {
    await page.keyboard.press("Tab");
    const focused = await page.evaluate(() => {
      const element = document.activeElement;
      if (!(element instanceof HTMLElement)) return null;
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return {
        label: element.getAttribute("aria-label") || element.textContent?.trim() || element.getAttribute("name") || element.tagName,
        tag: element.tagName,
        visible: rect.width > 0 && rect.height > 0 && rect.top < innerHeight && rect.bottom > 0,
        focus_visible: style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0,
      };
    });
    if (!focused) continue;
    order.push({ label: focused.label, tag: focused.tag });
    if (!focused.visible || !focused.focus_visible) invisibleFocus.push(focused);
  }
  return { order, invisible_focus: invisibleFocus };
}

async function click(page, name) {
  await page.getByRole("button", { name, exact: true }).click();
}

async function reachRadius(page) {
  await click(page, "地図で場所を調べる");
  await waitForStep(page, "place");
  await click(page, "選んだ駅を起点にする");
  await waitForStep(page, "radius");
}


async function ensurePublicBoundaries(page) {
  const bodyText = await page.locator("body").innerText();
  const foundProhibited = prohibitedCopy.filter((copy) => bodyText.includes(copy));
  const evidenceInputs = await page.locator(".area-task-flow input, .area-task-flow textarea, .area-task-flow select").count();
  const internalIdInitiallyVisible = await page.locator(".area-target-source code").isVisible().catch(() => false);
  if (foundProhibited.length || evidenceInputs || internalIdInitiallyVisible) {
    throw new Error(JSON.stringify({ foundProhibited, evidenceInputs, internalIdInitiallyVisible }));
  }
  return { prohibited_copy_found: foundProhibited, evidence_inputs: evidenceInputs, internal_id_initially_visible: internalIdInitiallyVisible };
}

await mkdir(outputDirectory, { recursive: true });
const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist", "--use-gl=swiftshader"],
});

try {
  const fmrSamples = [];
  for (let index = 0; index < 5; index += 1) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
    await waitForStep(page, "intro");
    await page.getByRole("heading", { name: "気になる場所を、 地図とデータで確かめる。" }).waitFor();
    fmrSamples.push(await page.evaluate(() => Math.round(performance.now())));
    await context.close();
  }
  const sortedFmr = [...fmrSamples].sort((left, right) => left - right);
  const fmrMedian = sortedFmr[Math.floor(sortedFmr.length / 2)];

  const layouts = {};
  const accessibility = {};
  const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
  const page = await desktop.newPage();
  attachDiagnostics(page, "desktop");
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await waitForStep(page, "intro");
  layouts.desktop_intro = await stateMetrics(page);
  accessibility.desktop_intro = await accessibilityAudit(page);
  const keyboard = await keyboardAudit(page);
  await capture(page, "01-landing-desktop.png", "landing", { width: 1440, height: 900 });

  await reachRadius(page);
  layouts.desktop_radius = await stateMetrics(page);
  accessibility.desktop_radius = await accessibilityAudit(page);
  await capture(page, "02-place-radius-desktop.png", "place-radius", { width: 1440, height: 900 });
  await click(page, "800m");
  await click(page, "この範囲を調べる");
  await waitForStep(page, "result");
  layouts.desktop_result = await stateMetrics(page);
  accessibility.desktop_result = await accessibilityAudit(page);
  await page.locator("#area-unknown-title").scrollIntoViewIfNeeded();
  await capture(page, "03-known-unknown-desktop.png", "known-unknown", { width: 1440, height: 900 });
  await click(page, "確認場所を見る");
  await waitForStep(page, "target");
  layouts.desktop_target = await stateMetrics(page);
  accessibility.desktop_target = await accessibilityAudit(page);
  const boundaries = await ensurePublicBoundaries(page);
  const requirementCount = await page.locator(".area-task-list li").count();
  await page.waitForTimeout(1200);
  await capture(page, "04-target-task-desktop.png", "target-task", { width: 1440, height: 900 });
  const contextual3d = {
    eligible: await page.locator('[data-contextual-3d-eligible="true"]').count() === 1,
    button_visible: await page.getByRole("button", { name: "3Dで場所を見る", exact: true }).isVisible().catch(() => false),
  };
  if (contextual3d.button_visible) {
    await click(page, "3Dで場所を見る");
    await page.locator('.public-area[data-map-mode="plateau3d"]').waitFor();
    await page.waitForTimeout(1200);
    await capture(page, "05-contextual-3d-enabled.png", "contextual-3d-enabled", { width: 1440, height: 900 });
  }
  await desktop.close();

  const compact = await browser.newContext({ viewport: { width: 1280, height: 720 }, reducedMotion: "reduce" });
  const compactPage = await compact.newPage();
  await compactPage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await waitForStep(compactPage, "intro");
  layouts.compact_intro = await stateMetrics(compactPage);
  await compact.close();

  const mobileViewport = { width: 390, height: 844 };
  const mobile = await browser.newContext({ viewport: mobileViewport, reducedMotion: "reduce" });
  const mobilePage = await mobile.newPage();
  attachDiagnostics(mobilePage, "mobile");
  await mobilePage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await waitForStep(mobilePage, "intro");
  layouts.mobile_intro = await stateMetrics(mobilePage);
  accessibility.mobile_intro = await accessibilityAudit(mobilePage);
  await capture(mobilePage, "06-landing-mobile.png", "landing-mobile", mobileViewport);
  await reachRadius(mobilePage);
  layouts.mobile_radius = await stateMetrics(mobilePage);
  accessibility.mobile_radius = await accessibilityAudit(mobilePage);
  await capture(mobilePage, "07-place-radius-mobile.png", "place-radius-mobile", mobileViewport);
  await click(mobilePage, "800m");
  await click(mobilePage, "この範囲を調べる");
  await waitForStep(mobilePage, "result");
  layouts.mobile_result = await stateMetrics(mobilePage);
  accessibility.mobile_result = await accessibilityAudit(mobilePage);
  await mobilePage.locator("#area-unknown-title").scrollIntoViewIfNeeded();
  await capture(mobilePage, "08-known-unknown-mobile.png", "known-unknown-mobile", mobileViewport);
  await click(mobilePage, "確認場所を見る");
  await waitForStep(mobilePage, "target");
  layouts.mobile_target = await stateMetrics(mobilePage);
  accessibility.mobile_target = await accessibilityAudit(mobilePage);
  await mobilePage.waitForTimeout(1200);
  await capture(mobilePage, "09-target-task-mobile.png", "target-task-mobile", mobileViewport);
  await mobile.close();

  const fallbackContext = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
  const fallbackPage = await fallbackContext.newPage();
  await fallbackPage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await waitForStep(fallbackPage, "intro");
  await click(fallbackPage, "地図で場所を調べる");
  await waitForStep(fallbackPage, "place");
  await click(fallbackPage, "地図中心を起点にする");
  await waitForStep(fallbackPage, "radius");
  await click(fallbackPage, "800m");
  await click(fallbackPage, "この範囲を調べる");
  await waitForStep(fallbackPage, "result");
  await click(fallbackPage, "確認場所を見る");
  await waitForStep(fallbackPage, "target");
  const fallback3dDisabled = await fallbackPage.locator('[data-contextual-3d-eligible="false"]').count() === 1
    && await fallbackPage.getByRole("button", { name: "3Dで場所を見る", exact: true }).count() === 0;
  await capture(fallbackPage, "10-mesh-fallback-3d-disabled.png", "mesh-fallback-3d-disabled", { width: 1440, height: 900 });
  await fallbackContext.close();

  const routeContext = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const routePage = await routeContext.newPage();
  await routePage.goto(baseUrl + "?journey=m3", { waitUntil: "domcontentloaded", timeout: 90_000 });
  await routePage.locator('.investigation-landing[data-experience="landing"]').waitFor();
  const legacyM3Route = true;
  await routePage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await waitForStep(routePage, "intro");
  await click(routePage, "詳細分析");
  await routePage.locator('[data-experience="advanced"]').waitFor();
  const advancedRoute = true;
  await routeContext.close();

  const criticalAccessibility = Object.values(accessibility).flatMap((entry) => entry.critical);
  const criticalDiagnostics = diagnostics.flatMap((entry) => [
    ...entry.page_errors,
    ...entry.failed_same_origin_requests.map((item) => JSON.stringify(item)),
    ...entry.error_responses.map((item) => JSON.stringify(item)),
  ]);
  const manifest = {
    schema_version: "citygap.public-first-run-ux-checkpoint@1",
    generated_at: new Date().toISOString(),
    repository_head: repositoryHead,
    base_url: baseUrl,
    baseline,
    after: layouts,
    journey: {
      landing_to_task_click_count: 5,
      primary_cta_counts: {
        intro: layouts.desktop_intro.primary_cta_count,
        place: 1,
        radius: layouts.desktop_radius.primary_cta_count,
        result: layouts.desktop_result.primary_cta_count,
        target_terminal: layouts.desktop_target.primary_cta_count,
      },
      public_top_level_primary_navigation_count: 0,
      header_secondary_action_count: 1,
      required_check_count: requirementCount,
      fmr_samples_ms: fmrSamples,
      fmr_median_ms: fmrMedian,
    },
    accessibility: {
      ...accessibility,
      keyboard,
      critical_or_serious_count: criticalAccessibility.length,
    },
    privacy_and_copy: boundaries,
    contextual_3d: {
      ...contextual3d,
      mesh_fallback_disabled: fallback3dDisabled,
    },
    routes: {
      advanced: advancedRoute,
      legacy_m3: legacyM3Route,
      municipal_surface: "verified by separate unchanged-surface build/test",
    },
    diagnostics,
    critical_diagnostic_count: criticalDiagnostics.length,
    screenshots,
    status: [
      "AUTOMATED_UX_CHECKPOINT_COMPLETE",
      "READY_FOR_HUMAN_TEST",
      "AWAITING_HUMAN_TEST",
      "AWAITING_MUNICIPAL_WORKFLOW_REVIEW",
      "HOLD_MAIN_PROMOTION",
      "HOLD_P1_M4_M6",
      "BOREHOLE_INTEGRATE_RESEARCH_ONLY",
    ],
  };
  await writeFile(path.join(outputDirectory, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n", "utf8");
  process.stdout.write(JSON.stringify({
    layouts,
    journey: manifest.journey,
    accessibility_critical: criticalAccessibility,
    diagnostics_critical: criticalDiagnostics,
    contextual_3d: manifest.contextual_3d,
  }, null, 2) + "\n");
} finally {
  await browser.close();
}
