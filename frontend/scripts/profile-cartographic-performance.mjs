import { execFileSync } from "node:child_process";
import { gzipSync } from "node:zlib";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { performance } from "node:perf_hooks";
import { chromium } from "playwright-core";

const parameters = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const argument = process.argv[index];
  if (!argument.startsWith("--")) continue;
  const value = process.argv[index + 1];
  parameters.set(argument, value && !value.startsWith("--") ? value : "true");
  if (value && !value.startsWith("--")) index += 1;
}

const baseUrl = parameters.get("--url") ?? "http://127.0.0.1:4173/plateau-city-gap/";
const sampleCount = Number.parseInt(parameters.get("--samples") ?? "5", 10);
const waitTimeoutMs = Number.parseInt(parameters.get("--timeout-ms") ?? "120000", 10);
const repositoryRoot = path.resolve(process.cwd(), "..");
const output = path.resolve(
  process.cwd(),
  parameters.get("--output") ?? "../analysis/outputs/real/cartographic-performance-profile-baseline.json",
);
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const cartographyRoot = path.join(process.cwd(), "public/data/cartography");
const manifest = JSON.parse(await readFile(path.join(cartographyRoot, "manifest.json"), "utf8"));

function median(values) {
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.floor(sorted.length / 2)];
}

async function fileProfile(filename) {
  const buffer = await readFile(path.join(cartographyRoot, filename));
  const parseSamples = [];
  for (let index = 0; index < 5; index += 1) {
    const startedAt = performance.now();
    JSON.parse(buffer.toString("utf8"));
    parseSamples.push(Number((performance.now() - startedAt).toFixed(3)));
  }
  const value = JSON.parse(buffer.toString("utf8"));
  return {
    path: filename,
    uncompressed_bytes: buffer.byteLength,
    gzip_bytes: gzipSync(buffer, { level: 9 }).byteLength,
    feature_count: Array.isArray(value.features) ? value.features.length : null,
    parse_samples_ms: parseSamples,
    parse_median_ms: median(parseSamples),
  };
}

const assetProfiles = {};
for (const [kind, artifact] of Object.entries(manifest.artifacts)) {
  assetProfiles[kind] = await fileProfile(artifact.path);
}
assetProfiles.manifest = await fileProfile("manifest.json");

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

async function installNetworkProbe(context) {
  await context.addInitScript(() => {
    const profile = {
      fetches: [],
      json: [],
      longTasks: [],
    };
    Object.defineProperty(window, "__cityGapNetworkProfile", { value: profile, writable: false });

    const originalFetch = window.fetch.bind(window);
    window.fetch = async (...args) => {
      const request = args[0];
      const url = typeof request === "string" ? request : request instanceof Request ? request.url : String(request);
      const startedAt = performance.now();
      try {
        const response = await originalFetch(...args);
        profile.fetches.push({
          url,
          started_at_ms: startedAt,
          headers_at_ms: performance.now(),
          status: response.status,
        });
        return response;
      } catch (error) {
        profile.fetches.push({
          url,
          started_at_ms: startedAt,
          failed_at_ms: performance.now(),
          error: error instanceof Error ? error.message : String(error),
        });
        throw error;
      }
    };

    const originalJson = Response.prototype.json;
    Response.prototype.json = async function profiledJson() {
      const startedAt = performance.now();
      try {
        const value = await originalJson.call(this);
        profile.json.push({
          url: this.url,
          started_at_ms: startedAt,
          completed_at_ms: performance.now(),
          ok: true,
        });
        return value;
      } catch (error) {
        profile.json.push({
          url: this.url,
          started_at_ms: startedAt,
          completed_at_ms: performance.now(),
          ok: false,
          error: error instanceof Error ? error.message : String(error),
        });
        throw error;
      }
    };

    try {
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          profile.longTasks.push({ start_ms: entry.startTime, duration_ms: entry.duration });
        }
      }).observe({ type: "longtask", buffered: true });
    } catch {
      // Long-task observation is optional in browser engines that do not expose it.
    }
  });
}

