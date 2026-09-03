import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
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
const ffmpeg = parameters.get("--ffmpeg") ?? "ffmpeg";
const ffprobe = parameters.get("--ffprobe") ?? "ffprobe";
const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
const hash = (buffer) => createHash("sha256").update(buffer).digest("hex");
const results = [];

if (manifest.schema_version !== "citygap.production-demo-video@1") throw new Error("unexpected demo-video manifest schema");
if (!manifest.source_production_url.startsWith("https://catlover-bot.github.io/plateau-city-gap/?experience=guided")) throw new Error("video source is not the production Guided URL");
if (!manifest.recording.prewarmed || manifest.recording.browser_chrome || manifest.recording.audio) throw new Error("recording conditions do not match the presentation contract");
if (manifest.diagnostics.console_errors || manifest.diagnostics.page_errors || manifest.diagnostics.request_errors) throw new Error("recording diagnostics are not empty");

for (const expected of manifest.files.videos) {
  const file = path.resolve(repositoryRoot, expected.path);
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
  results.push({ id: expected.id, duration, bytes: buffer.length, sha256: hash(buffer), decoded: true });
}

for (const expected of [manifest.files.poster, manifest.files.captions]) {
  const buffer = await readFile(path.resolve(repositoryRoot, expected.path));
  if (buffer.length !== expected.bytes || hash(buffer) !== expected.sha256) throw new Error(`supporting artifact hash or size mismatch: ${expected.path}`);
}
const captions = await readFile(path.resolve(repositoryRoot, manifest.files.captions.path), "utf8");
if (!captions.startsWith("WEBVTT") || (captions.match(/-->/g) ?? []).length !== manifest.files.captions.cues) throw new Error("caption cue contract failed");
if (manifest.repository_video_bytes > 35 * 1024 * 1024) throw new Error("repository video byte budget exceeded");

process.stdout.write(`${JSON.stringify({ schema_version: "citygap.production-demo-video-verification@1", passed: true, results }, null, 2)}\n`);
