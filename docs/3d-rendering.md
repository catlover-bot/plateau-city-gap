# PLATEAU 3D Decision Twin rendering

## Building delivery

建物は最初の意味ある形状を早く出しつつ、公式全市配信へ移行する3段階構成である。

1. `plateau-fast`: 公式b3dm 1 tile / 15棟。Dracoだけをlossless decodeし、形状簡略化・高さ推定をしない。
2. `plateau`: 検証済みlocal fallback 3 tiles / 856棟。公式配信が失敗してもDeep Dive操作を継続する。
3. PLATEAU VIEW official camera stream: 舞鶴市2025 LOD1 44,640棟。初期tile読込後にlocal 2段を非表示にする。

公式APIの可用性を暗黙に保証しない。画面DOMは `data-building-source` と `data-building-tiles-loaded` を公開し、監査が実際のstageを検証する。選択建物は黄色、他の公式建物は淡い灰緑で表示する。

## Actual PLATEAU DEM surface

局所地形は `analysis/scripts/build_plateau_terrain_web_tiles.py` で公式舞鶴市2025 CityGMLの `udx/dem/533513_dem_6697_00_op.gml` から生成する。

- source CRS: EPSG:6697（JGD2011 + JGD2011重力関連高）
- render CRS: EPSG:4979 / 4978（楕円体高 / ECEF）
- vertical transform: PROJの公式 `jp_gsi_gsigeo2011.tif` をinverse適用
- 走査1,896,487三角形、Deep Dive選択65,232、表示65,232
- 195,696頂点参照を同一座標でindex化し、再標本化なしで32,990頂点へ集約
- source標高25.063–164.581m、render楕円体高62.088–201.645m
- GLB 1,575,692 bytes、SHA-256 `137cb6478a7e7c26c921a7e50508547380149c7f02f399873b8e3486e20a99fa`
- 補間、平滑化、高さ誇張はしない

品質境界は常団地前バス停周辺、mesh `533513314` 近傍だけであり、全市の実CityGML DEM表示とは主張しない。広域地形はPLATEAU-Terrain quantized meshを用い、局所実TINを `plateau-terrain` Scene layerとして上に重ねる。

## Roads, analysis and policy objects

公式PLATEAU道路LOD1 polygonはCesium ground classificationで地形・3D Tilesの表面へ重ねる。施策候補地、Before/After経路、改善建物位置、災害stressの不通領域・critical edge・影響施設は同じCesium sceneへ追加する。ただし公式地物とCITY GAP派生成果物は色、legend、provenanceを分離する。

## Camera and render budget

CameraControllerは `city / mesh / building / route / hazard / scenario` の6 intentを持つ。建物は520m、道路は1,450m、災害は2,600m、施策は1,150mのrangeを基準とし、選択対象へ1.15–1.2秒で遷移する。

- Cesiumは `requestRenderMode=true`、`maximumRenderTimeChange=Infinity`。
- 3D Tiles SSEはdesktop 13、mobile 22。
- building cacheはdesktop 192MiB、mobile 96MiB。DEMは24MiB。
- dynamic SSEを有効化し、semantic zoom外のlayerはon-demand/camera streamとする。
- WebGL不可、公式stream失敗、局所DEM失敗を個別に通知し、2Dまたは検証済みfallbackを維持する。

初回3D JavaScriptはlazy chunkであり、2D discoveryの初期bundleから分離する。実測値は `docs/assets/spatial-v1/audit.json` に保存する。

## Production audit result

1440×900のproduction previewをChromium headless + SwiftShaderで測定した。2D product readyは5.000秒、3Dの最初の建物+局所DEMは8.071秒。最終PLATEAU detail captureでは公式stream 9 tiles / 2,720 features、局所DEM 1 tile、建物実pick成功。Hazard Sceneでは公式28 tiles / 7,795 features、resilience 88地物を同一sceneで確認した。console errorとHTTP 4xx/5xxは0。

強制連続render throughputは2.7 fpsだった。これはGPUを使わないCI用SwiftShader・1070×784 canvas・公式streamと局所TIN同時表示の値で、利用者端末のFPSやSLAとはみなさない。通常動作は `requestRenderMode` のため静止中に連続描画せず、cameraやstate変更時だけrenderする。実GPUの代表端末別測定は公開pilot前の残課題である。
