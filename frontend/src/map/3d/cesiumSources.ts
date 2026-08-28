import {
  Cesium3DTileStyle,
  Cesium3DTileset,
  CesiumTerrainProvider,
  Viewer
} from "cesium";
import type { AppData } from "../../types";
import type { AnalysisLens } from "../../state/spatial/types";

function absolutePublicUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  return `${import.meta.env.BASE_URL}${path.replace(/^\/+/, "")}`;
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
    conditions.push(["true", "color('#d7e0dc', 0.98)"]);
  }
  tileset.style = new Cesium3DTileStyle({
    color: { conditions },
  });
}

export function addTileset(viewer: Viewer, tileset: Cesium3DTileset) {
  viewer.scene.primitives.add(tileset);
  viewer.scene.requestRender();
}
