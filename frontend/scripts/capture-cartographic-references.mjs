import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright-core";

const references = [
  { id: "pit-route-finder", name: "PIT Environmental Cost Route Finder", url: "https://www.pit-creation.com/environment-cost-route-finder/" },
  { id: "municipal-wiki", name: "自治体別課題 Wiki", url: "https://github.com/azarashin/PLATEAUHackathon2006/wiki/%E8%87%AA%E6%B2%BB%E4%BD%93%E5%88%A5%E8%AA%B2%E9%A1%8C" },
  { id: "urbanor", name: "Urbanor PDF", url: "https://cdn.discordapp.com/attachments/1540472920487366799/1540624001292959755/PLATEAU_LTUrbanor.pdf" },
  { id: "platone", name: "PLATONE", url: "https://speakerdeck.com/toshiseisaku/no-dot-9-platone-puraton" },
  { id: "tide-viewer", name: "Tide Viewer", url: "https://xr.kuwa-ya.co.jp/tide-viewer/" },
  { id: "onocoro", name: "OnoCoro repository", url: "https://github.com/kuippa/OnoCoro/" },
  { id: "iwagaki-repository", name: "iwagaki repository", url: "https://github.com/masatomoty/iwagaki" },
  { id: "iwagaki-viewer", name: "iwagaki viewer", url: "https://iwagaki-viewer.tonbo.workers.dev/" },
  { id: "plateau-transit", name: "PLATEAU Transit POC", url: "https://plateau-transit-poc.vercel.app/" },
];

const viewport = { width: 1440, height: 900 };
const repositoryRoot = path.resolve(process.cwd(), "..");
const outputDirectory = path.join(repositoryRoot, "docs/assets/cartographic-benchmark");
const head = execFileSync("git", ["rev-parse", "HEAD"], {
  cwd: repositoryRoot,
  encoding: "utf8",
}).trim();
const executablePath =
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const sha256 = (value) => createHash("sha256").update(value).digest("hex");

await mkdir(outputDirectory, { recursive: true });
const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
});

const results = [];
try {
  for (const reference of references) {
    const context = await browser.newContext({ viewport, reducedMotion: "reduce" });
    const page = await context.newPage();
    const record = {
      ...reference,
      requested_url: reference.url,
      viewport,
      status: "ACCESS_UNAVAILABLE",
      http_status: null,
      final_url: null,
      title: null,
      body_text_length: 0,
      screenshot: null,
      screenshot_sha256: null,
      error: null,
    };
    try {
      const response = await page.goto(reference.url, {
        waitUntil: "domcontentloaded",
        timeout: 35_000,
      });
      record.http_status = response?.status() ?? null;
      record.final_url = page.url();
      record.title = await page.title();
      record.body_text_length = await page.locator("body").innerText({ timeout: 5_000 })
        .then((value) => value.trim().length)
        .catch(() => 0);
      if (record.http_status !== null && record.http_status >= 400) {
        record.status = "ACCESS_UNAVAILABLE";
      } else if (record.body_text_length < 40) {
        record.status = "ACCESS_UNAVAILABLE_FOR_VISUAL_CAPTURE";
      } else {
        await page.waitForTimeout(1_200);
        if (reference.id === "iwagaki-repository" || reference.id === "onocoro") {
          const documentationImage = page.locator("article.markdown-body img").first();
          if (await documentationImage.count()) {
            await documentationImage.scrollIntoViewIfNeeded();
            await page.waitForTimeout(400);
          }
        }
        const filename = `${reference.id}.png`;
        const screenshotPath = path.join(outputDirectory, filename);
        await page.screenshot({
          path: screenshotPath,
          fullPage: false,
          animations: "disabled",
          timeout: 30_000,
        });
        const png = await readFile(screenshotPath);
        record.screenshot = filename;
        record.screenshot_sha256 = sha256(png);
        record.status = {
          "municipal-wiki": "NON_VISUAL_REFERENCE",
          "platone": "PRESENTATION_CAPTURED",
          "tide-viewer": "SHELL_CAPTURED_RENDER_UNCONFIRMED",
          "onocoro": "REPOSITORY_DOCUMENTATION_CAPTURED_APP_UNCONFIRMED",
          "iwagaki-repository": "REPOSITORY_DOCUMENTATION_CAPTURED",
        }[reference.id] ?? "CAPTURED";
      }
    } catch (error) {
      record.error = error instanceof Error ? error.message : String(error);
    }
    results.push(record);
    await context.close();
  }
} finally {
  await browser.close();
}

const manifest = {
  schema_version: "citygap.cartographic-reference-evidence@1",
  captured_at: new Date().toISOString(),
  repository_head: head,
  viewport,
  third_party_assets_for_benchmark_only: true,
  references: results,
};
await writeFile(
  path.join(outputDirectory, "manifest.json"),
  JSON.stringify(manifest, null, 2) + "\n",
  "utf8",
);
process.stdout.write(JSON.stringify(results.map((item) => ({
  id: item.id,
  status: item.status,
  http_status: item.http_status,
  screenshot: item.screenshot,
  error: item.error,
})), null, 2) + "\n");
