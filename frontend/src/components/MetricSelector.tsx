import type { MetricMode } from "../types";

const MODES: Array<{ id: MetricMode; label: string; short: string; description: string }> = [
  { id: "gap", label: "CITY GAP", short: "総合", description: "高齢者数・交通距離・医療距離の相対値を重ねた追加調査指標" },
  { id: "elderly", label: "高齢人口", short: "人口", description: "500mメッシュの65歳以上人口の相対順位" },
  { id: "transport", label: "交通アクセス", short: "交通", description: "メッシュ中心から最寄り駅・バス停までの直線距離の相対順位" },
  { id: "medical", label: "医療アクセス", short: "医療", description: "メッシュ中心から最寄り医療機関までの直線距離の相対順位" }
];

interface MetricSelectorProps {
  value: MetricMode;
  onChange: (mode: MetricMode) => void;
}
export function MetricSelector({ value, onChange }: MetricSelectorProps) {
  return (
    <div className="metric-selector" role="group" aria-label="地図で見る指標">
      {MODES.map((mode) => (
        <button
          type="button"
          key={mode.id}
          className={value === mode.id ? "active" : ""}
          aria-pressed={value === mode.id}
          aria-label={mode.label}
          title={mode.description}
          onClick={() => onChange(mode.id)}
        >
          <span className="metric-label-long">{mode.label}</span>
          <span className="metric-label-short">{mode.short}</span>
        </button>
      ))}
    </div>
  );
}
