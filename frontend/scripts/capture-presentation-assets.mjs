import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { chromium } from "playwright-core";

process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY = "1";

const args = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const key = process.argv[index];
  if (!key.startsWith("--")) continue;
  const value = process.argv[index + 1];
  args.set(key, value && !value.startsWith("--") ? value : "true");
  if (value && !value.startsWith("--")) index += 1;
}

const repositoryRoot = path.resolve(process.cwd(), "..");
const rootUrl = new URL(args.get("--url") ?? "https://catlover-bot.github.io/plateau-city-gap/");
rootUrl.search = "";
rootUrl.hash = "";
const outputDirectory = path.resolve(args.get("--output") ?? "/tmp/citygap-presentation-images-next");
const sourceCommit = execFileSync("git", ["rev-parse", `${args.get("--source-commit") ?? "HEAD"}^{commit}`], { cwd: repositoryRoot, encoding: "utf8" }).trim();
const sourceBranch = execFileSync("git", ["branch", "--show-current"], { cwd: repositoryRoot, encoding: "utf8" }).trim();
const pagesRunId = args.get("--pages-run-id") ?? null;
const captureClockSource = args.get("--clock-source") ?? "runtime";
const hostPowershellExecutable = args.get("--host-powershell") ?? "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const ffmpeg = args.get("--ffmpeg") ?? "ffmpeg";
const selectedArea = "533513314";
const sectionArtifactId = "maizuru-533513314-plateau-2025-v1";
const diagnostics = [];
const records = [];

if (!new Set(["runtime", "host-powershell"]).has(captureClockSource)) throw new Error("--clock-source must be runtime or host-powershell");

const specifications = [
  { filename: "01-city-gap-overview-16x9.png", state: "guided-intro", purpose: "Service overview and first spatial impression", story: "intro", mesh: selectedArea, viewport: { width: 1920, height: 1080 }, dpr: 1 },
  { filename: "02-area-selection-16x9.png", state: "guided-scene-1-selected-area", purpose: "Map and Area list selection relationship", story: "find", mesh: selectedArea, viewport: { width: 1920, height: 1080 }, dpr: 1 },
  { filename: "03-plateau-section-hero-16x9.png", state: "guided-scene-2-section-hero", purpose: "PLATEAU buildings, roads, A–B line, Urban Section, and inspector", story: "understand", mesh: selectedArea, viewport: { width: 1920, height: 1080 }, dpr: 1 },
  { filename: "04-urban-section-closeup-16x9.png", state: "guided-scene-2-section-closeup", purpose: "Urban Section axes, endpoints, terrain, buildings, and named roads", story: "understand", mesh: selectedArea, viewport: { width: 1920, height: 1080 }, dpr: 1, sectionCloseup: true },
  { filename: "05-exact-field-target-16x9.png", state: "guided-scene-3-exact-road", purpose: "Exact PLATEAU road target and four unverified field checks", story: "verify", mesh: selectedArea, viewport: { width: 1920, height: 1080 }, dpr: 1 },
  { filename: "06-area-switching-16x9.png", state: "guided-scene-2-another-area", purpose: "A second real Area with different geometry and context capability", story: "understand", mesh: "533512362", viewport: { width: 1920, height: 1080 }, dpr: 1 },
  { filename: "07-mobile-workflow-portrait.png", state: "guided-scene-2-mobile-section", purpose: "Mobile map-to-Section workflow", story: "understand", mesh: selectedArea, viewport: { width: 390, height: 844 }, dpr: 2, mobileSection: true },
  { filename: "08-advanced-evidence-16x9.png", state: "advanced-evidence-ready", purpose: "Loaded specialist analysis and evidence surface", experience: "advanced", viewport: { width: 1920, height: 1080 }, dpr: 1 },
];

const sha256 = (value) => createHash("sha256").update(value).digest("hex");

function captureTimestamp() {
  if (captureClockSource === "host-powershell") {
    const hostTimestamp = execFileSync(hostPowershellExecutable, ["-NoProfile", "-NonInteractive", "-Command", "[DateTimeOffset]::UtcNow.ToString('o')"], { encoding: "utf8" }).trim();
    const parsed = new Date(hostTimestamp);
    if (!Number.isFinite(parsed.valueOf())) throw new Error(`host clock returned an invalid timestamp: ${hostTimestamp}`);
    return parsed.toISOString();
  }
  return new Date().toISOString();
}

function pageUrl(specification) {
  const target = new URL(rootUrl);
  if (specification.experience === "advanced") {
    target.search = `?experience=advanced&city=maizuru&task=operate&scene=gap_discovery&mesh=${selectedArea}&resolution=mesh&mapMode=map2d&inspector=open`;
  } else {
    target.search = `?experience=guided&story=${specification.story}&selectionType=mesh&selection=${specification.mesh}&mesh=${specification.mesh}`;
  }
  return target.toString();
}

