import type { Cesium3DTileset, GeoJsonDataSource, Viewer } from "cesium";
import { evaluateVisualReadiness, INITIAL_VISUAL_READINESS, type SceneReadinessRequirements, type VisualReadinessResult, type VisualReadinessSnapshot } from "./visualReadiness";

interface TilesetStatistics {
  numberOfCommands?: number;
  numberOfPendingRequests?: number;
  numberOfTilesProcessing?: number;
  numberOfTilesWithContentReady?: number;
  numberOfFeaturesSelected?: number;
  numberOfFeaturesLoaded?: number;
}

interface ReadinessTileset extends Cesium3DTileset {
  statistics?: TilesetStatistics;
}

export interface CesiumReadinessSources {
  buildingTilesets: Array<{
    source: string;
    tileset: Cesium3DTileset | undefined;
    targetFeatureCount?: number;
    packId?: string;
  }>;
  terrainTileset?: Cesium3DTileset;
  roads?: GeoJsonDataSource;
}

export interface CesiumReadinessFlags {
  appReady: boolean;
  basemapReady: boolean;
  analysisReady: boolean;
  broadTerrainReady: boolean;
  localDemLoaded: boolean;
  overlayReady: boolean;
}

export interface CesiumReadinessController {
  refresh(): void;
  destroy(): void;
}

function statistics(tileset: Cesium3DTileset | undefined): TilesetStatistics {
  return (tileset as ReadinessTileset | undefined)?.statistics ?? {};
}

function renderedGlobeTiles(viewer: Viewer): number {
  const globe = viewer.scene.globe as typeof viewer.scene.globe & {
    _surface?: { _tilesToRender?: unknown[] };
  };
  return globe._surface?._tilesToRender?.length ?? 0;
}

function cameraSignature(viewer: Viewer): string {
  const position = viewer.camera.positionCartographic;
  return [
    position.longitude.toFixed(8),
    position.latitude.toFixed(8),
    position.height.toFixed(1),
    viewer.camera.heading.toFixed(5),
    viewer.camera.pitch.toFixed(5),
  ].join(":");
}

function setDataset(container: HTMLElement, snapshot: VisualReadinessSnapshot, result: VisualReadinessResult) {
  container.dataset.visualReady = String(result.visualReady);
  container.dataset.interactionReady = String(result.interactionReady);
  container.dataset.visualComplete = String(result.visualComplete);
  container.dataset.captureStrictReady = String(result.captureStrictReady);
  container.dataset.visualUnmet = result.unmet.join(",");
  container.dataset.cameraSettled = String(snapshot.cameraSettled);
  container.dataset.canvasSizeReady = String(snapshot.canvasSizeReady);
  container.dataset.buildingFeatureCount = String(snapshot.buildingFeatureCount);
  container.dataset.targetBuildingCount = String(snapshot.targetBuildingCount);
  container.dataset.loadedTargetBuildingCount = String(snapshot.loadedTargetBuildingCount);
  container.dataset.targetCoverageRatio = snapshot.targetCoverageRatio.toFixed(6);
  container.dataset.terrainTileCount = String(snapshot.terrainTileCount);
  container.dataset.terrainReady = String(snapshot.terrainProviderReady);
  container.dataset.localDemReady = String(snapshot.localDemReady);
  container.dataset.roadsReady = String(snapshot.roadsReady);
  container.dataset.stableFrames = String(snapshot.stableFrameCount);
  container.dataset.criticalRequests = String(snapshot.outstandingCriticalRequests);
  container.dataset.terrainSource = snapshot.terrainSource;
  container.dataset.buildingSource = snapshot.buildingSource;
  container.dataset.packId = snapshot.packId;
}

