export const GUIDED_TARGET = "533513314";
export const GUIDED_PACK_ID = "maizuru-533513314-plateau-2025-v1";
export const COPY = {
  landingCta: "\u821e\u9db4\u306e\u4f8b\u30921\u5206\u3067\u898b\u308b",
  exploreCta: "\u81ea\u5206\u3067\u5730\u56f3\u3092\u8abf\u3079\u308b",
  questions: [
    "\u3069\u3053\u304c\u6c17\u306b\u306a\u308b\uff1f",
    "\u306a\u305c\u5019\u88dc\u306b\u306a\u3063\u305f\uff1f",
    "\u8857\u306e\u3069\u3053\u3067\u8d77\u304d\u3066\u3044\u308b\uff1f",
    "\u65bd\u7b56\u3092\u5909\u3048\u308b\u3068\u3069\u3046\u306a\u308b\uff1f",
    "\u305d\u306e\u6570\u5b57\u306e\u6839\u62e0\u306f\uff1f",
  ],
  next: [
    "\u7406\u7531\u3092\u898b\u308b",
    "\u5efa\u7269\u30fb\u9053\u8def\u30fb\u5730\u5f62\u3092\u898b\u308b",
    "\u6761\u4ef6\u3092\u5909\u3048\u3066\u6bd4\u3079\u308b",
    "\u6570\u5b57\u306e\u6839\u62e0\u3092\u898b\u308b",
  ],
  evidence: "\u8a73\u3057\u3044\u51fa\u5178\u3092\u898b\u308b",
  advanced: "\u8a73\u3057\u3044\u5206\u6790\u3092\u958b\u304f",
  close: "\u9589\u3058\u308b",
};

function fail(message, detail = "") {
  throw new Error(detail ? message + ": " + detail : message);
}

async function expectVisible(locator, label) {
  const count = await locator.count();
  if (count !== 1) fail(label + " must exist exactly once", String(count));
  if (!await locator.isVisible()) fail(label + " must be visible");
}

async function clickHitTarget(page, locator, label) {
  await expectVisible(locator, label);
  await locator.evaluate((element) => element.scrollIntoView({ block: "nearest", inline: "nearest" }));
  const before = await locator.boundingBox();
  await new Promise((resolve) => setTimeout(resolve, 75));
  const after = await locator.boundingBox();
  if (!before || !after) fail(label + " lost its visible box");
  const x = after.x + after.width / 2;
  const y = after.y + after.height / 2;
  const status = await locator.evaluate((element, point) => {
    const hit = document.elementFromPoint(point.x, point.y);
    const style = getComputedStyle(element);
    return {
      hit: hit === element || element.contains(hit),
      visible: style.visibility !== "hidden" && style.display !== "none",
      enabled: !(element instanceof HTMLButtonElement) || !element.disabled,
      insideViewport: point.x >= 0 && point.x <= innerWidth && point.y >= 0 && point.y <= innerHeight,
    };
  }, { x, y });
  const movement = Math.max(
    Math.abs(before.x - after.x),
    Math.abs(before.y - after.y),
    Math.abs(before.width - after.width),
    Math.abs(before.height - after.height),
  );
  if (!status.visible || !status.enabled || !status.insideViewport || !status.hit || movement > 1) {
    fail(label + " is not a stable human-click target", JSON.stringify({ before, after, ...status, movement }));
  }
  await page.mouse.click(x, y);
}

async function expectText(locator, expected, label) {
  const value = (await locator.innerText()).replace(/\s+/g, " ").trim();
  if (!value.includes(expected)) fail(label + " text mismatch", JSON.stringify({ expected, actual: value }));
}

async function expectAttribute(locator, name, expected, label) {
  const value = await locator.getAttribute(name);
  if (value !== expected) fail(label + " attribute mismatch", JSON.stringify({ name, expected, actual: value }));
}

function numeric(value, label) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) fail(label + " is not numeric", String(value));
  return parsed;
}

const OPTIONAL_ABORT_ERRORS = new Set([
  "net::ERR_ABORTED",
  "net::ERR_CANCELED",
  "NS_BINDING_ABORTED",
]);

