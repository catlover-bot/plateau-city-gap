import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import {
  access,
  mkdir,
  mkdtemp,
  lstat,
  readFile,
  readdir,
  rename,
  rm,
  readlink,
  stat,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";
import {
  advanceGuided,
  GUIDED_PACK_ID,
  assertGuidedStep,
  assertLanding,
  assertMobileGuidedLayout,
  assertNoCriticalBrowserErrors,
  attachBrowserDiagnostics,
  reviewEvidenceAndOpenAdvanced,
  startGuided,
} from "./guided-browser.mjs";

process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY = "1";

const CAPTURE_VERSION = "guided-first-run-capture@2.0.0";
const RENDERER_ARGS = ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist", "--use-gl=swiftshader"];
const NAMES = [
  "01-landing.png",
  "02-where.png",
  "03-why.png",
  "04-plateau-detail.png",
  "05-what-if.png",
  "06-evidence.png",
  "07-advanced.png",
  "08-mobile.png",
];

const parameters = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const argument = process.argv[index];
  if (!argument.startsWith("--")) continue;
  const value = process.argv[index + 1];
  parameters.set(argument, value && !value.startsWith("--") ? value : "true");
  if (value && !value.startsWith("--")) index += 1;
}

const repositoryRoot = path.resolve(process.cwd(), "..");
const baseUrl = parameters.get("--url") ?? "http://127.0.0.1:4173/plateau-city-gap/";
const outputDirectory = path.resolve(process.cwd(), parameters.get("--output") ?? "../docs/assets/current");
const diagnosticDirectory = path.resolve(process.cwd(), parameters.get("--diagnostics") ?? "../analysis/outputs/real/visual-readiness-failures");
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const repositoryHead = execFileSync("git", ["rev-parse", "HEAD"], { cwd: repositoryRoot, encoding: "utf8" }).trim();
const renderSourceCommit = execFileSync(
  "git",
  ["rev-parse", (process.env.CITYGAP_RENDER_SOURCE_COMMIT ?? repositoryHead) + "^{commit}"],
  { cwd: repositoryRoot, encoding: "utf8" },
).trim();
const captureAssetCommit = execFileSync(
  "git",
  ["rev-parse", (process.env.CITYGAP_CAPTURE_ASSET_COMMIT ?? repositoryHead) + "^{commit}"],
  { cwd: repositoryRoot, encoding: "utf8" },
).trim();
const captureScriptPath = fileURLToPath(import.meta.url);
const guidedBrowserPath = path.join(process.cwd(), "scripts/guided-browser.mjs");
const outputParent = path.dirname(outputDirectory);
const outputName = path.basename(outputDirectory);
const canonicalOutput = path.join(repositoryRoot, "docs/assets/current");
const analysisOutputRoot = path.join(repositoryRoot, "analysis/outputs/real");
const temporaryOutputRoot = path.resolve(tmpdir());

function isBelow(candidate, parent) {
  const relative = path.relative(parent, candidate);
  return relative !== "" && !relative.startsWith(".." + path.sep) && relative !== ".." && !path.isAbsolute(relative);
}

if (
  outputDirectory !== canonicalOutput
  && !isBelow(outputDirectory, analysisOutputRoot)
  && !isBelow(outputDirectory, temporaryOutputRoot)
) {
  throw new Error("capture output must be canonical current, an analysis output child, or a temporary-directory child: " + outputDirectory);
}
if ([path.parse(outputDirectory).root, repositoryRoot, process.cwd(), analysisOutputRoot, temporaryOutputRoot].includes(outputDirectory)) {
  throw new Error("refusing a broad capture output target: " + outputDirectory);
}

let stagingDirectory;
const captures = [];
let browser;
let desktopDiagnostics = null;
let mobileDiagnostics = null;
let runtimeEnvironment = null;
let published = false;
let recoveryBackup = null;

function assertManagedSibling(candidate, marker) {
  if (path.dirname(candidate) !== outputParent || !path.basename(candidate).startsWith(marker)) {
    throw new Error("refusing unmanaged temporary path: " + candidate);
  }
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}
async function sha256File(filename) {
  return sha256(await readFile(filename));
}

function gitBuffer(arguments_) {
  return execFileSync("git", arguments_, {
    cwd: repositoryRoot,
    encoding: null,
    maxBuffer: 128 * 1024 * 1024,
    env: { ...process.env, LC_ALL: "C" },
  });
}

function nullDelimitedPaths(value) {
  return value.toString("utf8").split("\0").filter(Boolean);
}

