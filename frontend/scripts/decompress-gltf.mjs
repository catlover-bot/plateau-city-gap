import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS, KHRDracoMeshCompression } from "@gltf-transform/extensions";
import draco3d from "draco3dgltf";
import { readFile, writeFile } from "node:fs/promises";

const [, , input, output] = process.argv;
if (!input || !output) throw new Error("usage: node decompress-gltf.mjs input.glb output.glb");

try {
  const parseGlb = (value) => {
    const buffer = Buffer.from(value);
    if (buffer.toString("ascii", 0, 4) !== "glTF") throw new Error("Expected binary glTF");
    const jsonLength = buffer.readUInt32LE(12);
    return {
      json: JSON.parse(buffer.toString("utf8", 20, 20 + jsonLength)),
      tail: buffer.subarray(20 + jsonLength),
    };
  };
  const encodeGlb = (json, tail) => {
    const rawJson = Buffer.from(JSON.stringify(json), "utf8");
    const padding = Buffer.alloc((4 - rawJson.length % 4) % 4, 0x20);
    const jsonChunk = Buffer.concat([rawJson, padding]);
    const header = Buffer.alloc(20);
    header.write("glTF", 0, "ascii");
    header.writeUInt32LE(2, 4);
    header.writeUInt32LE(20 + jsonChunk.length + tail.length, 8);
    header.writeUInt32LE(jsonChunk.length, 12);
    header.write("JSON", 16, "ascii");
    return Buffer.concat([header, jsonChunk, tail]);
  };

  // glTF-Transform intentionally rejects the legacy CESIUM_RTC extension.
  // Remove it only while decoding Draco, then restore the exact extension to
  // the rewritten GLB so the official real-time-center transform is retained.
  const source = parseGlb(await readFile(input));
  const rtc = source.json.extensions?.CESIUM_RTC;
  const rtcWasRequired = source.json.extensionsRequired?.includes("CESIUM_RTC") ?? false;
  if (source.json.extensions) delete source.json.extensions.CESIUM_RTC;
  source.json.extensionsUsed = source.json.extensionsUsed?.filter((name) => name !== "CESIUM_RTC");
  source.json.extensionsRequired = source.json.extensionsRequired?.filter((name) => name !== "CESIUM_RTC");
  const cleaned = encodeGlb(source.json, source.tail);
  const io = new NodeIO()
    .registerExtensions(ALL_EXTENSIONS)
    .registerDependencies({ "draco3d.decoder": await draco3d.createDecoderModule() });
  const document = await io.readBinary(cleaned);
  const draco = document.getRoot().listExtensionsUsed().find((extension) => extension instanceof KHRDracoMeshCompression);
  draco?.dispose();
  const decoded = parseGlb(await io.writeBinary(document));
  if (rtc) {
    decoded.json.extensions = { ...(decoded.json.extensions ?? {}), CESIUM_RTC: rtc };
    decoded.json.extensionsUsed = [...new Set([...(decoded.json.extensionsUsed ?? []), "CESIUM_RTC"])];
    if (rtcWasRequired) decoded.json.extensionsRequired = [...new Set([...(decoded.json.extensionsRequired ?? []), "CESIUM_RTC"])];
  }
  await writeFile(output, encodeGlb(decoded.json, decoded.tail));
} catch (error) {
  console.error(`${error?.name ?? "Error"}: ${error?.message ?? String(error)}`);
  process.exitCode = 1;
}