export function classifyOptionalNetworkFailure(url, errorText) {
  if (!OPTIONAL_ABORT_ERRORS.has(errorText)) return null;
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  const hostname = parsed.hostname.toLowerCase();
  const pathname = parsed.pathname.toLowerCase();
  if (hostname === "cyberjapandata.gsi.go.jp" && pathname.startsWith("/xyz/")) {
    return "cancelled-gsi-background-tile";
  }
  if (
    hostname === "assets.cms.plateau.reearth.io"
    && /\.(?:b3dm|glb|gltf|json|terrain)$/.test(pathname)
  ) {
    return "cancelled-plateau-stream-asset";
  }
  if (
    hostname === "plateau.geospatial.jp"
    && /\.(?:b3dm|glb|gltf|json|terrain)$/.test(pathname)
  ) {
    return "cancelled-plateau-catalog-asset";
  }
  return null;
}

export function attachBrowserDiagnostics(page) {
  const result = { pageErrors: [], failedRequests: [], errorResponses: [], ignoredOptionalFailures: [] };
  page.on("pageerror", (error) => result.pageErrors.push(error.message));
  page.on("requestfailed", (request) => {
    const item = { url: request.url(), error: request.failure()?.errorText ?? "unknown" };
    const reason = classifyOptionalNetworkFailure(item.url, item.error);
    if (reason) result.ignoredOptionalFailures.push({ ...item, reason });
    else result.failedRequests.push(item);
  });
  page.on("response", (response) => {
    if (response.status() >= 400) result.errorResponses.push({ url: response.url(), status: response.status() });
  });
  return result;
}

export function assertNoCriticalBrowserErrors(result) {
  if (result.pageErrors.length || result.failedRequests.length || result.errorResponses.length) {
    fail("critical browser diagnostics", JSON.stringify(result));
  }
}

export async function assertLanding(page) {
  await page.waitForSelector('.showcase-landing[data-experience="landing"]', { timeout: 90_000 });
  await expectVisible(page.getByRole("heading", { name: "CITY GAP", exact: true }), "landing title");
  await expectText(page.locator(".landing-lead"), "\u9ad8\u9f62\u8005\u304c\u591a\u3044\u306e\u306b\u3001\u4ea4\u901a\u3084\u533b\u7642\u3078\u5c4a\u304d\u306b\u304f\u3044\u5730\u57df\u3092\u898b\u3064\u3051\u307e\u3059\u3002", "landing lead");
  await expectText(page.locator(".landing-support"), "500m\u3067\u5019\u88dc\u3092\u898b\u3064\u3051\u3001PLATEAU\u306e\u5efa\u7269\u30fb\u9053\u8def\u30fb\u5730\u5f62\u307e\u3067\u6398\u308a\u4e0b\u3052\u3066\u78ba\u8a8d\u3057\u307e\u3059\u3002", "landing support");
  await expectVisible(page.getByRole("button", { name: COPY.landingCta, exact: true }), "landing primary CTA");
  await expectVisible(page.getByRole("button", { name: COPY.exploreCta, exact: true }), "landing secondary CTA");
  const promises = page.locator(".landing-promises > div");
  if (await promises.count() !== 3) fail("landing promises must total three", String(await promises.count()));
  for (const text of ["\u898b\u3064\u3051\u308b", "\u6398\u308a\u4e0b\u3052\u308b", "\u6bd4\u8f03\u3059\u308b"]) await expectText(page.locator(".landing-promises"), text, "landing promises");
  if (await page.locator(".task-navigation, .layer-controls, .resolution-rail, .analysis-lens-rail").count()) fail("advanced controls leaked into landing");
}

export async function startGuided(page) {
  const button = page.getByRole("button", { name: COPY.landingCta, exact: true });
  await expectVisible(button, "landing primary CTA");
  await clickHitTarget(page, button, "landing primary CTA");
  await assertGuidedStep(page, 1);
}

