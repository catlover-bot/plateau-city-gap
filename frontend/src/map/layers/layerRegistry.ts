import type { CityId, LayerPresetId } from "../../state/spatial/types";

export type LayerGroup = "Analysis" | "PLATEAU" | "Infrastructure" | "Planning" | "Hazard" | "Scenario" | "Validation" | "Reference";
export type LayerRenderMode = "2d" | "3d" | "both";
export type LayerAvailability = "available" | "available_with_limitation" | "not_available";
export type LayerSourceKind = "raster" | "static-geojson" | "mvt" | "derived" | "citygml";
export type LayerCapability = "screen" | "inspect" | "compare" | "stream" | "validate";
export type LayerPrivacyClass = "public-aggregate" | "public-official" | "municipal-restricted";
export type LayerLoadingStrategy = "eager" | "semantic-zoom" | "camera-stream" | "on-demand";
export type LayerInteraction = "none" | "hover" | "select" | "compare";

export interface LayerLegendStop {
  label: string;
  color: string;
  pattern?: "solid" | "line" | "dash" | "outline";
}

export interface LayerDefinition {
  id: string;
  name: string;
  group: LayerGroup;
  source: { kind: LayerSourceKind; url?: string; publicFallback?: string };
  year: string;
  sourceYear: string;
  provider: string;
  plateauTheme: string | null;
  availability: Record<CityId, LayerAvailability>;
  defaultVisibility: boolean;
  minZoom: number;
  maxZoom: number;
  minCameraHeight: number;
  maxCameraHeight: number;
  opacity: number;
  defaultOpacity: number;
  legend: LayerLegendStop[];
  attribution: string;
  renderMode: LayerRenderMode;
  exclusiveGroup: string | null;
  evidenceLink: string;
  capability: LayerCapability[];
  privacyClass: LayerPrivacyClass;
  loadingStrategy: LayerLoadingStrategy;
  interaction: LayerInteraction;
  provenance: { source: string; year: string; theme: string | null; evidenceLink: string };
}

type LayerSeed = Omit<LayerDefinition,
  "sourceYear" | "provider" | "minCameraHeight" | "maxCameraHeight" | "defaultOpacity" |
  "capability" | "privacyClass" | "loadingStrategy" | "interaction" | "provenance"
>;

const both = (value: LayerAvailability = "available"): Record<CityId, LayerAvailability> => ({ maizuru: value, fujisawa: value });
const thematic = "primary-thematic";
const plateau = "PLATEAU 2025";
const gsi = '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noreferrer">地理院タイル</a>';

