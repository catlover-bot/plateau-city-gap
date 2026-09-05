import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { chromium } from "playwright-core";
import { waitForReal3D } from "./capture-judging-3d.mjs";

// JSON only: no screenshots, recording, readiness overrides, or artifact writes.
// Normal runs measure CSS reflow, NOT browser zoom. --zoom-extension plus a
// fresh --profile uses chrome.tabs.setZoom in an external temporary MV3 helper;
// the browser's own zoom factor, viewport and visualViewport are verified.
const args = new Map();
for (let index = 2; index < process.argv.length; index += 2) args.set(process.argv[index], process.argv[index + 1]);
const base = new URL(args.get("--url") ?? "http://127.0.0.1:4190/plateau-city-gap/");
base.search = "";
const widths = (args.get("--widths") ?? "320,390").split(",").map(Number);
assert.ok(widths.every((width) => Number.isInteger(width) && width >= 320));
const experiences = (args.get("--experiences") ?? "public,guided,advanced").split(",");
assert.ok(experiences.every((value) => ["public", "guided", "advanced"].includes(value)));
const require = createRequire(import.meta.url);
const axeSource = await readFile(require.resolve("axe-core/axe.min.js"), "utf8");
const realZoom = args.has("--zoom-extension");
if (realZoom) assert.ok(args.get("--profile") && !args.has("--cdp"), "Real zoom requires an explicitly fresh temporary profile, not a retained CDP browser");
const report = { url: base.href, protocol: `${realZoom ? "Real chrome.tabs.setZoom automatic/per-tab 200%" : "DPR1 CSS reflow, not browser zoom"}; reduced motion; no images`, records: [], failures: [] };
const launchOptions = {
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath(),
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist",
    ...(args.get("--software") === "true" ? ["--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"] : [])],
};
const persistent = realZoom ? await chromium.launchPersistentContext(args.get("--profile"), {
  ...launchOptions, channel: "chromium", viewport: { width: 1440, height: 900 }, reducedMotion: "reduce",
  args: [...launchOptions.args, `--disable-extensions-except=${args.get("--zoom-extension")}`, `--load-extension=${args.get("--zoom-extension")}`],
}) : null;
const browser = persistent ? persistent.browser() : args.has("--cdp") ? await chromium.connectOverCDP(args.get("--cdp")) : await chromium.launch(launchOptions);
const zoomWorker = persistent ? persistent.serviceWorkers()[0] ?? await persistent.waitForEvent("serviceworker", { timeout: 15_000 }) : null;
report.browser = browser.version();
const check = (condition, label, evidence) => {
  if (!condition) {
    report.failures.push({ label, evidence });
    process.stderr.write(`[product-polish] FAIL ${label}\n`);
  }
};

