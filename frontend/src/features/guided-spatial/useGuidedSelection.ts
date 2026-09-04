import { useCallback, useEffect, useMemo } from "react";
import type { AppData } from "../../types";
import type { SpatialSelection, SpatialState, SpatialViewport } from "../../state/spatial/types";
import { GUIDED_DEFAULT_AREA, GUIDED_SHORTLIST, oneAreaCollection } from "./guidedData";

function meshSelection(data: AppData, meshCode: string): SpatialSelection | null {
  const feature = data.meshes.features.find((candidate) => String(candidate.properties?.mesh_code) === meshCode);
  if (!feature?.properties) return null;
  return {
    type: "mesh",
    id: meshCode,
    city: "maizuru",
    urbanState: "2025",
    label: meshCode === GUIDED_DEFAULT_AREA
      ? "常団地前周辺"
      : String(feature.properties.area_label ?? `500mメッシュ ${meshCode}`),
    longitude: Number(feature.properties.centroid_lon),
    latitude: Number(feature.properties.centroid_lat),
    properties: feature.properties,
  };
}

interface SelectionOptions {
  data: AppData;
  state: SpatialState;
  onSelectionChange(selection: SpatialSelection | null): void;
  onViewportChange(viewport: SpatialViewport): void;
}

export function useGuidedSelection({ data, state, onSelectionChange, onViewportChange }: SelectionOptions) {
  const validSelectedArea = state.selection?.type === "mesh"
    && data.meshes.features.some((feature) => String(feature.properties?.mesh_code) === state.selection?.id)
    ? state.selection.id
    : null;
  const selectedAreaId = validSelectedArea ?? GUIDED_DEFAULT_AREA;
  const selectedArea = useMemo(() => meshSelection(data, selectedAreaId), [data, selectedAreaId]);
  const selectedAreaFeature = useMemo(
    () => oneAreaCollection(data.meshes, selectedAreaId),
    [data.meshes, selectedAreaId],
  );
  const shortlisted = useMemo(
    () => GUIDED_SHORTLIST
      .map((meshCode) => meshSelection(data, meshCode))
      .filter((item): item is SpatialSelection => Boolean(item)),
    [data],
  );

  useEffect(() => {
    if (validSelectedArea || !selectedArea) return;
    onSelectionChange(selectedArea);
  }, [onSelectionChange, selectedArea, validSelectedArea]);

  const selectArea = useCallback((meshCode: string) => {
    const selection = meshSelection(data, meshCode);
    if (!selection) return;
    onSelectionChange(selection);
    if (selection.longitude !== undefined && selection.latitude !== undefined) {
      onViewportChange({
        longitude: selection.longitude,
        latitude: selection.latitude,
        zoom: 12.4,
        bearing: 0,
        pitch: 0,
      });
    }
  }, [data, onSelectionChange, onViewportChange]);

  const selectAreaFromMap = useCallback((selection: SpatialSelection | null) => {
    if (selection?.type === "mesh") selectArea(selection.id);
  }, [selectArea]);

  return {
    selectedAreaId,
    selectedArea,
    selectedAreaFeature,
    areaLabel: selectedArea?.label ?? `500mメッシュ ${selectedAreaId}`,
    properties: selectedArea?.properties ?? {},
    shortlisted,
    selectArea,
    selectAreaFromMap,
  };
}
