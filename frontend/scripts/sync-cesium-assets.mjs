import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const cesiumRoot = join(frontendRoot, "node_modules", "cesium", "Build", "Cesium");
const publicRoot = join(frontendRoot, "public", "cesium");
const directories = ["Workers", "ThirdParty", "Assets", "Widgets"];

for (const directory of directories) {
  const source = join(cesiumRoot, directory);
  if (!existsSync(source)) {
    throw new Error(`Cesium runtime asset directory is missing: ${source}`);
  }
  const destination = join(publicRoot, directory);
  mkdirSync(destination, { recursive: true });
  cpSync(source, destination, { recursive: true, force: true });
}
