import { execFileSync } from "node:child_process";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { chromium } from "playwright-core";

const args = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const key = process.argv[index];
  if (!key.startsWith("--")) continue;
  const value = process.argv[index + 1];
  args.set(key, value && !value.startsWith("--") ? value : "true");
  if (value && !value.startsWith("--")) index += 1;
}

const repositoryRoot = path.resolve(process.cwd(), "..");
const rootUrl = new URL(args.get("--url") ?? "http://127.0.0.1:4173/plateau-city-gap/");
rootUrl.search = "";
rootUrl.hash = "";
const output = path.resolve(process.cwd(), args.get("--output") ?? "../docs/assets/harbor-atlas-v2/after/accessibility.json");
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const require = createRequire(import.meta.url);
const axeSource = await readFile(require.resolve("axe-core/axe.min.js"), "utf8");
const diagnostics = [];
const records = [];

function pageUrl(experience, story = null) {
  const target = new URL(rootUrl);
  if (experience === "guided") {
    target.search = `?experience=guided&story=${story}&selectionType=mesh&selection=533513314&mesh=533513314`;
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
    if (request.url().startsWith(rootUrl.origin) && reason !== "net::ERR_ABORTED") diagnostics.push({ label, kind: "request", url: request.url(), message: reason });
  });
}

async function settle(page) {
  await page.evaluate(async () => {
    await document.fonts?.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
}

async function openState(page, state) {
  await page.goto(pageUrl(state.experience, state.story), { waitUntil: "domcontentloaded", timeout: 180_000 });
  if (state.section) process.stderr.write("[harbor-axe] mobile Section navigation ready\n");
  if (state.experience === "public") {
    await page.locator('.public-area[data-public-step="intro"]').waitFor({ timeout: 180_000 });
    await page.waitForFunction(() => document.querySelector(".analytical-map-shell")?.getAttribute("data-public-cartography-ready") === "true", null, { timeout: 180_000 });
  } else {
    const contextStatus = state.story === "intro" || state.story === "find" ? "idle" : "ready";
    await page.locator(`.guided-spatial-app[data-guided-story="${state.story}"][data-context-status="${contextStatus}"]`).waitFor({ timeout: 180_000 });
    if (state.section) process.stderr.write("[harbor-axe] mobile Section context ready\n");
    await page.waitForFunction(() => document.querySelector(".analytical-map-shell")?.getAttribute("data-guided-visual-ready") === "true", null, { timeout: 180_000 });
    if (state.section) process.stderr.write("[harbor-axe] mobile Section map ready\n");
    if (state.story === "understand") await page.locator('.urban-section[data-annotation-overlap-count="0"]').waitFor({ state: "attached", timeout: 180_000 });
    if (state.section) process.stderr.write("[harbor-axe] mobile Section annotations ready\n");
    if (state.story === "verify") await page.locator('.guided-spatial-app[data-target-resolution="exact"]').waitFor({ timeout: 180_000 });
    if (state.section) {
      await page.getByRole("button", { name: "街の断面", exact: true }).click();
      process.stderr.write("[harbor-axe] mobile Section switch clicked\n");
      await page.locator(".guided-section-dock.mobile-visible").waitFor({ state: "visible", timeout: 180_000 });
      process.stderr.write("[harbor-axe] mobile Section visible\n");
    }
  }
  await settle(page);
}

async function auditState(browser, state) {
  const context = await browser.newContext({ viewport: state.viewport, locale: "ja-JP", reducedMotion: "reduce", serviceWorkers: "block" });
  const page = await context.newPage();
  page.setDefaultTimeout(180_000);
  watch(page, state.label);
  process.stderr.write(`[harbor-axe] opening ${state.label}\n`);
  await openState(page, state);
  await page.addScriptTag({ content: axeSource });
  const result = await page.evaluate(async () => {
    const axeResult = await window.axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] },
      resultTypes: ["violations", "incomplete"],
    });
    const visible = (node) => {
      const rect = node.getBoundingClientRect();
      const style = getComputedStyle(node);
      return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
    };
    return {
      violations: axeResult.violations.map((violation) => ({
        id: violation.id,
        impact: violation.impact,
        help: violation.help,
        help_url: violation.helpUrl,
        nodes: violation.nodes.map((node) => ({ target: node.target, html: node.html, failure_summary: node.failureSummary })),
      })),
      incomplete_count: axeResult.incomplete.length,
      visible_h1_count: [...document.querySelectorAll("h1")].filter(visible).length,
      duplicate_id_count: [...document.querySelectorAll("[id]")].filter((node, index, nodes) => nodes.findIndex((candidate) => candidate.id === node.id) !== index).length,
      horizontal_overflow_px: Math.max(0, document.documentElement.scrollWidth - innerWidth),
      map_initialization_count: window.__cityGapMapInitCount ?? null,
    };
  });
  const criticalOrSerious = result.violations.filter((violation) => violation.impact === "critical" || violation.impact === "serious");
  records.push({
    ...state,
    url: page.url(),
    violation_count: result.violations.length,
    critical_or_serious_count: criticalOrSerious.length,
    violations: result.violations,
    incomplete_count: result.incomplete_count,
    visible_h1_count: result.visible_h1_count,
    duplicate_id_count: result.duplicate_id_count,
    horizontal_overflow_px: result.horizontal_overflow_px,
    map_initialization_count: result.map_initialization_count,
  });
  await context.close();
  process.stderr.write(`[harbor-axe] ${state.label}: ${criticalOrSerious.length} critical/serious, ${result.violations.length} total\n`);
}

