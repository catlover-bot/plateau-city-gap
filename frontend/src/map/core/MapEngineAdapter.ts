import type { SpatialSelection, SpatialViewport } from "../../state/spatial/types";

export interface MapBounds {
  west: number;
  south: number;
  east: number;
  north: number;
}

export interface MapEngineAdapter {
  setViewport(viewport: SpatialViewport): void;
  getViewport(): SpatialViewport;
  fitBounds(bounds: MapBounds): void;
  setSelection(selection: SpatialSelection | null): void;
  setLayers(layerIds: string[]): void;
  highlight(selection: SpatialSelection): void;
  clearHighlight(): void;
  exportView(): Promise<Blob | null>;
}

export interface MapEngineEvents {
  onViewportChange(viewport: SpatialViewport): void;
  onSelectionChange(selection: SpatialSelection | null): void;
  onReady?(): void;
  onError?(message: string): void;
}
