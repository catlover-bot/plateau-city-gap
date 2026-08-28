import type { ReactNode } from "react";

export function StatusChip({ value }: { value: string | null | undefined }) {
  const normalized = value ?? "unknown";
  const tone = ["available", "active", "passed", "promoted", "reviewed", "succeeded", "current", "closed"].includes(normalized)
    ? "positive"
    : ["failed", "rejected", "unavailable"].includes(normalized)
      ? "negative"
      : ["warning", "partial", "changes_requested", "on_hold"].includes(normalized)
        ? "warning"
        : "neutral";
  return <span className={`service-status ${tone}`}>{normalized.replaceAll("_", " ")}</span>;
}

export function ServiceTable({
  caption,
  columns,
  rows,
  empty,
  rowKey,
  onRow
}: {
  caption: string;
  columns: Array<{ key: string; label: string; render?(row: Record<string, unknown>): ReactNode }>;
  rows: Array<Record<string, unknown>>;
  empty: string;
  rowKey(row: Record<string, unknown>): string;
  onRow?(row: Record<string, unknown>): void;
}) {
  if (rows.length === 0) return <ServiceEmpty title={empty} detail="検索条件またはデータ登録状態を確認してください。" />;
  return <div className="service-table-wrap"><table className="service-table"><caption>{caption}</caption><thead><tr>{columns.map((column) => <th key={column.key} scope="col">{column.label}</th>)}</tr></thead><tbody>{rows.map((row) => <tr key={rowKey(row)} className={onRow ? "clickable" : undefined} onClick={onRow ? () => onRow(row) : undefined}>{columns.map((column) => <td key={column.key}>{column.render ? column.render(row) : String(row[column.key] ?? "—")}</td>)}</tr>)}</tbody></table></div>;
}

export function ServiceEmpty({ title, detail, action }: { title: string; detail: string; action?: ReactNode }) {
  return <div className="service-empty"><span aria-hidden="true">◇</span><strong>{title}</strong><p>{detail}</p>{action}</div>;
}

export function ServiceError({ message, requestId, onRetry }: { message: string; requestId?: string | null; onRetry(): void }) {
  return <main className="service-state error" role="alert"><span aria-hidden="true">!</span><h1>サービスを読み込めませんでした</h1><p>{message}</p>{requestId && <code>Request ID: {requestId}</code>}<button type="button" onClick={onRetry}>再読み込み</button></main>;
}

export function ServiceLoading() {
  return <main className="service-state" aria-live="polite" aria-busy="true"><div className="service-loader" /><h1>CITY GAP</h1><p>自治体ワークスペースを読み込んでいます</p></main>;
}
