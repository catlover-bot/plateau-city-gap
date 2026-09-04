import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

const parameters = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const key = process.argv[index];
  if (!key.startsWith("--")) continue;
  const value = process.argv[index + 1];
  parameters.set(key, value && !value.startsWith("--") ? value : "true");
  if (value && !value.startsWith("--")) index += 1;
}

const repositoryRoot = path.resolve(process.cwd(), "..");
const manifestPath = path.resolve(
  process.cwd(),
  parameters.get("--manifest") ?? "../docs/assets/demo-video/manifest.json",
);
const packageDirectory = path.resolve(parameters.get("--directory") ?? path.dirname(manifestPath));
const auditDirectory = parameters.has("--audit-directory") ? path.resolve(parameters.get("--audit-directory")) : null;
const expectedSourceCommit = parameters.get("--source-commit") ?? null;
const expectedPagesRunId = parameters.get("--pages-run-id") ?? null;
const ffmpeg = parameters.get("--ffmpeg") ?? "ffmpeg";
const ffprobe = parameters.get("--ffprobe") ?? "ffprobe";
const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
const hash = (buffer) => createHash("sha256").update(buffer).digest("hex");
const results = [];
const timelineAudits = [];

if (manifest.schema_version !== "citygap.production-demo-video@1") throw new Error("unexpected demo-video manifest schema");
if (!manifest.source_production_url.startsWith("https://catlover-bot.github.io/plateau-city-gap/?experience=guided")) throw new Error("video source is not the production Guided URL");
if (manifest.source_branch !== "feat/guided-spatial-storytelling-v1") throw new Error("unexpected source branch");
if (expectedSourceCommit && manifest.source_commit !== expectedSourceCommit) throw new Error("source commit mismatch");
if (expectedPagesRunId && String(manifest.pages_run_id) !== expectedPagesRunId) throw new Error("Pages run mismatch");
if (!manifest.live_build?.index?.matches_local_build || manifest.live_build.assets.some((asset) => !asset.matches_local_build)) throw new Error("live build identity gate failed");
if (!manifest.recording.prewarmed || manifest.recording.browser_chrome || manifest.recording.audio) throw new Error("recording conditions do not match the presentation contract");
if (manifest.diagnostics.console_errors || manifest.diagnostics.page_errors || manifest.diagnostics.request_errors) throw new Error("recording diagnostics are not empty");
if (!Number.isFinite(Date.parse(manifest.generated_at))) throw new Error("invalid generation timestamp");

const expectedNames = [
  "city-gap-demo-presentation-1080p.mp4",
  "city-gap-demo-clean-1080p.mp4",
  "city-gap-demo-short-15s.mp4",
  "city-gap-demo-poster.png",
  "city-gap-demo-captions.vtt",
  "manifest.json",
].sort();
const actualNames = (await readdir(packageDirectory)).sort();
if (JSON.stringify(actualNames) !== JSON.stringify(expectedNames)) throw new Error(`unexpected demo package contents: ${JSON.stringify(actualNames)}`);
if (JSON.stringify(manifest.files.videos.map((item) => item.id).sort()) !== JSON.stringify(["clean", "presentation", "short"])) throw new Error("expected presentation, clean, and short videos");
if (auditDirectory) {
  const protectedAuditPaths = new Set([path.parse(auditDirectory).root, repositoryRoot, process.cwd(), packageDirectory]);
  if (protectedAuditPaths.has(auditDirectory)) throw new Error(`refusing unsafe audit directory: ${auditDirectory}`);
  const temporaryRoot = path.resolve(tmpdir());
  const temporaryRelative = path.relative(temporaryRoot, auditDirectory);
  if (temporaryRelative.startsWith("..") || path.isAbsolute(temporaryRelative) || !path.basename(auditDirectory).startsWith("citygap-")) {
    throw new Error(`timeline audit output must be a named citygap-* directory under ${temporaryRoot}`);
  }
  await rm(auditDirectory, { recursive: true, force: true });
  await mkdir(auditDirectory, { recursive: true });
}

for (const expected of manifest.files.videos) {
  if (expected.path !== `docs/assets/demo-video/${expected.filename}`) throw new Error(`unexpected canonical manifest path: ${expected.path}`);
  const file = path.join(packageDirectory, expected.filename);
  const buffer = await readFile(file);
  if (buffer.length !== expected.bytes || hash(buffer) !== expected.sha256) throw new Error(`video hash or size mismatch: ${expected.path}`);
  execFileSync(ffmpeg, ["-v", "error", "-xerror", "-i", file, "-f", "null", "-"], { stdio: "inherit" });
  const probe = JSON.parse(execFileSync(ffprobe, ["-v", "error", "-show_streams", "-show_format", "-of", "json", file], { encoding: "utf8" }));
  const video = probe.streams.find((stream) => stream.codec_type === "video");
  const audio = probe.streams.filter((stream) => stream.codec_type === "audio");
  const duration = Number(probe.format.duration);
  if (!video || video.codec_name !== "h264" || video.width !== 1920 || video.height !== 1080 || video.pix_fmt !== "yuv420p" || video.avg_frame_rate !== "30/1" || audio.length) {
    throw new Error(`PowerPoint MP4 gate failed: ${expected.path}`);
  }
  if (expected.id === "short" ? duration < 12 || duration > 18 : duration < 42 || duration > 55) {
    throw new Error(`duration gate failed: ${expected.path} (${duration}s)`);
  }
  if (auditDirectory && expected.id !== "short") {
    const auditPath = path.join(auditDirectory, `${expected.id}-timeline.png`);
    execFileSync(ffmpeg, ["-y", "-hide_banner", "-loglevel", "error", "-i", file, "-vf", "fps=1/5,scale=480:270:flags=lanczos,tile=4x3:padding=0:margin=0", "-frames:v", "1", auditPath], { stdio: "inherit" });
    timelineAudits.push(auditPath);
  }
  results.push({ id: expected.id, duration, bytes: buffer.length, sha256: hash(buffer), decoded: true });
}

for (const expected of [manifest.files.poster, manifest.files.captions]) {
  const expectedFilename = path.basename(expected.path);
  if (expected.path !== `docs/assets/demo-video/${expectedFilename}`) throw new Error(`unexpected canonical manifest path: ${expected.path}`);
  const buffer = await readFile(path.join(packageDirectory, expectedFilename));
  if (buffer.length !== expected.bytes || hash(buffer) !== expected.sha256) throw new Error(`supporting artifact hash or size mismatch: ${expected.path}`);
}
const captions = await readFile(path.join(packageDirectory, path.basename(manifest.files.captions.path)), "utf8");
if (!captions.startsWith("WEBVTT") || (captions.match(/-->/g) ?? []).length !== manifest.files.captions.cues) throw new Error("caption cue contract failed");
if (manifest.repository_video_bytes > 35 * 1024 * 1024) throw new Error("repository video byte budget exceeded");

process.stdout.write(`${JSON.stringify({ schema_version: "citygap.production-demo-video-verification@1", passed: true, directory: packageDirectory, source_commit: manifest.source_commit, pages_run_id: manifest.pages_run_id, results, timeline_audits: timelineAudits }, null, 2)}\n`);
