import { useEffect, useRef } from "react";
import type { EvidenceData, InterventionPlan } from "../types";
import { formatDistance, formatScore } from "../lib/format";

interface EvidenceModalProps {
  open: boolean;
  mode?: "advanced" | "guided";
  evidence: EvidenceData | null;
  plan: InterventionPlan | null;
  onClose: () => void;
}

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

function GuidedEvidenceContent({ evidence, plan }: { evidence: EvidenceData; plan: InterventionPlan | null }) {
  const rankOne = evidence.rank_one;
  return (
    <>
      <p className="method-lead">表示している値の出典と、計算の考え方を確認できます。</p>

      <h3>使用しているデータ</h3>
      <dl className="evidence-chain-list guided-evidence-sources">
        <div><dt>人口・高齢者</dt><dd>国勢調査 2020</dd></div>
        <div><dt>公共交通</dt><dd>{rankOne.transport.dataset}、PLATEAU駅 2025</dd></div>
        <div><dt>医療施設</dt><dd>{rankOne.medical.dataset}</dd></div>
        <div><dt>街の形</dt><dd>PLATEAU 舞鶴市 2025（建物・道路・地形）</dd></div>
        <div><dt>分析方法</dt><dd>CITY GAPの再現可能な計算手順</dd></div>
      </dl>

      <h3>距離と候補度の計算</h3>
      <p className="evidence-explanation">交通・医療への距離は、500mメッシュの中心から最寄りの施設までの直線距離です。</p>
      <p className="evidence-explanation">高齢者人口、交通距離、医療距離の市内での相対値を組み合わせ、追加調査候補の並び順を作ります。危険度や政策の優先順位を示す数字ではありません。</p>

      {plan && (
        <>
          <h3>仮想地点を加えた条件</h3>
          <p className="evidence-equation">現在の距離と、仮想地点までの直線距離を比べ、短い方を使って再計算しています。</p>
          <div className="evidence-sites">
            {plan.sites.map((site) => (
              <div key={site.candidate_id}>
                <span>仮想地点 {site.site_order}</span>
                <strong>{site.road_name ? `${site.road_name}付近` : `${site.nearest_existing_transport_name}付近`}</strong>
                <small>PLATEAUの道路上に置いた比較用の点 · 現在の交通まで{formatDistance(site.existing_transport_distance_m)}</small>
              </div>
            ))}
          </div>
          <p className="evidence-equation">これは条件を変えた比較であり、設置の可否や実施後の効果を予測するものではありません。</p>
        </>
      )}
    </>
  );
}

export function EvidenceModal({ open, mode = "advanced", evidence, plan, onClose }: EvidenceModalProps) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const dialog = dialogRef.current;
      if (!dialog) return;
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
      if (focusable.length === 0) {
        event.preventDefault();
        dialog.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !dialog.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || !dialog.contains(active))) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => {
      window.removeEventListener("keydown", handleKey);
      previous?.focus();
    };
  }, [open, onClose]);
  if (!open || !evidence) return null;

  const rankOne = evidence.rank_one;
  const guided = mode === "guided";
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section ref={dialogRef} className="methodology-modal evidence-modal" role="dialog" aria-modal="true" aria-labelledby="evidence-title" data-ui-mode={mode} tabIndex={-1}>
        <div className="modal-header">
          <div><p>{guided ? "詳しい出典" : "EVIDENCE CHAIN"}</p><h2 id="evidence-title">{guided ? "その数字の根拠" : "この数字を根拠まで辿る"}</h2></div>
          <button ref={closeRef} type="button" aria-label="閉じる" onClick={onClose}>×</button>
        </div>
        <div className="modal-content">
          {guided ? <GuidedEvidenceContent evidence={evidence} plan={plan} /> : <>
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
          </>}
        </div>
      </section>
    </div>
  );
}