const LAYER_SEEDS: LayerSeed[] = [
  { id: "reference-gsi-pale", name: "地理院淡色地図", group: "Reference", source: { kind: "raster", url: "https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png" }, year: "current", plateauTheme: null, availability: both(), defaultVisibility: true, minZoom: 5, maxZoom: 18, opacity: .78, legend: [{ label: "地理的文脈", color: "#e8e7df" }], attribution: gsi, renderMode: "2d", exclusiveGroup: "basemap", evidenceLink: "https://maps.gsi.go.jp/development/ichiran.html" },
  { id: "analysis-city-gap", name: "CITY GAP", group: "Analysis", source: { kind: "mvt", url: "/api/tiles/{city}/meshes/{z}/{x}/{y}.mvt", publicFallback: "mesh_metrics.geojson" }, year: "2020–2025", plateauTheme: "building", availability: both(), defaultVisibility: true, minZoom: 8, maxZoom: 16, opacity: .58, legend: [{ label: "相対的に低い", color: "#dce9e2" }, { label: "要追加調査", color: "#c58b2b" }], attribution: "CITY GAP / e-Stat / PLATEAU", renderMode: "both", exclusiveGroup: thematic, evidenceLink: "data/evidence.json" },
  { id: "analysis-population", name: "65歳以上人口", group: "Analysis", source: { kind: "mvt", url: "/api/tiles/{city}/meshes/{z}/{x}/{y}.mvt", publicFallback: "mesh_metrics.geojson" }, year: "2020", plateauTheme: "building", availability: both(), defaultVisibility: false, minZoom: 8, maxZoom: 16, opacity: .52, legend: [{ label: "少ない", color: "#e8eee9" }, { label: "多い", color: "#ad7a36" }], attribution: "e-Stat 2020 / PLATEAU building allocation", renderMode: "both", exclusiveGroup: thematic, evidenceLink: "data/evidence.json" },
  { id: "analysis-transport", name: "公共交通アクセス", group: "Analysis", source: { kind: "mvt", url: "/api/tiles/{city}/meshes/{z}/{x}/{y}.mvt", publicFallback: "mesh_metrics.geojson" }, year: "2022", plateauTheme: "building", availability: both(), defaultVisibility: false, minZoom: 8, maxZoom: 16, opacity: .52, legend: [{ label: "近い", color: "#e4e9e8" }, { label: "遠い", color: "#607b8b" }], attribution: "国土数値情報 P11 2022 / PLATEAU", renderMode: "both", exclusiveGroup: thematic, evidenceLink: "data/evidence.json" },
  { id: "analysis-medical", name: "医療アクセス", group: "Analysis", source: { kind: "mvt", url: "/api/tiles/{city}/meshes/{z}/{x}/{y}.mvt", publicFallback: "mesh_metrics.geojson" }, year: "2020", plateauTheme: "building", availability: both(), defaultVisibility: false, minZoom: 8, maxZoom: 16, opacity: .52, legend: [{ label: "近い", color: "#eee9e4" }, { label: "遠い", color: "#9b5d4c" }], attribution: "国土数値情報 P04 2020 / PLATEAU", renderMode: "both", exclusiveGroup: thematic, evidenceLink: "data/evidence.json" },
  { id: "plateau-buildings", name: "建物", group: "PLATEAU", source: { kind: "citygml", publicFallback: "plateau_buildings.geojson" }, year: "2025", plateauTheme: "bldg", availability: both("available_with_limitation"), defaultVisibility: false, minZoom: 14, maxZoom: 22, opacity: .86, legend: [{ label: "PLATEAU建物", color: "#b8b8ad" }, { label: "選択建物", color: "#1b5d59", pattern: "outline" }], attribution: plateau, renderMode: "both", exclusiveGroup: null, evidenceLink: "data/plateau_metadata.json" },
  { id: "plateau-roads", name: "道路", group: "PLATEAU", source: { kind: "citygml", publicFallback: "plateau_roads.geojson" }, year: "2025", plateauTheme: "tran", availability: both(), defaultVisibility: false, minZoom: 13, maxZoom: 22, opacity: .72, legend: [{ label: "PLATEAU道路面", color: "#66736f", pattern: "line" }], attribution: plateau, renderMode: "both", exclusiveGroup: null, evidenceLink: "data/plateau_metadata.json" },
  { id: "plateau-terrain", name: "地形・DEM", group: "PLATEAU", source: { kind: "citygml" }, year: "2025", plateauTheme: "dem", availability: both("available_with_limitation"), defaultVisibility: false, minZoom: 10, maxZoom: 22, opacity: .45, legend: [{ label: "PLATEAU DEM", color: "#a9ad91" }], attribution: plateau, renderMode: "3d", exclusiveGroup: null, evidenceLink: "data/platform_registry.json" },
  { id: "plateau-landuse", name: "土地利用", group: "PLATEAU", source: { kind: "citygml" }, year: "2025", plateauTheme: "luse", availability: both(), defaultVisibility: false, minZoom: 11, maxZoom: 18, opacity: .38, legend: [{ label: "土地利用", color: "#98aa86" }], attribution: plateau, renderMode: "both", exclusiveGroup: thematic, evidenceLink: "data/platform_registry.json" },
  { id: "plateau-planning", name: "都市計画", group: "PLATEAU", source: { kind: "citygml" }, year: "2025", plateauTheme: "urf", availability: both(), defaultVisibility: false, minZoom: 10, maxZoom: 18, opacity: .32, legend: [{ label: "都市計画区域", color: "#756f91", pattern: "outline" }], attribution: plateau, renderMode: "both", exclusiveGroup: thematic, evidenceLink: "data/platform_registry.json" },
  { id: "plateau-flood", name: "洪水", group: "PLATEAU", source: { kind: "citygml" }, year: "2025", plateauTheme: "fld", availability: both(), defaultVisibility: false, minZoom: 9, maxZoom: 18, opacity: .42, legend: [{ label: "公式洪水クラス", color: "#6788a0" }], attribution: plateau, renderMode: "both", exclusiveGroup: thematic, evidenceLink: "data/platform_registry.json" },
  { id: "plateau-landslide", name: "土砂災害", group: "PLATEAU", source: { kind: "citygml" }, year: "2025", plateauTheme: "lsld", availability: both(), defaultVisibility: false, minZoom: 9, maxZoom: 18, opacity: .42, legend: [{ label: "公式土砂クラス", color: "#9a7254" }], attribution: plateau, renderMode: "both", exclusiveGroup: thematic, evidenceLink: "data/platform_registry.json" },
  { id: "plateau-tsunami", name: "津波", group: "PLATEAU", source: { kind: "citygml" }, year: "2025", plateauTheme: "tnm", availability: both(), defaultVisibility: false, minZoom: 9, maxZoom: 18, opacity: .42, legend: [{ label: "公式津波クラス", color: "#567b88" }], attribution: plateau, renderMode: "both", exclusiveGroup: thematic, evidenceLink: "data/platform_registry.json" },
  { id: "infra-stations", name: "鉄道駅", group: "Infrastructure", source: { kind: "static-geojson", publicFallback: "stations.geojson" }, year: "2022", plateauTheme: null, availability: both(), defaultVisibility: true, minZoom: 10.5, maxZoom: 22, opacity: .9, legend: [{ label: "駅", color: "#506978" }], attribution: "国土数値情報 P11", renderMode: "2d", exclusiveGroup: null, evidenceLink: "data/evidence.json" },
  { id: "infra-bus", name: "バス停", group: "Infrastructure", source: { kind: "static-geojson", publicFallback: "bus_stops.geojson" }, year: "2022", plateauTheme: null, availability: both(), defaultVisibility: false, minZoom: 13, maxZoom: 22, opacity: .72, legend: [{ label: "バス停", color: "#71858e" }], attribution: "国土数値情報 P11", renderMode: "2d", exclusiveGroup: null, evidenceLink: "data/evidence.json" },
  { id: "infra-medical", name: "医療施設", group: "Infrastructure", source: { kind: "static-geojson", publicFallback: "medical_facilities.geojson" }, year: "2020", plateauTheme: null, availability: both(), defaultVisibility: true, minZoom: 10.5, maxZoom: 22, opacity: .9, legend: [{ label: "医療施設", color: "#985746" }], attribution: "国土数値情報 P04", renderMode: "2d", exclusiveGroup: null, evidenceLink: "data/evidence.json" },
  { id: "planning-context", name: "計画コンテキスト", group: "Planning", source: { kind: "mvt", url: "/api/tiles/{city}/planning/{z}/{x}/{y}.mvt" }, year: "2025", plateauTheme: "urf", availability: both(), defaultVisibility: false, minZoom: 10, maxZoom: 18, opacity: .28, legend: [{ label: "用途・計画", color: "#766d88", pattern: "outline" }], attribution: plateau, renderMode: "both", exclusiveGroup: thematic, evidenceLink: "data/platform_registry.json" },
  { id: "hazard-composite", name: "災害コンテキスト", group: "Hazard", source: { kind: "derived" }, year: "latest official", plateauTheme: "fld/lsld/tnm", availability: both(), defaultVisibility: false, minZoom: 9, maxZoom: 18, opacity: .4, legend: [{ label: "洪水", color: "#66889e" }, { label: "土砂", color: "#987154", pattern: "dash" }, { label: "津波", color: "#517786", pattern: "outline" }], attribution: "PLATEAU / 国土数値情報", renderMode: "both", exclusiveGroup: thematic, evidenceLink: "data/urban_futures_resilience.json" },
  { id: "scenario-footprint", name: "施策範囲", group: "Scenario", source: { kind: "derived" }, year: "counterfactual", plateauTheme: "building/road", availability: { maizuru: "available", fujisawa: "not_available" }, defaultVisibility: false, minZoom: 9, maxZoom: 18, opacity: .48, legend: [{ label: "Scenario A", color: "#25766f" }, { label: "Scenario B", color: "#aa7a2f" }, { label: "Scenario C", color: "#855f78" }], attribution: "CITY GAP scenario model", renderMode: "both", exclusiveGroup: thematic, evidenceLink: "data/intervention_scenarios.json" },
  { id: "scenario-sites", name: "施策候補地", group: "Scenario", source: { kind: "derived" }, year: "counterfactual", plateauTheme: null, availability: { maizuru: "available", fujisawa: "not_available" }, defaultVisibility: false, minZoom: 10, maxZoom: 22, opacity: 1, legend: [{ label: "候補地", color: "#1d635f", pattern: "outline" }], attribution: "CITY GAP scenario model", renderMode: "both", exclusiveGroup: null, evidenceLink: "data/intervention_scenarios.json" },
  { id: "scenario-routes", name: "施策経路", group: "Scenario", source: { kind: "derived" }, year: "counterfactual", plateauTheme: "tran", availability: { maizuru: "available", fujisawa: "not_available" }, defaultVisibility: false, minZoom: 12, maxZoom: 22, opacity: .9, legend: [{ label: "モデル経路", color: "#536f76", pattern: "line" }], attribution: "CITY GAP scenario model", renderMode: "both", exclusiveGroup: null, evidenceLink: "data/intervention_scenarios.json" },
  { id: "validation-primary-route", name: "PLATEAU実験経路", group: "Validation", source: { kind: "static-geojson", publicFallback: "validation/network_disagreement_routes.geojson" }, year: "2025", plateauTheme: "tran", availability: both(), defaultVisibility: false, minZoom: 10, maxZoom: 22, opacity: .92, legend: [{ label: "PLATEAU実験graph", color: "#3f7c8b", pattern: "line" }], attribution: plateau, renderMode: "both", exclusiveGroup: null, evidenceLink: "data/validation/network_cross_validation.json" },
  { id: "validation-reference-route", name: "OSM参照経路", group: "Validation", source: { kind: "static-geojson", publicFallback: "validation/network_disagreement_routes.geojson" }, year: "2026-08-27", plateauTheme: null, availability: both(), defaultVisibility: false, minZoom: 10, maxZoom: 22, opacity: .92, legend: [{ label: "OSM reference", color: "#81a64b", pattern: "dash" }], attribution: "© OpenStreetMap contributors, ODbL", renderMode: "2d", exclusiveGroup: null, evidenceLink: "data/validation/network_cross_validation.json" },
  { id: "validation-disagreement", name: "経路不一致", group: "Validation", source: { kind: "static-geojson", publicFallback: "validation/network_disagreement_routes.geojson" }, year: "2025/2026", plateauTheme: "tran", availability: both(), defaultVisibility: false, minZoom: 9, maxZoom: 22, opacity: 1, legend: [{ label: "不一致sample", color: "#c28a2a", pattern: "outline" }], attribution: "CITY GAP validation", renderMode: "2d", exclusiveGroup: thematic, evidenceLink: "data/validation/network_cross_validation.json" },
  { id: "validation-temporal", name: "年次差分", group: "Validation", source: { kind: "static-geojson", publicFallback: "validation/temporal_change_samples.geojson" }, year: "2023→2025", plateauTheme: "bldg/tran/luse/urf", availability: both("available_with_limitation"), defaultVisibility: false, minZoom: 10, maxZoom: 22, opacity: .68, legend: [{ label: "追加", color: "#2b7a6e" }, { label: "削除", color: "#9a5547", pattern: "dash" }, { label: "変更", color: "#b4862e", pattern: "outline" }], attribution: "PLATEAU 国立市 2023/2025", renderMode: "2d", exclusiveGroup: thematic, evidenceLink: "data/validation/real_temporal_validation.json" },
  { id: "reference-osm", name: "OSM参照ネットワーク", group: "Reference", source: { kind: "derived" }, year: "2026-08-27", plateauTheme: null, availability: both(), defaultVisibility: false, minZoom: 12, maxZoom: 22, opacity: .45, legend: [{ label: "参照network", color: "#78994e", pattern: "dash" }], attribution: "© OpenStreetMap contributors, ODbL", renderMode: "2d", exclusiveGroup: null, evidenceLink: "data/validation/network_cross_validation.json" }
];