function watch(page, label) {
  page.on("pageerror", (error) => diagnostics.push({ label, kind: "page", message: error.message }));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("cyberjapandata.gsi.go.jp")) diagnostics.push({ label, kind: "console", message: message.text() });
  });
  page.on("requestfailed", (request) => {
    const reason = request.failure()?.errorText ?? "unknown";
    if (reason !== "net::ERR_ABORTED" && request.url().startsWith(rootUrl.origin)) diagnostics.push({ label, kind: "request", url: request.url(), message: reason });
  });
  page.on("response", (response) => {
    if (response.status() >= 400 && response.url().startsWith(rootUrl.origin)) diagnostics.push({ label, kind: "http", url: response.url(), status: response.status() });
  });
}

async function settle(page) {
  await page.evaluate(async () => {
    await document.fonts?.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
}

async function waitForState(page, specification) {
  await page.goto(pageUrl(specification), { waitUntil: "domcontentloaded", timeout: 180_000 });
  if (specification.experience === "advanced") {
    await page.locator('.product-app[data-experience="advanced"] .map-stage').waitFor({ timeout: 180_000 });
    await page.waitForFunction(() => document.documentElement.dataset.captureStrictReady === "true" && document.documentElement.dataset.visualReady === "true", null, { timeout: 180_000 });
  } else {
    const contextStatus = specification.story === "intro" || specification.story === "find" ? "idle" : "ready";
    await page.locator(`.guided-spatial-app[data-guided-story="${specification.story}"][data-area-id="${specification.mesh}"][data-context-status="${contextStatus}"]`).waitFor({ timeout: 180_000 });
    await page.waitForFunction(() => document.querySelector(".analytical-map-shell")?.getAttribute("data-guided-visual-ready") === "true", null, { timeout: 180_000 });
    if (specification.story === "understand" && specification.mesh === selectedArea) {
      await page.locator(`.guided-spatial-app[data-section-pack="${sectionArtifactId}"]`).waitFor({ timeout: 180_000 });
      await page.locator('.urban-section[data-terrain-samples="94"][data-direct-building-count="17"][data-direct-road-count="14"][data-annotation-overlap-count="0"]').waitFor({ state: specification.mobileSection ? "attached" : "visible", timeout: 180_000 });
    }
    if (specification.story === "verify") {
      await page.locator('.guided-spatial-app[data-target-kind="road"][data-target-resolution="exact"]').waitFor({ timeout: 180_000 });
      const checks = await page.locator(".guided-check-list > li").count();
      if (checks !== 4) throw new Error(`expected four field checks, received ${checks}`);
    }
    if (specification.mobileSection) {
      await page.getByRole("button", { name: "街の断面", exact: true }).click();
      await page.locator(".guided-section-dock.mobile-visible").waitFor({ state: "visible", timeout: 180_000 });
    }
    await page.waitForFunction(() => Boolean(document.querySelector(".analytical-map-canvas")?.__cityGapMap?.isStyleLoaded()), null, { timeout: 180_000 });
  }
  await settle(page);
}

async function readiness(page, specification) {
  return page.evaluate(({ experience, expectedMesh, sectionPack }) => {
    const visible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
    };
    const root = document.querySelector(".guided-spatial-app");
    const mapCanvas = document.querySelector(".analytical-map-canvas");
    const map = mapCanvas?.__cityGapMap;
    const section = document.querySelector(".urban-section");
    const loading = [...document.querySelectorAll(".state-screen, [aria-busy='true']")].filter(visible);
    return {
      experience: experience ?? "guided",
      story: root?.getAttribute("data-guided-story") ?? null,
      area: root?.getAttribute("data-area-id") ?? expectedMesh,
      context_status: root?.getAttribute("data-context-status") ?? null,
      target_kind: root?.getAttribute("data-target-kind") ?? null,
      target_key: root?.getAttribute("data-target-key") ?? null,
      target_resolution: root?.getAttribute("data-target-resolution") ?? null,
      section_pack: root?.getAttribute("data-section-pack") ?? null,
      expected_section_pack: sectionPack,
      section_overlap_count: section ? Number(section.getAttribute("data-annotation-overlap-count")) : null,
      section_terrain_samples: section ? Number(section.getAttribute("data-terrain-samples")) : null,
      field_check_count: document.querySelectorAll(".guided-check-list > li").length,
      map_initialization_count: window.__cityGapMapInitCount ?? null,
      map_style_loaded: Boolean(map?.isStyleLoaded()),
      map_render_state: document.querySelector(".analytical-map-shell")?.getAttribute("data-map-render-state") ?? null,
      map_width: Math.round(mapCanvas?.getBoundingClientRect().width ?? 0),
      map_height: Math.round(mapCanvas?.getBoundingClientRect().height ?? 0),
      fonts_ready: document.fonts.status === "loaded",
      strict_ready: document.documentElement.dataset.captureStrictReady ?? null,
      visual_ready: document.documentElement.dataset.visualReady ?? null,
      loading_surface_count: loading.length,
      horizontal_overflow_px: Math.max(0, document.documentElement.scrollWidth - innerWidth),
      unfinished_loading_copy: /読み込み中|loading/i.test(document.body.innerText),
      debug_surface_count: document.querySelectorAll("vite-error-overlay, .debug, [data-debug='true']").length,
    };
  }, { experience: specification.experience, expectedMesh: specification.mesh ?? selectedArea, sectionPack: sectionArtifactId });
}

async function capture(page, specification) {
  const target = path.join(outputDirectory, specification.filename);
  if (specification.sectionCloseup) {
    const section = page.locator(".guided-section-dock");
    await section.focus();
    await page.keyboard.press("ArrowRight");
    await settle(page);
    const sourceCrop = path.join(outputDirectory, ".urban-section-source.png");
    await section.screenshot({ path: sourceCrop, animations: "disabled", timeout: 180_000 });
    execFileSync(ffmpeg, ["-y", "-hide_banner", "-loglevel", "error", "-i", sourceCrop, "-vf", "scale=1920:-2:flags=lanczos,pad=1920:1080:0:(oh-ih)/2:color=#f7f6ef", "-frames:v", "1", target]);
    await rm(sourceCrop);
  } else {
    await page.screenshot({ path: target, fullPage: false, animations: "disabled", timeout: 180_000 });
  }
  const buffer = await readFile(target);
  const stateReadiness = await readiness(page, specification);
  const stateDiagnostics = diagnostics.filter((item) => item.label === specification.state);
  if (stateDiagnostics.length || !stateReadiness.fonts_ready || !stateReadiness.map_style_loaded || stateReadiness.loading_surface_count || stateReadiness.unfinished_loading_copy || stateReadiness.horizontal_overflow_px || stateReadiness.debug_surface_count) throw new Error(`capture gate failed for ${specification.state}: ${JSON.stringify({ stateReadiness, stateDiagnostics })}`);
  records.push({
    filename: specification.filename,
    purpose: specification.purpose,
    state: specification.state,
    url: page.url(),
    captured_at: captureTimestamp(),
    viewport: specification.viewport,
    dpr: specification.dpr,
    output_dimensions: specification.dpr === 2 ? { width: specification.viewport.width * 2, height: specification.viewport.height * 2 } : specification.viewport,
    selected_area: specification.mesh ?? selectedArea,
    selected_target: stateReadiness.target_key,
    bytes: buffer.length,
    sha256: sha256(buffer),
    derived_crop: specification.sectionCloseup ? { method: "production DOM Section dock screenshot, proportionally scaled and padded to 1920x1080", background: "#f7f6ef" } : null,
    readiness: stateReadiness,
    diagnostics: stateDiagnostics,
  });
  process.stderr.write(`[presentation-images] saved ${specification.filename}\n`);
}

async function verifyLiveBuild() {
  const liveIndex = Buffer.from(await (await fetch(rootUrl)).arrayBuffer());
  const localIndex = await readFile(path.join(process.cwd(), "dist/index.html"));
  if (!liveIndex.equals(localIndex)) throw new Error("live index does not match the local build of the declared source commit");
  const assetPaths = [...liveIndex.toString("utf8").matchAll(/(?:src|href)="([^"]+\.(?:js|css))"/g)].map((match) => match[1]);
  const assets = [];
  for (const assetPath of assetPaths) {
    const live = Buffer.from(await (await fetch(new URL(assetPath, rootUrl))).arrayBuffer());
    const local = await readFile(path.join(process.cwd(), "dist", assetPath.replace("/plateau-city-gap/", "")));
    if (!live.equals(local)) throw new Error(`live asset does not match local build: ${assetPath}`);
    assets.push({ path: assetPath, bytes: live.length, sha256: sha256(live), matches_local_build: true });
  }
  return { index: { bytes: liveIndex.length, sha256: sha256(liveIndex), matches_local_build: true }, assets };
}

async function createContactSheet(browser) {
  const items = await Promise.all(records.map(async (record, index) => ({ number: String(index + 1).padStart(2, "0"), filename: record.filename, purpose: record.purpose, dataUrl: `data:image/png;base64,${(await readFile(path.join(outputDirectory, record.filename))).toString("base64")}` })));
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  await page.setContent(`<!doctype html><html lang="en"><meta charset="utf-8"><style>
    *{box-sizing:border-box}body{margin:0;padding:42px 48px;background:#f7f6ef;color:#162d2b;font-family:Arial,"Noto Sans JP",sans-serif}
    h1{margin:0 0 26px;font-size:32px;letter-spacing:.02em}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:24px 20px}
    figure{margin:0;background:#fff;border:1px solid #b8c1bc;padding:10px;height:445px;display:flex;flex-direction:column}
    img{width:100%;height:340px;object-fit:contain;background:#e7ece8}figcaption{padding:10px 4px 0;line-height:1.28}
    strong{display:block;font-size:17px;margin-bottom:5px}.purpose{font-size:14px;color:#46625d}.source{position:fixed;right:48px;top:49px;font-size:14px;color:#60726d}
  </style><body><h1>CITY GAP · production presentation images</h1><div class="source">UI ${sourceCommit.slice(0, 12)} · Pages ${pagesRunId}</div><main class="grid">${items.map((item) => `<figure><img src="${item.dataUrl}"><figcaption><strong>${item.number} · ${item.filename}</strong><span class="purpose">${item.purpose}</span></figcaption></figure>`).join("")}</main></body></html>`, { waitUntil: "load" });
  await page.screenshot({ path: path.join(outputDirectory, "contact-sheet.png"), animations: "disabled" });
  await context.close();
  const buffer = await readFile(path.join(outputDirectory, "contact-sheet.png"));
  return { filename: "contact-sheet.png", width: 1920, height: 1080, bytes: buffer.length, sha256: sha256(buffer) };
}

if (!pagesRunId) throw new Error("--pages-run-id is required for production presentation capture");
const protectedOutputPaths = new Set([path.parse(outputDirectory).root, repositoryRoot, process.cwd()]);
if (protectedOutputPaths.has(outputDirectory)) throw new Error(`refusing unsafe output directory: ${outputDirectory}`);
const temporaryRoot = path.resolve(tmpdir());
const temporaryRelative = path.relative(temporaryRoot, outputDirectory);
if (temporaryRelative.startsWith("..") || path.isAbsolute(temporaryRelative) || !path.basename(outputDirectory).startsWith("citygap-")) {
  throw new Error(`presentation capture output must be a named citygap-* directory under ${temporaryRoot}`);
}
await rm(outputDirectory, { recursive: true, force: true });
await mkdir(outputDirectory, { recursive: true });
const liveBuild = await verifyLiveBuild();
const browser = await chromium.launch({ executablePath, headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"] });
let contactSheet;
try {
  for (const specification of specifications) {
    const context = await browser.newContext({ viewport: specification.viewport, deviceScaleFactor: specification.dpr, locale: "ja-JP", reducedMotion: "reduce", serviceWorkers: "block" });
    const page = await context.newPage();
    page.setDefaultTimeout(180_000);
    watch(page, specification.state);
    await waitForState(page, specification);
    await capture(page, specification);
    await context.close();
  }
  contactSheet = await createContactSheet(browser);
} finally {
  await browser.close();
}

if (diagnostics.length) throw new Error(`presentation capture diagnostics are not empty: ${JSON.stringify(diagnostics, null, 2)}`);
const manifest = {
  schema_version: "citygap.production-presentation-images@1",
  generated_at: captureTimestamp(),
  source_production_url: rootUrl.toString(),
  source_branch: sourceBranch,
  source_commit: sourceCommit,
  pages_run_id: pagesRunId,
  protocol: "production-only; browser chrome hidden; reduced motion; fonts, map, Area, Section, target and strict Advanced readiness; stable compositor frames",
  capture_clock: { source: captureClockSource === "host-powershell" ? "Windows host clock queried for each timestamp" : "runtime clock", offset_seconds: null, executable: captureClockSource === "host-powershell" ? hostPowershellExecutable : null },
  tools: { playwright: JSON.parse(await readFile(path.join(process.cwd(), "node_modules/playwright-core/package.json"), "utf8")).version, chromium_executable: executablePath, ffmpeg: execFileSync(ffmpeg, ["-version"], { encoding: "utf8" }).split("\n")[0].trim() },
  live_build: liveBuild,
  images: records,
  contact_sheet: contactSheet,
  diagnostics,
  passed: records.length === specifications.length && diagnostics.length === 0,
  human_review: { visual_quality: "READY_FOR_SELF_VISUAL_REVIEW", presentation: "READY_FOR_DEMO_REVIEW", human_test: "AWAITING_HUMAN_TEST", municipal_workflow: "AWAITING_MUNICIPAL_WORKFLOW_REVIEW" },
};
await writeFile(path.join(outputDirectory, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
process.stdout.write(`${JSON.stringify({ outputDirectory, images: records.length, contactSheet, diagnostics: diagnostics.length, sourceCommit, pagesRunId, passed: manifest.passed }, null, 2)}\n`);
