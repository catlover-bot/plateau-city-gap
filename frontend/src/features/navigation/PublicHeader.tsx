interface Props {
  onRestart(): void;
  onOpenAdvanced(): void;
}

export function PublicHeader({ onRestart, onOpenAdvanced }: Props) {
  return (
    <header className="public-header">
      <button
        type="button"
        className="public-brand"
        onClick={onRestart}
        aria-label="CITY GAPを最初から見る"
      >
        CITY GAP
      </button>
      <strong>舞鶴市</strong>
      <button
        type="button"
        className="public-advanced-link"
        onClick={onOpenAdvanced}
      >
        詳細分析
      </button>
    </header>
  );
}