function providerFor(layer: LayerSeed): string {
  if (layer.id === "reference-gsi-pale") return "国土地理院";
  if (layer.id === "reference-osm" || layer.id === "validation-reference-route") return "OpenStreetMap contributors";
  if (layer.plateauTheme) return "Project PLATEAU / 国土交通省";
  if (layer.group === "Infrastructure") return "国土数値情報 / 国土交通省";
  return "CITY GAP";
}

function capabilitiesFor(layer: LayerSeed): LayerCapability[] {
  const capabilities: LayerCapability[] = ["screen"];
  if (layer.renderMode === "3d" || layer.renderMode === "both") capabilities.push("inspect");
  if (layer.group === "Scenario" || layer.group === "Hazard") capabilities.push("compare");
  if (layer.group === "Validation" || layer.group === "Reference") capabilities.push("validate");
  if (layer.source.kind === "citygml") capabilities.push("stream");
  return [...new Set(capabilities)];
}

export const LAYER_REGISTRY: LayerDefinition[] = LAYER_SEEDS.map((layer) => ({
  ...layer,
  sourceYear: layer.year,
  provider: providerFor(layer),
  minCameraHeight: layer.minZoom >= 14 ? 25 : layer.minZoom >= 12 ? 75 : 250,
  maxCameraHeight: layer.maxZoom >= 22 ? 25_000 : 100_000,
  defaultOpacity: layer.opacity,
  capability: capabilitiesFor(layer),
  privacyClass: layer.id.startsWith("analysis-") ? "public-aggregate" : "public-official",
  loadingStrategy: layer.source.kind === "citygml" && layer.renderMode !== "2d" ? "camera-stream" : layer.defaultVisibility ? "eager" : layer.minZoom >= 12 ? "semantic-zoom" : "on-demand",
  interaction: layer.group === "Validation" ? "compare" : layer.renderMode === "3d" || layer.renderMode === "both" ? "select" : layer.legend.length ? "hover" : "none",
  provenance: { source: providerFor(layer), year: layer.year, theme: layer.plateauTheme, evidenceLink: layer.evidenceLink },
}));

