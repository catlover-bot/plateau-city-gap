import type { SpatialResolution } from "../../state/spatial/types";

const STEPS: Array<{ id: SpatialResolution; label: string; hint: string }> = [
  { id: "city", label: "都市", hint: "舞鶴全体" },
  { id: "district", label: "地区", hint: "統計区" },
  { id: "mesh", label: "500m", hint: "候補を絞る" },
  { id: "building_group", label: "建物群", hint: "PLATEAU" },
  { id: "building", label: "建物", hint: "属性を確認" },
  { id: "road", label: "道路", hint: "距離関係" },
  { id: "site", label: "施策", hint: "案を比較" },
];

interface Props {
  value: SpatialResolution;
  onChange(value: SpatialResolution): void;
}

export function ResolutionRail({ value, onChange }: Props) {
  const activeIndex = STEPS.findIndex((step) => step.id === value);
  return (
    <nav className="resolution-rail" aria-label="空間解像度">
      <span className="resolution-rail-label">解像度</span>
      <ol>
        {STEPS.map((step, index) => (
          <li key={step.id} className={index <= activeIndex ? "reached" : ""}>
            <button type="button" className={value === step.id ? "active" : ""} aria-current={value === step.id ? "step" : undefined} onClick={() => onChange(step.id)}>
              <strong>{step.label}</strong><small>{step.hint}</small>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}
