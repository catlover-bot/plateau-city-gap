import { layerById } from "../../map/layers/layerRegistry";
import type { SpatialSelection } from "../../state/spatial/types";

const lineageByLayer: Record<string, Array<{ label: string; plateau?: boolean }>> = {
  "analysis-city-gap": [{ label: "e-Stat人口統計" }, { label: "PLATEAU建物", plateau: true }, { label: "交通・医療施設" }, { label: "CITY GAP候補" }],
  "analysis-population": [{ label: "国勢調査500m mesh" }, { label: "PLATEAU建物", plateau: true }, { label: "建物配分モデル" }],
  "analysis-transport": [{ label: "PLATEAU住宅建物", plateau: true }, { label: "PLATEAU道路", plateau: true }, { label: "駅・バス停" }, { label: "交通距離" }],
  "analysis-medical": [{ label: "PLATEAU住宅建物", plateau: true }, { label: "PLATEAU道路", plateau: true }, { label: "医療施設" }, { label: "医療距離" }],
  "hazard-composite": [{ label: "PLATEAU道路", plateau: true }, { label: "PLATEAU災害", plateau: true }, { label: "閉鎖仮定S1–S5" }, { label: "到達性差分" }],
  "scenario-footprint": [{ label: "CITY GAP候補" }, { label: "PLATEAU道路", plateau: true }, { label: "配置候補" }, { label: "施策案A/B/C" }],
  "validation-disagreement": [{ label: "PLATEAU道路graph", plateau: true }, { label: "OSM reference" }, { label: "同一OD比較" }, { label: "不一致case" }],
  "validation-temporal": [{ label: "PLATEAU 2023", plateau: true }, { label: "PLATEAU 2025", plateau: true }, { label: "ID・形状match" }, { label: "年次差分" }],
  "plateau-buildings": [{ label: "PLATEAU CityGML", plateau: true }, { label: "建物属性", plateau: true }, { label: "選択建物" }]
};

const CONTRIBUTIONS = [
  { label: "建物用途", layer: "plateau-buildings", theme: "bldg", note: "用途・建物属性" },
  { label: "建物高さ・階数", layer: "plateau-buildings", theme: "bldg", note: "公式属性（存在時）" },
  { label: "建物形状", layer: "plateau-buildings", theme: "bldg", note: "人口配分・3D確認" },
  { label: "道路LOD1", layer: "plateau-roads", theme: "tran", note: "経路graph・道路面" },
  { label: "DEM", layer: "plateau-terrain", theme: "dem", note: "実TIN地形" },
  { label: "土地利用", layer: "plateau-landuse", theme: "luse", note: "計画context" },
  { label: "都市計画", layer: "plateau-planning", theme: "urf", note: "区域・用途context" },
  { label: "洪水", layer: "plateau-flood", theme: "fld", note: "仮定Stress入力" },
] as const;

const USED_BY_ANALYSIS: Record<string, string[]> = {
  "analysis-city-gap": ["bldg", "tran"],
  "analysis-population": ["bldg"],
  "analysis-transport": ["bldg", "tran"],
  "analysis-medical": ["bldg", "tran"],
  "plateau-buildings": ["bldg", "tran", "dem"],
  "hazard-composite": ["bldg", "tran", "dem", "fld"],
  "scenario-footprint": ["bldg", "tran", "dem", "luse", "urf"],
  "validation-disagreement": ["tran"],
  "validation-temporal": ["bldg", "tran", "luse", "urf"],
};

interface Props {
  primaryLayer: string;
  selection: SpatialSelection | null;
  onSelectLayer(layerId: string): void;
}

export function PlateauLineage({ primaryLayer, selection, onSelectLayer }: Props) {
  const layer = layerById(primaryLayer);
  const lineage = lineageByLayer[primaryLayer] ?? [{ label: layer?.attribution ?? "公式データ" }, { label: layer?.name ?? primaryLayer }];
  const usedThemes = new Set(USED_BY_ANALYSIS[primaryLayer] ?? (selection?.type === "building" ? ["bldg", "tran", "dem"] : []));
  return (
    <>
      <section className="plateau-lineage" aria-label="この分析でPLATEAUをどう使ったか">
        <header><strong>この分析でPLATEAUをどう使ったか</strong><span>決定的metadata</span></header>
        <div>{lineage.map((node, index) => <span key={`${node.label}-${index}`}><b className={node.plateau ? "plateau-data-badge" : "source-data-badge"}>{node.plateau ? "PLATEAU" : "SOURCE"}</b><strong>{node.label}</strong>{index < lineage.length - 1 && <i aria-hidden="true">→</i>}</span>)}</div>
        <small>出典: {layer?.provider ?? layer?.attribution ?? "登録済みsource"} · {layer?.sourceYear ?? layer?.year}</small>
      </section>
      <section className="plateau-contribution" aria-label="PLATEAU Contribution">
        <header><div><span>PLATEAU CONTRIBUTION</span><strong>この結果に使ったPLATEAU</strong></div><small>項目を選ぶと該当layerへ移動</small></header>
        <div className="contribution-grid">
          {CONTRIBUTIONS.map((item) => {
            const used = usedThemes.has(item.theme);
            const definition = layerById(item.layer);
            return <button key={`${item.theme}-${item.label}`} type="button" className={used ? "used" : "available"} onClick={() => onSelectLayer(item.layer)} title={`${definition?.provider ?? "Project PLATEAU"} ${definition?.sourceYear ?? "2025"} · theme ${item.theme}`}><span aria-hidden="true">{used ? "✓" : "＋"}</span><strong>{item.label}</strong><small>{item.note}</small></button>;
          })}
        </div>
        <p><b>✓ 使用</b> は現在の結果へ決定的に入力。<b>＋ 確認可</b> は追加contextです。</p>
      </section>
    </>
  );
}
