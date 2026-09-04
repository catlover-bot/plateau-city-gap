import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { chromium } from "playwright-core";

const args = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const key = process.argv[index];
  if (!key.startsWith("--")) continue;
  const next = process.argv[index + 1];
  args.set(key, next && !next.startsWith("--") ? next : "true");
  if (next && !next.startsWith("--")) index += 1;
}

const baseUrl = args.get("--url") ?? "http://127.0.0.1:4173/plateau-city-gap/?experience=guided&story=intro";
const capture = args.get("--capture") === "true";
const artifacts = resolve(process.cwd(), "../docs/assets/guided-spatial-checkpoint");
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const launchOptions = {
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
};
const browser = await chromium.launch(launchOptions);

const phase = (message) => process.stderr.write(`[guided] ${message}\n`);

const errors = [];
const screenshots = [];
const snapshots = [];
const accessibility = [];
const routeRegressions = [];
const sectionAudits = [];

function attachDiagnostics(page, label) {
  page.on("pageerror", (error) => errors.push(`${label}: pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("cyberjapandata.gsi.go.jp")) {
      errors.push(`${label}: console: ${message.text()}`);
    }
  });
}

async function waitShell(page, story, areaId) {
  const status = story === "intro" || story === "find" ? "idle" : "ready";
  await page.locator(`.guided-spatial-app[data-guided-story="${story}"][data-area-id="${areaId}"][data-context-status="${status}"]`).waitFor({ timeout: 180_000 });
  await page.waitForFunction(() => document.querySelector(".analytical-map-shell")?.getAttribute("data-guided-visual-ready") === "true", null, { timeout: 120_000 });
}

async function ready(page, areaId) {
  await page.locator(`.guided-spatial-app[data-area-id="${areaId}"][data-context-status="ready"]`).waitFor({ timeout: 180_000 });
  await page.waitForFunction(() => document.querySelector(".analytical-map-shell")?.getAttribute("data-guided-visual-ready") === "true", null, { timeout: 120_000 });
}

async function auditAccessibility(page, label) {
  const result = await page.evaluate(() => {
    const visible = (element) => {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
    };
    const named = (element) => {
      if (element.getAttribute("aria-label")?.trim()) return true;
      const labelled = element.getAttribute("aria-labelledby");
      if (labelled && labelled.split(/\s+/).some((id) => document.getElementById(id)?.textContent?.trim())) return true;
      if (element.closest("label")?.textContent?.trim()) return true;
      return Boolean(element.textContent?.trim());
    };
    const controls = [...document.querySelectorAll("button, select, input, a[href], summary")].filter(visible);
    const panelControls = controls.filter((control) => control.closest(".guided-story-panel, .guided-mobile-surface-switch"));
    const primaryControls = [...document.querySelectorAll(".guided-primary")].filter(visible);
    const ids = [...document.querySelectorAll("[id]")].map((node) => node.id);
    const workspace = document.querySelector(".guided-spatial-workspace")?.getBoundingClientRect();
    const map = document.querySelector(".guided-map-stage")?.getBoundingClientRect();
    const panel = document.querySelector(".guided-story-panel")?.getBoundingClientRect();
    const borderedSurfaces = [...document.querySelectorAll(".guided-current-area, .guided-known-summary, .guided-section-note, .guided-unknown-bridge, .guided-target-summary, .guided-check-list, .guided-boundary")].filter(visible).length;
    return {
      h1: [...document.querySelectorAll("h1")].filter(visible).length,
      unnamed: controls.filter((control) => !named(control)).length,
      duplicateIds: [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))],
      horizontalOverflow: Math.max(0, document.documentElement.scrollWidth - innerWidth),
      verticalOverflow: Math.max(0, document.documentElement.scrollHeight - innerHeight),
      visibleControls: controls.length,
      smallPanelControls: panelControls.filter((control) => {
        const rect = control.getBoundingClientRect();
        return rect.width < 44 || rect.height < 44;
      }).length,
      primaryCtaCount: primaryControls.length,
      primaryCtaInViewport: primaryControls.every((control) => {
        const rect = control.getBoundingClientRect();
        return rect.top >= 0 && rect.bottom <= innerHeight && rect.left >= 0 && rect.right <= innerWidth;
      }),
      mapShare: workspace && map ? Number((map.width / workspace.width * 100).toFixed(1)) : null,
      panelShare: workspace && panel ? Number((panel.width / workspace.width * 100).toFixed(1)) : null,
      borderedSurfaces,
    };
  });
  accessibility.push({ label, ...result });
  const mobilePrimaryFailure = label.startsWith("mobile-")
    && !label.includes("verify")
    && (result.primaryCtaCount !== 1 || !result.primaryCtaInViewport);
  if (result.h1 !== 1 || result.unnamed || result.duplicateIds.length || result.horizontalOverflow || result.smallPanelControls || (!label.startsWith("mobile") && result.verticalOverflow) || mobilePrimaryFailure) {
    throw new Error(`accessibility/layout failure ${label}: ${JSON.stringify(result)}`);
  }
}

async function mapSnapshot(page, label) {
  const result = await page.evaluate((snapshotLabel) => {
    const root = document.querySelector(".guided-spatial-app");
    const canvas = document.querySelector(".analytical-map-canvas");
    const map = canvas?.__cityGapMap;
    const data = (id) => map?.getSource(id)?.serialize?.().data ?? null;
    const firstId = (id) => data(id)?.features?.[0]?.id ?? data(id)?.features?.[0]?.properties?.object_id ?? null;
    const center = map?.getCenter();
    return {
      label: snapshotLabel,
      story: root?.getAttribute("data-guided-story"),
      areaId: root?.getAttribute("data-area-id"),
      areaLabel: root?.getAttribute("data-area-label"),
      targetKind: root?.getAttribute("data-target-kind"),
      targetKey: root?.getAttribute("data-target-key"),
      buildings: Number(root?.getAttribute("data-context-buildings")),
      roads: Number(root?.getAttribute("data-context-roads")),
      planning: Number(root?.getAttribute("data-context-planning")),
      sectionPack: root?.getAttribute("data-section-pack"),
      targetResolution: root?.getAttribute("data-target-resolution"),
      mapInitCount: window.__cityGapMapInitCount,
      camera: center ? [Number(center.lng.toFixed(6)), Number(center.lat.toFixed(6)), Number(map.getZoom().toFixed(2))] : null,
      areaGeometry: JSON.stringify(data("guided-area")?.features?.[0]?.geometry ?? null),
      firstBuildingId: firstId("guided-buildings"),
      firstRoadId: firstId("guided-roads"),
      firstPlanningId: firstId("guided-planning"),
      targetGeometry: JSON.stringify(data("guided-target")?.features?.[0]?.geometry ?? null),
      targetSourceId: firstId("guided-target"),
      buildingVisible: map?.getLayoutProperty("guided-buildings-fill", "visibility") !== "none",
      targetVisible: map?.getLayoutProperty("guided-target-line", "visibility") !== "none",
      targetPointVisible: map?.getLayoutProperty("guided-target-point", "visibility") !== "none",
      sectionVisible: map?.getLayoutProperty("guided-section-line", "visibility") !== "none",
      shortlistVisible: map?.getLayoutProperty("mesh-top-outline", "visibility") !== "none",
      selectedVisible: map?.getLayoutProperty("mesh-selected", "visibility") !== "none",
    };
  }, label);
  snapshots.push(result);
  return result;
}

async function auditGuidedSection(page, label, { maxAnnotations, minHeight }) {
  const result = await page.evaluate((auditLabel) => {
    const section = document.querySelector(".urban-section.guided");
    const labels = [...document.querySelectorAll('[data-section-annotation-kind="road"]')];
    const distanceTicks = document.querySelectorAll('[data-section-axis-tick="distance"]').length;
    const elevationTicks = document.querySelectorAll('[data-section-axis-tick="elevation"]').length;
    const summary = document.querySelector("#section-accessible-summary")?.textContent?.replace(/\s+/g, " ").trim() ?? "";
    return {
      label: auditLabel,
      height: document.querySelector(".guided-section-dock svg")?.getBoundingClientRect().height ?? 0,
      annotations: Number(section?.getAttribute("data-static-annotation-count")),
      roadAnnotations: Number(section?.getAttribute("data-road-annotation-count")),
      hidden: Number(section?.getAttribute("data-hidden-low-priority-annotations")),
      calculationMs: Number(section?.getAttribute("data-annotation-calculation-ms")),
      internalOverlaps: Number(section?.getAttribute("data-annotation-overlap-count")),
      uniqueRoadLabels: new Set(labels.map((node) => node.textContent?.trim())).size,
      distanceTicks,
      elevationTicks,
      tabStops: section?.querySelectorAll('[tabindex="0"]').length ?? 0,
      legendItems: section?.querySelectorAll(".section-visual-legend > span").length ?? 0,
      summary,
    };
  }, label);
  sectionAudits.push(result);
  if (
    result.height < minHeight
    || result.annotations > maxAnnotations
    || result.roadAnnotations > maxAnnotations - 2
    || result.roadAnnotations !== result.uniqueRoadLabels
    || result.internalOverlaps !== 0
    || result.calculationMs > 50
    || result.distanceTicks < 3
    || result.distanceTicks > 6
    || result.elevationTicks < 3
    || result.elevationTicks > 5
    || result.tabStops !== 1
    || result.legendItems !== 3
    || !/AからBまで約\d+m/.test(result.summary)
    || !/標高は\d+\.\d+mから\d+\.\d+m/.test(result.summary)
    || !/直接交差する建物は17棟、道路は14本/.test(result.summary)
  ) throw new Error(`guided Section audit failure: ${JSON.stringify(result)}`);
  return result;
}

async function shot(page, filename) {
  if (!capture) return;
  mkdirSync(artifacts, { recursive: true });
  const path = resolve(artifacts, filename);
  await page.screenshot({ path, fullPage: true });
  const metadata = await page.evaluate(() => {
    const root = document.querySelector(".guided-spatial-app");
    return {
      devicePixelRatio,
      selectedArea: root?.getAttribute("data-area-id"),
      selectedTarget: root?.getAttribute("data-target-key"),
      sourceArtifactHashes: {
        areaGeometry: root?.getAttribute("data-area-geometry-hash"),
        context: root?.getAttribute("data-context-hash"),
        citygml: root?.getAttribute("data-source-hash"),
        section: root?.getAttribute("data-section-hash"),
      },
    };
  });
  screenshots.push({
    file: filename,
    sha256: createHash("sha256").update(readFileSync(path)).digest("hex"),
    bytes: readFileSync(path).byteLength,
    url: page.url(),
    viewport: page.viewportSize(),
    ...metadata,
  });
}

async function setArea(page, meshCode) {
  await page.getByLabel("495の範囲から選ぶ").selectOption(meshCode);
  await waitShell(page, "find", meshCode);
}

async function enterUnderstand(page, meshCode) {
  const before = await mapSnapshot(page, `${meshCode}:find`);
  await page.getByRole("button", { name: "街の形を見る", exact: true }).click();
  await page.locator('.guided-spatial-app[data-guided-story="understand"]', { hasText: meshCode === "533513314" ? "常団地前" : "" }).waitFor();
  await ready(page, meshCode);
  const after = await mapSnapshot(page, `${meshCode}:understand`);
  if (after.mapInitCount !== before.mapInitCount || !after.buildingVisible) {
    throw new Error(`persistent map or understand layer failure: ${JSON.stringify({ before, after })}`);
  }
  return after;
}

async function enterVerify(page, meshCode) {
  const before = await mapSnapshot(page, `${meshCode}:understand-before-verify`);
  await page.getByRole("button", { name: "確認場所を見る", exact: true }).click();
  await page.locator('.guided-spatial-app[data-guided-story="verify"]').waitFor();
  await ready(page, meshCode);
  const after = await mapSnapshot(page, `${meshCode}:verify`);
  const checks = await page.locator(".guided-check-list > li").count();
  const captureTerms = await page.locator(".guided-check-list").innerText();
  if (after.mapInitCount !== before.mapInitCount || !after.targetVisible || checks < 3 || checks > 5 || /写真|GPS|撮影/.test(captureTerms)) {
    throw new Error(`verify contract failure: ${JSON.stringify({ before, after, checks, captureTerms })}`);
  }
  return after;
}

try {
  phase("desktop journey");
  const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, reducedMotion: "reduce" });
  const page = await desktop.newPage();
  page.setDefaultTimeout(120_000);
  attachDiagnostics(page, "desktop");
  const contextRequests = [];
  const initialDataRequests = [];
  page.on("request", (request) => {
    if (/\/guided\/area-context\/[^/]+\.json(?:\?|$)/.test(request.url())) contextRequests.push(request.url());
    if (/\/data\/[^?]+/.test(request.url())) initialDataRequests.push(request.url());
  });
  const started = Date.now();
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 120_000 });
  await waitShell(page, "intro", "533513314");
  const firstReadyMs = Date.now() - started;
  const initialMapCount = await page.evaluate(() => window.__cityGapMapInitCount);
  await auditAccessibility(page, "desktop-intro");
  await shot(page, "desktop-intro.png");
  if (contextRequests.length) throw new Error(`intro loaded Area context eagerly: ${JSON.stringify(contextRequests)}`);
  const forbiddenInitialBundles = ["intervention_scenarios.json", "robustness.json", "plateau_buildings.geojson", "plateau_roads.geojson"];
  if (initialDataRequests.some((url) => forbiddenInitialBundles.some((filename) => url.includes(filename)))) {
    throw new Error(`intro loaded non-Guided bundles: ${JSON.stringify(initialDataRequests)}`);
  }
  const initialDataRequestSnapshot = initialDataRequests.filter((url, index) => initialDataRequests.indexOf(url) === index);
  const introSnapshot = await mapSnapshot(page, "intro");
  await page.getByRole("button", { name: "デモを始める", exact: true }).click();
  await waitShell(page, "find", "533513314");
  const findSnapshot = await mapSnapshot(page, "find-start");
  if (findSnapshot.mapInitCount !== introSnapshot.mapInitCount || contextRequests.length || introSnapshot.shortlistVisible || !findSnapshot.shortlistVisible) {
    throw new Error(`intro transition remounted map or fetched context: ${JSON.stringify({ introSnapshot, findSnapshot, contextRequests })}`);
  }
  const initialContextRequestCount = contextRequests.length;
  await auditAccessibility(page, "desktop-find");
  await shot(page, "desktop-find-tsune.png");

  const nioButton = page.getByRole("button", { name: /二尾バス停周辺/ }).first();
  await nioButton.hover();
  await page.locator('.guided-spatial-app[data-hovered-area-id="533512753"]').waitFor();
  const nioPoint = await page.evaluate(() => {
    const canvas = document.querySelector(".analytical-map-canvas");
    const map = canvas?.__cityGapMap;
    const bounds = canvas?.getBoundingClientRect();
    const feature = map?.getSource("meshes")?.serialize?.().data?.features?.find((candidate) => String(candidate.properties?.mesh_code) === "533512753");
    if (!map || !bounds || !feature) return null;
    const projected = map.project([Number(feature.properties.centroid_lon), Number(feature.properties.centroid_lat)]);
    return { x: bounds.left + projected.x, y: bounds.top + projected.y };
  });
  if (!nioPoint) throw new Error("Nio candidate could not be projected on the map");
  await page.mouse.click(nioPoint.x, nioPoint.y);
  await waitShell(page, "find", "533512753");
  await page.locator('.guided-area-list button[aria-pressed="true"]', { hasText: "二尾バス停周辺" }).waitFor();
  const clickedMapState = await mapSnapshot(page, "map-click-nio");
  if (clickedMapState.camera?.[0] !== 135.315625 || clickedMapState.camera?.[1] !== 35.48125) {
    throw new Error(`map click did not synchronize selection and camera: ${JSON.stringify(clickedMapState)}`);
  }
  await page.getByRole("button", { name: /常団地前周辺/ }).first().click();
  await waitShell(page, "find", "533513314");

  const forbiddenCoreCopy = await page.locator(".guided-spatial-app").innerText();
  if (/GUIDED STORY|AWAITING_|validation_status|写真|GPS|撮影/.test(forbiddenCoreCopy) || await page.locator(".guided-intro-sequence, .guided-progress").count()) {
    throw new Error("Guided core exposes tutorial or field-capture terminology");
  }

  const sequence = ["533513314", "533512753", "533522274", "533502752", "533512264", "533512362"];
  for (const [index, meshCode] of sequence.entries()) {
    phase(`desktop ${meshCode}`);
    if (index > 0) await setArea(page, meshCode);
    const understand = await enterUnderstand(page, meshCode);
    await auditAccessibility(page, `desktop-understand-${meshCode}`);
    await shot(page, `desktop-understand-${meshCode}.png`);
    if (meshCode === "533513314") {
      await page.locator('.guided-spatial-app[data-section-pack="maizuru-533513314-plateau-2025-v1"]').waitFor({ timeout: 120_000 });
      await page.locator('.urban-section[data-terrain-samples="94"][data-direct-building-count="17"][data-direct-road-count="14"]').waitFor();
      const sectionContract = await page.evaluate(() => {
        const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
        const geometry = map?.getSource("guided-section")?.serialize?.().data?.features?.[0]?.geometry;
        const plotHeight = document.querySelector(".guided-section-dock svg")?.getBoundingClientRect().height;
        return { geometry, plotHeight };
      });
      if (JSON.stringify(sectionContract.geometry?.coordinates) !== JSON.stringify([[135.398125, 35.44583333333334], [135.398125, 35.45]]) || sectionContract.plotHeight < 320 || sectionContract.plotHeight > 380) {
        throw new Error(`section contract failure: ${JSON.stringify(sectionContract)}`);
      }
      const sectionSnapshot = await mapSnapshot(page, `${meshCode}:section-ready`);
      if (!sectionSnapshot.sectionVisible) throw new Error("verified section line is not visible on its owning Area");
      await auditGuidedSection(page, "desktop", { maxAnnotations: 6, minHeight: 360 });
    } else if (understand.sectionPack !== "none" || await page.locator(".guided-section-dock").count()) {
      throw new Error(`stale section leaked into ${meshCode}`);
    }
    const verify = await enterVerify(page, meshCode);
    if ((meshCode === "533513314") !== (verify.targetResolution === "exact")) {
      throw new Error(`target resolution mismatch for ${meshCode}`);
    }
    await shot(page, `desktop-verify-${meshCode}.png`);
    if (meshCode === "533513314") {
      const roadGeometry = verify.targetGeometry;
      const buildingOption = page.locator('.guided-target-select option[value^="building:"]').first();
      if (await buildingOption.count()) {
        const buildingValue = await buildingOption.getAttribute("value");
        if (!buildingValue) throw new Error("building target option has no value");
        await page.locator(".guided-target-select select").selectOption(buildingValue);
        await page.waitForFunction(() => document.querySelector(".guided-spatial-app")?.getAttribute("data-target-kind") === "building");
        const buildingTarget = await mapSnapshot(page, `${meshCode}:building-target`);
        if (buildingTarget.targetGeometry === roadGeometry || buildingTarget.targetKind !== "building") {
          throw new Error(`building target did not replace road target: ${JSON.stringify(buildingTarget)}`);
        }
        await shot(page, "desktop-verify-building.png");
      }
    }
    if (index < sequence.length - 1) {
      await page.getByRole("button", { name: "街の形へ戻る", exact: true }).click();
      await page.getByRole("button", { name: "範囲選択へ戻る", exact: true }).click();
      await page.locator('.guided-spatial-app[data-guided-story="find"]').waitFor();
    }
  }

  const mapCounts = new Set(snapshots.map((item) => item.mapInitCount));
  const areaGeometries = new Set(snapshots.filter((item) => item.story === "understand").map((item) => item.areaGeometry));
  const labels = new Set(snapshots.filter((item) => item.story === "understand").map((item) => item.areaLabel));
  const contextSignatures = new Set(snapshots.filter((item) => item.story === "understand").map((item) => `${item.buildings}/${item.roads}/${item.planning}/${item.firstBuildingId}/${item.firstRoadId}`));
  if (mapCounts.size !== 1 || !mapCounts.has(initialMapCount) || areaGeometries.size !== sequence.length || labels.size !== sequence.length || contextSignatures.size < 3) {
    throw new Error(`same-workspace switch gate failed: ${JSON.stringify({ mapCounts: [...mapCounts], areaGeometries: areaGeometries.size, labels: labels.size, contextSignatures: contextSignatures.size })}`);
  }
  await desktop.close();

  const facilityContext = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, reducedMotion: "reduce" });
  const facilityPage = await facilityContext.newPage();
  attachDiagnostics(facilityPage, "facility");
  await facilityPage.goto(baseUrl.replace("story=intro", "story=verify") + "&mesh=533513611", { waitUntil: "domcontentloaded", timeout: 120_000 });
  await ready(facilityPage, "533513611");
  const facilityOption = facilityPage.locator('.guided-target-select option[value^="facility:"]').first();
  await facilityOption.waitFor({ state: "attached", timeout: 120_000 });
  if (!await facilityOption.count()) throw new Error("registered facility target fixture is unavailable in 533513611");
  const facilityValue = await facilityOption.getAttribute("value");
  if (!facilityValue) throw new Error("facility target option has no value");
  await facilityPage.locator(".guided-target-select select").selectOption(facilityValue);
  await facilityPage.waitForFunction(() => document.querySelector(".guided-spatial-app")?.getAttribute("data-target-kind") === "facility");
  const facilityState = await facilityPage.evaluate(() => {
    const root = document.querySelector(".guided-spatial-app");
    const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
    return {
      kind: root?.getAttribute("data-target-kind"),
      sourceType: map?.getSource("guided-target")?.serialize?.().data?.features?.[0]?.geometry?.type,
      pointVisible: map?.getLayoutProperty("guided-target-point", "visibility") !== "none",
      checks: document.querySelectorAll(".guided-check-list > li").length,
    };
  });
  if (facilityState.kind !== "facility" || facilityState.sourceType !== "Point" || !facilityState.pointVisible || facilityState.checks < 3 || facilityState.checks > 5) {
    throw new Error(`facility target contract failure: ${JSON.stringify(facilityState)}`);
  }
  await shot(facilityPage, "desktop-verify-facility.png");
  await facilityContext.close();

  const routeContext = await browser.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1, reducedMotion: "reduce" });
  const routePage = await routeContext.newPage();
  routePage.setDefaultTimeout(180_000);
  attachDiagnostics(routePage, "routes");
  const rootUrl = new URL(baseUrl);
  const routeCases = [
    { query: "?guide=1", selector: '.guided-spatial-app[data-guided-story="find"]', destination: "guided/find" },
    { query: "?guide=2", selector: '.guided-spatial-app[data-guided-story="find"]', destination: "guided/find?detail=reason" },
    { query: "?guide=3", selector: '.guided-spatial-app[data-guided-story="understand"]', destination: "guided/understand" },
    { query: "?guide=4", selector: '.guided-spatial-app[data-guided-story="verify"]', destination: "guided/verify" },
    { query: "?guide=5", selector: '.product-app[data-experience="advanced"]', destination: "advanced/field-sheet" },
    { query: "?guide=6", selector: '.product-app[data-experience="advanced"]', destination: "advanced/municipal-review" },
    { query: "", selector: ".product-app.public-area", destination: "public-root" },
  ];
  for (const routeCase of routeCases) {
    const url = `${rootUrl.origin}${rootUrl.pathname}${routeCase.query}`;
    await routePage.goto(url, { waitUntil: "domcontentloaded", timeout: 180_000 });
    await routePage.locator(routeCase.selector).waitFor({ timeout: 180_000 });
    routeRegressions.push({ query: routeCase.query || "public-root", destination: routeCase.destination, finalUrl: routePage.url() });
  }
  await routeContext.close();

  const compact = await browser.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1, reducedMotion: "reduce" });
  const compactPage = await compact.newPage();
  attachDiagnostics(compactPage, "compact");
  await compactPage.goto(baseUrl.replace("story=intro", "story=understand") + "&mesh=533513314", { waitUntil: "domcontentloaded", timeout: 120_000 });
  await ready(compactPage, "533513314");
  await compactPage.locator('.guided-spatial-app[data-section-pack="maizuru-533513314-plateau-2025-v1"]').waitFor({ timeout: 120_000 });
  const compactSectionHeight = await compactPage.locator(".guided-section-dock svg").evaluate((node) => node.getBoundingClientRect().height);
  if (compactSectionHeight < 300 || compactSectionHeight > 320) throw new Error(`1280 section plot height outside 300-320px: ${compactSectionHeight}`);
  await auditGuidedSection(compactPage, "compact", { maxAnnotations: 6, minHeight: 300 });
  await auditAccessibility(compactPage, "compact-understand");
  await shot(compactPage, "compact-understand-section.png");
  await compact.close();

  const dprBrowser = await chromium.launch(launchOptions);
  try {
    phase("DPR2 hero");
    const dpr2 = await dprBrowser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, reducedMotion: "reduce" });
    const dpr2Page = await dpr2.newPage();
    attachDiagnostics(dpr2Page, "dpr2");
    await dpr2Page.goto(baseUrl.replace("story=intro", "story=understand") + "&mesh=533513314", { waitUntil: "domcontentloaded", timeout: 180_000 });
    await ready(dpr2Page, "533513314");
    await dpr2Page.locator('.guided-spatial-app[data-section-pack="maizuru-533513314-plateau-2025-v1"]').waitFor({ timeout: 180_000 });
    await shot(dpr2Page, "dpr2-understand-section.png");
    await dpr2.close();
  } finally {
    await dprBrowser.close();
  }

  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, reducedMotion: "reduce" });
  phase("mobile and keyboard");
  const mobilePage = await mobile.newPage();
  mobilePage.setDefaultTimeout(120_000);
  attachDiagnostics(mobilePage, "mobile");
  await mobilePage.goto(baseUrl.replace("story=intro", "story=understand") + "&mesh=533513314", { waitUntil: "domcontentloaded", timeout: 120_000 });
  await ready(mobilePage, "533513314");
  await mobilePage.locator('.guided-spatial-app[data-section-pack="maizuru-533513314-plateau-2025-v1"]').waitFor({ timeout: 120_000 });
  await auditAccessibility(mobilePage, "mobile-understand-map");
  await shot(mobilePage, "mobile-understand-map.png");
  await mobilePage.getByRole("button", { name: "街の断面", exact: true }).click();
  await mobilePage.locator(".guided-section-dock.mobile-visible").waitFor({ state: "visible" });
  await mobilePage.waitForFunction(() => (document.querySelector(".guided-section-dock svg")?.getBoundingClientRect().height ?? 0) >= 300);
  const sectionHeight = await mobilePage.locator(".guided-section-dock svg").evaluate((node) => node.getBoundingClientRect().height);
  if (sectionHeight < 300) throw new Error(`mobile section plot is too short: ${sectionHeight}`);
  await auditGuidedSection(mobilePage, "mobile", { maxAnnotations: 4, minHeight: 300 });
  const sectionSvg = mobilePage.locator(".urban-section.guided svg");
  await sectionSvg.focus();
  await mobilePage.keyboard.press("ArrowRight");
  await mobilePage.waitForFunction(() => {
    const section = document.querySelector(".urban-section.guided");
    const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
    const focusSource = map?.getSource("guided-section-focus")?.serialize?.().data;
    return section?.getAttribute("data-selected-annotation-visible") === "true"
      && focusSource?.features?.length === 1;
  });
  const focusAudit = await mobilePage.evaluate(() => {
    const section = document.querySelector(".urban-section.guided");
    const callout = section?.querySelector("[data-section-focus-annotation]");
    return {
      selectedVisible: section?.getAttribute("data-selected-annotation-visible"),
      focusedKind: section?.getAttribute("data-focused-object-kind"),
      callout: callout?.textContent?.replace(/\s+/g, " ").trim() ?? "",
      mapInitCount: window.__cityGapMapInitCount,
    };
  });
  sectionAudits.push({ label: "mobile-focus", ...focusAudit });
  if (focusAudit.selectedVisible !== "true" || !/building|road/.test(focusAudit.focusedKind ?? "") || !/標高/.test(focusAudit.callout) || focusAudit.mapInitCount !== initialMapCount) {
    throw new Error(`Section focus synchronization failure: ${JSON.stringify(focusAudit)}`);
  }
  await auditAccessibility(mobilePage, "mobile-understand-section");
  await shot(mobilePage, "mobile-understand-section.png");

  await mobilePage.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
  const keyboard = [];
  for (let index = 0; index < 10; index += 1) {
    await mobilePage.keyboard.press("Tab");
    keyboard.push(await mobilePage.evaluate(() => {
      const node = document.activeElement;
      if (!(node instanceof Element)) return null;
      if (!node.matches("button, select, input, a[href], summary, [tabindex]")) return null;
      const style = getComputedStyle(node);
      return { name: node.getAttribute("aria-label") || node.textContent?.trim(), focusVisible: style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0 };
    }));
  }
  if (keyboard.filter(Boolean).some((item) => !item.focusVisible)) throw new Error(`keyboard focus is not visible: ${JSON.stringify(keyboard)}`);
  await mobilePage.getByRole("button", { name: "地図", exact: true }).click();
  await mobilePage.getByRole("button", { name: "範囲選択へ戻る", exact: true }).click();
  await waitShell(mobilePage, "find", "533513314");
  await auditAccessibility(mobilePage, "mobile-find");
  await shot(mobilePage, "mobile-find.png");
  await mobilePage.getByRole("button", { name: "街の形を見る", exact: true }).click();
  await ready(mobilePage, "533513314");
  await mobilePage.getByRole("button", { name: "確認場所を見る", exact: true }).click();
  await ready(mobilePage, "533513314");
  await auditAccessibility(mobilePage, "mobile-verify");
  await shot(mobilePage, "mobile-verify.png");
  await mobile.close();

  if (errors.length) throw new Error(errors.join("\n"));
  const manifest = {
    schema_version: "citygap.guided-spatial-checkpoint@1",
    generated_at: new Date().toISOString(),
    branch: execFileSync("git", ["branch", "--show-current"], { encoding: "utf8" }).trim(),
    commit: execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).trim(),
    url: baseUrl,
    first_ready_ms: firstReadyMs,
    map_init_count: initialMapCount,
    initial_context_request_count: initialContextRequestCount,
    initial_data_requests: initialDataRequestSnapshot,
    context_requests: contextRequests.filter((url, index) => contextRequests.indexOf(url) === index),
    area_switch_sequence: sequence,
    snapshots,
    accessibility,
    section_audits: sectionAudits,
    keyboard,
    route_regressions: routeRegressions,
    screenshots,
    errors,
  };
  if (capture) {
    mkdirSync(artifacts, { recursive: true });
    writeFileSync(resolve(artifacts, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  }
  phase("checkpoint complete");
  process.stdout.write(`${JSON.stringify(manifest, null, 2)}\n`);
} finally {
  await browser.close();
}
