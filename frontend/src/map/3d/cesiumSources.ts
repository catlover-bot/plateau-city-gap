import {
  Cesium3DTileStyle,
  Cesium3DTileset,
  CesiumTerrainProvider,
  Viewer
} from "cesium";
import type { AppData } from "../../types";
import type { AnalysisLens } from "../../state/spatial/types";

const SPATIAL_PACK_ID = "maizuru-533513314-plateau-2025-v1";

interface SpatialPackObjectCollection {
  objects: Array<{
    object_type: string;
    geometry?: { coordinates?: unknown };
    properties?: {
      measured_height_m?: number | null;
      source_tile?: string;
      source_z_min_m?: number | null;
    };
  }>;
}

interface PlateauAssetMetadata {
  selection?: { deep_dive?: { expected_buildings?: number } };
  files?: Array<{ uri: string; bytes: number; sha256: string }>;
}

interface SpatialPackManifest {
  pack_id?: string;
  status?: string;
  objects?: { target_buildings?: number; loaded_target_buildings?: number };
  artifacts?: { "objects.json"?: { bytes?: number; sha256?: string } };
}

export interface SpatialPackVerification {
  packId: string;
  targetFeatureCount: number;
  loadedTargetFeatureCount: number;
  targetPositions: Array<[number, number, number]>;
  artifactBytes: number;
  sourceTileCount: number;
  artifactsReady: true;
}

function absolutePublicUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  return `${import.meta.env.BASE_URL}${path.replace(/^\/+/, "")}`;
}

function sha256Hex(buffer: ArrayBuffer): Promise<string> {
  return crypto.subtle.digest("SHA-256", buffer).then((digest) =>
    Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("")
  );
}

function polygonCenter(coordinates: unknown): [number, number] | null {
  if (!Array.isArray(coordinates) || !Array.isArray(coordinates[0])) return null;
  const ring = coordinates[0] as unknown[];
  const points = ring.filter((point): point is [number, number] =>
    Array.isArray(point)
    && typeof point[0] === "number"
    && typeof point[1] === "number"
  );
  if (points.length === 0) return null;
  const longitude = points.reduce((total, point) => total + point[0], 0) / points.length;
  const latitude = points.reduce((total, point) => total + point[1], 0) / points.length;
  return [longitude, latitude];
}

/**
 * Verifies the complete bounded pack separately from Cesium's view-dependent tile
 * statistics. A target is counted as loaded only after its catalog and every
 * referenced, tracked B3DM payload have passed their recorded SHA-256 checks.
 */
export async function verifySpatialEvidencePack(): Promise<SpatialPackVerification> {
  if (!crypto.subtle) throw new Error("Web Crypto is required for Spatial Evidence Pack verification");
  const packBase = `data/spatial-packs/${SPATIAL_PACK_ID}/`;
  const [manifestResponse, objectsResponse, metadataResponse] = await Promise.all([
    fetch(absolutePublicUrl(`${packBase}manifest.json`)),
    fetch(absolutePublicUrl(`${packBase}objects.json`)),
    fetch(absolutePublicUrl("data/plateau/metadata.json")),
  ]);
  if (!manifestResponse.ok || !objectsResponse.ok || !metadataResponse.ok) {
    throw new Error("Spatial Evidence Pack catalog could not be loaded");
  }
  const [manifest, objectsBuffer, metadata] = await Promise.all([
    manifestResponse.json() as Promise<SpatialPackManifest>,
    objectsResponse.arrayBuffer(),
    metadataResponse.json() as Promise<PlateauAssetMetadata>,
  ]);
  if (manifest.pack_id !== SPATIAL_PACK_ID || manifest.status !== "ready") {
    throw new Error("Spatial Evidence Pack manifest is not ready");
  }
  const expectedObjectsHash = manifest.artifacts?.["objects.json"]?.sha256;
  const actualObjectsHash = await sha256Hex(objectsBuffer);
  if (!expectedObjectsHash || actualObjectsHash !== expectedObjectsHash) {
    throw new Error("Spatial Evidence Pack object catalog hash mismatch");
  }
  const objectCollection = JSON.parse(new TextDecoder().decode(objectsBuffer)) as SpatialPackObjectCollection;
  const buildings = objectCollection.objects.filter((object) => object.object_type === "building");
  const expectedCount = metadata.selection?.deep_dive?.expected_buildings ?? 0;
  if (
    expectedCount <= 0
    || buildings.length !== expectedCount
    || manifest.objects?.target_buildings !== expectedCount
    || manifest.objects?.loaded_target_buildings !== expectedCount
  ) {
    throw new Error(`Spatial Evidence Pack target count mismatch: ${buildings.length}/${expectedCount}`);
  }
  const sourceTiles = new Set(buildings.map((building) => building.properties?.source_tile).filter(Boolean));
  const files = metadata.files ?? [];
  const trackedTiles = new Set(files.map((file) => `plateau/${file.uri}`));
  if (files.length === 0 || sourceTiles.size !== trackedTiles.size || [...sourceTiles].some((uri) => !trackedTiles.has(uri!))) {
    throw new Error("Spatial Evidence Pack source-tile lineage is incomplete");
  }
  const verifiedBytes = await Promise.all(files.map(async (file) => {
    const response = await fetch(absolutePublicUrl(`data/plateau/${file.uri}`));
    if (!response.ok) throw new Error(`Spatial Evidence Pack B3DM HTTP ${response.status}: ${file.uri}`);
    const buffer = await response.arrayBuffer();
    if (buffer.byteLength !== file.bytes || await sha256Hex(buffer) !== file.sha256) {
      throw new Error(`Spatial Evidence Pack B3DM hash mismatch: ${file.uri}`);
    }
    return buffer.byteLength;
  }));
  const targetPositions = buildings.flatMap((building) => {
    const center = polygonCenter(building.geometry?.coordinates);
    if (!center) return [];
    const base = building.properties?.source_z_min_m;
    const height = building.properties?.measured_height_m;
    return [[center[0], center[1], (typeof base === "number" ? base : 0) + (typeof height === "number" ? height / 2 : 1.5)] as [number, number, number]];
  });
  if (targetPositions.length !== expectedCount) {
    throw new Error("Spatial Evidence Pack target positions are incomplete");
  }
  return {
    packId: SPATIAL_PACK_ID,
    targetFeatureCount: expectedCount,
    loadedTargetFeatureCount: buildings.length,
    targetPositions,
    artifactBytes: objectsBuffer.byteLength + verifiedBytes.reduce((total, bytes) => total + bytes, 0),
    sourceTileCount: files.length,
    artifactsReady: true,
  };
}

