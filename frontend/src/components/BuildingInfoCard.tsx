import type { BuildingInfo } from "../types";
import { formatDistance, formatInteger } from "../lib/format";

function formatArea(value: number | null): string {
  return value === null ? "属性なし" : `${value.toLocaleString("ja-JP", { maximumFractionDigits: 1 })} m²`;
}

export function BuildingInfoCard({ building, onClose }: { building: BuildingInfo; onClose: () => void }) {
  return (
    <section className="building-card" aria-live="polite">
      <button type="button" aria-label="建物情報を閉じる" onClick={onClose}>×</button>
      <p>PLATEAU 舞鶴市 2025</p>
      <h2>実在する3D建物</h2>
      <dl>
        <div><dt>ID</dt><dd>{building.id}</dd></div>
        <div><dt>用途</dt><dd>{building.usage ?? "属性なし"}</dd></div>
        <div><dt>計測高さ</dt><dd>{formatDistance(building.measuredHeight)}</dd></div>
        <div><dt>地上階数</dt><dd>{formatInteger(building.storeysAboveGround, "階")}</dd></div>
        <div><dt>地下階数</dt><dd>{formatInteger(building.storeysBelowGround, "階")}</dd></div>
        <div><dt>建築面積</dt><dd>{formatArea(building.footprintArea)}</dd></div>
        <div><dt>延べ面積</dt><dd>{formatArea(building.totalFloorArea)}</dd></div>
        <div><dt>表示LOD</dt><dd>{building.lod ?? "—"}</dd></div>
      </dl>
      <small>公式3D Tilesに実在する属性だけを表示。CITY GAPは500mメッシュ単位で、建物単位の評価ではありません。</small>
    </section>
  );
}
