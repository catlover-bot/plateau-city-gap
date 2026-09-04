import { createHash } from "node:crypto";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";

const args = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const key = process.argv[index];
  if (!key.startsWith("--")) continue;
  const value = process.argv[index + 1];
  args.set(key, value && !value.startsWith("--") ? value : "true");
  if (value && !value.startsWith("--")) index += 1;
}

const directory = path.resolve(args.get("--directory") ?? "../docs/assets/presentation-images");
const expectedSourceCommit = args.get("--source-commit") ?? null;
const expectedPagesRunId = args.get("--pages-run-id") ?? null;
const expectedImages = new Map([
  ["01-city-gap-overview-16x9.png", [1920, 1080]],
  ["02-area-selection-16x9.png", [1920, 1080]],
  ["03-plateau-section-hero-16x9.png", [1920, 1080]],
  ["04-urban-section-closeup-16x9.png", [1920, 1080]],
  ["05-exact-field-target-16x9.png", [1920, 1080]],
  ["06-area-switching-16x9.png", [1920, 1080]],
  ["07-mobile-workflow-portrait.png", [780, 1688]],
  ["08-advanced-evidence-16x9.png", [1920, 1080]],
]);
const sha256 = (buffer) => createHash("sha256").update(buffer).digest("hex");

function pngDimensions(buffer, filename) {
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  if (buffer.length < 24 || !buffer.subarray(0, 8).equals(signature) || buffer.toString("ascii", 12, 16) !== "IHDR") {
    throw new Error(`not a valid PNG with an IHDR header: ${filename}`);
  }
  return [buffer.readUInt32BE(16), buffer.readUInt32BE(20)];
}

const manifest = JSON.parse(await readFile(path.join(directory, "manifest.json"), "utf8"));
if (manifest.schema_version !== "citygap.production-presentation-images@1") throw new Error("unexpected presentation-image manifest schema");
if (manifest.source_production_url !== "https://catlover-bot.github.io/plateau-city-gap/") throw new Error("images were not captured from the canonical production URL");
if (manifest.source_branch !== "feat/guided-spatial-storytelling-v1") throw new Error("unexpected source branch");
if (expectedSourceCommit && manifest.source_commit !== expectedSourceCommit) throw new Error("source commit mismatch");
if (expectedPagesRunId && String(manifest.pages_run_id) !== expectedPagesRunId) throw new Error("Pages run mismatch");
if (!manifest.passed || manifest.diagnostics.length) throw new Error("capture manifest did not pass cleanly");
if (!manifest.live_build?.index?.matches_local_build || manifest.live_build.assets.some((asset) => !asset.matches_local_build)) {
  throw new Error("production assets did not match the local source build");
}

const actualNames = (await readdir(directory)).sort();
const requiredNames = [...expectedImages.keys(), "contact-sheet.png", "manifest.json"].sort();
if (JSON.stringify(actualNames) !== JSON.stringify(requiredNames)) throw new Error(`unexpected package contents: ${JSON.stringify(actualNames)}`);
if (manifest.images.length !== expectedImages.size) throw new Error(`expected ${expectedImages.size} image records`);

const timestamps = [];
for (const record of manifest.images) {
  const expectedDimensions = expectedImages.get(record.filename);
  if (!expectedDimensions) throw new Error(`unexpected image record: ${record.filename}`);
  const buffer = await readFile(path.join(directory, record.filename));
  const dimensions = pngDimensions(buffer, record.filename);
  if (dimensions[0] !== expectedDimensions[0] || dimensions[1] !== expectedDimensions[1]) throw new Error(`dimension mismatch for ${record.filename}: ${dimensions.join("x")}`);
  if (buffer.length !== record.bytes || sha256(buffer) !== record.sha256) throw new Error(`hash or size mismatch: ${record.filename}`);
  if (record.output_dimensions.width !== dimensions[0] || record.output_dimensions.height !== dimensions[1]) throw new Error(`manifest dimension mismatch: ${record.filename}`);
  const readiness = record.readiness;
  if (record.diagnostics.length || !readiness.fonts_ready || !readiness.map_style_loaded || readiness.loading_surface_count || readiness.unfinished_loading_copy || readiness.horizontal_overflow_px || readiness.debug_surface_count) {
    throw new Error(`readiness gate failed: ${record.filename}`);
  }
  if (record.filename.startsWith("03-") || record.filename.startsWith("04-") || record.filename.startsWith("07-")) {
    if (readiness.section_pack !== readiness.expected_section_pack || readiness.section_overlap_count !== 0 || readiness.section_terrain_samples !== 94) throw new Error(`Urban Section provenance gate failed: ${record.filename}`);
  }
  if (record.filename.startsWith("05-") && (readiness.target_kind !== "road" || readiness.target_resolution !== "exact" || readiness.field_check_count !== 4)) throw new Error("exact field-target gate failed");
  if (record.filename.startsWith("06-") && record.selected_area !== "533512362") throw new Error("Area-switching gate failed");
  if (record.filename !== "08-advanced-evidence-16x9.png" && readiness.map_initialization_count !== 1) throw new Error(`map initialization gate failed: ${record.filename}`);
  const timestamp = Date.parse(record.captured_at);
  if (!Number.isFinite(timestamp)) throw new Error(`invalid capture timestamp: ${record.filename}`);
  timestamps.push(timestamp);
}

const generatedAt = Date.parse(manifest.generated_at);
if (!Number.isFinite(generatedAt) || generatedAt < Math.max(...timestamps) || generatedAt - Math.min(...timestamps) > 30 * 60 * 1_000) throw new Error("capture timestamp sequence is invalid");

const contactBuffer = await readFile(path.join(directory, manifest.contact_sheet.filename));
const contactDimensions = pngDimensions(contactBuffer, manifest.contact_sheet.filename);
if (contactDimensions[0] !== 1920 || contactDimensions[1] !== 1080 || contactBuffer.length !== manifest.contact_sheet.bytes || sha256(contactBuffer) !== manifest.contact_sheet.sha256) throw new Error("contact-sheet gate failed");

process.stdout.write(`${JSON.stringify({
  schema_version: "citygap.production-presentation-images-verification@1",
  passed: true,
  directory,
  images: manifest.images.length,
  source_commit: manifest.source_commit,
  pages_run_id: manifest.pages_run_id,
  generated_at: manifest.generated_at,
}, null, 2)}\n`);