async function waitForStep(page, step) {
  await page.locator(`.public-area[data-public-step="${step}"]`).waitFor({ timeout: waitTimeoutMs });
}

async function waitForCartography(page) {
  await page.locator('.public-area[data-cartography-state="ready"]').waitFor({ timeout: waitTimeoutMs });
}

async function waitForMap(page, expected = {}) {
  await page.waitForFunction((value) => {
    const nodes = [...document.querySelectorAll("[data-public-cartography-ready]")];
    const node = nodes.find((candidate) => candidate.getAttribute("data-public-cartography-ready") === "true");
    if (!node) return false;
    if (value.story && node.getAttribute("data-public-story") !== value.story) return false;
    if (value.target && node.getAttribute("data-target-resolution") !== value.target) return false;
    return true;
  }, expected, { timeout: waitTimeoutMs });
}

async function installMapProbe(page) {
  await page.waitForFunction(() => Boolean(document.querySelector(".analytical-map-canvas")?.__cityGapMap), null, {
    timeout: waitTimeoutMs,
  });
  await page.evaluate(() => {
    const canvas = document.querySelector(".analytical-map-canvas");
    const map = canvas?.__cityGapMap;
    if (!map) throw new Error("MapLibre instance is unavailable");
    const state = {
      map,
      label: "idle",
      actionStart: performance.now(),
      calls: [],
      events: [],
      mutations: [],
      initialSourceCount: Object.keys(map.getStyle()?.sources ?? {}).length,
      initialLayerCount: map.getStyle()?.layers?.length ?? 0,
    };
    Object.defineProperty(window, "__cityGapMapProfile", { value: state, writable: false });

    const recordCall = (method, detail = {}) => state.calls.push({
      method,
      at_ms: performance.now(),
      ...detail,
    });
    for (const method of [
      "addSource", "addLayer", "removeSource", "removeLayer", "setLayoutProperty",
      "setPaintProperty", "setFilter", "fitBounds", "easeTo", "jumpTo",
    ]) {
      const original = map[method]?.bind(map);
      if (!original) continue;
      map[method] = (...args) => {
        recordCall(method, {
          id: typeof args[0] === "string" ? args[0] : null,
          property: typeof args[1] === "string" ? args[1] : null,
        });
        return original(...args);
      };
    }

    const wrapSources = () => {
      for (const id of [
        "public-area", "public-area-mask", "public-buildings", "public-roads",
        "public-planning", "public-target", "public-origin",
      ]) {
        const source = map.getSource(id);
        if (!source?.setData || source.__cityGapProfileWrapped) continue;
        const original = source.setData.bind(source);
        source.setData = (data) => {
          const startedAt = performance.now();
          const result = original(data);
          recordCall("setData", {
            id,
            completed_at_ms: performance.now(),
            feature_count: Array.isArray(data?.features) ? data.features.length : null,
          });
          state.calls[state.calls.length - 1].started_at_ms = startedAt;
          return result;
        };
        Object.defineProperty(source, "__cityGapProfileWrapped", { value: true });
      }
    };
    wrapSources();

    for (const eventName of ["render", "idle", "movestart", "moveend", "sourcedata", "styledata"]) {
      map.on(eventName, (event) => {
        if (eventName === "sourcedata" && !String(event.sourceId ?? "").startsWith("public-")) return;
        state.events.push({
          event: eventName,
          at_ms: performance.now(),
          source_id: event.sourceId ?? null,
          source_loaded: eventName === "sourcedata" && event.sourceId ? map.isSourceLoaded(event.sourceId) : null,
        });
        wrapSources();
      });
    }

    const shell = canvas.closest(".analytical-map-shell");
    if (shell) {
      new MutationObserver((records) => {
        for (const record of records) {
          state.mutations.push({
            attribute: record.attributeName,
            value: record.attributeName ? shell.getAttribute(record.attributeName) : null,
            at_ms: performance.now(),
          });
        }
      }).observe(shell, { attributes: true });
    }

    window.__cityGapResetMapProfile = (label) => {
      state.label = label;
      state.actionStart = performance.now();
      state.calls.length = 0;
      state.events.length = 0;
      state.mutations.length = 0;
      return state.actionStart;
    };
    window.__cityGapReadMapProfile = () => ({
      label: state.label,
      action_start_ms: state.actionStart,
      completed_at_ms: performance.now(),
      calls: state.calls.map((item) => ({ ...item, relative_ms: item.at_ms - state.actionStart })),
      events: state.events.map((item) => ({ ...item, relative_ms: item.at_ms - state.actionStart })),
      mutations: state.mutations.map((item) => ({ ...item, relative_ms: item.at_ms - state.actionStart })),
      map_recreated: document.querySelector(".analytical-map-canvas")?.__cityGapMap !== state.map,
      source_count: Object.keys(map.getStyle()?.sources ?? {}).length,
      layer_count: map.getStyle()?.layers?.length ?? 0,
      initial_source_count: state.initialSourceCount,
      initial_layer_count: state.initialLayerCount,
    });
  });
}

