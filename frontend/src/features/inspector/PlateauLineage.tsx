import { layerById } from "../../map/layers/layerRegistry";

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

export function PlateauLineage({ primaryLayer }: { primaryLayer: string }) {
  const layer = layerById(primaryLayer);
  const lineage = lineageByLayer[primaryLayer] ?? [{ label: layer?.attribution ?? "公式データ" }, { label: layer?.name ?? primaryLayer }];
  return (
    <section className="plateau-lineage" aria-label="この分析でPLATEAUをどう使ったか">
      <header><strong>この分析でPLATEAUをどう使ったか</strong><span>決定的metadata</span></header>
      <div>{lineage.map((node, index) => <span key={`${node.label}-${index}`}><b className={node.plateau ? "plateau-data-badge" : "source-data-badge"}>{node.plateau ? "PLATEAU" : "SOURCE"}</b><strong>{node.label}</strong>{index < lineage.length - 1 && <i aria-hidden="true">→</i>}</span>)}</div>
      <small>出典: {layer?.attribution ?? "登録済みsource"} · {layer?.year}</small>
    </section>
  );
}
