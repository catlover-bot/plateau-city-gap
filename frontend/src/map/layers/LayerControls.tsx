import { useMemo, useState } from "react";
import type { CityId, LayerPresetId, MapMode } from "../../state/spatial/types";
import { LAYER_PRESETS, LAYER_REGISTRY, layerById, type LayerDefinition } from "./layerRegistry";

interface Props {
  city: CityId;
  preset: LayerPresetId;
  mapMode: MapMode;
  primaryLayer: string;
  activeLayerIds: string[];
  onPresetChange(preset: LayerPresetId, primaryLayer: string, layerIds: string[]): void;
  onPrimaryLayerChange(layerId: string): void;
  onContextLayerToggle(layerId: string): void;
}

const groups = ["Analysis", "PLATEAU", "Infrastructure", "Planning", "Hazard", "Scenario", "Validation", "Reference"] as const;

function Availability({ layer, city }: { layer: LayerDefinition; city: CityId }) {
  const status = layer.availability[city];
  return <small className={`layer-availability ${status}`}>{status === "available" ? "利用可" : status === "available_with_limitation" ? "条件付き" : "利用不可"}</small>;
}

export function LayerControls({ city, preset, mapMode, primaryLayer, activeLayerIds, onPresetChange, onPrimaryLayerChange, onContextLayerToggle }: Props) {
  const [open, setOpen] = useState(false);
  const active = useMemo(() => new Set(activeLayerIds), [activeLayerIds]);
  const primary = layerById(primaryLayer);
  return (
    <>
      <div className="map-preset-bar" aria-label="地図プリセット">
        <span>表示</span>
        <div role="group" aria-label="用途別の地図表示">
          {LAYER_PRESETS.map((item) => <button key={item.id} type="button" className={preset === item.id ? "active" : ""} aria-pressed={preset === item.id} onClick={() => onPresetChange(item.id, item.primaryLayer, [item.primaryLayer, ...item.contextLayers])}>{item.name}</button>)}
        </div>
        <button type="button" className="layer-catalog-trigger" aria-expanded={open} onClick={() => setOpen((value) => !value)}>レイヤー詳細 <span>{active.size}</span></button>
      </div>
      {open && <section className="layer-catalog" aria-label="Layer Registry">
        <header><div><strong>表示レイヤー</strong><span>Primaryは1つ。Contextは低い不透明度で補助します。</span></div><button type="button" aria-label="レイヤー詳細を閉じる" onClick={() => setOpen(false)}>×</button></header>
        <div className="layer-current"><span>Primary</span><strong>{primary?.name ?? primaryLayer}</strong><small>{primary?.year}</small></div>
        <div className="layer-groups">
          {groups.map((group) => <details key={group} open={group === "PLATEAU" || group === primary?.group}><summary>{group}<span>{LAYER_REGISTRY.filter((layer) => layer.group === group).length}</span></summary>{LAYER_REGISTRY.filter((layer) => layer.group === group && (layer.renderMode === "both" || layer.renderMode === mapMode.replace("map2d", "2d").replace("plateau3d", "3d"))).map((layer) => {
            const isPrimary = layer.exclusiveGroup === "primary-thematic";
            return <label key={layer.id} className={layer.availability[city] === "not_available" ? "disabled" : ""}><input type={isPrimary ? "radio" : "checkbox"} name={isPrimary ? "primary-layer" : undefined} checked={isPrimary ? primaryLayer === layer.id : active.has(layer.id)} disabled={layer.availability[city] === "not_available"} onChange={() => isPrimary ? onPrimaryLayerChange(layer.id) : onContextLayerToggle(layer.id)} /><span><strong>{layer.name}</strong><small>{layer.year} · {layer.plateauTheme ?? layer.source.kind}</small></span><Availability layer={layer} city={city} /></label>;
          })}</details>)}
        </div>
      </section>}
    </>
  );
}
