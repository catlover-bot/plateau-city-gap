export function LoadingState() {
  return (
    <main className="state-screen" aria-live="polite" aria-busy="true">
      <div className="brand-mark large" aria-hidden="true"><i /><i /><i /></div>
      <p>舞鶴市の実データを準備しています</p>
      <div className="loading-bar"><span /></div>
      <small>500mメッシュと都市サービスを読み込み中</small>
    </main>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <main className="state-screen error-state" role="alert">
      <span className="state-icon" aria-hidden="true">!</span>
      <h1>データを読み込めませんでした</h1>
      <p>{message}</p>
      <button type="button" onClick={onRetry}>もう一度試す</button>
      <small>公開データファイルが配置されているか確認してください。</small>
    </main>
  );
}

export function EmptyState({ onMethodology }: { onMethodology: () => void }) {
  return (
    <main className="state-screen">
      <span className="state-icon empty" aria-hidden="true">◇</span>
      <h1>表示できるメッシュがありません</h1>
      <p>分析結果は読み込めましたが、地図に表示できるgeometryが0件でした。</p>
      <button type="button" onClick={onMethodology}>データについて確認</button>
    </main>
  );
}
