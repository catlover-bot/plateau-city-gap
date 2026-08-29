# PLATEAU 3D rendering

## Purpose

3Dは独立した閲覧機能ではない。500mで見つけたFindingを、同じselectionのまま建物群、建物、道路、地形、計画・災害contextへ詳細化する調査面として使う。

PLATEAUを外すと建物level Investigation、道路object調査、実DEM上の位置関係、Planning/Hazard object context、objectからFindingへの逆引きが成立しない。2D discoveryはPLATEAUなしでも一部成立する。

## Building delivery

建物は実データだけを3段階で配信する。

1. `plateau-fast`: 公式b3dm 1 tile / 15棟。geometry simplification、height estimationなし。
2. `plateau`: 検証済みlocal subset 3 tiles / 856棟。対象mesh内296棟。
3. 公式camera stream: 舞鶴市2025 LOD1 44,640棟。

通常はfast-start → Spatial Evidence Pack → optional official streamへprogressiveに移行する。`INTERACTION_READY` は15棟で操作を解放するが、正規captureは `buildingSource=spatial-pack` で対象296棟の95%以上がloadedになるまで成功しない。外部全市streamはstrict条件をblockしない。

Urban X-Rayは建物高さを変形しない。選択mesh内の建物所属をamber、対象外をneutral/dim、選択建物をsemantic accentで表示する。個別建物へ500m統計値を付与しない。

## Terrain

局所地形は舞鶴市2025 CityGML `dem:TINRelief` から生成する。

- source CRS: EPSG:6697
- render CRS: EPSG:4979 / 4978
- vertical transform: `jp_gsi_gsigeo2011.tif`
- Deep Dive: 65,232 triangles、32,990 indexed vertices
- interpolation、smoothing、vertical exaggerationなし（1.0）
- coverage: mesh `533513314`近傍のみ

広域はPLATEAU-Terrain、Deep Diveは実TINを使用する。Urban X-Ray分析面は実terrainより上に分離し、legendとcopyで「実地形ではない」と表示する。DEMから歩行負荷、斜度、危険度を新たに推定しない。

## Roads and object graph

公式PLATEAU道路LOD1 polygonを地形上へ表示し、クリック可能なobjectとして扱う。Building → nearest Road、Mesh → Road、Road → FindingをUrban Object Graphで辿る。距離は選択座標から道路geometry頂点への概算直線距離である。

graph semanticsは常に `experimental PLATEAU LOD1 road-surface adjacency`。pedestrian network、walking network、walking timeではない。

## Analysis overlays

- Urban X-Ray: 既存 `exploratory_score_c` だけを半透明analysis surfaceへ変換
- Service Pulse: 既存representative routeのnetwork distance band（500m / 1km / 2km / endpoint）
- Counterfactual Twin: 既存scenario結果のchanged road / affected building / siteだけを強調
- Temporal Ghost: 公開済みactual Point sampleだけをadded / removed / changedとして表示

Pulseはpath distanceを毎frame計算しない。precomputed route positionsを使い、reduced motionではanimationを止めてstatic distance bandsだけを残す。routeの水平geometryは既存結果を維持し、3D表示線だけを地形から25m分離する。この高さはroute標高ではない。Scenarioで架空の建物新設・撤去・変形を行わない。

## Camera choreography

`CameraController`は `city / mesh / building / route / hazard / scenario` のintentを持つ。

- city: top-down
- mesh: slight tilt
- building: architectural perspective
- route/service: routeと関係objectが読める角度
- hazard/scenario:対象contextを含む高めのview

Sceneとresolutionは独立stateである。sceneは何を調べるか、resolutionはどの粒度で見るかを表す。URL fixtureがcameraとselectionを固定し、手作業のcamera位置を正規画像に使わない。

## Visual Readiness Protocol

撮影は時間待ちではなく、`INTERACTION_READY / VISUAL_COMPLETE / CAPTURE_STRICT_READY`を別々に評価する。

- app、basemap、analysis、overlay、font ready
- camera settled
- Cesium sceneとcanvas CSS / drawing bufferの寸法一致
- building tiles loadedかつfeature countが閾値以上
- terrain provider ready、必要sceneはlocal DEM ready、terrain tile count > 0
- road objects ready
- outstanding critical requests = 0
- 同一readiness signatureが3 render frame連続

通常操作は `dataset.interactionReady` だけを待つ。画像は `dataset.captureStrictReady`（互換alias `visualReady`）だけを待つ。15棟fast-start、terrain fallback、空断面、coverage不足は画像を保存せず、readiness、camera、target count、network failure、consoleを診断JSONへ保存する。画面外の任意LOD refinementはcritical resourceと分ける。

## Render budget

- `requestRenderMode=true`
- building SSE: desktop 13、mobile 22
- building cache: desktop 192MiB、mobile 96MiB
- DEM cache: 24MiB
- Cesiumは2D initial bundleからlazy-load
- WebGL、全市stream、local DEMの失敗を別々に扱う

SwiftShader値は実GPU SLAとして扱わない。正規計測値はcurrent capture manifestとperformance auditへ記録し、旧screenshot auditを参照しない。
