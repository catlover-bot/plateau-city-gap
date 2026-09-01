import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { createHash, webcrypto } from "node:crypto";
import type { GeoJsonFeatureCollection } from "../../types";
import type { AreaTarget, InvestigationAreaSummary } from "./areaTypes";
import {
  buildPublicAreaGeometry,
  derivativeAvailableFor,
  loadPublicCartographyData,
  loadPublicStoryArtifact,
  loadPublicTargetData,
  publicStoryLegend,
  resolvePublicTarget,
  type PublicCartographyData,
  type PublicCartographyManifest,
  type PublicTargetData,
} from "./publicCartography";

beforeAll(() => vi.stubGlobal("crypto", webcrypto));
afterAll(() => vi.unstubAllGlobals());

const empty: GeoJsonFeatureCollection = { type: "FeatureCollection", features: [] };
const building = {
  type: "Feature" as const,
  id: "building-1",
  properties: { object_id: "building-1", object_type: "building" },
  geometry: {
    type: "Polygon",
    coordinates: [[[135.32, 35.43], [135.33, 35.43], [135.33, 35.44], [135.32, 35.44], [135.32, 35.43]]],
  },
};

const manifest: PublicCartographyManifest = {
  schema_version: "citygap.public-cartography@1",
  artifact_kind: "display_derivative",
  rule_version: "test@1",
  source: {
    path: "city.gml.zip",
    version: "plateau-maizuru-2025",
    sha256: "source-hash",
    city_code: "26202",
    crs: "EPSG:4326",
  },
  scope: {
    area_id: "nishi-maizuru-800m-v1",
    area_version: 1,
    radius_m: 800,
    area_content_sha256: "area-hash",
    origin: {
      kind: "station",
      source_feature_id: "station-007",
      coordinates: [135.33, 35.44],
    },
  },
  target_ids: ["building-1"],
  resolved_target_ids: { buildings: ["building-1"], roads: [], planning: [] },
  artifacts: {
    buildings: { path: "buildings.geojson", feature_count: 1, geometry_types: ["Polygon"], property_allowlist: ["object_id"], sha256: "building-hash" },
    roads: { path: "roads.geojson", feature_count: 0, geometry_types: [], property_allowlist: ["object_id"], sha256: "road-hash" },
    planning: { path: "planning.geojson", feature_count: 0, geometry_types: [], property_allowlist: ["object_id"], sha256: "planning-hash" },
    targets: {
      artifact_kind: "exact_target_display_derivative",
      path: "targets.geojson",
      source_dataset_version: "plateau-maizuru-2025",
      source_sha256: "source-hash",
      rule_version: "test@1",
      feature_count: 1,
      geometry_types: ["Polygon"],
      object_ids: ["building-1"],
      property_allowlist: ["object_id", "object_type"],
      sha256: "target-hash",
    },
  },
};

const data: PublicCartographyData = {
  manifest,
  buildings: { type: "FeatureCollection", features: [building] },
  roads: empty,
  planning: empty,
};
const targetData: PublicTargetData = {
  manifest,
  targets: { type: "FeatureCollection", features: [building] },
};

function jsonBytes(value: unknown) {
  return new TextEncoder().encode(JSON.stringify(value));
}

function bytesHash(bytes: Uint8Array) {
  return createHash("sha256").update(bytes).digest("hex");
}

