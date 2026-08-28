# Architecture

CITY GAPは、公式都市データを「発見」から「検証可能な施策比較」へつなぐ静的Webアプリである。分析結果はPythonで生成・検証し、ブラウザは公開可能な集計assetだけを読み込む。PLATEAUは背景装飾ではなく、500mメッシュのFindingを実在する都市objectへ詳細化するUrban Object Modelとして扱う。

## System map

```text
PLATEAU
  建物 / 道路 / 地形 / 土地利用 / 都市計画 / 洪水・土砂・津波
国勢調査 / 国土数値情報 / GTFS・施設
                         │
                         ▼
Urban Data Platform
  version / CRS / lineage / disclosure / validation
             ┌───────────┼───────────┐
             ▼           ▼           ▼
        建物人口配分   経路・距離   災害・計画context
             └───────────┼───────────┘
                         ▼
CITY GAP Engine
          発見 ── 検証 ── 施策案 ── 複数案比較
                         │
                         ▼
               自治体レビュー / Decision Record
```

## Trust boundary

- `analysis/outputs/real/` が計算結果のSingle Source of Truthである。
- `analysis/scripts/build_web_assets.py` がschema、値域、geometry、lineageを検証して `frontend/public/data/` を生成する。
- Reactは人口・距離・スコアを再計算して確定値を作らない。表示、選択、trace、既存scenarioの比較だけを担う。
- 公開面は集計・非機微・read-onlyであり、認証済み自治体APIやDecision Recordの書込みを装わない。
- 不足データは `unavailable` のまま扱い、施設、費用、承認、観察結果を補完しない。

## Spatial state model

SceneとResolutionを独立stateにする。

- Scene: `city_overview / gap_discovery / plateau_detail / network_access / healthcare_access / hazard_context / scenario_compare / temporal_change`
- Resolution: `city → district → mesh → building_group → building → road → site`
- Selection: mesh、building、road、siteと座標をURLへ直列化する。
- Lens: `none / urban-xray / service-pulse / changed-only / temporal-ghost`
- Twin: `baseline / scenario`

Sceneは「何を調べるか」、Resolutionは「どの粒度で調べるか」である。Scene切替はResolutionを暗黙に上書きしない。URL fixtureから同じ選択、カメラ、分析Lensを復元できる。

## Urban Object Graph

`frontend/src/map/core/urbanObjectGraph.ts` が、UIやrendererに依存しないobject関係を構築する。

```text
City
 └─ Mesh 500m
     ├─ contains → Building Group → Building
     ├─ intersects / nearest → Road
     ├─ context → Land Use / Planning / Hazard
     └─ supports ↔ Finding

Building ─ nearest → Road
Road ─ supports ↔ Finding
Finding ─ derived from → metric + source + method + limitation
```

Object Lensは選択objectからsource、year、ID、属性、関係object、Findingを双方向に辿る。対象Deep Dive mesh `533513314` では実在296棟のmembershipを確認できる。それ以外で建物object coverageがない場合は `unavailable` と表示する。

## PLATEAU rendering boundary

- Building: 公式b3dm fast-start、検証済みlocal subset、公式camera streamをprogressiveに扱う。
- Road: 公式LOD1道路面を表示・pickし、実験的road-surface adjacencyとしてだけ使う。
- Terrain: 実CityGML TINを説明contextとして表示する。歩行負荷、斜度、危険度を推定しない。
- Land use / planning / hazard: source属性を関係contextとして表示し、適法性や危険を自動判定しない。
- Urban X-Ray: 既存CITY GAP scoreの位置関係を分析面として分離表示し、建物geometryを変形しない。

公共画面の建物人口は「モデル推計配分（実居住者数ではない）」である。建物ごとの人数は公開せず、帯域・集計だけを表示する。

## Analysis overlays

| Lens | Existing evidence | Claim boundary |
|---|---|---|
| Urban X-Ray | `exploratory_score_c` | 実地形・建物固有スコアではない |
| Service Pulse | representative route上のprecomputed network distance | 徒歩、時間、pedestrian networkではない |
| Counterfactual Twin | 既存scenarioのchanged road / building band / site | 建物の新設・撤去・変形ではない |
| Temporal Ghost | 公開済みactual Point sample | 公式polygon差分や全棟変化ではない |

## Runtime surfaces

`VITE_CITYGAP_SURFACE` で配信面を分ける。

- `showcase`: 地図中心の公開調査面。MapLibreを初期表示し、CesiumをPLATEAU sceneでlazy-loadする。
- `municipal`: 調査、比較、レビュー、現地確認を扱う自治体運用面。公開デモではread-only境界を保つ。

両面は同じdata contractsとclaim boundaryを使う。UIは分析値を独自に再解釈しない。

## Visual Readiness Protocol

正規画像は固定時間待ちではなく、scene requirementsで撮影可否を決める。

- basemap、font、analysis、overlay ready
- camera settled
- canvas CSS寸法とWebGL drawing buffer寸法が一致
- required building、road、terrain、local DEMがready
- critical request 0
- 同一readiness signatureが3 frame以上継続

timeout時は画像を保存せず診断JSONを残す。画面外LOD refinementはoptionalとして分離する。capture manifestはcommit、URL、viewport、camera、source、feature/tile count、readiness、SHA-256を記録する。

## Deployment

Viteのbase pathは `/plateau-city-gap/`。mainへのpushで既存9ゲートを実行し、GitHub Pagesへstatic artifactを配信する。秘密鍵、外部地図API key、常時APIは不要である。分析入力の取得・再生成、PostGIS統合、自治体運用面の詳細は各SSOT文書を参照する。

PLATEAU 3D source tier、DEM、道路、カメラ、render budgetは [3d-rendering.md](./3d-rendering.md)、色・レイアウト・画面構成は [visual-system.md](./visual-system.md) に定義する。
