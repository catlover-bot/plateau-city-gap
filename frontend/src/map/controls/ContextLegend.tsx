import { layerById } from "../layers/layerRegistry";

export function ContextLegend({ layerId }: { layerId: string }) {
  const layer = layerById(layerId);
  if (!layer) return null;
  return (
    <section className="context-legend" aria-label={`${layer.name}の凡例`}>
      <header><span>PRIMARY</span><strong>{layer.name}</strong><small>{layer.year}</small></header>
      <div>{layer.legend.map((stop) => <span key={stop.label}><i className={stop.pattern ?? "solid"} style={{ "--legend-color": stop.color } as React.CSSProperties} /><b>{stop.label}</b></span>)}</div>
    </section>
  );
}
