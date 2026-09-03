export function LoadingState({
  message = "舞鶴市の都市データを読み込んでいます",
  detail = "500mの地域と収録施設を確認中",
}: {
  message?: string;
  detail?: string;
} = {}) {
  return (
    <main className="state-screen" aria-live="polite" aria-busy="true">
      <div className="brand-mark large" aria-hidden="true"><i /><i /><i /></div>
      <h1>CITY GAP</h1>
      <p>{message}</p>
      <div className="loading-bar"><span /></div>
      <small>{detail}</small>
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