async function assertGuidedShell(page, step) {
  const root = page.locator('.guided-showcase[data-experience="guided"][data-guided-step="' + step + '"]');
  await root.waitFor({ state: "visible", timeout: 90_000 });
  await expectText(page.locator(".guided-progress-row"), step + " / 5", "guided progress");
  await expectText(page.locator("#guided-question"), COPY.questions[step - 1], "current question");
  await expectAttribute(page.locator('.guided-progress-row li[aria-current="step"]'), "aria-label", step + " / 5 " + COPY.questions[step - 1], "current progress step");
  if (await page.locator(".task-navigation, .layer-controls, .resolution-rail, .analysis-lens-rail, .map-mode-switch").count()) fail("advanced controls leaked into guided step " + step);
  if (await page.locator(".guided-actions .guided-next").count() !== 1) fail("guided step " + step + " must have one primary action");
  if (await page.locator(".guided-actions .guided-back").count() !== 1) fail("guided step " + step + " must have one secondary action");
}

export async function assertGuidedStep(page, step) {
  await assertGuidedShell(page, step);
  const sheet = page.locator(".guided-step-sheet");
  if (step === 1) {
    await expectAttribute(page.locator(".guided-place-card"), "data-guided-target", GUIDED_TARGET, "guided target");
    for (const text of ["\u5e38\u56e3\u5730\u524d\u5468\u8fba", "23\u4f4d", "495\u30e1\u30c3\u30b7\u30e5", GUIDED_TARGET]) await expectText(sheet, text, "where step");
    await expectText(sheet, "\u5371\u967a\u5ea6\u3084\u653f\u7b56\u512a\u5148\u9806\u4f4d\u3067\u306f\u3042\u308a\u307e\u305b\u3093", "rank boundary");
  } else if (step === 2) {
    const facts = page.locator(".guided-primary-facts [data-primary-fact]");
    if (await facts.count() !== 3) fail("why step must expose exactly three primary facts", String(await facts.count()));
    await expectText(page.locator('[data-primary-fact="elderly"]'), "200\u4eba", "elderly fact");
    await expectText(page.locator('[data-primary-fact="transport"]'), "563m", "transport fact");
    await expectText(page.locator('[data-primary-fact="medical"]'), "1.45km", "medical fact");
    await expectText(page.locator(".guided-optional-fact"), "471\u4eba", "optional population fact");
  } else if (step === 3) {
    for (const text of ["500m", "296\u68df", "135\u9762", "\u5b9f\u969b\u306ePLATEAU\u5efa\u7269", "PLATEAU\u306e\u5730\u5f62"]) await expectText(page.locator(".resolution-lift"), text, "PLATEAU resolution lift");
    const threeDRenderer = page.locator('.plateau-3d-shell[data-ui-mode="guided"]');
    const staticRenderer = page.locator('.guided-static-map[data-render-source="verified-section"]');
    const threeDCount = await threeDRenderer.count();
    const staticCount = await staticRenderer.count();
    if (threeDCount + staticCount !== 1) {
      fail("step 3 must mount exactly one verified renderer", JSON.stringify({ threeDCount, staticCount }));
    }
    await expectVisible(threeDCount === 1 ? threeDRenderer : staticRenderer, "guided verified renderer");
    const path = await page.locator(".guided-showcase").getAttribute("data-guided-render-path");
    if (!["static-section", "three-d"].includes(path)) fail("guided render path must be honest", String(path));
    const section = page.locator('.urban-section[data-transect-ready="true"]');
    await section.waitFor({ state: "attached", timeout: 60_000 });
    if (numeric(await section.getAttribute("data-building-count"), "section buildings") <= 0) fail("actual section has no buildings");
    if (numeric(await section.getAttribute("data-road-count"), "section roads") <= 0) fail("actual section has no roads");
    if (numeric(await section.getAttribute("data-terrain-covered"), "section terrain coverage") <= 0) fail("actual section has no terrain coverage");
    const interactiveBuildings = page.locator('.urban-section[data-ui-mode="guided"] [data-section-building][role="button"], .urban-section[data-ui-mode="guided"] [data-section-building][tabindex="0"]');
    if (await interactiveBuildings.count() !== 0) fail("guided section buildings must not expose unsupported interaction");
  } else if (step === 4) {
    for (const text of ["563m", "30m", "\u2212533m"]) await expectText(page.locator(".guided-comparison"), text, "scenario comparison");
    await expectText(sheet, "\u5b9f\u65bd\u52b9\u679c\u306e\u4e88\u6e2c\u3067\u306f\u3042\u308a\u307e\u305b\u3093", "scenario boundary");
    await page.locator('.urban-section[data-counterfactual-ready="true"]').waitFor({ state: "attached", timeout: 30_000 });
    await expectAttribute(page.locator(".urban-section"), "data-counterfactual-ready", "true", "scenario section");
  } else if (step === 5) {
    const sources = page.locator(".guided-sources [data-source-id]");
    if (await sources.count() !== 5) fail("evidence step must expose five source groups", String(await sources.count()));
    const expected = {
      population: ["\u56fd\u52e2\u8abf\u67fb", "2020"],
      transport: ["\u99c5\u30fb\u30d0\u30b9\u505c", "2025", "2022"],
      medical: ["\u533b\u7642\u65bd\u8a2d\u30c7\u30fc\u30bf", "2020"],
      plateau: ["PLATEAU \u821e\u9db4\u5e02", "2025"],
      method: ["CITY GAP\u8a08\u7b97\u65b9\u6cd5", "500m"],
    };
    for (const [id, values] of Object.entries(expected)) for (const text of values) await expectText(page.locator('[data-source-id="' + id + '"]'), text, "source " + id);
  }
}

