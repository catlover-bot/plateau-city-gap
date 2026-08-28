import type { UrbanObjectGraph, UrbanObjectKind, UrbanObjectNode } from "../../map/core/urbanObjectGraph";

interface Props {
  graph: UrbanObjectGraph;
  onSelectObject(node: UrbanObjectNode): void;
}

const SELECTABLE = new Set<UrbanObjectKind>(["mesh", "building_group", "building", "road", "terrain", "planning", "hazard", "site"]);

const KIND_LABELS: Record<UrbanObjectKind, string> = {
  city: "都市",
  district: "地区",
  mesh: "500mメッシュ",
  building_group: "PLATEAU建物群",
  building: "PLATEAU建物",
  road: "PLATEAU道路",
  terrain: "PLATEAU地形",
  landuse: "土地利用",
  planning: "都市計画",
  hazard: "災害",
  site: "施策地点",
  analysis: "分析",
  finding: "Finding",
};

function valueLabel(value: string | number | boolean | null): string {
  if (value === null) return "データなし";
  if (typeof value === "boolean") return value ? "はい" : "いいえ";
  return String(value);
}

export function ObjectLens({ graph, onSelectObject }: Props) {
  const selected = graph.nodes.find((node) => node.id === graph.selectedObjectId)
    ?? graph.nodes.find((node) => node.kind === "mesh")
    ?? graph.nodes[0];
  const related = graph.relations
    .filter((relation) => relation.from === selected?.id || relation.to === selected?.id)
    .map((relation) => ({
      relation,
      node: graph.nodes.find((node) => node.id === (relation.from === selected?.id ? relation.to : relation.from)),
    }))
    .filter((item): item is { relation: typeof graph.relations[number]; node: UrbanObjectNode } => Boolean(item.node));
  const findingRelations = graph.relations.filter((relation) => relation.from.startsWith("finding:") || relation.to.startsWith("finding:"));

  return (
    <section className="object-lens" aria-label="PLATEAU Object Lens">
      <header>
        <span>PLATEAU OBJECT LENS</span>
        <strong>{selected ? KIND_LABELS[selected.kind] : "都市地物"}</strong>
      </header>
      {selected && <div className="object-lens-current">
        <h3>{selected.label}</h3>
        <dl>
          <div><dt>Source</dt><dd>{selected.source}</dd></div>
          <div><dt>Year</dt><dd>{selected.year}</dd></div>
          {Object.entries(selected.attributes).slice(0, 6).map(([key, value]) => (
            <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{valueLabel(value)}</dd></div>
          ))}
        </dl>
      </div>}
      <div className="object-lens-relations">
        <h3>この地物との関係</h3>
        {related.length === 0 ? <p>関係地物は選択後に表示します。</p> : related.map(({ relation, node }) => (
          <button key={`${relation.from}-${relation.to}-${relation.kind}`} type="button" disabled={!SELECTABLE.has(node.kind)} onClick={() => onSelectObject(node)}>
            <span>{relation.label}</span>
            <strong>{node.label}</strong>
            <small>{relation.semantics}</small>
          </button>
        ))}
      </div>
      <details className="object-lens-trace" open={Boolean(graph.findingId)}>
        <summary>Finding ↔ PLATEAU 追跡</summary>
        {findingRelations.map((relation) => (
          <p key={`${relation.from}-${relation.to}-${relation.kind}`}><b>{relation.label}</b><span>{relation.semantics}</span></p>
        ))}
      </details>
      <div className="plateau-off-audit">
        <strong>PLATEAUを外すと失われるもの</strong>
        <ul>{graph.plateauOffLoss.map((loss) => <li key={loss}>{loss}</li>)}</ul>
      </div>
      <div className="source-timeline" aria-label="Source Timeline">
        <span><b>2020</b> 統計</span><i aria-hidden="true" />
        <span><b>2025</b> PLATEAU</span><i aria-hidden="true" />
        <span><b>現行</b> CITY GAP分析</span>
      </div>
    </section>
  );
}
