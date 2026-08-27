import { useEffect, useRef, useState } from "react";
import type { AppData, MeshMetrics } from "../../types";
import { PRODUCT_ROUTES } from "../../app/routes";
import type { ProductTask } from "../../state/spatial/types";

interface Props {
  open: boolean;
  data: AppData;
  onClose(): void;
  onMesh(mesh: MeshMetrics): void;
  onTask(task: ProductTask): void;
}

export function SpatialSearch({ open, data, onClose, onMesh, onTask }: Props) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!open) return;
    setQuery("");
    window.setTimeout(() => inputRef.current?.focus(), 0);
    const close = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose, open]);
  if (!open) return null;
  const normalized = query.trim().toLowerCase();
  const meshes = data.top10.filter((item) => !normalized || `${item.mesh_code} ${item.area_label ?? ""}`.toLowerCase().includes(normalized)).slice(0, 6);
  return <div className="search-backdrop" role="presentation" onMouseDown={(event) => event.currentTarget === event.target && onClose()}><section className="spatial-search" role="dialog" aria-modal="true" aria-label="地域・機能を検索"><header><span>⌕</span><input ref={inputRef} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="地域名、mesh、目的を検索" aria-label="検索語" /><kbd>ESC</kbd></header><div className="search-results"><p>目的</p>{PRODUCT_ROUTES.filter((route) => !normalized || `${route.label} ${route.description}`.toLowerCase().includes(normalized)).map((route) => <button type="button" key={route.id} onClick={() => { onTask(route.id); onClose(); }}><span>目的</span><strong>{route.label}</strong><small>{route.description}</small></button>)}<p>追加調査候補</p>{meshes.map((mesh) => <button type="button" key={mesh.mesh_code} onClick={() => { onMesh(mesh); onClose(); }}><span>500m</span><strong>{mesh.area_label || `Mesh ${mesh.mesh_code}`}</strong><small>{mesh.mesh_code}</small></button>)}</div></section></div>;
}