export function startCesiumReadinessController(input: {
  viewer: Viewer;
  container: HTMLElement;
  requirements(): SceneReadinessRequirements;
  sources(): CesiumReadinessSources;
  flags(): CesiumReadinessFlags;
  onChange(snapshot: VisualReadinessSnapshot, result: VisualReadinessResult): void;
}): CesiumReadinessController {
  const { viewer, container } = input;
  let destroyed = false;
  let cameraSettled = true;
  let fontReady = document.fonts?.status === "loaded";
  let stableFrameCount = 0;
  let lastSignature = "";
  let lastEmission = "";
  let animationFrame = 0;
  let globePendingRequests = 0;

  const requestNext = () => {
    if (destroyed || viewer.isDestroyed() || animationFrame) return;
    animationFrame = requestAnimationFrame(() => {
      animationFrame = 0;
      if (!destroyed && !viewer.isDestroyed()) viewer.scene.requestRender();
    });
  };

  const evaluate = () => {
    if (destroyed || viewer.isDestroyed()) return;
    const sources = input.sources();
    const flags = input.flags();
    const requirements = input.requirements();
    const globeTiles = renderedGlobeTiles(viewer);
    const containerRect = container.getBoundingClientRect();
    const canvasRect = viewer.scene.canvas.getBoundingClientRect();
    const canvasSizeReady = containerRect.width > 0
      && containerRect.height > 0
      && canvasRect.width >= containerRect.width * 0.98
      && canvasRect.height >= containerRect.height * 0.98
      && viewer.scene.drawingBufferWidth >= containerRect.width * 0.9
      && viewer.scene.drawingBufferHeight >= containerRect.height * 0.9;
    container.dataset.canvasCssSize = `${Math.round(canvasRect.width)}x${Math.round(canvasRect.height)}`;
    container.dataset.drawingBufferSize = `${viewer.scene.drawingBufferWidth}x${viewer.scene.drawingBufferHeight}`;
    const visibleBuildings = sources.buildingTilesets
      .filter((item) => item.tileset?.show)
      .map((item) => ({ ...item, stats: statistics(item.tileset) }));
    const minimumBuildingFeatures = requirements.minimumBuildingFeatures;
    const hasRequiredBuildingContent = (item: typeof visibleBuildings[number]) => {
      const featureCount = Math.max(item.stats.numberOfFeaturesSelected ?? 0, item.stats.numberOfFeaturesLoaded ?? 0);
      return (item.stats.numberOfTilesWithContentReady ?? 0) > 0 && featureCount >= minimumBuildingFeatures;
    };
    const activeBuilding = [...visibleBuildings]
      .sort((a, b) => {
        const aReady = hasRequiredBuildingContent(a);
        const bReady = hasRequiredBuildingContent(b);
        return Number(bReady) - Number(aReady)
          || (b.stats.numberOfFeaturesSelected ?? 0) - (a.stats.numberOfFeaturesSelected ?? 0);
      })[0];
    const buildingFeatureCount = activeBuilding
      ? Math.max(activeBuilding.stats.numberOfFeaturesSelected ?? 0, activeBuilding.stats.numberOfFeaturesLoaded ?? 0)
      : 0;
    const buildingTilesReady = Boolean(activeBuilding && hasRequiredBuildingContent(activeBuilding));
    const expectedTargetBuildings = requirements.expectedTargetBuildingCount ?? requirements.minimumBuildingFeatures;
    const targetBuildingCount = expectedTargetBuildings > 0 ? expectedTargetBuildings : 0;
    const loadedTargetBuildingCount = activeBuilding?.tileset?.tilesLoaded
      ? Math.min(targetBuildingCount, activeBuilding.targetFeatureCount ?? 0)
      : Math.min(targetBuildingCount, buildingFeatureCount, activeBuilding?.targetFeatureCount ?? 0);
    const targetCoverageRatio = targetBuildingCount > 0
      ? loadedTargetBuildingCount / targetBuildingCount
      : 1;
    const terrainStats = statistics(sources.terrainTileset);
    const localTerrainTiles = terrainStats.numberOfTilesWithContentReady ?? 0;
    const terrainTileCount = Math.max(localTerrainTiles, globeTiles);
    const localDemReady = Boolean(flags.localDemLoaded && sources.terrainTileset?.tilesLoaded && localTerrainTiles > 0);
    const activeBuildingRequests = activeBuilding
      ? (activeBuilding.stats.numberOfPendingRequests ?? 0) + (activeBuilding.stats.numberOfTilesProcessing ?? 0)
      : 0;
    const optionalBuildingRequests = visibleBuildings
      .filter((item) => item !== activeBuilding)
      .reduce((total, item) => total + (item.stats.numberOfPendingRequests ?? 0) + (item.stats.numberOfTilesProcessing ?? 0), 0)
      + (buildingTilesReady ? activeBuildingRequests : 0);
    const outstandingCriticalRequests = (buildingTilesReady ? 0 : activeBuildingRequests)
      + (terrainStats.numberOfPendingRequests ?? 0)
      + (terrainStats.numberOfTilesProcessing ?? 0)
      + (requirements.requiresBasemap && globeTiles === 0 ? globePendingRequests : 0);
    container.dataset.optionalGlobeRequests = String(globeTiles > 0 ? globePendingRequests : 0);
    container.dataset.optionalBuildingRequests = String(optionalBuildingRequests);
    const signature = [
      cameraSignature(viewer),
      activeBuilding?.source ?? "none",
      buildingTilesReady,
      localDemReady,
      globeTiles > 0,
      outstandingCriticalRequests,
      flags.overlayReady,
      canvasSizeReady,
    ].join("|");
    stableFrameCount = signature === lastSignature && cameraSettled && outstandingCriticalRequests === 0
      ? stableFrameCount + 1
      : 0;
    lastSignature = signature;
    const snapshot: VisualReadinessSnapshot = {
      ...INITIAL_VISUAL_READINESS,
      appReady: flags.appReady,
      basemapReady: flags.basemapReady && globeTiles > 0,
      analysisReady: flags.analysisReady,
      cameraSettled,
      cesiumSceneReady: !viewer.scene.isDestroyed(),
      canvasSizeReady,
      buildingTilesReady,
      buildingFeatureCount,
      targetBuildingCount,
      loadedTargetBuildingCount,
      targetCoverageRatio,
      terrainProviderReady: (flags.broadTerrainReady && globeTiles > 0) || localDemReady,
      terrainTileCount,
      localDemReady,
      roadsReady: Boolean(sources.roads?.show && sources.roads.entities.values.length > 0),
      overlayReady: flags.overlayReady,
      fontReady,
      outstandingCriticalRequests,
      stableFrameCount,
      terrainSource: requirements.requiresLocalDem && localDemReady ? "plateau-local-dem" : flags.broadTerrainReady ? "plateau-terrain" : localDemReady ? "plateau-local-dem-context" : "none",
      buildingSource: activeBuilding?.source ?? "none",
      packId: activeBuilding?.packId ?? "none",
    };
    const result = evaluateVisualReadiness(snapshot, requirements);
    setDataset(container, snapshot, result);
    const emission = JSON.stringify({ snapshot, result });
    if (emission !== lastEmission) {
      lastEmission = emission;
      input.onChange(snapshot, result);
    }
    if (!result.captureStrictReady) requestNext();
  };

  const removeMoveStart = viewer.camera.moveStart.addEventListener(() => {
    cameraSettled = false;
    stableFrameCount = 0;
    evaluate();
  });
  const removeMoveEnd = viewer.camera.moveEnd.addEventListener(() => {
    cameraSettled = true;
    viewer.scene.requestRender();
  });
  const removeTileProgress = viewer.scene.globe.tileLoadProgressEvent.addEventListener((queuedTiles) => {
    globePendingRequests = queuedTiles;
    viewer.scene.requestRender();
  });
  const removePostRender = viewer.scene.postRender.addEventListener(evaluate);
  void document.fonts?.ready.then(() => {
    fontReady = true;
    if (!destroyed && !viewer.isDestroyed()) viewer.scene.requestRender();
  });
  requestNext();

  return {
    refresh() {
      stableFrameCount = 0;
      lastSignature = "";
      if (!viewer.isDestroyed()) viewer.scene.requestRender();
    },
    destroy() {
      destroyed = true;
      if (animationFrame) cancelAnimationFrame(animationFrame);
      removeMoveStart();
      removeMoveEnd();
      removeTileProgress();
      removePostRender();
    },
  };
}