async function resetProbe(page, label) {
  await page.evaluate((value) => window.__cityGapResetMapProfile(value), label);
}

async function compositorTimestamp(page) {
  return page.evaluate(() => new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve(performance.now())));
  }));
}

async function performanceMetrics(client) {
  const response = await client.send("Performance.getMetrics");
  return Object.fromEntries(response.metrics
    .filter((item) => [
      "JSHeapUsedSize", "Nodes", "LayoutCount", "RecalcStyleCount", "ScriptDuration", "TaskDuration",
    ].includes(item.name))
    .map((item) => [item.name, item.value]));
}

async function readPathProfile(page, client, readyAt, beforeMetrics) {
  const compositorAt = await compositorTimestamp(page);
  const map = await page.evaluate(() => window.__cityGapReadMapProfile());
  const afterMetrics = await performanceMetrics(client);
  const firstLoadedSource = map.events.find((item) => item.event === "sourcedata" && item.source_loaded);
  const firstIdle = map.events.find((item) => item.event === "idle");
  const firstMoveEnd = map.events.find((item) => item.event === "moveend");
  const firstReadyMutation = map.mutations.find((item) => item.attribute === "data-public-cartography-ready" && item.value === "true");
  return {
    ready_ms: Number((readyAt - map.action_start_ms).toFixed(3)),
    compositor_stable_ms: Number((compositorAt - map.action_start_ms).toFixed(3)),
    first_source_ready_ms: firstLoadedSource ? Number(firstLoadedSource.relative_ms.toFixed(3)) : null,
    camera_complete_ms: firstMoveEnd ? Number(firstMoveEnd.relative_ms.toFixed(3)) : null,
    map_idle_ms: firstIdle ? Number(firstIdle.relative_ms.toFixed(3)) : null,
    readiness_attribute_ms: firstReadyMutation ? Number(firstReadyMutation.relative_ms.toFixed(3)) : null,
    map_recreated: map.map_recreated,
    source_count_before_after: [map.initial_source_count, map.source_count],
    layer_count_before_after: [map.initial_layer_count, map.layer_count],
    calls: map.calls,
    event_count: map.events.length,
    mutation_count: map.mutations.length,
    browser_metric_delta: Object.fromEntries(Object.keys(afterMetrics).map((key) => [
      key,
      Number((afterMetrics[key] - (beforeMetrics[key] ?? 0)).toFixed(6)),
    ])),
  };
}

