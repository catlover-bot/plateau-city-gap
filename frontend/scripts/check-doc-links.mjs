import { access, readdir, readFile } from "node:fs/promises";
import path from "node:path";

const repositoryRoot = path.resolve(process.cwd(), "..");

async function markdownFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(target);
    return entry.name.endsWith(".md") ? [target] : [];
  }));
  return files.flat();
}

const files = [path.join(repositoryRoot, "README.md"), ...await markdownFiles(path.join(repositoryRoot, "docs"))];
const missing = [];
for (const file of files) {
  const source = await readFile(file, "utf8");
  for (const match of source.matchAll(/!?(?:\[[^\]]*\])\(([^)]+)\)/g)) {
    const raw = match[1].trim().replace(/^<|>$/g, "").split(/\s+['"]/)[0];
    if (!raw || /^(?:https?:|mailto:|#|data:)/.test(raw)) continue;
    const withoutFragment = raw.split("#")[0].split("?")[0];
    if (!withoutFragment) continue;
    const target = path.resolve(path.dirname(file), decodeURIComponent(withoutFragment));
    try {
      await access(target);
    } catch {
      missing.push({ document: path.relative(repositoryRoot, file), link: raw, target: path.relative(repositoryRoot, target) });
    }
  }
}

if (missing.length) {
  process.stderr.write(`${JSON.stringify({ missing }, null, 2)}\n`);
  process.exitCode = 1;
} else {
  process.stdout.write(`${files.length} Markdown files: all local links resolve\n`);
}