async function pathEvidence(filename) {
  try {
    const details = await lstat(filename);
    if (details.isSymbolicLink()) return { kind: "symlink", content: Buffer.from(await readlink(filename), "utf8") };
    if (details.isFile()) return { kind: "file", content: await readFile(filename) };
    return { kind: "other", content: Buffer.from(String(details.mode), "utf8") };
  } catch (error) {
    if (error?.code === "ENOENT") return { kind: "deleted", content: Buffer.alloc(0) };
    throw error;
  }
}

async function filesBelow(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map((entry) => {
    const target = path.join(directory, entry.name);
    return entry.isDirectory() ? filesBelow(target) : [target];
  }));
  return nested.flat().sort();
}

async function aggregateFileSet(files, relativeRoot) {
  const uniqueFiles = [...new Set(files)].sort();
  const digest = createHash("sha256");
  for (const filename of uniqueFiles) {
    const relative = path.relative(relativeRoot, filename).replaceAll(path.sep, "/");
    const evidence = await pathEvidence(filename);
    digest.update(relative);
    digest.update("\0");
    digest.update(evidence.kind);
    digest.update("\0");
    digest.update(evidence.content);
    digest.update("\0");
  }
  return { sha256: digest.digest("hex"), file_count: uniqueFiles.length };
}

async function frontendSourceEvidence() {
  const frontendRoot = process.cwd();
  const sourceFiles = await filesBelow(path.join(frontendRoot, "src"));
  const buildInputs = [
    "index.html",
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "tsconfig.app.json",
    "tsconfig.node.json",
    "vite.config.ts",
  ].map((filename) => path.join(frontendRoot, filename));
  const presentInputs = [];
  for (const filename of buildInputs) if (await exists(filename)) presentInputs.push(filename);
  return aggregateFileSet([...sourceFiles, ...presentInputs], frontendRoot);
}

async function worktreeEvidence() {
  const status = gitBuffer(["status", "--porcelain=v1", "-z", "--untracked-files=all"]);
  const changedPaths = new Set([
    ...nullDelimitedPaths(gitBuffer(["diff", "--name-only", "-z", "HEAD", "--"])),
    ...nullDelimitedPaths(gitBuffer(["ls-files", "--others", "--exclude-standard", "-z"])),
  ]);
  const orderedPaths = [...changedPaths].sort();
  const digest = createHash("sha256");
  digest.update("citygap.worktree@1\0");
  digest.update(status);
  digest.update("\0");
  for (const relative of orderedPaths) {
    const absolute = path.resolve(repositoryRoot, relative);
    if (absolute !== repositoryRoot && !isBelow(absolute, repositoryRoot)) {
      throw new Error("git reported a path outside the repository: " + relative);
    }
    const evidence = await pathEvidence(absolute);
    digest.update(relative.replaceAll(path.sep, "/"));
    digest.update("\0");
    digest.update(evidence.kind);
    digest.update("\0");
    digest.update(evidence.content);
    digest.update("\0");
  }
  return {
    clean: status.length === 0,
    changed_path_count: orderedPaths.length,
    status_sha256: sha256(status),
    fingerprint_sha256: digest.digest("hex"),
    fingerprint_contract: "git-status+changed-path-content@1",
  };
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]));
  }
  return value;
}

function provenanceFingerprint(value) {
  return sha256(Buffer.from(JSON.stringify(canonicalize(value)), "utf8"));
}

async function runtimeRendererEvidence(page) {
  return page.evaluate(() => {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
    const extension = gl?.getExtension("WEBGL_debug_renderer_info");
    return {
      user_agent: navigator.userAgent,
      webgl_vendor: gl && extension ? gl.getParameter(extension.UNMASKED_VENDOR_WEBGL) : null,
      webgl_renderer: gl && extension ? gl.getParameter(extension.UNMASKED_RENDERER_WEBGL) : null,
    };
  });
}

