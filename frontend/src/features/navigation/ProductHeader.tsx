import { routeById } from "../../app/routes";
import { useSpatialContext } from "../../app/context/SpatialContext";

interface Props {
  evidenceStatus: string;
  onOpenMenu(): void;
  onOpenSearch(): void;
}

const stateLabels = { "2020": "2020 統計", "2023": "2023 実測", "2025": "2025 現況", "2040": "2040 シナリオ" } as const;

export function ProductHeader({ evidenceStatus, onOpenMenu, onOpenSearch }: Props) {
  const { state, dispatch } = useSpatialContext();
  const route = routeById(state.task);
  return (
    <header className="product-header">
      <a className="product-brand" href={import.meta.env.BASE_URL} aria-label="CITY GAP ホーム">
        <strong>CITY GAP</strong><span>統計の候補を、建物・道路まで調べる</span>
      </a>
      <div className="spatial-context-bar" aria-label="現在の空間コンテキスト">
        <label><span>都市</span><select aria-label="都市" value={state.city} onChange={(event) => dispatch({ type: "set-city", city: event.target.value as "maizuru" | "fujisawa" })}><option value="maizuru">舞鶴市</option><option value="fujisawa">藤沢市</option></select></label>
        <label><span>都市状態</span><select aria-label="都市状態" value={state.urbanState} onChange={(event) => dispatch({ type: "set-urban-state", urbanState: event.target.value as keyof typeof stateLabels })}>{Object.entries(stateLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <div className="current-task"><span>現在の目的</span><strong>{route.label}</strong></div>
        <div className="evidence-status"><span>根拠</span><strong><i />{evidenceStatus}</strong></div>
      </div>
      <div className="product-header-actions">
        <button type="button" className="search-button" onClick={onOpenSearch} aria-label="地域・施設・シナリオを検索"><kbd>⌘ K</kbd><span>検索</span></button>
        <button type="button" className="utility-button" onClick={onOpenMenu} aria-label="設定と管理を開く">•••</button>
      </div>
    </header>
  );
}
