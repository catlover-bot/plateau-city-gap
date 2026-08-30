import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import {
  access,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { chromium } from "playwright-core";

process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY = "1";

const NAMES = [
  "01-value-landing.png",
  "02-candidate-shortlist.png",
  "03-candidate-brief.png",
  "04-plateau-field-context.png",
  "05-field-checklist.png",
  "06-investigation-sheet.png",
  "07-municipal-review.png",
  "08-mobile-field.png",
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
const canonicalOutput = path.join(repositoryRoot, "docs/assets/current");
const outputDirectory = path.resolve(process.cwd(), parameters.get("--output") ?? "../docs/assets/current");
const baseUrl = parameters.get("--url") ?? "http://127.0.0.1:4173/plateau-city-gap/";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const repositoryHead = execFileSync("git", ["rev-parse", "HEAD"], { cwd: repositoryRoot, encoding: "utf8" }).trim();
const worktreeStatus = execFileSync("git", ["status", "--porcelain"], { cwd: repositoryRoot, encoding: "utf8" });
const temporaryRoot = path.resolve(tmpdir());

function below(candidate, parent) {
  const relative = path.relative(parent, candidate);
  return relative && !relative.startsWith("..") && !path.isAbsolute(relative);
}

if (outputDirectory !== canonicalOutput && !below(outputDirectory, temporaryRoot)) {
  throw new Error("capture output must be docs/assets/current or a temporary-directory child");
}
if (outputDirectory === canonicalOutput && worktreeStatus.trim()) {
  throw new Error("canonical capture requires a clean worktree; commit source changes first");
}

const outputParent = path.dirname(outputDirectory);
const outputName = path.basename(outputDirectory);
await mkdir(outputParent, { recursive: true });
const stagingDirectory = await mkdtemp(path.join(outputParent, `.${outputName}.staging-`));
const captures = [];
let browser;
let published = false;

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

async function exists(filename) {
  return access(filename).then(() => true).catch(() => false);
}

async function waitForStep(page, step) {
  await page.locator(`.investigation-journey[data-investigation-step="${step}"]`).waitFor({
    state: "visible",
    timeout: 120_000,
  });
}

async function next(page, label, expectedStep) {
  await page.getByRole("button", { name: label, exact: true }).click();
  await waitForStep(page, expectedStep);
}

async function capture(page, filename, viewport, scene) {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(350);
  const target = path.join(stagingDirectory, filename);
  await page.screenshot({ path: target, fullPage: false, animations: "disabled", timeout: 180_000 });
  const png = await readFile(target);
  if (png.length < 10_000 || png.subarray(1, 4).toString("ascii") !== "PNG") {
    throw new Error("invalid screenshot: " + filename);
  }
  const width = png.readUInt32BE(16);
  const height = png.readUInt32BE(20);
  if (width !== viewport.width || height !== viewport.height) {
    throw new Error(`unexpected screenshot dimensions for ${filename}: ${width}x${height}`);
  }
  captures.push({
    filename,
    scene,
    viewport,
    url: page.url(),
    bytes: png.length,
    sha256: sha256(png),
  });
}

async function validateStage() {
  const files = (await readdir(stagingDirectory)).filter((name) => name.endsWith(".png")).sort();
  if (JSON.stringify(files) !== JSON.stringify([...NAMES].sort())) {
    throw new Error("capture stage does not contain the exact canonical eight files");
  }
  if (captures.length !== 8) throw new Error("capture manifest must contain eight scenes");
  for (const item of captures) {
    const filename = path.join(stagingDirectory, item.filename);
    if ((await stat(filename)).size !== item.bytes || sha256(await readFile(filename)) !== item.sha256) {
      throw new Error("screenshot integrity mismatch: " + item.filename);
    }
  }
}

async function publish() {
  const backup = path.join(outputParent, `.${outputName}.backup-${process.pid}-${Date.now()}`);
  const hadOutput = await exists(outputDirectory);
  if (hadOutput) await rename(outputDirectory, backup);
  try {
    await rename(stagingDirectory, outputDirectory);
    published = true;
  } catch (error) {
    if (hadOutput && !await exists(outputDirectory)) await rename(backup, outputDirectory);
    throw error;
  }
  if (hadOutput) await rm(backup, { recursive: true, force: true });
}

try {
  browser = await chromium.launch({
    executablePath,
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist", "--use-gl=swiftshader"],
  });

  const desktopViewport = { width: 1440, height: 900 };
  const desktop = await browser.newContext({
    viewport: desktopViewport,
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  const page = await desktop.newPage();
  page.setDefaultTimeout(120_000);
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await page.getByRole("heading", { name: /どこから現地確認するかを/ }).waitFor();
  await capture(page, NAMES[0], desktopViewport, "value-landing");

  await page.getByRole("button", { name: "舞鶴の現地調査候補を見る", exact: true }).click();
  await waitForStep(page, 1);
  await capture(page, NAMES[1], desktopViewport, "candidate-shortlist");

  await next(page, "候補理由を見る", 2);
  await capture(page, NAMES[2], desktopViewport, "candidate-brief");

  await next(page, "街の構造を見る", 3);
  await page.getByText("296棟", { exact: true }).waitFor();
  await page.locator('.plateau-3d-shell[data-ui-mode="guided"]').waitFor({ state: "visible" });
  await page.locator(".plateau-3d-shell .map-engine-loading").last().waitFor({
    state: "hidden",
    timeout: 180_000,
  });
  await page.locator(".plateau-3d-shell canvas").first().waitFor({ state: "visible" });
  await page.waitForTimeout(1_000);
  await capture(page, NAMES[3], desktopViewport, "plateau-field-context");

  await next(page, "確認項目を見る", 4);
  await page.getByText("確認する理由", { exact: true }).first().waitFor();
  await capture(page, NAMES[4], desktopViewport, "field-checklist");

  await next(page, "現地確認を開始", 5);
  const firstCheck = page.locator(".editable-checks > li").first();
  await firstCheck.getByLabel("担当").fill("地域公共交通担当");
  await firstCheck.getByLabel("メモ").fill("現地で確認する内部メモ");
  await capture(page, NAMES[5], desktopViewport, "investigation-sheet");

  await next(page, "調査サマリーを見る", 6);
  await page.locator(".municipal-review").scrollIntoViewIfNeeded();
  await capture(page, NAMES[6], desktopViewport, "municipal-review");
  if (pageErrors.length) throw new Error("browser page errors: " + JSON.stringify(pageErrors));
  await desktop.close();

  const mobileViewport = { width: 390, height: 844 };
  const mobile = await browser.newContext({
    viewport: mobileViewport,
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  const mobilePage = await mobile.newPage();
  mobilePage.setDefaultTimeout(120_000);
  await mobilePage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await mobilePage.getByRole("button", { name: "舞鶴の現地調査候補を見る", exact: true }).click();
  await waitForStep(mobilePage, 1);
  await next(mobilePage, "候補理由を見る", 2);
  await next(mobilePage, "街の構造を見る", 3);
  await next(mobilePage, "確認項目を見る", 4);
  await next(mobilePage, "現地確認を開始", 5);
  await mobilePage.locator(".sheet-meta").scrollIntoViewIfNeeded();
  await capture(mobilePage, NAMES[7], mobileViewport, "mobile-field");
  await mobile.close();

  await validateStage();
  await writeFile(path.join(stagingDirectory, "manifest.json"), JSON.stringify({
    schema_version: "citygap.investigation-capture-manifest@1",
    generated_at: new Date().toISOString(),
    repository_head: repositoryHead,
    base_url: baseUrl,
    capture_count: captures.length,
    required_png_files: NAMES,
    statuses: {
      human_test: "AWAITING_HUMAN_TEST",
      municipal_review: "AWAITING_MUNICIPAL_REVIEW",
    },
    captures,
  }, null, 2) + "\n", "utf8");
  await publish();
  process.stdout.write("8 validated field-investigation captures published to " + outputDirectory + "\n");
} finally {
  await browser?.close();
  if (!published && await exists(stagingDirectory)) {
    await rm(stagingDirectory, { recursive: true, force: true });
  }
}
