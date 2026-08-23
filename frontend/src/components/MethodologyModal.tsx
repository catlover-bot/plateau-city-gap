import { useEffect, useRef } from "react";
import type { AppData } from "../types";
import { comparisonMeshScope } from "../lib/format";
import {
  formatBuildingCount,
  referenceCoverageSentence,
  summarizePlateauCoverage,
  top10CoverageLabel,
  top10CoverageSentence,
} from "../lib/plateau";

interface MethodologyModalProps {
  open: boolean;
  data: AppData;
  onClose: () => void;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function sourceRows(value: unknown): Array<{ label: string; title: string; year: string }> {
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    const labels: Record<string, string> = {
      population: "人口",
      bus_stops: "バス停",
      medical: "医療",
      plateau: "3D都市",
      stations: "駅",
      boundary: "行政界"
    };
    return Object.entries(value).flatMap(([key, item]) => {
      if (typeof item !== "object" || item === null) return [];
      const row = item as Record<string, unknown>;
      return [{
        label: labels[key] ?? "データ",
        title: String(row.provider ?? row.title ?? "—"),
        year: typeof row.year === "number" ? `${row.year}年` : "年次不明"
      }];
    });
  }
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (typeof item !== "object" || item === null) return [];
    const row = item as Record<string, unknown>;
    const id = String(row.id ?? "");
    const label = id.includes("estat") ? "人口" : id.includes("p11") ? "バス停" : id.includes("p04") ? "医療" : id.includes("plateau") ? "3D都市" : "データ";
    return [{
      label,
      title: String(row.provider ?? row.title ?? "—"),
      year: typeof row.year === "number" ? `${row.year}年` : "年次不明"
    }];
  });
}