function arrayBuffer(bytes: Uint8Array) {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

const summary = {
  radius_m: 800,
  origin: {
    kind: "station",
    source_feature_id: "station-007",
    coordinates: [135.33, 35.44],
  },
} as InvestigationAreaSummary;

const buildingTarget: AreaTarget = {
  scope: "plateau_object",
  object_type: "building",
  source_object_id: "building-1",
  label: "PLATEAU建物",
  longitude: 135.325,
  latitude: 35.435,
  dataset: "PLATEAU舞鶴市 2025",
  role: "primary",
};

describe("Public cartography contract", () => {
  it("builds a deterministic 96-segment display circle and outside mask", () => {
    const first = buildPublicAreaGeometry([135.33, 35.44], 800);
    const second = buildPublicAreaGeometry([135.33, 35.44], 800);

    expect(second).toEqual(first);
    expect((first.polygon.features[0].geometry?.coordinates as number[][][])[0]).toHaveLength(97);
    expect(first.outsideMask.features[0].properties?.role).toBe("outside_context");
    expect(first.bounds.west).toBeLessThan(135.33);
    expect(first.bounds.east).toBeGreaterThan(135.33);
  });

  it("limits a display derivative to its versioned station Area", () => {
    expect(derivativeAvailableFor(data, summary)).toBe(true);
    expect(derivativeAvailableFor(data, { ...summary, radius_m: 1000 })).toBe(false);
    expect(derivativeAvailableFor(data, {
      ...summary,
      origin: { ...summary.origin, kind: "map_point" },
    })).toBe(false);
  });

  it("distinguishes exact geometry, reference positions, and Area fallback", () => {
    expect(resolvePublicTarget(buildingTarget, data, true)).toMatchObject({
      resolution: "exact",
      objectId: "building-1",
    });
    expect(resolvePublicTarget({ ...buildingTarget, source_object_id: "missing" }, data, true)).toMatchObject({
      resolution: "reference_position",
    });
    expect(resolvePublicTarget({
      ...buildingTarget,
      scope: "mesh",
      object_type: "mesh",
      source_object_id: "mesh-1",
    }, data, true)).toMatchObject({
      resolution: "area_fallback",
      geometry: empty,
    });
  });

  it("resolves the same exact polygon from the lightweight target derivative", () => {
    expect(resolvePublicTarget(buildingTarget, null, true, targetData)).toMatchObject({
      resolution: "exact",
      objectId: "building-1",
      geometry: { features: [building] },
    });
  });

  it("keeps an honest fallback while display geometry loads in the background", () => {
    expect(derivativeAvailableFor(null, summary)).toBe(false);
    expect(resolvePublicTarget(buildingTarget, null, false)).toMatchObject({
      resolution: "reference_position",
      objectId: "building-1",
    });
  });

  it("provides one contextual legend without inventing establishment points", () => {
    expect(publicStoryLegend("building-use", true)?.items).toHaveLength(4);
    expect(publicStoryLegend("transport", true)?.items).toHaveLength(2);
    expect(publicStoryLegend("establishments", true)).toMatchObject({
      items: [],
      note: "範囲集計・個別事業所の位置は表示していません",
    });
  });

  it("loads only manifest-declared display artifacts", async () => {
    const responses = new Map<string, unknown>([
      ["/base/data/cartography/manifest.json", manifest],
      ["/base/data/cartography/buildings.geojson", data.buildings],
      ["/base/data/cartography/roads.geojson", data.roads],
      ["/base/data/cartography/planning.geojson", data.planning],
    ]);
    const fetchMock = vi.fn(async (url: string | URL | Request) => ({
      ok: responses.has(String(url)),
      status: responses.has(String(url)) ? 200 : 404,
      json: async () => responses.get(String(url)),
    }));
    const fetcher = fetchMock as unknown as typeof fetch;

    const loaded = await loadPublicCartographyData(fetcher, "/base/");
    expect(loaded).toEqual(data);
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      "/base/data/cartography/manifest.json",
      "/base/data/cartography/buildings.geojson",
      "/base/data/cartography/roads.geojson",
      "/base/data/cartography/planning.geojson",
    ]);
  });

  it("loads a provenance-matched exact target artifact without Area story geometry", async () => {
    const targetBytes = jsonBytes(targetData.targets);
    const targetManifest = {
      ...manifest,
      artifacts: {
        ...manifest.artifacts,
        targets: {
          ...manifest.artifacts.targets,
          sha256: bytesHash(targetBytes),
          artifact_sha256: bytesHash(targetBytes),
        },
      },
    };
    const responses = new Map<string, unknown>([
      ["/target/data/cartography/manifest.json", targetManifest],
    ]);
    const fetchMock = vi.fn(async (url: string | URL | Request) => ({
      ok: responses.has(String(url)),
      status: responses.has(String(url)) ? 200 : 404,
      json: async () => responses.get(String(url)),
      arrayBuffer: async () => arrayBuffer(targetBytes),
    }));
    fetchMock.mockImplementation(async (url: string | URL | Request) => ({
      ok: String(url).endsWith("targets.geojson") || responses.has(String(url)),
      status: String(url).endsWith("targets.geojson") || responses.has(String(url)) ? 200 : 404,
      json: async () => responses.get(String(url)),
      arrayBuffer: async () => arrayBuffer(targetBytes),
    }));

    const loaded = await loadPublicTargetData(fetchMock as unknown as typeof fetch, "/target/");

    expect(loaded).toEqual({ manifest: targetManifest, targets: targetData.targets });
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      "/target/data/cartography/manifest.json",
      "/target/data/cartography/targets.geojson",
    ]);
  });

  it("loads and reuses one hash-verified story artifact", async () => {
    const buildingCollection = { type: "FeatureCollection" as const, features: [building] };
    const buildingBytes = jsonBytes(buildingCollection);
    const storyManifest = {
      ...manifest,
      source: { ...manifest.source, version: "story-source-v1" },
      artifacts: {
        ...manifest.artifacts,
        buildings: {
          ...manifest.artifacts.buildings,
          source_dataset_version: "story-source-v1",
          source_sha256: manifest.source.sha256,
          rule_version: manifest.rule_version,
          sha256: bytesHash(buildingBytes),
          artifact_sha256: bytesHash(buildingBytes),
        },
      },
    };
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => storyManifest,
      arrayBuffer: async () => arrayBuffer(buildingBytes),
    }));

    const first = await loadPublicStoryArtifact("buildings", fetchMock as unknown as typeof fetch, "/story/");
    const second = await loadPublicStoryArtifact("buildings", fetchMock as unknown as typeof fetch, "/story/");

    expect(first.collection).toEqual(buildingCollection);
    expect(second.collection).toBe(first.collection);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("rejects stale story bytes instead of caching them", async () => {
    const staleBytes = jsonBytes({ type: "FeatureCollection", features: [] });
    const staleManifest = {
      ...manifest,
      source: { ...manifest.source, version: "stale-story-source" },
      artifacts: {
        ...manifest.artifacts,
        buildings: {
          ...manifest.artifacts.buildings,
          source_dataset_version: "stale-story-source",
          source_sha256: manifest.source.sha256,
          rule_version: manifest.rule_version,
          sha256: "0".repeat(64),
        },
      },
    };
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => staleManifest,
      arrayBuffer: async () => arrayBuffer(staleBytes),
    }));

    await expect(loadPublicStoryArtifact("buildings", fetchMock as unknown as typeof fetch, "/stale-story/"))
      .rejects.toThrow("artifact hash");
  });

  it("passes cancellation to a stale story request", async () => {
    const controller = new AbortController();
    const abortManifest = {
      ...manifest,
      source: { ...manifest.source, version: "abort-story-source" },
      artifacts: {
        ...manifest.artifacts,
        buildings: {
          ...manifest.artifacts.buildings,
          source_dataset_version: "abort-story-source",
          source_sha256: manifest.source.sha256,
          rule_version: manifest.rule_version,
        },
      },
    };
    const fetchMock = vi.fn((url: string | URL | Request, init?: RequestInit) => {
      if (String(url).endsWith("manifest.json")) {
        return Promise.resolve({ ok: true, status: 200, json: async () => abortManifest });
      }
      return new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
      });
    });

    const pending = loadPublicStoryArtifact(
      "buildings",
      fetchMock as unknown as typeof fetch,
      "/abort-story/",
      controller.signal,
    );
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    controller.abort();

    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });

  it("rejects a target artifact whose provenance does not match the manifest source", async () => {
    const staleManifest = {
      ...manifest,
      artifacts: {
        ...manifest.artifacts,
        targets: { ...manifest.artifacts.targets, source_sha256: "stale-source" },
      },
    };
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => staleManifest,
    }));

    await expect(loadPublicTargetData(fetchMock as unknown as typeof fetch, "/stale/"))
      .rejects.toThrow("provenance");
  });
});
