import type { MetricMode } from "../types";

const MODES: Array<{ id: MetricMode; label: string; short: string }> = [
  { id: "gap", label: "CITY GAP", short: "総合" },
  { id: "elderly", label: "高齢人口", short: "人口" },
  { id: "transport", label: "交通アクセス", short: "交通" },
  { id: "medical", label: "医療アクセス", short: "医療" }
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
          onClick={() => onChange(mode.id)}
        >
          <span className="metric-label-long">{mode.label}</span>
          <span className="metric-label-short">{mode.short}</span>
        </button>
      ))}
    </div>
  );
}