async function layout(page, label) {
  await page.addScriptTag({ content: axeSource });
  const evidence = await page.evaluate(async () => {
    const rect = (node) => { const r = node.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height, right: r.right, bottom: r.bottom }; };
    const visible = (node) => node.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true }) && node.getBoundingClientRect().width > 0 && node.getBoundingClientRect().height > 0;
    const overlap = (a, b) => Math.max(0, Math.min(a.right, b.right) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.y, b.y));
    const root = document.querySelector(".guided-spatial-app, .advanced-3d-product, .public-area");
    const panels = [[".guided-map-stage", ".guided-story-panel"], [".advanced-3d-stage", ".advanced-reading-panel"], [".advanced-scene-heading", ".advanced-scene-controls"]];
    const panelOverlaps = panels.flatMap(([a, b]) => {
      const left = document.querySelector(a); const right = document.querySelector(b);
      if (!left || !right || !visible(left) || !visible(right)) return [];
      return [{ a, b, pixels: overlap(rect(left), rect(right)) }];
    });
    const section = document.querySelector(".urban-section");
    const texts = [...(section?.querySelectorAll("svg text") ?? [])].filter(visible).map((node) => {
      const matrix = node.getScreenCTM();
      return { text: node.textContent, rect: rect(node), rendered_font_px: parseFloat(getComputedStyle(node).fontSize) * Math.min(Math.hypot(matrix.a, matrix.b), Math.hypot(matrix.c, matrix.d)) };
    });
    const textOverlaps = texts.flatMap((a, index) => texts.slice(index + 1).filter((b) => overlap(a.rect, b.rect) > 1).map((b) => [a.text, b.text]));
    const controls = [...root.querySelectorAll("button, select, summary")].filter(visible).filter((node) => !node.closest(".cesium-widget, .maplibregl-control-container"));
    const smallControls = controls.filter((node) => { const r = rect(node); return r.width < 44 || r.height < 44; }).map((node) => ({ name: node.textContent?.trim(), rect: rect(node) }));
    const activeMotion = root.getAnimations({ subtree: true }).filter((animation) => animation.playState === "running" && Number(animation.effect?.getComputedTiming().duration) > 1).map((animation) => ({ type: animation.constructor.name, duration: animation.effect?.getComputedTiming().duration }));
    const axe = await window.axe.run(root, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] }, resultTypes: ["violations", "incomplete"] });
    return { inner_width: innerWidth, inner_height: innerHeight, dpr: devicePixelRatio,
      overflow_px: Math.max(0, document.documentElement.scrollWidth - innerWidth),
      reduced_motion: matchMedia("(prefers-reduced-motion: reduce)").matches,
      active_motion: activeMotion, small_controls: smallControls, panel_overlaps: panelOverlaps,
      section: section && visible(section) ? { pack: section.dataset.packId, declared_overlap_count: Number(section.dataset.annotationOverlapCount), texts, text_overlaps: textOverlaps } : null,
      axe_serious_critical: axe.violations.filter((item) => ["critical", "serious"].includes(item.impact)).map((item) => ({ id: item.id, nodes: item.nodes.map((node) => node.target) })), axe_incomplete: axe.incomplete.length };
  });
  report.records.push({ label, layout: evidence });
  check(evidence.overflow_px <= 1, `${label}: horizontal reflow`, evidence.overflow_px);
  check(evidence.reduced_motion && evidence.active_motion.length === 0, `${label}: reduced motion`, evidence.active_motion);
  check(evidence.small_controls.length === 0, `${label}: 44px non-map controls`, evidence.small_controls);
  check(evidence.panel_overlaps.every((item) => item.pixels <= 1), `${label}: panel overlap`, evidence.panel_overlaps);
  check(evidence.axe_serious_critical.length === 0, `${label}: automated accessibility`, evidence.axe_serious_critical);
  if (evidence.section) {
    check(evidence.section.declared_overlap_count === 0 && evidence.section.text_overlaps.length === 0, `${label}: Section annotation overlap`, evidence.section);
    check(evidence.section.texts.every((item) => item.rendered_font_px >= 11.95), `${label}: actual rendered Section font minimum 12px`, evidence.section.texts);
  }
}

async function keyboard(page, label) {
  const records = [];
  const first = page.locator(".guided-spatial-header a, .advanced-3d-header a, .public-area header a").first();
  if (await first.count()) await first.focus();
  for (let index = 0; index < 16; index += 1) {
    await page.keyboard.press("Tab");
    const item = await page.evaluate(() => {
      const node = document.activeElement;
      if (!(node instanceof Element) || node === document.body) return null;
      const r = node.getBoundingClientRect(); const style = getComputedStyle(node);
      const x = Math.max(0, Math.min(innerWidth - 1, r.x + r.width / 2));
      const y = Math.max(0, Math.min(innerHeight - 1, r.y + r.height / 2));
      const hit = document.elementFromPoint(x, y);
      const outline = style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0;
      const svgStroke = node instanceof SVGElement && style.stroke !== "none" && parseFloat(style.strokeWidth) >= 2;
      const focusSamples = [[x, y], [r.x + 0.5, y], [r.right - 0.5, y], [x, r.y + 0.5], [x, r.bottom - 0.5]].map(([sx, sy]) => {
        const candidate = sx >= 0 && sy >= 0 && sx < innerWidth && sy < innerHeight ? document.elementFromPoint(sx, sy) : null;
        return candidate === node || node.contains(candidate);
      });
      const id = node.getAttribute("data-section-building-id") ?? node.querySelector("title")?.textContent?.split(" · ")[0];
      const focusOverlay = document.querySelector("[data-section-keyboard-focus]");
      const overlayRects = [...(focusOverlay?.querySelectorAll("rect") ?? [])];
      const exactOverlay = Boolean(svgStroke && id && focusOverlay?.getAttribute("data-section-keyboard-focus") === id
        && focusOverlay.parentElement?.lastElementChild === focusOverlay
        && focusOverlay.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })
        && overlayRects.some((outlineNode) => {
          const box = outlineNode.getBoundingClientRect(); const paint = getComputedStyle(outlineNode);
          return Math.abs(box.x - r.x) < 0.1 && Math.abs(box.y - r.y) < 0.1 && Math.abs(box.width - r.width) < 0.1 && Math.abs(box.height - r.height) < 0.1
            && paint.stroke !== "none" && parseFloat(paint.strokeWidth) >= 2 && paint.pointerEvents === "none";
        }));
      return { name: node.getAttribute("aria-label") || node.textContent?.trim().slice(0, 120), tag: node.tagName,
        visible_focus: node.matches(":focus-visible") && (outline || style.boxShadow !== "none" || svgStroke),
        in_view: r.right > 0 && r.x < innerWidth && r.bottom > 0 && r.y < innerHeight,
        unobscured_center: hit === node || node.contains(hit),
        visible_focus_samples: focusSamples.filter(Boolean).length,
        // Spatial SVG features may legitimately overlap. Check that their
        // focused boundary is visible, not that all geometry centers are free.
        focus_not_obscured: svgStroke ? focusSamples.some(Boolean) || exactOverlay : hit === node || node.contains(hit),
        exact_focused_overlay: exactOverlay, focused_source_id: id ?? null,
        rect: { x: r.x, y: r.y, width: r.width, height: r.height }, href: node.getAttribute("href"),
        hit: hit ? { tag: hit.tagName, class: hit.getAttribute("class"), text: hit.textContent?.trim().slice(0, 100) } : null,
        map_control: Boolean(node.closest(".cesium-widget, .maplibregl-control-container")) };
    });
    if (item) records.push(item);
  }
  report.records.push({ label, keyboard: records });
  check(records.length > 0, `${label}: keyboard reaches controls`, records);
  check(records.every((item) => item.visible_focus && item.in_view && item.focus_not_obscured), `${label}: visible unobscured keyboard focus`, records);
}