async function startStationArea(page) {
  await page.getByRole("button", { name: "地図で場所を調べる", exact: true }).click();
  await waitForStep(page, "place");
  await page.getByRole("button", { name: "選んだ駅を起点にする", exact: true }).click();
  await waitForStep(page, "radius");
  await waitForMap(page);
  await page.getByRole("button", { name: "800m", exact: true }).click();
  await waitForMap(page);
  await resetProbe(page, "asset-load");
  await page.getByRole("button", { name: "この範囲を調べる", exact: true }).click();
  await waitForStep(page, "result");
  await waitForCartography(page);
  await waitForMap(page, { story: "population-age" });
}

async function selectStory(page, label, expectedId) {
  const section = page.locator(".area-metric-group").filter({ hasText: label }).first();
  await section.locator(".area-story-action").click();
  await page.locator(`.public-area[data-active-story="${expectedId}"]`).waitFor({ timeout: waitTimeoutMs });
  await waitForMap(page, { story: expectedId });
  if (expectedId === "building-use") {
    await page.waitForFunction(() => {
      const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
      if (!map?.getLayer("public-buildings-fill")) return false;
      return map.queryRenderedFeatures(undefined, { layers: ["public-buildings-fill"] }).length > 0;
    }, null, { timeout: waitTimeoutMs });
  }
  return page.evaluate(() => performance.now());
}

async function selectUnknown(page, name) {
  const button = page.locator(".area-unknown-list").getByRole("button", { name, exact: true });
  await button.click();
  await page.waitForFunction((label) => [...document.querySelectorAll(".area-unknown-list button")]
    .some((candidate) => candidate.textContent?.trim() === label && candidate.getAttribute("aria-pressed") === "true"), name);
}

async function openTarget(page, resolution, kind) {
  await page.getByRole("button", { name: "確認場所を見る", exact: true }).click();
  await waitForStep(page, "target");
  await page.locator(`.public-map-target-label[data-target-resolution="${resolution}"]`).waitFor({ timeout: waitTimeoutMs });
  await waitForMap(page, { target: resolution });
  if (resolution === "exact") {
    await page.waitForFunction((expectedKind) => {
      const map = document.querySelector(".analytical-map-canvas")?.__cityGapMap;
      const data = map?.getSource("public-target")?._data?.geojson;
      if (!data?.features?.length || data.features.some((feature) => feature.properties?.object_type !== expectedKind)) return false;
      return ["public-target-fill", "public-target-halo", "public-target-line", "public-target-point"]
        .filter((id) => map.getLayer(id))
        .some((id) => map.queryRenderedFeatures(undefined, { layers: [id] }).length > 0);
    }, kind, { timeout: waitTimeoutMs });
  } else {
    await page.locator(".public-reference-target-marker").waitFor({ state: "visible", timeout: waitTimeoutMs });
  }
  return page.evaluate(() => performance.now());
}

async function returnToResult(page) {
  await page.locator(".public-area-actions").getByRole("button", { name: "戻る", exact: true }).click();
  await waitForStep(page, "result");
  await waitForMap(page);
}

async function profileStory(page, client, phase) {
  if (phase === "warm") {
    await selectStory(page, "人口・年齢", "population-age");
  }
  await resetProbe(page, `building-use:${phase}`);
  const before = await performanceMetrics(client);
  const readyAt = await selectStory(page, "建物の使われ方", "building-use");
  return readPathProfile(page, client, readyAt, before);
}

async function profileTarget(page, client, { label, name, resolution, kind, phase }) {
  if (await page.locator('.public-area[data-public-step="target"]').count()) await returnToResult(page);
  await selectUnknown(page, name);
  await resetProbe(page, `${label}:${phase}`);
  const before = await performanceMetrics(client);
  const readyAt = await openTarget(page, resolution, kind);
  return readPathProfile(page, client, readyAt, before);
}

