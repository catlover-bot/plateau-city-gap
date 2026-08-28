import { SCENE_PRESETS } from "../core/scenePresets";
import type { ScenePresetId } from "../../state/spatial/types";

const INVESTIGATION: Array<{ scene: ScenePresetId; number: string; caption: string }> = [
  { scene: "city_overview", number: "01", caption: "舞鶴全体" },
  { scene: "gap_discovery", number: "02", caption: "追加調査候補" },
  { scene: "plateau_detail", number: "03", caption: "建物・道路" },
  { scene: "hazard_stress", number: "04", caption: "条件比較" },
  { scene: "validation_disagreement", number: "05", caption: "自治体確認" },
];

interface Props {
  open: boolean;
  value: ScenePresetId;
  onClose(): void;
  onSelect(scene: ScenePresetId): void;
}

export function SavedInvestigationRail({ open, value, onClose, onSelect }: Props) {
  if (!open) return null;
  return (
    <section className="saved-investigation-rail" aria-label="保存済み調査の閲覧">
      <header><span>SAVED INVESTIGATION · READ ONLY</span><strong>{SCENE_PRESETS[value].description}</strong><button type="button" onClick={onClose} aria-label="保存済み調査を閉じる">×</button></header>
      <ol>{INVESTIGATION.map((step) => <li key={step.scene}><button type="button" className={value === step.scene ? "active" : ""} aria-pressed={value === step.scene} onClick={() => onSelect(step.scene)}><span>{step.number}</span><strong>{step.caption}</strong></button></li>)}</ol>
    </section>
  );
}
