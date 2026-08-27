import type { MunicipalWorkspaceData } from "../../types";

export function OperationsWorkspace({ data, onShare, onEvidence }: { data: MunicipalWorkspaceData | null; onShare(): void; onEvidence(): void }) {
  const capabilities = data?.registry.capabilities.filter((item) => item.city_code === "262021");
  const available = capabilities?.filter((item) => item.status === "available").length ?? 0;
  return (
    <section className="task-workspace operations-workspace">
      <header className="workspace-intro"><p>MUNICIPAL WORKFLOW</p><h3>確認から自治体レビューへ</h3><span>分析結果ではなく、判断に必要な確認事項を引き継ぎます。</span></header>
      <ol className="municipal-flow"><li className="done"><span>1</span><div><strong>課題候補を確認</strong><small>screening</small></div></li><li className="current"><span>2</span><div><strong>地図・PLATEAUで確認</strong><small>いまここ</small></div></li><li><span>3</span><div><strong>複数案を比較</strong><small>scenario</small></div></li><li><span>4</span><div><strong>現地確認</strong><small>field</small></div></li><li><span>5</span><div><strong>根拠とともにレビュー</strong><small>evidence</small></div></li></ol>
      <div className="operations-status"><span>舞鶴市で利用可能</span><strong>{available}<small> / {capabilities?.length ?? "—"} capabilities</small></strong></div>
      <div className="workspace-actions"><button type="button" className="primary-action" onClick={onShare}>この場所を共有</button><button type="button" onClick={onEvidence}>根拠を確認</button></div>
      <p className="claim-boundary">庁内レビュー、現地確認、権利・運行条件の確認前に採択判断をしません。</p>
    </section>
  );
}