const dataManifestPath = path.join(process.cwd(), "public/data/manifest.json");
const packManifestPath = path.join(process.cwd(), "public/data/spatial-packs", GUIDED_PACK_ID, "manifest.json");
const publicDataManifest = JSON.parse(await readFile(dataManifestPath, "utf8"));
const packManifest = JSON.parse(await readFile(packManifestPath, "utf8"));
if (packManifest.pack_id !== GUIDED_PACK_ID) {
  throw new Error("spatial-pack manifest ID mismatch: " + String(packManifest.pack_id));
}
const frontendSource = await frontendSourceEvidence();
const frontendDistAssets = await aggregateFileSet(await filesBelow(path.join(process.cwd(), "dist/assets")), path.join(process.cwd(), "dist/assets"));
const worktreeAtCaptureStart = await worktreeEvidence();
const sourceDataIds = [
  "plateau-building-2025:" + packManifest.source_versions.buildings.sha256,
  "plateau-dem-2025:" + packManifest.source_versions.terrain.source_archive_sha256,
  "plateau-road-lod1-maizuru-2025",
  ...publicDataManifest.source_datasets.map((dataset) => dataset.id),
];
const provenanceAtCaptureStart = {
  repository_head: repositoryHead,
  render_source_commit: renderSourceCommit,
  capture_asset_commit: captureAssetCommit,
  frontend_source_sha256: frontendSource.sha256,
  frontend_source_file_count: frontendSource.file_count,
  frontend_dist_asset_sha256: frontendDistAssets.sha256,
  frontend_dist_asset_file_count: frontendDistAssets.file_count,
  capture_script_version: CAPTURE_VERSION,
  capture_script_sha256: await sha256File(captureScriptPath),
  guided_browser_contract_sha256: await sha256File(guidedBrowserPath),
  data_manifest_sha256: await sha256File(dataManifestPath),
  data_manifest_schema_version: publicDataManifest.schema_version,
  pack_id: packManifest.pack_id,
  pack_schema: packManifest.schema,
  pack_content_sha256: packManifest.content_sha256,
  pack_manifest_sha256: packManifest.pack_manifest_sha256,
  pack_manifest_file_sha256: await sha256File(packManifestPath),
  pack_artifact_sha256: Object.fromEntries(
    Object.entries(packManifest.artifacts).map(([name, artifact]) => [name, artifact.sha256]),
  ),
  finding_id: packManifest.finding,
  investigation_id: packManifest.investigation,
  source_data_ids: sourceDataIds,
  worktree: worktreeAtCaptureStart,
  difference_reasons: [
    ...(repositoryHead !== renderSourceCommit ? [{ fields: ["repository_head", "render_source_commit"], reason: "the rendered frontend was built from a different immutable commit" }] : []),
    ...(captureAssetCommit !== renderSourceCommit ? [{ fields: ["capture_asset_commit", "render_source_commit"], reason: "capture assets are assigned to a different immutable commit than rendered source" }] : []),
  ],
};
if (outputDirectory === canonicalOutput && !worktreeAtCaptureStart.clean) {
  throw new Error("refusing canonical docs/assets/current publication from a dirty worktree; commit or clean the source first (fingerprint " + worktreeAtCaptureStart.fingerprint_sha256 + ")");
}

await mkdir(outputParent, { recursive: true });
stagingDirectory = await mkdtemp(path.join(outputParent, "." + outputName + ".staging-"));

async function exists(filename) {
  return access(filename).then(() => true).catch(() => false);
}

async function capture(page, filename, viewport, scene) {
  const { advancedRenderState, ...sceneMetadata } = scene;
  await page.evaluate(() => document.fonts.ready);
  await new Promise((resolve) => setTimeout(resolve, 100));
  if (sceneMetadata.question) {
    const box = await page.locator("#guided-question").boundingBox();
    if (!box || box.y < 0 || box.y + box.height > viewport.height) {
      throw new Error("current question is not readable in " + filename + ": " + JSON.stringify(box));
    }
  }
  const target = path.join(stagingDirectory, filename);
  await page.screenshot({ path: target, fullPage: false, animations: "disabled", timeout: 180_000 });
  const image = await readFile(target);
  if (image.length < 10_000 || image.subarray(1, 4).toString("ascii") !== "PNG") {
    throw new Error("invalid or implausibly small PNG: " + filename);
  }
  const width = image.readUInt32BE(16);
  const height = image.readUInt32BE(20);
  if (width !== viewport.width || height !== viewport.height) {
    throw new Error("PNG dimensions mismatch for " + filename + ": " + width + "x" + height);
  }
  captures.push({
    filename,
    scene: sceneMetadata,
    ...(advancedRenderState ? { advanced_render_state: advancedRenderState } : {}),
    viewport,
    url: page.url(),
    question: sceneMetadata.question ? (await page.locator("#guided-question").innerText()).trim() : null,
    guided_render_path: await page.locator(".guided-showcase").count()
      ? await page.locator(".guided-showcase").getAttribute("data-guided-render-path")
      : null,
    section: await page.locator(".urban-section").count()
      ? await page.locator(".urban-section").evaluate((element) => ({
        ready: element.getAttribute("data-transect-ready") === "true",
        pack_id: element.getAttribute("data-pack-id"),
        buildings: Number(element.getAttribute("data-building-count") ?? 0),
        roads: Number(element.getAttribute("data-road-count") ?? 0),
        terrain_covered: Number(element.getAttribute("data-terrain-covered") ?? 0),
      }))
      : null,
    sha256: sha256(image),
    bytes: image.length,
  });
}

