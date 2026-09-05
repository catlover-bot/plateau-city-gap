import assert from "node:assert/strict";
import { performance } from "node:perf_hooks";
import { chromium } from "playwright-core";

const args = new Map();
for (let index = 2; index < process.argv.length; index += 2) {
  args.set(process.argv[index], process.argv[index + 1]);
}
const baseUrl = new URL(args.get("--url") ?? "http://127.0.0.1:4173/plateau-city-gap/");
baseUrl.search = "";
const queryUrl = (query) => new URL(`?${query}`, baseUrl).href;
const supportedArea = "533513314";
const unsupportedArea = "533512753";
const directQuery = `experience=guided&story=understand&mapMode=plateau3d&selectionType=mesh&selection=${supportedArea}`;
const report = { base_url: baseUrl.href, direct_url: queryUrl(directQuery), flows: {}, diagnostics: [] };
const browser = args.has("--cdp") ? await chromium.connectOverCDP(args.get("--cdp")) : await chromium.launch({
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath(),
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist",
    ...(args.get("--software") === "true"
      ? ["--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"] : [])],
});
const ownedContexts = new Set();

function phase(message) { process.stderr.write(`[guided-3d] ${message}\n`); }

async function createPage(viewport, { expectedFailure = () => false } = {}) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1, reducedMotion: "reduce", serviceWorkers: "block" });
  ownedContexts.add(context);
  context.on("close", () => ownedContexts.delete(context));
  const page = await context.newPage();
  page.setDefaultTimeout(60_000);
  const diagnostics = { page_errors: [], local_request_errors: [], local_http_errors: [] };
  page.on("pageerror", (error) => diagnostics.page_errors.push(error.message));
  page.on("requestfailed", (request) => {
    if (request.url().startsWith(baseUrl.href) && !expectedFailure(request.url()) && request.failure()?.errorText !== "net::ERR_ABORTED") {
      diagnostics.local_request_errors.push({ url: request.url(), error: request.failure()?.errorText });
    }
  });
  page.on("response", (response) => {
    if (response.url().startsWith(baseUrl.href) && response.status() >= 400 && !expectedFailure(response.url())) {
      diagnostics.local_http_errors.push({ url: response.url(), status: response.status() });
    }
  });
  report.diagnostics.push(diagnostics);
  return { context, page, diagnostics };
}

async function waitArea(page, area = supportedArea, story = "understand") {
  await page.locator(`.guided-spatial-app[data-area-id="${area}"][data-guided-story="${story}"][data-context-status="ready"]`).waitFor();
}

async function wait3D(page) {
  await waitArea(page);
  await page.locator('.plateau-3d-shell[data-ui-mode="guided"]').waitFor();
  await page.waitForFunction(() => {
    const shell = document.querySelector(".plateau-3d-shell");
    const viewer = window.__cityGapCesiumViewer;
    return shell?.getAttribute("data-ready") === "true"
      && document.documentElement.dataset.captureStrictReady === "true"
      && viewer && !viewer.isDestroyed();
  }, null, { timeout: 90_000 });
  const state = await page.evaluate(() => {
    const viewer = window.__cityGapCesiumViewer;
    const container = viewer.container;
    return {
      attributes: Object.fromEntries([...container.attributes].filter((item) => item.name.startsWith("data-")).map((item) => [item.name, item.value])),
      canvas: { width: viewer.canvas.width, height: viewer.canvas.height },
      camera_pitch_degrees: viewer.camera.pitch * 180 / Math.PI,
      visible_road_sources: Array.from({ length: viewer.dataSources.length }, (_, index) => viewer.dataSources.get(index))
        .filter((source) => source.show && source.entities.values.some((entity) => entity.properties?.road_id)).length,
      map_init_count: window.__cityGapMapInitCount,
    };
  });
  assert.equal(state.attributes["data-local-dem"], "ready", "local PLATEAU DEM must be loaded");
  assert.equal(state.attributes["data-pack-artifacts-ready"], "true", "verified pack files must be ready");
  assert.equal(state.attributes["data-building-content-ready"], "true", "tileset content must be ready independently of downloaded hashes");
  assert.ok(Number(state.attributes["data-rendered-building-feature-count"]) > 0, "the current camera must have rendered actual building features");
  assert.ok(state.visible_road_sources > 0, "real PLATEAU road source must remain visible");
  assert.ok(state.camera_pitch_degrees < -15 && state.camera_pitch_degrees > -80, "camera must show building height obliquely");
  return state;
}