function cartographyNetwork(pageProfile) {
  const resourceEntries = pageProfile.resources.filter((item) => item.name.includes("/data/cartography/"));
  const fetches = pageProfile.network.fetches.filter((item) => item.url.includes("/data/cartography/"));
  const json = pageProfile.network.json.filter((item) => item.url.includes("/data/cartography/"));
  const fetchCounts = fetches.reduce((counts, item) => {
    counts.set(item.url, (counts.get(item.url) ?? 0) + 1);
    return counts;
  }, new Map());
  return {
    resources: resourceEntries,
    fetches,
    json,
    duplicate_fetches: [...fetchCounts.entries()]
      .filter(([, count]) => count > 1)
      .map(([url, count]) => ({ url, count })),
  };
}

const samples = [];
try {
  for (let sample = 1; sample <= sampleCount; sample += 1) {
    process.stderr.write(`[profile] sample ${sample}/${sampleCount}: open page\n`);
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      reducedMotion: "reduce",
      serviceWorkers: "block",
    });
    await context.route("https://cyberjapandata.gsi.go.jp/**", (route) => route.abort("blockedbyclient"));
    await installNetworkProbe(context);
    const page = await context.newPage();
    const client = await context.newCDPSession(page);
    await client.send("Performance.enable");
    const pageErrors = [];
    const requestFailures = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    page.on("requestfailed", (request) => requestFailures.push({
      url: request.url(),
      error: request.failure()?.errorText ?? "unknown",
    }));
    await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: waitTimeoutMs });
    await waitForStep(page, "intro");
    await installMapProbe(page);
    process.stderr.write(`[profile] sample ${sample}: start 800m Area\n`);
    await startStationArea(page);

    process.stderr.write(`[profile] sample ${sample}: cold building story\n`);
    const coldBuildingUse = await profileStory(page, client, "cold");
    process.stderr.write(`[profile] sample ${sample}: cold road target\n`);
    const coldRoad = await profileTarget(page, client, {
        label: "road", phase: "cold", name: "駅から周辺へ実際に歩いて通れる経路", resolution: "exact", kind: "road",
      });
    process.stderr.write(`[profile] sample ${sample}: cold building target\n`);
    const coldBuilding = await profileTarget(page, client, {
        label: "building", phase: "cold", name: "PLATEAU建物の現在の使われ方", resolution: "exact", kind: "building",
      });
    process.stderr.write(`[profile] sample ${sample}: cold facility target\n`);
    const coldFacility = await profileTarget(page, client, {
        label: "facility", phase: "cold", name: "登録施設が現在も利用できるか", resolution: "reference_position", kind: "facility",
      });
    const cold = {
      building_use: coldBuildingUse,
      road: coldRoad,
      building: coldBuilding,
      facility: coldFacility,
    };
    await returnToResult(page);
    process.stderr.write(`[profile] sample ${sample}: warm building story\n`);
    const warmBuildingUse = await profileStory(page, client, "warm");
    process.stderr.write(`[profile] sample ${sample}: warm road target\n`);
    const warmRoad = await profileTarget(page, client, {
        label: "road", phase: "warm", name: "駅から周辺へ実際に歩いて通れる経路", resolution: "exact", kind: "road",
      });
    process.stderr.write(`[profile] sample ${sample}: warm building target\n`);
    const warmBuilding = await profileTarget(page, client, {
        label: "building", phase: "warm", name: "PLATEAU建物の現在の使われ方", resolution: "exact", kind: "building",
      });
    process.stderr.write(`[profile] sample ${sample}: warm facility target\n`);
    const warmFacility = await profileTarget(page, client, {
        label: "facility", phase: "warm", name: "登録施設が現在も利用できるか", resolution: "reference_position", kind: "facility",
      });
    const warm = {
      building_use: warmBuildingUse,
      road: warmRoad,
      building: warmBuilding,
      facility: warmFacility,
    };
    process.stderr.write(`[profile] sample ${sample}: collect page profile\n`);

    const pageProfile = await page.evaluate(() => ({
      network: window.__cityGapNetworkProfile,
      resources: performance.getEntriesByType("resource").map((entry) => ({
        name: entry.name,
        start_time_ms: entry.startTime,
        response_start_ms: entry.responseStart,
        response_end_ms: entry.responseEnd,
        duration_ms: entry.duration,
        transfer_size: entry.transferSize,
        encoded_body_size: entry.encodedBodySize,
        decoded_body_size: entry.decodedBodySize,
      })),
    }));
    samples.push({
      sample,
      cold,
      warm,
      network: cartographyNetwork(pageProfile),
      page_errors: pageErrors,
      request_failures: requestFailures.filter((item) => !item.url.includes("cyberjapandata.gsi.go.jp")),
      basemap_failures: requestFailures.filter((item) => item.url.includes("cyberjapandata.gsi.go.jp")),
    });
    await context.close();
  }
} finally {
  await browser.close();
}

