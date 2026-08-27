import type { SpatialSelection } from "../../state/spatial/types";

export function DetailWorkspace({ selection, onOpen3D }: { selection: SpatialSelection | null; onOpen3D(): void }) {
  return (
    <section className="task-workspace detail-workspace">
      <header className="workspace-intro"><p>PLATEAU DETAIL</p><h3>建物・道路を実在形状で確認</h3><span>2Dで場所を保ったまま、必要なときだけ3Dを読み込みます。</span></header>
      <div className="detail-layer-list">
        <div><b className="plateau-data-badge">PLATEAU</b><span><strong>建物</strong><small>用途・高さ・階数・LOD</small></span></div>
        <div><b className="plateau-data-badge">PLATEAU</b><span><strong>道路</strong><small>道路面・経路との関係</small></span></div>
        <div><b className="plateau-data-badge">PLATEAU</b><span><strong>地形・計画・災害</strong><small>利用可否はレイヤー詳細で確認</small></span></div>
      </div>
      <button type="button" className="primary-action" onClick={onOpen3D}>{selection ? "選択地点をPLATEAU 3Dで開く" : "PLATEAU 3Dを開く"}</button>
      {!selection && <p className="workspace-hint">地図上の500mメッシュを先に選ぶと、その地点へ移動します。</p>}
    </section>
  );
}