export function MethodologyModal({ open, data, onClose }: MethodologyModalProps) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
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
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )).filter((element) => !element.hidden && element.getAttribute("aria-hidden") !== "true");
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
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => {
      window.removeEventListener("keydown", handleKey);
      previouslyFocused?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;
  const limitations = [
    ...stringList(data.manifest.limitations),
    ...stringList(data.summary.limitations)
  ].filter((item, index, all) => all.indexOf(item) === index);
  const generatedAt = data.manifest.generated_at
    ? new Date(data.manifest.generated_at).toLocaleString("ja-JP")
    : "—";
  const sources = sourceRows(data.manifest.source_datasets);
  const plateauCoverage = summarizePlateauCoverage(data.plateauMetadata);
  const comparisonScope = comparisonMeshScope(data.summary.record_counts?.population_unaffected);
  const eligibleCount = data.summary.record_counts?.primary_rank_eligible_meshes;
  const analysisCrs = data.summary.analysis_crs?.code ?? "分析用投影座標系";

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section ref={dialogRef} tabIndex={-1} className="methodology-modal" role="dialog" aria-modal="true" aria-labelledby="methodology-title">
        <div className="modal-header">
          <div>
            <p>DATA &amp; METHODOLOGY</p>
            <h2 id="methodology-title">この数字は何？</h2>
          </div>
          <button ref={closeRef} type="button" aria-label="閉じる" onClick={onClose}>×</button>
        </div>
        <div className="modal-content">
          <p className="method-lead">
            CITY GAPは、地域の人口・高齢化というニーズと、公共交通・医療へのアクセシビリティの空間的なミスマッチを探すサービスです。
            「課題の確定」ではなく、現地確認や施策検討を始めるための候補を示します。
          </p>

          <h3>使用データ</h3>
          <div className="dataset-grid">
            {(sources.length > 0 ? sources : [
              { label: "人口", title: "e-Stat 国勢調査", year: "2020年・500mメッシュ" },
              { label: "バス停", title: "国土数値情報 P11", year: "2022年" },
              { label: "医療", title: "国土数値情報 P04", year: "2020年" },
              { label: "3D都市", title: "Project PLATEAU", year: "舞鶴市・2025年度" }
            ]).map((source) => (
              <div key={`${source.label}-${source.title}`}>
                <span>{source.label}</span><strong>{source.title}</strong><small>{source.year}</small>
              </div>
            ))}
          </div>

          <h3>計算方法</h3>
          <div className="formula-card">
            <code>高齢者数 percentile × 交通距離 percentile × 医療距離 percentile</code>
            <p>
              距離は{analysisCrs}上で、500mメッシュ中心から施設までを測ったユークリッド直線距離です。
              percentileの比較母集団は{comparisonScope}です。Primaryは、そのうち人口20人以上・65歳以上10人以上を満たす
              {eligibleCount ? `${eligibleCount.toLocaleString("ja-JP")}メッシュ` : "メッシュ"}をランキング対象にする条件です。
            </p>
            <p>画面では実距離を主表示し、percentileは「この都市の比較対象内でどの位置か」を添えます。97 percentileは危険度97%でも、交通困難地域の認定でもありません。</p>
          </div>

          {data.finalDemo ? (
            <>
              <h3>What-ifの再計算</h3>
              <div className="formula-card scenario-formula">
                <code>new distance = min(現在の交通距離, 仮想地点への直線距離)</code>
                <p>
                  クリック座標をWGS84から{analysisCrs}へ変換し、{comparisonScope}で交通距離percentileと探索スコアを再計算します。
                  値は入力地点から決定論的に計算し、固定のBefore / Afterは使いません。
                </p>
              </div>

              <h3>PLATEAU建物の範囲</h3>
              <div className="plateau-method-note">
                <strong>
                  公式配布全体 {formatBuildingCount(plateauCoverage.distributionCount)} / CITY GAP Top 10内 {top10CoverageLabel(plateauCoverage)}
                </strong>
                <p>
                  {top10CoverageSentence(plateauCoverage)}画面では架空建物を作りません。
                  これはPLATEAUへの評価ではなく、年度・整備範囲・LOD方針を含む都市データの空白を、意思決定上の発見として扱います。
                  {referenceCoverageSentence(plateauCoverage)}
                </p>
              </div>

              <h3>Why PLATEAU — 30秒で答える</h3>
              <div className="formula-card why-plateau-card">
                <strong>今できたこと</strong>
                <p>
                  公式市境界・駅と500m分析を重ね、建物収録範囲を全44,640棟で検証しました。
                  全市{data.finalDemo.deep_dive.overall_rank}位の{data.finalDemo.deep_dive.area_label}では、
                  公式建物{data.finalDemo.deep_dive.plateau_building_count.toLocaleString("ja-JP")}棟、道路面、建物用途・高さ・階数・面積・LODを実物で確認し、道路面上から配置探索アンカーを生成しています。
                </p>
                <strong>まだしていないこと</strong>
                <p>
                  建物起点の歩行経路、道路接続・横断・坂を含む到達圏、用地や運行条件を含む評価です。
                  道路LOD1は面形状で接続トポロジーを持たないため、直線距離を経路距離と偽って置き換えていません。
                </p>
              </div>
            </>
          ) : (
            <div className="plateau-method-note">
              <strong>藤沢市は横展開検証モード</strong>
              <p>同じ人口・交通・医療の計算処理とPLATEAU行政界・駅を使用しています。3D Deep Diveと施策シミュレーションは、この検証範囲には含めません。</p>
            </div>
          )}

          <h3>2D分析とPLATEAUの役割</h3>
          <div className="formula-card">
            <p>2D統計で追加調査候補を発見し、PLATEAUで都市空間の文脈確認と施策候補の空間制約へ進みます。CITY GAP探索スコア自体は、PLATEAU建物がなければ計算できない指標ではありません。</p>
          </div>

          <h3>大切な限界</h3>
          <ul className="limitation-list">
            {(limitations.length > 0 ? limitations : [
              "公共交通の運行頻度を評価していません。",
              "デマンド交通や施設送迎を含みません。",
              "道路距離・坂・歩行可能性を評価していません。",
              "データ年次は統一されていません。",
              "医療施設の現在の開設状況を保証しません。"
            ]).map((limitation) => <li key={limitation}>{limitation}</li>)}
          </ul>

          <div className="provenance-row">
            <span>Analysis {data.manifest.analysis_version ?? "—"}</span>
            <span>生成: {generatedAt}</span>
            <span>PLATEAU: Top 10内 {top10CoverageLabel(plateauCoverage)} / 3D Deep Dive subset {plateauCoverage.referenceIncluded ? formatBuildingCount(plateauCoverage.referenceCount) : "収録状況を確認できません"}</span>
          </div>
          {data.warnings.length > 0 && (
            <details className="data-warnings">
              <summary>読み込めなかった任意レイヤー（{data.warnings.length}）</summary>
              <ul>{data.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
            </details>
          )}
        </div>
      </section>
    </div>
  );
}