export interface LayerPreset {
  id: LayerPresetId;
  name: string;
  primaryLayer: string;
  contextLayers: string[];
  description: string;
}

export const LAYER_PRESETS: LayerPreset[] = [
  { id: "discovery", name: "課題を探す", primaryLayer: "analysis-city-gap", contextLayers: ["reference-gsi-pale", "infra-stations", "infra-medical"], description: "CITY GAPと主要施設だけで都市全体を読む" },
  { id: "plateau-detail", name: "PLATEAU詳細", primaryLayer: "plateau-buildings", contextLayers: ["reference-gsi-pale", "plateau-roads", "plateau-terrain"], description: "実建物・道路・DEM地形を同じ場所で確認" },
  { id: "transport", name: "交通を見る", primaryLayer: "analysis-transport", contextLayers: ["reference-gsi-pale", "infra-stations", "infra-bus"], description: "交通アクセスと施設を読む" },
  { id: "medical", name: "医療を見る", primaryLayer: "analysis-medical", contextLayers: ["reference-gsi-pale", "infra-medical"], description: "医療アクセスと施設を読む" },
  { id: "hazard", name: "災害を見る", primaryLayer: "hazard-composite", contextLayers: ["reference-gsi-pale", "plateau-roads", "infra-medical"], description: "公式hazardと道路・医療を重ねる" },
  { id: "scenario-compare", name: "Scenario比較", primaryLayer: "scenario-footprint", contextLayers: ["reference-gsi-pale", "scenario-sites", "scenario-routes"], description: "Before/AfterとA/B/Cを比較" },
  { id: "validation-compare", name: "Validation比較", primaryLayer: "validation-disagreement", contextLayers: ["reference-gsi-pale", "validation-primary-route", "validation-reference-route"], description: "同一ODの実験網と参照網を比較" }
];

export const layerById = (id: string): LayerDefinition | undefined => LAYER_REGISTRY.find((layer) => layer.id === id);
export const presetById = (id: LayerPresetId): LayerPreset => LAYER_PRESETS.find((preset) => preset.id === id) ?? LAYER_PRESETS[0];
export const activeLayerIds = (presetId: LayerPresetId): string[] => {
  const preset = presetById(presetId);
  return [preset.primaryLayer, ...preset.contextLayers];
};