export async function createBroadTerrain(data: AppData): Promise<CesiumTerrainProvider | null> {
  const url = data.plateauMetadata?.streaming?.terrain_url;
  if (!url) return null;
  return CesiumTerrainProvider.fromUrl(url, {
    requestVertexNormals: true,
    requestWaterMask: false,
  });
}

async function createBuildingTileset(url: string): Promise<Cesium3DTileset> {
  return Cesium3DTileset.fromUrl(absolutePublicUrl(url), {
    maximumScreenSpaceError: window.innerWidth < 768 ? 22 : 13,
    dynamicScreenSpaceError: true,
    dynamicScreenSpaceErrorDensity: 0.00278,
    dynamicScreenSpaceErrorFactor: 4,
    skipLevelOfDetail: false,
    preloadWhenHidden: false,
    cacheBytes: window.innerWidth < 768 ? 96 * 1024 * 1024 : 192 * 1024 * 1024,
  });
}

export async function loadOfficialBuildingTileset(data: AppData): Promise<Cesium3DTileset | null> {
  const official = data.plateauMetadata?.streaming?.building_tileset_url;
  return official ? createBuildingTileset(official) : null;
}

export async function loadBundledBuildingTileset(data: AppData): Promise<Cesium3DTileset | null> {
  const fallback = data.plateauMetadata?.streaming?.fallback_tileset_url
    ?? data.plateauMetadata?.reference_layer?.tileset_url;
  if (!fallback) return null;
  return createBuildingTileset(fallback);
}

export async function loadFastStartBuildingTileset(data: AppData): Promise<Cesium3DTileset | null> {
  const url = data.plateauMetadata?.streaming?.fast_start_tileset_url;
  return url ? createBuildingTileset(url) : null;
}

export async function loadLocalDemTileset(data: AppData): Promise<Cesium3DTileset | null> {
  const url = data.plateauMetadata?.streaming?.local_dem_tileset_url;
  if (!url) return null;
  return Cesium3DTileset.fromUrl(absolutePublicUrl(url), {
    maximumScreenSpaceError: 2,
    skipLevelOfDetail: false,
    preloadWhenHidden: false,
    cacheBytes: 24 * 1024 * 1024,
  });
}

export interface BuildingStyleContext {
  analysisLens?: AnalysisLens;
  selectedMeshBounds?: [number, number, number, number] | null;
  guidedPresentation?: boolean;
}

export function applyBuildingStyle(tileset: Cesium3DTileset, selectedBuildingId: string | null, context: BuildingStyleContext = {}) {
  const selected = selectedBuildingId?.replaceAll("'", "\\'");
  const bounds = context.selectedMeshBounds;
  const inSelectedMesh = bounds
    ? `\${_x} >= ${bounds[0]} && \${_x} <= ${bounds[2]} && \${_y} >= ${bounds[1]} && \${_y} <= ${bounds[3]}`
    : null;
  const conditions: Array<[string, string]> = [];
  if (selected) conditions.push([`\${gml_id} === '${selected}'`, "color('#be5b37', 1.0)"]);
  if (context.analysisLens === "urban-xray" && inSelectedMesh) {
    conditions.push([inSelectedMesh, "color('#d59b3e', 0.96)"]);
    conditions.push(["true", "color('#cbd2ce', 0.20)"]);
  } else if (context.analysisLens === "changed-only") {
    conditions.push(["true", "color('#c7cfca', 0.32)"]);
  } else if (context.analysisLens === "service-pulse") {
    conditions.push(["true", "color('#ced6d2', 0.72)"]);
  } else {
    conditions.push(["true", context.guidedPresentation ? "color('#e3e7e0', 1.0)" : "color('#d7e0dc', 0.98)"]);
  }
  tileset.style = new Cesium3DTileStyle({
    color: { conditions },
  });
}

export function addTileset(viewer: Viewer, tileset: Cesium3DTileset) {
  viewer.scene.primitives.add(tileset);
  viewer.scene.requestRender();
}