// Pick the rendered model with Cesium's normal screen picking, then click the
// same browser position. No callback, React state, or model data is injected.
async function clickRenderedBuilding(page) {
  const point = await page.evaluate(() => {
    const viewer = window.__cityGapCesiumViewer;
    const canvas = viewer.canvas;
    const rect = canvas.getBoundingClientRect();
    const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
    const areaBuildings = map?.getSource("guided-buildings")?.serialize?.().data?.features ?? [];
    const allowedIds = new Set(areaBuildings.flatMap((feature) => [String(feature.id), String(feature.properties?.object_id)]));
    for (let radius = 0; radius <= 5; radius += 1) {
      for (let dy = -radius; dy <= radius; dy += 1) {
        for (let dx = -radius; dx <= radius; dx += 1) {
          if (radius && Math.abs(dx) !== radius && Math.abs(dy) !== radius) continue;
          const x = rect.width * 0.5 + dx * 34;
          const y = rect.height * 0.45 + dy * 30;
          if (x < 10 || y < 10 || x > rect.width - 10 || y > rect.height - 10) continue;
          if (!canvas.contains(document.elementFromPoint(rect.left + x, rect.top + y))) continue;
          const feature = viewer.scene.drillPick({ x, y }, 20).find((candidate) => {
            if (typeof candidate?.getProperty !== "function") return false;
            const id = String(candidate.getProperty("gml_id") ?? "");
            return id.startsWith("bldg_") && allowedIds.has(id);
          });
          if (!feature) continue;
          const attributes = feature.getProperty("attributes") ?? {};
          const read = (name) => feature.getProperty(name) ?? attributes[name] ?? null;
          return {
            x: rect.left + x, y: rect.top + y,
            id: feature.getProperty("gml_id"),
            usage: read("bldg:usage"),
            height: read("bldg:measuredHeight"),
            storeys: read("bldg:storeysAboveGround"),
            lod: feature.getProperty("_lod"),
            color_before: feature.color?.toCssColorString(),
          };
        }
      }
    }
    return null;
  });
  assert.ok(point, "a real PLATEAU building must be screen-pickable");
  await page.mouse.click(point.x, point.y);
  await page.locator(`.guided-spatial-app[data-object-id="${point.id}"]`).waitFor();
  await page.locator(`.cesium-map[data-selected-building-id="${point.id}"]`).waitFor();
  await page.locator(".guided-object-attributes summary").click();
  const panel = await page.locator(".guided-story-panel").innerText();
  assert.ok(panel.includes(point.id), "Inspector must identify the clicked building");
  for (const value of [point.usage, point.height, point.storeys]) {
    if (value !== null && value !== undefined && Number(value) > -9998) {
      assert.ok(panel.includes(String(value)), `Inspector must show source attribute ${value}`);
    } else if (typeof value === "string" && value.trim()) {
      assert.ok(panel.includes(value), "Inspector must show the official usage");
    } else {
      assert.ok(panel.includes("データなし"), "missing official attribute must remain missing");
    }
  }
  assert.match(panel, /PLATEAU/);
  assert.match(panel, /2025/);
  assert.equal(new URL(page.url()).searchParams.get("selection"), supportedArea, "building pick must preserve the selected Area");
  return point;
}

async function assertChecks(page, kind) {
  const labels = await page.locator(".guided-check-list > li > strong").allTextContents();
  const expected = kind === "building"
    ? ["建物の入口と道路のつながり", "建物が現在使われているか", "入口までに段差や通行制限があるか"]
    : ["道路を実際に歩いて通行できるか", "歩道の有無と有効幅員", "横断箇所と横断時の見通し", "建物から道路までの接続"];
  assert.deepEqual(labels, expected, "checks must belong to the selected object kind");
  assert.match(await page.locator(".guided-task-heading").innerText(), /未確認/);
  return labels;
}