async function validateStaging() {
  const files = (await readdir(stagingDirectory)).filter((name) => name.endsWith(".png")).sort();
  if (JSON.stringify(files) !== JSON.stringify([...NAMES].sort())) {
    throw new Error("capture set is not the exact required eight PNGs: " + JSON.stringify(files));
  }
  if (captures.length !== NAMES.length) throw new Error("capture manifest must contain exactly eight entries");
  for (const item of captures) {
    const filename = path.join(stagingDirectory, item.filename);
    if ((await stat(filename)).size !== item.bytes || sha256(await readFile(filename)) !== item.sha256) {
      throw new Error("staged screenshot integrity mismatch: " + item.filename);
    }
  }
  const guided = captures.filter((item) => item.scene.question);
  if (guided.length !== 6 || guided.some((item) => !item.question)) {
    throw new Error("all guided captures must retain a readable current question");
  }
  const advanced = captures.find((item) => item.filename === "07-advanced.png");
  const advancedState = advanced?.advanced_render_state;
  if (
    !advancedState?.complete
    || !advancedState.retained_target
    || !advancedState.task_navigation_visible
    || (!advancedState.section?.verified && !advancedState.renderer?.ready)
  ) {
    throw new Error("advanced capture lacks validated retained-target renderer state");
  }
}

async function validateCompletedStage() {
  const files = (await readdir(stagingDirectory)).sort();
  const expected = [...NAMES, "manifest.json"].sort();
  if (JSON.stringify(files) !== JSON.stringify(expected)) {
    throw new Error("completed stage contains missing or stale files: " + JSON.stringify(files));
  }
  const manifest = JSON.parse(await readFile(path.join(stagingDirectory, "manifest.json"), "utf8"));
  const advanced = manifest.captures.find((item) => item.filename === "07-advanced.png");
  if (
    manifest.schema_version !== "citygap.guided-capture-manifest@2"
    || manifest.capture_count !== 8
    || JSON.stringify([...manifest.required_png_files].sort()) !== JSON.stringify([...NAMES].sort())
    || JSON.stringify(manifest.captures.map((item) => item.filename).sort()) !== JSON.stringify([...NAMES].sort())
    || !manifest.provenance?.provenance_fingerprint_sha256
    || !advanced?.advanced_render_state?.complete
    || (!advanced?.advanced_render_state?.section?.verified && !advanced?.advanced_render_state?.renderer?.ready)
  ) {
    throw new Error("completed capture manifest does not describe the exact eight PNGs");
  }
}

async function publishStaging() {
  const backup = path.join(outputParent, "." + outputName + ".backup-" + process.pid + "-" + Date.now());
  assertManagedSibling(backup, "." + outputName + ".backup-");
  const hadOutput = await exists(outputDirectory);
  let oldMoved = false;
  try {
    if (hadOutput) {
      await rename(outputDirectory, backup);
      recoveryBackup = backup;
      oldMoved = true;
    }
    await rename(stagingDirectory, outputDirectory);
    published = true;
  } catch (error) {
    if (oldMoved && !await exists(outputDirectory)) {
      try {
        await rename(backup, outputDirectory);
        recoveryBackup = null;
      } catch (restoreError) {
        throw new Error("publication failed; prior output remains preserved at " + backup + "; restore also failed: " + restoreError.message, { cause: error });
      }
    }
    throw error;
  }
  if (oldMoved) {
    assertManagedSibling(backup, "." + outputName + ".backup-");
    await rm(backup, { recursive: true, force: true }).then(
      () => { recoveryBackup = null; },
      (error) => process.stderr.write("capture published; old backup retained at " + backup + ": " + error.message + "\n"),
    );
  }
}