const paths = ["building_use", "building", "facility", "road"];
const medians = {};
for (const phase of ["cold", "warm"]) {
  medians[phase] = {};
  for (const label of paths) {
    medians[phase][label] = {
      ready_ms: median(samples.map((item) => item[phase][label].ready_ms)),
      compositor_stable_ms: median(samples.map((item) => item[phase][label].compositor_stable_ms)),
      first_source_ready_ms: median(samples.map((item) => item[phase][label].first_source_ready_ms).filter((value) => value !== null)),
      camera_complete_ms: median(samples.map((item) => item[phase][label].camera_complete_ms).filter((value) => value !== null)),
      map_idle_ms: median(samples.map((item) => item[phase][label].map_idle_ms).filter((value) => value !== null)),
      set_data_count: median(samples.map((item) => item[phase][label].calls.filter((call) => call.method === "setData").length)),
      set_data_feature_count: median(samples.map((item) => item[phase][label].calls
        .filter((call) => call.method === "setData")
        .reduce((total, call) => total + (call.feature_count ?? 0), 0))),
      paint_layout_filter_count: median(samples.map((item) => item[phase][label].calls
        .filter((call) => ["setPaintProperty", "setLayoutProperty", "setFilter"].includes(call.method)).length)),
      map_recreation_count: samples.filter((item) => item[phase][label].map_recreated).length,
    };
  }
}

const profile = {
  schema_version: "citygap.cartographic-performance-profile@1",
  generated_at: new Date().toISOString(),
  branch: execFileSync("git", ["branch", "--show-current"], { cwd: repositoryRoot, encoding: "utf8" }).trim(),
  commit: execFileSync("git", ["rev-parse", "HEAD"], { cwd: repositoryRoot, encoding: "utf8" }).trim(),
  base_url: baseUrl,
  sample_count: sampleCount,
  conditions: {
    browser_context_per_sample: "fresh",
    reduced_motion: true,
    service_worker: "blocked",
    external_basemap: "intentionally blocked so local cartographic readiness is measured under the documented degraded state",
    cold_definition: "first path activation in a fresh page after the existing C5 full derivative reaches ready",
    warm_definition: "second activation of the same path in the same page with the same semantic ready gate",
    ready_definition: {
      story: "requested story active, public MapLibre sources ready, and first thematic building feature rendered",
      exact_target: "target step active, exact source geometry in public-target, MapLibre source ready, and exact feature rendered",
      facility_reference: "target step active, registered-position marker visible, and essential local Area sources ready",
      compositor: "two animation frames after ready; reported separately",
    },
  },
  assets: assetProfiles,
  medians,
  samples,
  garbage_collection: "not directly observable without intrusive V8 tracing; JS heap/task deltas and long tasks are retained instead",
};

await writeFile(output, `${JSON.stringify(profile, null, 2)}\n`, "utf8");
process.stdout.write(`${JSON.stringify({ output, medians, assets: assetProfiles }, null, 2)}\n`);