const allStates = [
  { label: "public-desktop", experience: "public", story: null, section: false, viewport: { width: 1440, height: 900 } },
  { label: "public-mobile", experience: "public", story: null, section: false, viewport: { width: 390, height: 844 } },
  { label: "guided-intro", experience: "guided", story: "intro", section: false, viewport: { width: 1440, height: 900 } },
  { label: "guided-find", experience: "guided", story: "find", section: false, viewport: { width: 1440, height: 900 } },
  { label: "guided-understand", experience: "guided", story: "understand", section: false, viewport: { width: 1440, height: 900 } },
  {
    label: "guided-understand-200pct-reflow",
    experience: "guided",
    story: "understand",
    section: false,
    viewport: { width: 720, height: 450 },
    zoom_equivalent: "1440x900 at 200% browser zoom",
  },
  { label: "guided-verify", experience: "guided", story: "verify", section: false, viewport: { width: 1440, height: 900 } },
  { label: "guided-section-mobile", experience: "guided", story: "understand", section: true, viewport: { width: 390, height: 844 } },
];
const requestedState = args.get("--state") ?? null;
const states = requestedState ? allStates.filter((state) => state.label === requestedState) : allStates;
if (!states.length) throw new Error(`unknown accessibility state: ${requestedState}`);

const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"],
});
try {
  for (const state of states) await auditState(browser, state);
} finally {
  await browser.close();
}

const criticalOrSeriousCount = records.reduce((sum, record) => sum + record.critical_or_serious_count, 0);
const structuralFailures = records.filter((record) => record.visible_h1_count !== 1 || record.duplicate_id_count !== 0 || record.horizontal_overflow_px !== 0 || record.map_initialization_count !== 1);
const report = {
  schema_version: "citygap.harbor-atlas-accessibility@1",
  generated_at: new Date().toISOString(),
  source_branch: execFileSync("git", ["branch", "--show-current"], { cwd: repositoryRoot, encoding: "utf8" }).trim(),
  source_commit: execFileSync("git", ["rev-parse", "HEAD"], { cwd: repositoryRoot, encoding: "utf8" }).trim(),
  source_url: rootUrl.toString(),
  axe_core_version: JSON.parse(await readFile(require.resolve("axe-core/package.json"), "utf8")).version,
  protocol: "axe-core WCAG 2 A/AA, 2.1 A/AA, and 2.2 AA tags; production build; reduced motion; font and map readiness; 720x450 CSS viewport as 1440x900 at 200% zoom reflow equivalent",
  state_count: records.length,
  critical_or_serious_count: criticalOrSeriousCount,
  structural_failure_count: structuralFailures.length,
  diagnostics,
  records,
  passed: criticalOrSeriousCount === 0 && structuralFailures.length === 0 && diagnostics.length === 0,
};
await mkdir(path.dirname(output), { recursive: true });
await writeFile(output, `${JSON.stringify(report, null, 2)}\n`);
process.stdout.write(`${JSON.stringify({ output, states: records.length, critical_or_serious: criticalOrSeriousCount, structural_failures: structuralFailures.length, diagnostics: diagnostics.length, passed: report.passed }, null, 2)}\n`);
if (!report.passed) process.exitCode = 1;
