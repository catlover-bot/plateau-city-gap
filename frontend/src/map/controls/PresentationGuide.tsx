import { SCENE_PRESETS } from "../core/scenePresets";
import type { ScenePresetId } from "../../state/spatial/types";

const STORY: Array<{ scene: ScenePresetId; number: string; caption: string }> = [
  { scene: "city_overview", number: "01", caption: "舞鶴全体" },
  { scene: "gap_discovery", number: "02", caption: "CITY GAP候補" },
  { scene: "plateau_detail", number: "03", caption: "PLATEAU 3D" },
  { scene: "hazard_stress", number: "04", caption: "施策・Stress" },
  { scene: "validation_disagreement", number: "05", caption: "自治体Review" },
];

interface Props {
  open: boolean;
  value: ScenePresetId;
  onClose(): void;
  onSelect(scene: ScenePresetId): void;
}

export function PresentationGuide({ open, value, onClose, onSelect }: Props) {
  if (!open) return null;
  return (
    <section className="presentation-guide" aria-label="4分デモの進行">
      <header><span>GUIDED PRESENTATION</span><strong>{SCENE_PRESETS[value].description}</strong><button type="button" onClick={onClose} aria-label="発表モードを閉じる">×</button></header>
      <ol>{STORY.map((step) => <li key={step.scene}><button type="button" className={value === step.scene ? "active" : ""} aria-pressed={value === step.scene} onClick={() => onSelect(step.scene)}><span>{step.number}</span><strong>{step.caption}</strong></button></li>)}</ol>
    </section>
  );
}