try {
  browser = await chromium.launch({
    executablePath,
    headless: true,
    args: RENDERER_ARGS,
  });

  const desktopViewport = { width: 1440, height: 900 };
  const desktop = await browser.newContext({ viewport: desktopViewport, deviceScaleFactor: 1, reducedMotion: "reduce" });
  const page = await desktop.newPage();
  desktopDiagnostics = attachBrowserDiagnostics(page);
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await assertLanding(page);
  runtimeEnvironment = {
    browser: {
      engine: "chromium",
      version: browser.version(),
    },
    renderer: {
      requested_backend: "swiftshader",
      launch_args: RENDERER_ARGS,
      reduced_motion: "reduce",
      device_scale_factor: 1,
      ...await runtimeRendererEvidence(page),
    },
  };
  await capture(page, "01-landing.png", desktopViewport, { id: "landing", question: false });
  await startGuided(page);
  await capture(page, "02-where.png", desktopViewport, { id: "where", question: true, step: 1 });
  await advanceGuided(page, 1);
  await capture(page, "03-why.png", desktopViewport, { id: "why", question: true, step: 2 });
  await advanceGuided(page, 2);
  await capture(page, "04-plateau-detail.png", desktopViewport, { id: "plateau-detail", question: true, step: 3 });
  await advanceGuided(page, 3);
  await capture(page, "05-what-if.png", desktopViewport, { id: "what-if", question: true, step: 4 });
  await advanceGuided(page, 4);
  await capture(page, "06-evidence.png", desktopViewport, { id: "evidence", question: true, step: 5 });
  const advancedRenderState = await reviewEvidenceAndOpenAdvanced(page);
  await capture(page, "07-advanced.png", desktopViewport, { id: "advanced", question: false, advancedRenderState });
  assertNoCriticalBrowserErrors(desktopDiagnostics);
  desktopDiagnostics = JSON.parse(JSON.stringify(desktopDiagnostics));
  await desktop.close();

  const mobileViewport = { width: 390, height: 844 };
  const mobile = await browser.newContext({ viewport: mobileViewport, deviceScaleFactor: 1, reducedMotion: "reduce" });
  const mobilePage = await mobile.newPage();
  mobileDiagnostics = attachBrowserDiagnostics(mobilePage);
  await mobilePage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await assertLanding(mobilePage);
  await startGuided(mobilePage);
  await advanceGuided(mobilePage, 1);
  await advanceGuided(mobilePage, 2);
  await assertMobileGuidedLayout(mobilePage);
  await assertGuidedStep(mobilePage, 3);
  await capture(mobilePage, "08-mobile.png", mobileViewport, { id: "mobile", question: true, step: 3 });
  assertNoCriticalBrowserErrors(mobileDiagnostics);
  mobileDiagnostics = JSON.parse(JSON.stringify(mobileDiagnostics));
  await mobile.close();

  await validateStaging();
  const provenance = {
    ...provenanceAtCaptureStart,
    runtime_environment: runtimeEnvironment,
  };
  provenance.provenance_fingerprint_sha256 = provenanceFingerprint(provenance);
  await writeFile(path.join(stagingDirectory, "manifest.json"), JSON.stringify({
    schema_version: "citygap.guided-capture-manifest@2",
    generated_at: new Date().toISOString(),
    capture_script_version: CAPTURE_VERSION,
    repository_head: repositoryHead,
    base_url: baseUrl,
    capture_count: captures.length,
    required_png_files: NAMES,
    publication_contract: "stage-validate-atomic-swap",
    provenance,
    network_observations: {
      desktop: desktopDiagnostics,
      mobile: mobileDiagnostics,
    },
    captures,
  }, null, 2) + "\n", "utf8");
  await validateCompletedStage();
  await publishStaging();
  process.stdout.write("8 validated Guided captures published to " + outputDirectory + "\n");
} catch (error) {
  await mkdir(diagnosticDirectory, { recursive: true });
  const diagnostic = {
    schema_version: "citygap.guided-capture-failure@2",
    generated_at: new Date().toISOString(),
    error: error instanceof Error ? error.stack ?? error.message : String(error),
    base_url: baseUrl,
    intended_output: outputDirectory,
    existing_output_preserved: await exists(outputDirectory) || Boolean(recoveryBackup && await exists(recoveryBackup)),
    recovery_backup: recoveryBackup && await exists(recoveryBackup) ? recoveryBackup : null,
    partial_output_published: false,
    provenance_at_capture_start: provenanceAtCaptureStart,
    runtime_environment: runtimeEnvironment,
    network_observations: {
      desktop: desktopDiagnostics,
      mobile: mobileDiagnostics,
    },
    completed_staged_captures: captures,
  };
  const filename = path.join(diagnosticDirectory, "guided-capture-" + Date.now() + ".json");
  await writeFile(filename, JSON.stringify(diagnostic, null, 2) + "\n", "utf8");
  process.stderr.write("Guided capture failed; no partial capture set was published. Diagnostic: " + filename + "\n");
  process.exitCode = 1;
} finally {
  await browser?.close().catch(() => undefined);
  if (!published && await exists(stagingDirectory)) {
    assertManagedSibling(stagingDirectory, "." + outputName + ".staging-");
    await rm(stagingDirectory, { recursive: true, force: true });
  }
}
