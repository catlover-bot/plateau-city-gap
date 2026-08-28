import { useMemo, useState, type ReactNode } from "react";

export function StatusChip({ value }: { value: string | null | undefined }) {
  const normalized = value ?? "unknown";
  const tone = [
    "available",
    "active",
    "passed",
    "promoted",
    "reviewed",
    "succeeded",
    "current",
    "closed",
  ].includes(normalized)
    ? "positive"
    : ["failed", "rejected", "unavailable"].includes(normalized)
      ? "negative"
      : ["warning", "partial", "changes_requested", "on_hold"].includes(
            normalized,
          )
        ? "warning"
        : "neutral";
  return (
    <span className={`service-status ${tone}`}>
      {normalized.replaceAll("_", " ")}
    </span>
  );
}

export function ServiceTable({
  caption,
  columns,
  rows,
  empty,
  rowKey,
  onRow,
  pageSize = 20,
}: {
  caption: string;
  columns: Array<{
    key: string;
    label: string;
    render?(row: Record<string, unknown>): ReactNode;
  }>;
  rows: Array<Record<string, unknown>>;
  empty: string;
  rowKey(row: Record<string, unknown>): string;
  onRow?(row: Record<string, unknown>): void;
  pageSize?: number;
}) {
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [descending, setDescending] = useState(false);
  const [page, setPage] = useState(0);
  const [hiddenColumns, setHiddenColumns] = useState<Set<string>>(
    () => new Set(),
  );
  const visibleColumns = columns.filter(
    (column) => !hiddenColumns.has(column.key),
  );
  const filteredRows = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("ja");
    const filtered = normalizedQuery
      ? rows.filter((row) =>
          columns.some((column) =>
            String(row[column.key] ?? "")
              .toLocaleLowerCase("ja")
              .includes(normalizedQuery),
          ),
        )
      : rows;
    if (!sortKey) return filtered;
    return [...filtered].sort((left, right) => {
      const first = String(left[sortKey] ?? "");
      const second = String(right[sortKey] ?? "");
      const result = first.localeCompare(second, "ja", { numeric: true });
      return descending ? -result : result;
    });
  }, [columns, descending, query, rows, sortKey]);
  const pageCount = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const currentPage = Math.min(page, pageCount - 1);
  const pageRows = filteredRows.slice(
    currentPage * pageSize,
    (currentPage + 1) * pageSize,
  );

  if (rows.length === 0)
    return (
      <ServiceEmpty
        title={empty}
        detail="検索条件またはデータ登録状態を確認してください。"
      />
    );
  return (
    <div className="service-table-system">
      <div className="service-table-tools">
        <label>
          表を絞り込む
          <input
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(0);
            }}
          />
        </label>
        <details>
          <summary>表示列</summary>
          {columns.map((column) => (
            <label key={column.key}>
              <input
                type="checkbox"
                checked={!hiddenColumns.has(column.key)}
                onChange={() =>
                  setHiddenColumns((current) => {
                    const next = new Set(current);
                    if (next.has(column.key)) next.delete(column.key);
                    else if (current.size < columns.length - 1)
                      next.add(column.key);
                    return next;
                  })
                }
              />
              {column.label}
            </label>
          ))}
        </details>
      </div>
      <div className="service-table-wrap">
        <table className="service-table">
          <caption>{caption}</caption>
          <thead>
            <tr>
              {visibleColumns.map((column) => (
                <th key={column.key} scope="col">
                  <button
                    type="button"
                    onClick={() => {
                      setDescending(
                        sortKey === column.key ? !descending : false,
                      );
                      setSortKey(column.key);
                      setPage(0);
                    }}
                    aria-label={`${column.label}で並べ替え`}
                  >
                    {column.label}
                    {sortKey === column.key ? (descending ? " ↓" : " ↑") : ""}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row) => (
              <tr
                key={rowKey(row)}
                className={onRow ? "clickable" : undefined}
                tabIndex={onRow ? 0 : undefined}
                onClick={onRow ? () => onRow(row) : undefined}
                onKeyDown={
                  onRow
                    ? (event) => {
                        if (event.key === "Enter" || event.key === " ")
                          onRow(row);
                      }
                    : undefined
                }
              >
                {visibleColumns.map((column) => (
                  <td key={column.key}>
                    {column.render
                      ? column.render(row)
                      : String(row[column.key] ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <footer className="service-table-pagination">
        <span>
          {filteredRows.length}件 · {currentPage + 1}/{pageCount}ページ
        </span>
        <button
          type="button"
          disabled={currentPage === 0}
          onClick={() => setPage((value) => Math.max(0, value - 1))}
        >
          前へ
        </button>
        <button
          type="button"
          disabled={currentPage >= pageCount - 1}
          onClick={() => setPage((value) => Math.min(pageCount - 1, value + 1))}
        >
          次へ
        </button>
      </footer>
    </div>
  );
}

export function ServiceEmpty({
  title,
  detail,
  action,
}: {
  title: string;
  detail: string;
  action?: ReactNode;
}) {
  return (
    <div className="service-empty">
      <span aria-hidden="true">◇</span>
      <strong>{title}</strong>
      <p>{detail}</p>
      {action}
    </div>
  );
}

export function ServiceError({
  message,
  requestId,
  onRetry,
}: {
  message: string;
  requestId?: string | null;
  onRetry(): void;
}) {
  return (
    <main className="service-state error" role="alert">
      <span aria-hidden="true">!</span>
      <h1>サービスを読み込めませんでした</h1>
      <p>{message}</p>
      {requestId && <code>Request ID: {requestId}</code>}
      <button type="button" onClick={onRetry}>
        再読み込み
      </button>
    </main>
  );
}

export function ServiceLoading() {
  return (
    <main className="service-state" aria-live="polite" aria-busy="true">
      <div className="service-loader" />
      <h1>CITY GAP</h1>
      <p>自治体ワークスペースを読み込んでいます</p>
    </main>
  );
}