export async function advanceGuided(page, currentStep) {
  const button = page.getByRole("button", { name: COPY.next[currentStep - 1], exact: true });
  await expectVisible(button, "step " + currentStep + " primary action");
  await clickHitTarget(page, button, "step " + currentStep + " primary action");
  await assertGuidedStep(page, currentStep + 1);
}

export async function reviewEvidenceAndOpenAdvanced(page) {
  const button = page.getByRole("button", { name: COPY.evidence, exact: true });
  await expectVisible(button, "evidence CTA");
  await clickHitTarget(page, button, "evidence CTA");
  const dialog = page.getByRole("dialog");
  await dialog.waitFor({ state: "visible", timeout: 30_000 });
  for (const text of ["\u6839\u62e0", "\u516c\u5171\u4ea4\u901a", "\u30c7\u30fc\u30bf", "\u8a08\u7b97", "P11 2022", "PLATEAU\u99c5 2025"]) await expectText(dialog, text, "evidence dialog");
  const close = dialog.getByRole("button", { name: COPY.close, exact: true });
  await expectVisible(close, "evidence close");
  if (!await close.evaluate((element) => element === document.activeElement)) fail("evidence dialog must focus its close button");
  await page.keyboard.press("Tab");
  if (!await dialog.evaluate((element) => element.contains(document.activeElement))) fail("Tab escaped the evidence dialog");
  await page.keyboard.press("Shift+Tab");
  if (!await dialog.evaluate((element) => element.contains(document.activeElement))) fail("Shift+Tab escaped the evidence dialog");
  await page.keyboard.press("Escape");
  await dialog.waitFor({ state: "hidden" });
  const advanced = page.getByRole("button", { name: COPY.advanced, exact: true });
  await expectVisible(advanced, "advanced CTA after evidence");
  if (!await advanced.evaluate((element) => element === document.activeElement)) fail("evidence dialog did not restore focus to the advanced CTA");
  await clickHitTarget(page, advanced, "advanced CTA");
  return assertAdvancedReady(page);
}

