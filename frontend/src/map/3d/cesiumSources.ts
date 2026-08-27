import {
  Cesium3DTileStyle,
  Cesium3DTileset,
  CesiumTerrainProvider,
  Viewer
} from "cesium";
import type { AppData } from "../../types";

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

export function applyBuildingStyle(tileset: Cesium3DTileset, selectedBuildingId: string | null) {
  const selected = selectedBuildingId?.replaceAll("'", "\\'");
  tileset.style = new Cesium3DTileStyle({
    color: selected
      ? {
          conditions: [
            [`\${gml_id} === '${selected}'`, "color('#e2ad3f', 1.0)"],
            ["true", "color('#d7e0dc', 0.98)"],
          ],
        }
      : "color('#d7e0dc', 0.98)",
  });
}

export function addTileset(viewer: Viewer, tileset: Cesium3DTileset) {
  viewer.scene.primitives.add(tileset);
  viewer.scene.requestRender();
}
