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
    const svg = section?.querySelector("svg");
    const svgRect = svg ? rect(svg) : null;
    const allTextNodes = [...(section?.querySelectorAll("svg text") ?? [])];
    const texts = allTextNodes.filter(visible).map((node) => {
      const matrix = node.getScreenCTM();
      const textRect = rect(node);
      return { text: node.textContent, rect: textRect,
        containment_margins_css_px: { left: textRect.x - svgRect.x, right: svgRect.right - textRect.right, top: textRect.y - svgRect.y, bottom: svgRect.bottom - textRect.bottom },
        rendered_font_px: parseFloat(getComputedStyle(node).fontSize) * Math.min(Math.hypot(matrix.a, matrix.b), Math.hypot(matrix.c, matrix.d)) };
    });
    const textOverlaps = texts.flatMap((a, index) => texts.slice(index + 1).filter((b) => overlap(a.rect, b.rect) > 1).map((b) => [a.text, b.text]));
    const clippedTexts = texts.filter((item) => Object.values(item.containment_margins_css_px).some((margin) => margin < 0));
    const callouts = [...(section?.querySelectorAll(".section-focus-callout") ?? [])].filter(visible).map((node) => {
      const box = rect(node.querySelector("rect"));
      const matrix = node.getScreenCTM();
      const rows = [...node.querySelectorAll("text")].map((text) => {
        const row = rect(text);
        return { text: text.textContent, class: text.getAttribute("class"), rect: row,
          containment_margins_css_px: { left: row.x - box.x, right: box.right - row.right, top: row.y - box.y, bottom: box.bottom - row.bottom } };
      });
      const metadata = rows.filter((row) => row.class === "focus-meta");
      return { rect: box, rows, screen_ctm: { a: matrix.a, b: matrix.b, c: matrix.c, d: matrix.d, e: matrix.e, f: matrix.f },
        metadata_row_count: metadata.length, metadata_relation_gap_css_px: metadata.length === 2 ? metadata[1].rect.y - metadata[0].rect.bottom : null };
    });
    let publicHeadingWord = null;
    if (root.matches(".public-area")) {
      const heading = root.querySelector("h1");
      const text = heading?.textContent ?? "";
      const wordStart = text.indexOf("地図");
      const walker = document.createTreeWalker(heading, NodeFilter.SHOW_TEXT);
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      const glyphs = wordStart < 0 ? [] : [0, 1].map((offset) => {
        let remaining = wordStart + offset;
        const node = nodes.find((candidate) => {
          if (remaining < candidate.textContent.length) return true;
          remaining -= candidate.textContent.length;
          return false;
        });
        const range = document.createRange();
        range.setStart(node, remaining);
        range.setEnd(node, remaining + 1);
        const box = range.getBoundingClientRect();
        return { character: text[wordStart + offset], x: box.x, y: box.y, width: box.width, height: box.height, bottom: box.bottom };
      });
      publicHeadingWord = { text, glyphs, same_rendered_line: glyphs.length === 2 && glyphs.every((glyph) => glyph.width > 0 && glyph.height > 0)
        && Math.abs(glyphs[0].y - glyphs[1].y) < 0.5 && Math.abs(glyphs[0].bottom - glyphs[1].bottom) < 0.5 };
    }
    const controls = [...root.querySelectorAll("button, select, summary")].filter(visible).filter((node) => !node.closest(".cesium-widget, .maplibregl-control-container"));
    const smallControls = controls.filter((node) => { const r = rect(node); return r.width < 44 || r.height < 44; }).map((node) => ({ name: node.textContent?.trim(), rect: rect(node) }));
    const activeMotion = root.getAnimations({ subtree: true }).filter((animation) => animation.playState === "running" && Number(animation.effect?.getComputedTiming().duration) > 1).map((animation) => ({ type: animation.constructor.name, duration: animation.effect?.getComputedTiming().duration }));
    const axe = await window.axe.run(root, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] }, resultTypes: ["violations", "incomplete"] });
    return { inner_width: innerWidth, inner_height: innerHeight, dpr: devicePixelRatio,
      overflow_px: Math.max(0, document.documentElement.scrollWidth - innerWidth),
      reduced_motion: matchMedia("(prefers-reduced-motion: reduce)").matches,
      public_heading_word: publicHeadingWord,
      active_motion: activeMotion, small_controls: smallControls, panel_overlaps: panelOverlaps,
      section: section && visible(section) ? { pack: section.dataset.packId, declared_overlap_count: Number(section.dataset.annotationOverlapCount), svg_rect: svgRect, texts, text_overlaps: textOverlaps, clipped_texts: clippedTexts, callouts,
        hidden_texts: allTextNodes.filter((node) => !visible(node)).map((node) => node.textContent),
        required_labels: { endpoint_a: [...section.querySelectorAll('[data-section-endpoint="A"]')].some(visible), endpoint_b: [...section.querySelectorAll('[data-section-endpoint="B"]')].some(visible),
          elevation_axis: [...section.querySelectorAll("svg text.axis-title")].some((node) => visible(node) && node.textContent.includes("標高")), distance_axis: [...section.querySelectorAll("svg text.axis-title")].some((node) => visible(node) && node.textContent.includes("距離")) } } : null,
      axe_serious_critical: axe.violations.filter((item) => ["critical", "serious"].includes(item.impact)).map((item) => ({ id: item.id, nodes: item.nodes.map((node) => node.target) })), axe_incomplete: axe.incomplete.length };
  });
  report.records.push({ label, layout: evidence });
  check(evidence.overflow_px <= 1, `${label}: horizontal reflow`, evidence.overflow_px);
  check(evidence.reduced_motion && evidence.active_motion.length === 0, `${label}: reduced motion`, evidence.active_motion);
  check(evidence.small_controls.length === 0, `${label}: 44px non-map controls`, evidence.small_controls);
  check(evidence.panel_overlaps.every((item) => item.pixels <= 1), `${label}: panel overlap`, evidence.panel_overlaps);
  check(evidence.axe_serious_critical.length === 0, `${label}: automated accessibility`, evidence.axe_serious_critical);
  if (evidence.public_heading_word) check(evidence.public_heading_word.same_rendered_line, `${label}: Public 地図 remains on one rendered line`, evidence.public_heading_word);
  if (evidence.section) {
    check(evidence.section.declared_overlap_count === 0 && evidence.section.text_overlaps.length === 0, `${label}: Section annotation overlap`, evidence.section);
    check(evidence.section.texts.every((item) => item.rendered_font_px >= 11.95), `${label}: actual rendered Section font minimum 12px`, evidence.section.texts);
    check(evidence.section.clipped_texts.length === 0, `${label}: all Section text bounds are contained by its SVG`, evidence.section.clipped_texts);
    check(evidence.section.hidden_texts.length === 0, `${label}: Section text is not hidden to satisfy containment`, evidence.section.hidden_texts);
    check(Object.values(evidence.section.required_labels).every(Boolean), `${label}: visible Section A/B and both axis labels retained`, evidence.section.required_labels);
    check(evidence.section.callouts.length > 0 && evidence.section.callouts.every((callout) => callout.metadata_row_count === 2 && callout.metadata_relation_gap_css_px > 0),
      `${label}: Section metadata and relation have positive rendered separation`, evidence.section.callouts);
    check(evidence.section.callouts.every((callout) => callout.rows.length === 3 && callout.rows.every((row) => Object.values(row.containment_margins_css_px).every((margin) => margin >= 0))),
      `${label}: all callout text is contained by its own background`, evidence.section.callouts);
  }
}

