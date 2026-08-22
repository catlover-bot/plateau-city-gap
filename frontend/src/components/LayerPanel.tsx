import type { AppData, LayerVisibility } from "../types";
import {
  formatBuildingCount,
  summarizePlateauCoverage,
  top10CoverageSentence,
} from "../lib/plateau";

interface LayerPanelProps {
  data: AppData;
  value: LayerVisibility;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onChange: (value: LayerVisibility) => void;
  onResetView: () => void;
}

export function LayerPanel({ data, value, open, onOpenChange, onChange, onResetView }: LayerPanelProps) {
  const plateauCoverage = summarizePlateauCoverage(data.plateauMetadata);
  const layers: Array<{
    key: keyof LayerVisibility;
    label: string;
    swatch: string;
    available: boolean;
  }> = [
    { key: "meshes", label: "500mメッシュ", swatch: "gradient", available: data.meshes.features.length > 0 },
    { key: "boundary", label: "舞鶴市境界", swatch: "boundary", available: Boolean(data.boundary?.features.length) },
    { key: "stations", label: "駅", swatch: "station", available: Boolean(data.stations?.features.length) },
    { key: "busStops", label: "バス停", swatch: "bus", available: Boolean(data.busStops?.features.length) },
    { key: "medical", label: "医療施設", swatch: "medical", available: Boolean(data.medicalFacilities?.features.length) },
    {
      key: "plateau",
      label: "PLATEAU建物（駅周辺）",
      swatch: "plateau",
      available: plateauCoverage.referenceIncluded || Boolean(data.plateauBuildings?.features.length)
    }
  ];

  return (
    <div className={`layer-control ${open ? "open" : ""}`}>
      <div className="map-actions">
        <button
          type="button"
          className="map-action-button"
          aria-expanded={open}
          aria-controls="layer-options"
          onClick={() => onOpenChange(!open)}
        >
          <span aria-hidden="true">◫</span>
          レイヤー
        </button>
        <button type="button" className="map-action-icon" aria-label="舞鶴市全体に戻る" onClick={onResetView}>
          ⌂
        </button>
      </div>
      {open && (
        <div id="layer-options" className="layer-popover">
          <div className="layer-heading">
            <strong>地図レイヤー</strong>
            <button type="button" aria-label="レイヤーを閉じる" onClick={() => onOpenChange(false)}>
              ×
            </button>
          </div>
          {layers.map((layer) => (
            <label key={layer.key} className={`layer-row ${!layer.available ? "disabled" : ""}`}>
              <span className={`layer-swatch ${layer.swatch}`} aria-hidden="true" />
              <span>{layer.label}</span>
              {!layer.available && <small>未収録</small>}
              <input
                type="checkbox"
                checked={value[layer.key] && layer.available}
                disabled={!layer.available}
                onChange={(event) => onChange({ ...value, [layer.key]: event.target.checked })}
              />
              <span className="toggle" aria-hidden="true" />
            </label>
          ))}
          <p className="layer-source">PLATEAU 2025 / 国土数値情報 / e-Stat</p>
          {plateauCoverage.referenceIncluded && (
            <p className="layer-coverage-note">
              公式3D Tiles {formatBuildingCount(plateauCoverage.referenceCount)}。{top10CoverageSentence(plateauCoverage)}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