async function audit(experience, width) {
  const label = `${experience}-${width}${realZoom ? "-actual200pct" : ""}`;
  const viewport = { width, height: width >= 1000 ? (width === 1280 ? 720 : width === 1920 ? 1080 : 900) : 844 };
  const context = persistent ?? await browser.newContext({ viewport, deviceScaleFactor: 1, locale: "ja-JP", reducedMotion: "reduce", serviceWorkers: "block" });
  const page = await context.newPage();
  if (persistent) await page.setViewportSize(viewport);
  page.setDefaultTimeout(60_000);
  const diagnostics = { page: [], console: [], http: [], requests: [], cancellations: [] };
  let phase = "initial-navigation";
  page.on("pageerror", (error) => diagnostics.page.push({ phase, message: error.message }));
  page.on("console", (message) => { if (message.type() === "error") diagnostics.console.push({ phase, message: message.text() }); });
  page.on("response", (response) => { if (response.status() >= 400) diagnostics.http.push({ phase, url: response.url(), status: response.status() }); });
  page.on("requestfailed", (request) => {
    const record = { phase, url: request.url(), error: request.failure()?.errorText, same_origin: new URL(request.url()).origin === base.origin };
    // Cancellation is retained with its phase. No blanket ERR_ABORTED exemption.
    if (record.error === "net::ERR_ABORTED") diagnostics.cancellations.push(record);
    else diagnostics.requests.push(record);
  });
  try {
    process.stderr.write(`[product-polish] ${label}\n`);
    const query = experience === "public" ? "" : experience === "guided"
      ? "?experience=guided&story=understand&mapMode=plateau3d&selectionType=mesh&selection=533513314"
      : "?experience=advanced&task=detail&scene=plateau_detail&mapMode=plateau3d&selectionType=mesh&selection=533513314";
    await page.goto(new URL(query, base).href, { waitUntil: "domcontentloaded" });
    if (experience === "public") {
      await page.locator('.public-area[data-public-step="intro"]').waitFor();
      await page.waitForFunction(() => document.querySelector(".analytical-map-shell")?.dataset.publicCartographyReady === "true");
    } else {
      await page.locator(experience === "guided" ? '.guided-spatial-app[data-area-id="533513314"][data-context-status="ready"]' : '.advanced-3d-product[data-area-id="533513314"][data-context-status="ready"]').waitFor();
      await waitForReal3D(page, 60_000);
    }
    if (realZoom) {
      phase = "browser-zoom-change";
      const before = await page.evaluate(() => ({ width: innerWidth, height: innerHeight, dpr: devicePixelRatio, visual_scale: visualViewport.scale }));
      const zoom = await zoomWorker.evaluate(async (url) => {
        const tabs = globalThis.chrome.tabs;
        const tab = (await tabs.query({})).find((item) => item.url === url);
        if (!tab) throw new Error("Owned test tab was not found by the temporary zoom extension");
        await tabs.setZoomSettings(tab.id, { mode: "automatic", scope: "per-tab" });
        const before = await tabs.getZoom(tab.id);
        await tabs.setZoom(tab.id, 2);
        return { before, after: await tabs.getZoom(tab.id), settings: await tabs.getZoomSettings(tab.id) };
      }, page.url());
      await page.waitForFunction((original) => devicePixelRatio === original.dpr * 2 && innerWidth === Math.round(original.width / 2), before);
      const after = await page.evaluate(() => ({ width: innerWidth, height: innerHeight, dpr: devicePixelRatio, visual_scale: visualViewport.scale }));
      check(zoom.before === 1 && zoom.after === 2 && zoom.settings.mode === "automatic" && after.visual_scale === 1, `${label}: actual browser zoom`, { before, zoom, after });
      report.records.push({ label, actual_browser_zoom: { before, zoom, after } });
      if (experience !== "public") await waitForReal3D(page, 60_000);
    }
    phase = "ready-closed";
    await layout(page, `${label}-closed`);
    await keyboard(page, `${label}-closed`);
    if (experience !== "public") {
      phase = "user-opens-section";
      await page.getByRole("button", { name: experience === "guided" ? "街の断面" : "A–B断面", exact: true }).click();
      const section = page.locator(`.urban-section[data-ui-mode="${experience}"][data-transect-ready="true"]`);
      await section.waitFor();
      if (experience === "guided" && await page.evaluate(() => matchMedia("(max-width: 900px)").matches)) {
        const hiddenScene = await page.locator(".guided-3d-view").evaluate((node) => ({ inert: node.inert, aria_hidden: node.getAttribute("aria-hidden") }));
        check(hiddenScene.inert && hiddenScene.aria_hidden === "true", `${label}: replaced 3D scene is not keyboard reachable`, hiddenScene);
      }
      const svg = section.locator("svg");
      await svg.focus();
      await page.keyboard.press("ArrowRight");
      await section.locator("[data-section-focus-annotation]").waitFor();
      if (experience === "advanced") {
        const building = section.locator('[data-section-building][role="button"]').first();
        const id = (await building.locator("title").textContent()).split(" · ")[0];
        await building.focus();
        await page.keyboard.press("Enter");
        await page.locator(`.advanced-target-card[data-object-id="${id}"][data-unconfirmed="3"]`).waitFor();
        const checks = await page.locator(".advanced-target-card li").evaluateAll((nodes) => nodes.map((node) => ({ id: node.dataset.checkId, status: node.dataset.status })));
        check(checks.length === 3 && checks.every((item) => item.id && item.status === "unconfirmed"), `${label}: same keyboard-selected exact target checks`, { id, checks });
        await page.waitForFunction((selectedId) => {
          const params = new URL(location.href).searchParams;
          return params.get("parentMesh") === "533513314" && params.get("selection") === selectedId;
        }, id);
        const selectedUrl = new URL(page.url());
        check(selectedUrl.searchParams.get("parentMesh") === "533513314" && selectedUrl.searchParams.get("selection") === id, `${label}: exact object URL parent`, selectedUrl.href);
      }
      phase = "ready-section";
      await layout(page, `${label}-section`);
      await keyboard(page, `${label}-section`);
      if (experience === "guided") {
        phase = "user-returns-to-3d";
        await page.getByRole("button", { name: "PLATEAU 3D", exact: true }).click();
        await waitForReal3D(page, 60_000);
        const restored = await page.locator(".guided-3d-view").evaluate((node) => ({ inert: node.inert, aria_hidden: node.getAttribute("aria-hidden"), visible: node.checkVisibility({ checkVisibilityCSS: true }) }));
        check(!restored.inert && restored.aria_hidden !== "true" && restored.visible, `${label}: returning to 3D restores its accessibility`, restored);
      }
    }
  } catch (error) {
    report.failures.push({ label, phase, error: error instanceof Error ? error.message : String(error) });
    process.stderr.write(`[product-polish] FAIL ${label} at ${phase}: ${error.message}\n`);
  } finally {
    // Closing an owned context intentionally cancels remaining work; keep it
    // distinct from any cancellation during a ready, user-visible state.
    phase = "owned-context-close";
    if (persistent) await page.close();
    else await context.close();
    const unexpectedCancellations = diagnostics.cancellations.filter((item) => item.same_origin && item.phase !== "owned-context-close");
    check(diagnostics.page.length + diagnostics.console.length + diagnostics.http.length + diagnostics.requests.length === 0 && unexpectedCancellations.length === 0, `${label}: diagnostics (cancellations separately classified)`, diagnostics);
    report.records.push({ label, diagnostics });
  }
}

try {
  for (const width of widths) for (const experience of experiences) await audit(experience, width);
} finally { if (persistent) await persistent.close(); else await browser.close(); }
report.passed = report.failures.length === 0;
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
if (!report.passed) process.exitCode = 1;
