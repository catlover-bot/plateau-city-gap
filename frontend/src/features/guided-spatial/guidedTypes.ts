import type { GeoJsonFeatureCollection } from "../../types";
import type { GuidedStory } from "../../state/spatial/types";

export type GuidedCapabilityStatus = "available" | "partial" | "unavailable";

export interface GuidedCapability {
  status: GuidedCapabilityStatus;
  reason: string;
  object_count?: number;
  pack_id?: string;
  path?: string;
  sha256?: string;
  bytes?: number;
}

export interface GuidedAreaCapabilities {
  plateau_buildings: GuidedCapability;
  plateau_roads: GuidedCapability;
  planning: GuidedCapability;
  terrain: GuidedCapability;
  urban_section: GuidedCapability;
  verification_targets: GuidedCapability;
}

export interface GuidedAreaCatalogItem {
  area_id: string;
  mesh_code: string;
  context_path: string;
  context_sha256: string;
  context_bytes: number;
  area_geometry_sha256: string;
  capabilities: GuidedAreaCapabilities;
  counts: Record<"buildings" | "roads" | "planning", number>;
}

export interface GuidedAreaContextCatalog {
  schema_version: "citygap.guided-area-context-catalog@1";
  source: {
    dataset: string;
    version: string;
    sha256: string;
    limitations: string[];
  };
  mesh_source: { path: string; sha256: string; area_count: number };
  items: GuidedAreaCatalogItem[];
  prohibitions: string[];
}

export interface GuidedAreaContext {
  schema_version: "citygap.guided-area-context@1";
  area_id: string;
  mesh_code: string;
  area_geometry_sha256: string;
  source: GuidedAreaContextCatalog["source"];
  capabilities: GuidedAreaCapabilities;
  layers: {
    buildings: GeoJsonFeatureCollection;
    roads: GeoJsonFeatureCollection;
    planning: GeoJsonFeatureCollection;
  };
  section: GuidedCapability;
}

export interface GuidedMapPresentation {
  story: GuidedStory;
  area: GeoJsonFeatureCollection;
  areaId: string;
  hoveredAreaId: string | null;
  context: GuidedAreaContext | null;
  contextStatus: "idle" | "loading" | "ready" | "error";
  target: GeoJsonFeatureCollection;
  targetKind: "road" | "building" | "facility" | "area";
  targetResolution: "exact" | "area_fallback";
  sectionLine: GeoJsonFeatureCollection;
  sectionFocus: GeoJsonFeatureCollection;
  shortlistIds: string[];
}

export interface GuidedSectionReference {
  status: "available";
  pack_id: string;
  path: string;
}