try {
  phase("Public entry, lazy loading, and actual rendered building selection");
  const { context, page } = await createPage({ width: 1440, height: 900 });
  const requests = [];
  page.on("request", (request) => requests.push(request.url()));
  await page.goto(baseUrl.href, { waitUntil: "domcontentloaded" });
  await page.locator(".product-app.public-area").waitFor();
  assert.equal(requests.filter((url) => /CesiumMap|cesium\/Workers|cesium\/Assets/.test(url)).length, 0,
    "Public must not eagerly load Cesium");
  const entry = page.getByRole("link", { name: /PLATEAU.*3D/ });
  assert.equal(await entry.count(), 1, "Public must offer one explicit 3D example entry");
  assert.match(await entry.innerText(), /常団地前/);
  const started = performance.now();
  await entry.click();
  const readiness = await wait3D(page);
  const readyMs = Math.round(performance.now() - started);
  const building = await clickRenderedBuilding(page);
  report.flows.public_to_3d = { passed: true, readiness, ready_ms: readyMs, building };

  phase("same Area and object retained when switching 3D to 2D");
  await page.getByRole("button", { name: "2D地図", exact: true }).click();
  await page.locator(".plateau-3d-shell").waitFor({ state: "hidden" });
  assert.ok((await page.locator(".guided-story-panel").innerText()).includes(building.id));
  assert.equal(await page.evaluate(() => window.__cityGapMapInitCount), readiness.map_init_count);
  await page.getByRole("button", { name: "PLATEAU 3D", exact: true }).click();
  await wait3D(page);
  report.flows.mode_selection_retained = { passed: true, building_id: building.id };

  phase("verified A–B Section and map focus synchronization");
  await page.getByRole("button", { name: "街の断面", exact: true }).click();
  const svg = page.locator(".urban-section.guided svg");
  await svg.waitFor();
  const section = await page.evaluate(() => {
    const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
    return map?.getSource("guided-section")?.serialize?.().data?.features?.[0]?.geometry;
  });
  assert.deepEqual(section?.coordinates, [[135.398125, 35.44583333333334], [135.398125, 35.45]]);
  await svg.focus();
  await page.keyboard.press("ArrowRight");
  await page.waitForFunction(() => document.querySelector(".urban-section.guided")?.getAttribute("data-selected-annotation-visible") === "true");
  const focus = await page.evaluate(() => {
    const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
    const viewer = window.__cityGapCesiumViewer;
    return {
      map: map?.getSource("guided-section-focus")?.serialize?.().data?.features?.[0]?.geometry?.coordinates,
      entities: viewer.entities.values.filter((entity) => /section/.test(entity.id)).map((entity) => ({
        id: entity.id,
        position: entity.position ? viewer.scene.globe.ellipsoid.cartesianToCartographic(entity.position.getValue(viewer.clock.currentTime)) : null,
        line: entity.polyline?.positions?.getValue(viewer.clock.currentTime)?.map((position) => {
          const coordinate = viewer.scene.globe.ellipsoid.cartesianToCartographic(position);
          return [coordinate.longitude * 180 / Math.PI, coordinate.latitude * 180 / Math.PI];
        }),
      })),
    };
  });
  assert.equal(focus.map?.length, 2, "Section must update the persistent map focus");
  const line3d = focus.entities.find((entity) => entity.id.startsWith("urban-section-transect:"))?.line;
  assert.ok(line3d?.length >= 2, "3D must retain the actual verified A–B polyline");
  for (const [endpoint, actual] of [[section.coordinates[0], line3d[0]], [section.coordinates.at(-1), line3d.at(-1)]]) {
    assert.ok(Math.abs(endpoint[0] - actual[0]) < 1e-7 && Math.abs(endpoint[1] - actual[1]) < 1e-7,
      "3D and Section A–B endpoints must match the same real coordinates");
  }
  assert.ok(focus.entities.some((entity) => entity.position
    && Math.abs(entity.position.longitude * 180 / Math.PI - focus.map[0]) < 1e-7
    && Math.abs(entity.position.latitude * 180 / Math.PI - focus.map[1]) < 1e-7), "3D focus must mark the same Section longitude/latitude");
  report.flows.section = { passed: true, geometry: section, focus };

  phase("building and road checks remain object-specific");
  await page.getByRole("button", { name: "確認場所を見る", exact: true }).click();
  await waitArea(page, supportedArea, "verify");
  assert.equal(await page.locator(".guided-spatial-app").getAttribute("data-target-key"), `building:${building.id}`);
  const buildingChecks = await assertChecks(page, "building");
  const targetSelect = page.locator(".guided-target-select select");
  const roadKey = await targetSelect.locator('option[value^="road:"]').first().getAttribute("value");
  assert.ok(roadKey, "existing exact road target must remain selectable");
  await targetSelect.selectOption(roadKey);
  const roadChecks = await assertChecks(page, "road");
  assert.equal(await page.locator(".guided-spatial-app").getAttribute("data-target-key"), roadKey);
  report.flows.target_checks = { passed: true, building: building.id, building_checks: buildingChecks, road: roadKey, road_checks: roadChecks };

  phase("Area change rejects stale objects and unsupported 3D");
  await page.getByRole("button", { name: "街の形へ戻る", exact: true }).click();
  await page.getByRole("button", { name: "範囲選択へ戻る", exact: true }).click();
  await page.getByLabel("495の範囲から選ぶ").selectOption(unsupportedArea);
  await page.getByRole("button", { name: "街の形を見る", exact: true }).click();
  await waitArea(page, unsupportedArea);
  assert.equal(await page.locator(".plateau-3d-shell, .urban-section.guided").count(), 0);
  assert.ok(!(await page.locator(".guided-story-panel").innerText()).includes(building.id));
  assert.equal(await page.evaluate(() => window.__cityGapMapInitCount), readiness.map_init_count);
  await page.goto(queryUrl(directQuery.replace(supportedArea, unsupportedArea)), { waitUntil: "domcontentloaded" });
  await waitArea(page, unsupportedArea);
  assert.equal(await page.locator(".plateau-3d-shell, .urban-section.guided").count(), 0);
  report.flows.unsupported_area = { passed: true, area: unsupportedArea, direct_link_rejected: true };

  phase("Guided to Advanced settles completely");
  await page.getByRole("button", { name: "詳細分析", exact: true }).click();
  await page.locator('.product-app[data-experience="advanced"] .task-navigation').waitFor({ timeout: 90_000 });
  const upgrade = await page.evaluate(() => window.__cityGapFullDataUpgrade);
  assert.equal(upgrade?.mode, "full");
  assert.equal(upgrade?.settleResult, "success");
  report.flows.guided_advanced = { passed: true, upgrade };
  await context.close();

  phase("390px 3D errors, retry, controls, and return path");
  let failTiles = true;
  const tileFailure = (url) => /\/plateau\/.*\.(?:b3dm|glb)(?:\?|$)/.test(url);
  const mobile = await createPage({ width: 390, height: 844 }, { expectedFailure: tileFailure });
  await mobile.context.route("**/plateau/**", async (route) => {
    if (failTiles && tileFailure(route.request().url())) {
      await route.fulfill({ status: 503, contentType: "application/octet-stream", body: "temporarily unavailable" });
    } else await route.continue();
  });
  const errorStarted = performance.now();
  await mobile.page.goto(queryUrl(directQuery), { waitUntil: "domcontentloaded" });
  await mobile.page.locator(".guided-3d-view [role=alert]").waitFor({ timeout: 90_000 });
  const errorMs = Math.round(performance.now() - errorStarted);
  assert.ok(errorMs < 90_000, "3D failure must settle within a finite bound");
  const retry = mobile.page.getByRole("button", { name: /再試行|もう一度/ });
  const back2d = mobile.page.getByRole("button", { name: "2D地図に戻る", exact: true });
  for (const control of [retry, back2d]) {
    await control.scrollIntoViewIfNeeded();
    const rect = await control.boundingBox();
    assert.ok(rect && rect.width >= 44 && rect.height >= 44 && rect.x >= 0 && rect.x + rect.width <= 391,
      "390px recovery controls must be visible and touch-sized");
  }
  failTiles = false;
  await retry.click();
  const mobileReady = await wait3D(mobile.page);
  assert.ok(await mobile.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  await mobile.page.getByRole("button", { name: "2D地図", exact: true }).click();
  await mobile.page.getByRole("button", { name: "範囲選択へ戻る", exact: true }).click();
  await mobile.page.locator('.guided-spatial-app[data-guided-story="find"]').waitFor();
  report.flows.mobile_failure_retry = { passed: true, error_ms: errorMs, readiness: mobileReady };
  await mobile.context.close();

  for (const diagnostics of report.diagnostics) {
    assert.deepEqual(diagnostics.page_errors, []);
    assert.deepEqual(diagnostics.local_request_errors, []);
    assert.deepEqual(diagnostics.local_http_errors, []);
  }
  report.passed = true;
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
} catch (error) {
  report.passed = false;
  report.error = error instanceof Error ? error.message : String(error);
  process.stderr.write(`${JSON.stringify(report, null, 2)}\n`);
  process.exitCode = 1;
} finally {
  for (const context of ownedContexts) await context.close();
  await browser.close();
}