export async function assertAdvancedReady(page) {
  await page.locator('.product-app[data-experience="advanced"]').waitFor({ state: "visible", timeout: 90_000 });
  await expectVisible(page.locator(".task-navigation"), "advanced task navigation");
  const params = new URL(page.url()).searchParams;
  if ((params.get("selection") ?? params.get("mesh")) !== GUIDED_TARGET) fail("advanced transition did not retain target", page.url());
  await page.waitForFunction(
    ({ packId }) => {
      const section = document.querySelector(".urban-section");
      const sectionReady = section?.getAttribute("data-transect-ready") === "true"
        && section.getAttribute("data-pack-id") === packId
        && Number(section.getAttribute("data-building-count") ?? 0) > 0
        && Number(section.getAttribute("data-road-count") ?? 0) > 0
        && Number(section.getAttribute("data-terrain-covered") ?? 0) > 0;
      const renderer = document.querySelector('.plateau-3d-shell[data-ui-mode="advanced"]');
      const rendererReady = renderer?.getAttribute("data-ready") === "true";
      return sectionReady || rendererReady;
    },
    { packId: GUIDED_PACK_ID },
    { timeout: 120_000 },
  );
  const state = await page.evaluate(({ target, packId }) => {
    const params = new URL(location.href).searchParams;
    const retainedTarget = (params.get("selection") ?? params.get("mesh")) === target;
    const section = document.querySelector(".urban-section");
    const sectionState = {
      present: Boolean(section),
      ready: section?.getAttribute("data-transect-ready") === "true",
      pack_id: section?.getAttribute("data-pack-id") ?? null,
      buildings: Number(section?.getAttribute("data-building-count") ?? 0),
      roads: Number(section?.getAttribute("data-road-count") ?? 0),
      terrain_covered: Number(section?.getAttribute("data-terrain-covered") ?? 0),
    };
    sectionState.verified = sectionState.ready
      && sectionState.pack_id === packId
      && sectionState.buildings > 0
      && sectionState.roads > 0
      && sectionState.terrain_covered > 0;
    const renderer = document.querySelector('.plateau-3d-shell[data-ui-mode="advanced"]');
    const rendererState = {
      present: Boolean(renderer),
      engine: renderer?.getAttribute("data-map-engine") ?? null,
      ui_mode: renderer?.getAttribute("data-ui-mode") ?? null,
      ready: renderer?.getAttribute("data-ready") === "true",
    };
    const readiness = [
      ...(sectionState.verified ? ["verified-section"] : []),
      ...(rendererState.ready ? ["ready-renderer"] : []),
    ];
    return {
      complete: retainedTarget && readiness.length > 0,
      retained_target: retainedTarget,
      target_id: target,
      task_navigation_visible: Boolean(document.querySelector(".task-navigation")),
      readiness_path: readiness.join("+"),
      section: sectionState,
      renderer: rendererState,
    };
  }, { target: GUIDED_TARGET, packId: GUIDED_PACK_ID });
  if (!state.complete || !state.task_navigation_visible) fail("advanced workspace is not capture-ready", JSON.stringify(state));
  return state;
}

export async function assertMobileGuidedLayout(page) {
  const result = await page.evaluate(() => {
    const rect = (selector) => {
      const value = document.querySelector(selector)?.getBoundingClientRect();
      return value && { top: value.top, bottom: value.bottom, width: value.width, height: value.height };
    };
    return { innerWidth, innerHeight, scrollWidth: document.documentElement.scrollWidth, map: rect(".guided-map-stage"), sheet: rect(".guided-step-sheet"), action: rect(".guided-actions .guided-next") };
  });
  if (result.innerWidth !== 390 || result.innerHeight !== 844) fail("mobile viewport mismatch", JSON.stringify(result));
  if (result.scrollWidth > result.innerWidth + 1) fail("mobile page has horizontal overflow", JSON.stringify(result));
  if (!result.map || result.map.top > 60 || result.map.width < 389) fail("mobile map is not top/background", JSON.stringify(result));
  if (!result.sheet || result.sheet.top <= result.map.top || Math.abs(result.sheet.bottom - result.innerHeight) > 2) fail("mobile sheet is not bottom anchored", JSON.stringify(result));
  if (!result.action || result.action.height < 44 || result.action.top < 0 || result.action.bottom > result.innerHeight) fail("mobile CTA is not visible/touch sized", JSON.stringify(result));
}