async function programmaticHeadingFocus(page, label, experience) {
  if (experience !== "public" && experience !== "guided") return;
  const evidence = await page.locator(experience === "public" ? ".public-area-panel h1" : ".guided-story-panel h1").evaluate((heading) => {
    const style = getComputedStyle(heading);
    return { text: heading.textContent, active: document.activeElement === heading, tab_index: heading.tabIndex,
      outline_style: style.outlineStyle, outline_width_px: parseFloat(style.outlineWidth), box_shadow: style.boxShadow };
  });
  report.records.push({ label, programmatic_heading_focus: evidence });
  check(evidence.active && evidence.tab_index === -1, `${label}: programmatic H1 focus is preserved`, evidence);
  check((evidence.outline_style === "none" || evidence.outline_width_px === 0) && evidence.box_shadow === "none", `${label}: programmatic H1 has no outline or box shadow`, evidence);
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

async function desktopSectionLayoutReady(page, label, deadline) {
  const remaining = () => {
    const milliseconds = Math.ceil(deadline - performance.now());
    if (milliseconds <= 0) throw new Error(`${label}: shared 60s Section readiness budget exhausted`);
    return milliseconds;
  };
  const evidence = () => page.evaluate(() => {
    const stage = document.querySelector(".guided-map-stage");
    const view = stage?.querySelector(".guided-3d-view");
    const dock = stage?.querySelector(".guided-section-dock");
    const canvas = view?.querySelector(".cesium-widget canvas");
    const rect = (node) => {
      const box = node?.getBoundingClientRect();
      return box ? { x: box.x, y: box.y, width: box.width, height: box.height, bottom: box.bottom } : null;
    };
    const viewBox = view?.getBoundingClientRect();
    const dockBox = dock?.getBoundingClientRect();
    const canvasBox = canvas?.getBoundingClientRect();
    return { stage_expanded: stage?.dataset.sectionExpanded, map_mode: stage?.dataset.guidedMapMode,
      view: rect(view), dock: rect(dock), canvas: rect(canvas),
      view_inert: view?.inert, view_aria_hidden: view?.getAttribute("aria-hidden"),
      predicates: {
        expanded: stage?.dataset.sectionExpanded === "true", map3d: stage?.dataset.guidedMapMode === "plateau3d",
        view_visible: Boolean(view?.checkVisibility({ checkVisibilityCSS: true })),
        dock_visible: Boolean(dock?.checkVisibility({ checkVisibilityCSS: true })),
        accessible_scene: Boolean(view && !view.inert && view.getAttribute("aria-hidden") !== "true"),
        positive_view: Boolean(viewBox && viewBox.width > 0 && viewBox.height > 0),
        positive_dock: Boolean(dockBox && dockBox.width > 0 && dockBox.height > 0),
        separate_regions: Boolean(viewBox && dockBox && viewBox.bottom <= dockBox.y),
        canvas_contained: Boolean(viewBox && canvasBox && canvasBox.width > 0 && canvasBox.height > 0
          && canvasBox.x >= viewBox.x && canvasBox.right <= viewBox.right && canvasBox.y >= viewBox.y && canvasBox.bottom <= viewBox.bottom),
      },
      data_readiness: { ...view?.querySelector("[data-building-source][data-local-dem]")?.dataset },
      credit_rects: [...(view?.querySelectorAll('a[href="https://cesium.com/"]') ?? [])].map(rect) };
  });
  const immediate = await evidence();
  const started = performance.now();
  const readiness = { immediate, settled: null, ready_wait_ms: null, shared_budget_remaining_ms: remaining() };
  report.records.push({ label, desktop_section_layout: readiness });
  // Do not interact with Section while the previous full-height scene is still
  // being presented. Renderer, current split geometry, and post-focus renderer
  // checks share ONE finite stage budget, including font/frame waits.
  let deadlineTimer;
  try {
    await Promise.race([
      (async () => {
        await waitForReal3D(page, remaining());
        await page.waitForFunction(() => {
          const stage = document.querySelector(".guided-map-stage");
          const view = stage?.querySelector(".guided-3d-view");
          const dock = stage?.querySelector(".guided-section-dock");
          const canvas = view?.querySelector(".cesium-widget canvas");
          const viewBox = view?.getBoundingClientRect();
          const dockBox = dock?.getBoundingClientRect();
          const canvasBox = canvas?.getBoundingClientRect();
          return stage?.dataset.sectionExpanded === "true" && stage.dataset.guidedMapMode === "plateau3d"
            && view?.checkVisibility({ checkVisibilityCSS: true }) && dock?.checkVisibility({ checkVisibilityCSS: true })
            && !view.inert && view.getAttribute("aria-hidden") !== "true"
            && viewBox.width > 0 && viewBox.height > 0 && dockBox.width > 0 && dockBox.height > 0
            && viewBox.bottom <= dockBox.y && canvasBox?.width > 0 && canvasBox.height > 0
            && canvasBox.x >= viewBox.x && canvasBox.right <= viewBox.right
            && canvasBox.y >= viewBox.y && canvasBox.bottom <= viewBox.bottom;
        }, null, { timeout: remaining() });
        await waitForReal3D(page, remaining());
        await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      })(),
      new Promise((_, reject) => { deadlineTimer = setTimeout(() => reject(new Error(`${label}: shared 60s Section readiness budget exhausted`)), remaining()); }),
    ]);
  } finally { clearTimeout(deadlineTimer); }
  const settled = await evidence();
  readiness.settled = settled;
  readiness.ready_wait_ms = Math.round(performance.now() - started);
  readiness.shared_budget_remaining_ms = remaining();
  check(Object.values(settled.predicates).every(Boolean),
  `${label}: desktop Section and ready 3D occupy separate visible regions`, settled);
}

async function sectionPaintReady(page, label, deadline) {
  const remaining = () => {
    const milliseconds = Math.ceil(deadline - performance.now());
    if (milliseconds <= 0) throw new Error(`${label}: shared 60s Section readiness budget exhausted`);
    return milliseconds;
  };
  const evidence = () => page.evaluate(() => {
    const section = document.querySelector(".urban-section");
    const background = section?.querySelector(".section-focus-callout > rect");
    const box = background?.getBoundingClientRect();
    return { focused_object_id: section?.getAttribute("data-focused-object-id"),
      selected_annotation_id: section?.getAttribute("data-selection-annotation-id"),
      fonts: document.fonts.status, rect_dom_x: background?.getAttribute("x"),
      rect_computed_x: background ? getComputedStyle(background).x : null,
      rect: box ? { x: box.x, y: box.y, width: box.width, height: box.height } : null,
      active_animations: section?.getAnimations({ subtree: true }).filter((animation) => animation.pending || animation.playState === "running").length ?? 0 };
  });
  const started = performance.now();
  const readiness = { immediate: await evidence(), settled: null, ready_wait_ms: null, shared_budget_remaining_ms: remaining() };
  report.records.push({ label, section_paint: readiness });
  let deadlineTimer;
  try {
    await Promise.race([
      (async () => {
        // Even the existing reduced-motion 0.01ms transition needs a presented
        // frame. Wait for paint/animations, NOT for containment to become true.
        await page.evaluate(async () => {
          await document.fonts.ready;
          await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        });
        await page.waitForFunction(() => {
          const section = document.querySelector(".urban-section");
          return document.fonts.status === "loaded" && section?.checkVisibility({ checkVisibilityCSS: true })
            && section.getAnimations({ subtree: true }).every((animation) => !animation.pending && animation.playState !== "running");
        }, null, { timeout: remaining() });
        await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      })(),
      new Promise((_, reject) => { deadlineTimer = setTimeout(() => reject(new Error(`${label}: shared 60s Section readiness budget exhausted`)), remaining()); }),
    ]);
  } finally { clearTimeout(deadlineTimer); }
  readiness.settled = await evidence();
  readiness.ready_wait_ms = Math.round(performance.now() - started);
  readiness.shared_budget_remaining_ms = remaining();
  check(readiness.immediate.focused_object_id === readiness.settled.focused_object_id
    && readiness.immediate.selected_annotation_id === readiness.settled.selected_annotation_id,
  `${label}: Section paint settles without changing focused or selected identity`, readiness);
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
    await programmaticHeadingFocus(page, label, experience);
    await layout(page, `${label}-closed`);
    await keyboard(page, `${label}-closed`);
    if (experience !== "public") {
      phase = "user-opens-section";
      const sectionReadyDeadline = performance.now() + 60_000;
      await page.getByRole("button", { name: experience === "guided" ? "街の断面" : "A–B断面", exact: true }).click();
      const section = page.locator(`.urban-section[data-ui-mode="${experience}"][data-transect-ready="true"]`);
      await section.waitFor();
      if (experience === "guided" && await page.evaluate(() => matchMedia("(max-width: 900px)").matches)) {
        const hiddenScene = await page.locator(".guided-3d-view").evaluate((node) => ({ inert: node.inert, aria_hidden: node.getAttribute("aria-hidden") }));
        check(hiddenScene.inert && hiddenScene.aria_hidden === "true", `${label}: replaced 3D scene is not keyboard reachable`, hiddenScene);
      }
      const desktopGuidedSection = experience === "guided" && await page.evaluate(() => !matchMedia("(max-width: 900px)").matches);
      if (desktopGuidedSection) {
        await desktopSectionLayoutReady(page, `${label}-section-before-keyboard`, sectionReadyDeadline);
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
      if (desktopGuidedSection) {
        await desktopSectionLayoutReady(page, `${label}-section`, sectionReadyDeadline);
      }
      await sectionPaintReady(page, `${label}-section`, sectionReadyDeadline);
      await layout(page, `${label}-section`);
      await keyboard(page, `${label}-section`);
      if (experience === "guided") {
        phase = "user-returns-to-3d";
        await page.getByRole("button", { name: "PLATEAU 3D", exact: true }).click();
        await waitForReal3D(page, 60_000);
        const returnEvidence = () => page.locator(".guided-3d-view").evaluate((node) => ({
          inert: node.inert, aria_hidden: node.getAttribute("aria-hidden"), visible: node.checkVisibility({ checkVisibilityCSS: true }),
          stage_expanded: node.closest(".guided-map-stage")?.getAttribute("data-section-expanded"),
          mobile_viewport: matchMedia("(max-width: 900px)").matches,
          computed_visibility: getComputedStyle(node).visibility, computed_display: getComputedStyle(node).display,
          client_rects: [...node.getClientRects()].map((rect) => ({ x: rect.x, y: rect.y, width: rect.width, height: rect.height })),
        }));
        const immediate = await returnEvidence();
        const visibleStarted = performance.now();
        // Engine readiness can still describe the mounted previous frame.
        // Also require the actual post-interaction UI visibility contract.
        await page.waitForFunction(() => {
          const node = document.querySelector(".guided-3d-view");
          return node && !node.inert && node.getAttribute("aria-hidden") !== "true"
            && node.closest(".guided-map-stage")?.getAttribute("data-section-expanded") === "false"
            && getComputedStyle(node).visibility === "visible" && node.checkVisibility({ checkVisibilityCSS: true });
        }, null, { timeout: 5_000 });
        const restored = await returnEvidence();
        report.records.push({ label, return_to_3d: { immediate, settled: restored, visible_wait_ms: Math.round(performance.now() - visibleStarted) } });
        check(!restored.inert && restored.aria_hidden !== "true" && restored.visible && restored.stage_expanded === "false", `${label}: returning to 3D restores its accessibility`, restored);
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
