import { useEffect, useRef } from "react";
import type { EvidenceData, InterventionPlan } from "../types";
import { formatDistance, formatScore } from "../lib/format";

interface EvidenceModalProps {
  open: boolean;
  evidence: EvidenceData | null;
  plan: InterventionPlan | null;
  onClose: () => void;
}

export function EvidenceModal({ open, evidence, plan, onClose }: EvidenceModalProps) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => {
      window.removeEventListener("keydown", handleKey);
      previous?.focus();
    };
  }, [open, onClose]);
  if (!open || !evidence) return null;

  const rankOne = evidence.rank_one;
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="methodology-modal evidence-modal" role="dialog" aria-modal="true" aria-labelledby="evidence-title">
        <div className="modal-header">
          <div><p>EVIDENCE CHAIN</p><h2 id="evidence-title">この数字を根拠まで辿る</h2></div>
          <button ref={closeRef} type="button" aria-label="閉じる" onClick={onClose}>×</button>
        </div>
        <div className="modal-content">
          <p className="method-lead">{evidence.philosophy}</p>

          <h3>公共交通 {formatDistance(rankOne.transport.value_m)}</h3>
          <dl className="evidence-chain-list">
            <div><dt>起点</dt><dd>{rankOne.transport.origin} · Mesh {rankOne.mesh_code}</dd></div>
            <div><dt>到達先</dt><dd>{rankOne.transport.destination}</dd></div>
            <div><dt>データ</dt><dd>{rankOne.transport.dataset}</dd></div>
            <div><dt>計算</dt><dd>{rankOne.transport.crs} · {rankOne.transport.calculation}</dd></div>
            <div><dt>丸め前</dt><dd><code>{rankOne.transport.value_m.toFixed(9)} m</code></dd></div>
          </dl>

          <h3>Score C {formatScore(rankOne.score_c.value)}</h3>
          <div className="evidence-formula">
            {Object.entries(rankOne.score_c.components).map(([key, value], index) => (
              <span key={key}><small>{key.replace("_percentile", "")}</small><strong>{value.toFixed(9)}</strong>{index < 2 && <i>×</i>}</span>
            ))}
            <b>= {rankOne.score_c.value.toFixed(10)}</b>
          </div>

          {plan && (
            <>
              <h3>施策案 {plan.site_count}地点</h3>
              <p className="evidence-equation">{evidence.intervention.formula}</p>
              <div className="evidence-sites">
                {plan.sites.map((site) => (
                  <div key={site.candidate_id}>
                    <span>地点 {site.site_order}</span>
                    <strong>{site.road_name ? `${site.road_name}付近` : site.nearest_existing_transport_name}</strong>
                    <code>{site.latitude.toFixed(9)}, {site.longitude.toFixed(9)}</code>
                    <small>PLATEAU道路LOD1面代表点 · 既存交通まで{formatDistance(site.existing_transport_distance_m)}</small>
                  </div>
                ))}
              </div>
              <p className="evidence-equation">Score C合計純減少: {plan.impact.total_score_c_reduction.toFixed(9)} · 独立再計算済み</p>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
