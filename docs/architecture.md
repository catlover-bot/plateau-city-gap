# Architecture

CITY GAPは分析と配信を分離した静的Webアプリです。Python側の実分析成果物をSingle Source of Truthとし、ブラウザは検証済みの公開assetを読み込みます。常時稼働するAPI、データベース、認証、API keyはありません。

## System overview

```text
公式公開データ
  ├─ e-Stat人口 2020
  ├─ 国土数値情報 P11 2022 / P04 2020
  └─ Project PLATEAU 舞鶴市 2025
          │
          ▼
Python / GeoPandas analysis（EPSG:6674）
          │
          ▼
analysis/outputs/real/
  CSV + GeoJSON + summary.json
  └─ 分析値のSingle Source of Truth
          │
          ▼
build_web_assets.py
  schema・値・geometry・lineage検証
          │
          ▼
frontend/public/data/
  軽量GeoJSON / JSON + PLATEAU 3D Tiles subset
  + PLATEAU道路subset + final demo candidates
          │
          ▼
React + TypeScript + CesiumJS
  ├─ ranking / detail / Story Mode
  ├─ metric・point・3D layer
  └─ browser内What-if（proj4 / EPSG:6674）
          │
          ▼
Vite static build → GitHub Pages
```

## Analysis layer

`analysis/src/` は計算責務を分けています。

| Module | Responsibility |
|---|---|
| `mesh.py` | JIS X 0410 500mメッシュの復号とgeometry |
| `population.py` | 5歳階級から65歳以上人口を集計 |
| `spatial.py` | 行政界との交差・point抽出 |
| `distances.py` / `accessibility.py` | EPSG:6674上の最寄り直線距離 |
| `metrics.py` | percentile、Score A/B/C、Pareto |
| `ranking.py` | 開示条件・人口条件を明示した順位 |
| `validation.py` | CRS、schema、値域、件数の検証 |

`analysis/outputs/real/maizuru_city_gap.geojson`、`maizuru_city_gap_top10.csv`、`maizuru_summary.json` がプロダクトへ渡す確定値です。React側でRank 1などを再入力しません。

## Web asset boundary

`analysis/scripts/build_web_assets.py` は分析用の広いschemaから、ブラウザに必要な属性だけを選択し `frontend/public/data/` に出力します。

- 495メッシュとTop 10の対応、rank 1〜10、mesh code一意性
- 人口・65歳以上人口・距離の値域
- 緯度経度範囲とGeoJSON geometry
- 駅・バス停・医療施設・行政界の件数
- 入力ファイルのbyte数とSHA-256、変換履歴
- PLATEAU建物inspectionの件数とTop 10 coverage

異常時は不完全なassetを公開せずbuildを失敗させます。`manifest.json` は生成日時、分析version、CRS、データ年次、source record、output hash、limitationsを持ちます。

## PLATEAU 3D pipeline

公式「3D都市モデル（舞鶴市）2025年度」3D Tiles/MVT ZIPは約161MBのため `data/raw/plateau_3d/` に置き、Git管理外にします。

1. `download_plateau_3d.py` が公式ZIPのbyte数・SHA-256・ZIP pathを検証し、LOD1/LOD2建物containerを展開する。
2. `inspect_plateau_buildings.py` がLOD1/LOD2配布コンテナの各427 b3dmを検査する。
3. `gml_id` でtile間の重複を除き、公式配布3D Tiles内44,640棟とLOD1/LOD2 ID一致を確認する。
4. Top 10の各500m polygonと建物代表点・bounding boxを照合する。
5. Top 10内0棟をcoverage結果として記録し、geometryを推定しない。
6. `build_final_demo_assets.py` が44,640建物代表点を500mメッシュへ結合し、PLATEAU-covered Top 5を生成する。
7. 同scriptがCityGML道路16,778面を読み、既存交通から150m超の道路面代表点でWhat-ifを評価し、1.5km以上離したTop 3を生成する。Deep Diveでは道路135面とDEM TINを抽出する。
8. `build_plateau_web_subset.py` が全市23位 `533513314` と交差する3 leaf tileを選び、公式ZIP内memberへhash照合して公開する。

現在のsubset payloadは4,313,608 bytes、856棟です。対象500mメッシュ内の代表点は296棟で、実際のgeometryは全856棟がLOD1です。用途・計測高さ・階数・建築面積・延べ面積・LODはbatch tableに存在する値だけを表示します。

このsubsetはCITY GAP Top 10の周辺ではありません。Story Mode Step 3はPLATEAU-coveredの全市23位へ移動し、Top 10の0棟coverageと区別します。

## Frontend

`frontend/src/` の主な責務は次の通りです。

| Area | Responsibility |
|---|---|
| `lib/data.ts` | 相対base pathからassetをloadし、必須・任意layerを区別 |
| `CesiumMap` | 500m polygon、point、行政界、3D Tiles、camera、pick |
| `RankingPanel` / `DetailPanel` | Top 10、実測値、最寄り施設、percentile、説明 |
| `MetricSelector` / `LayerPanel` | 指標色分けとlayer表示状態 |
| `StoryMode` | 指標比較 → Rank 1 → 3D Deep Dive → 配置候補 → 意思決定の5ステップ |
| `ScenarioPanel` / `lib/scenario.ts` | 仮想交通支援拠点とBefore / After |
| `MethodologyModal` | source、計算式、coverage、限界 |

Cesiumは500m polygonと施設pointをローカルGeoJSONから、PLATEAU建物をローカル3D Tilesから読みます。背景にはCesium同梱のNatural Earth II静的tileを使い、外部地図APIへ実行時依存しません。地図を操作できなくても、ranking/detailから同じ数値へ到達できます。

## What-if data flow

```text
PLATEAU道路面Top 3 または map click（EPSG:4326）
  → proj4でEPSG:6674
  → 秘匿・合算影響のない286比較meshの中心までのEuclidean距離
  → min(既存交通距離, 仮想地点距離)
  → 286件で交通距離percentileを再計算
  → Score C after
  → selected mesh Before/After
     + 改善mesh数
     + 対象meshの65歳以上人口合計
     + 平均距離短縮 / Score C合計純減少
     + 改善幅Top 5
```

再計算はブラウザ内だけで完結し、サーバへ保存しません。同じassetと同じ座標なら同じ結果になります。これは直線距離だけの感度確認で、交通計画の最適化モデルではありません。

## Deployment and performance

Viteのbase pathは `/plateau-city-gap/`。GitHub ActionsはmainへのpushでNode install、typecheck、test、production buildを実行し、GitHub Pages artifactを配信します。

公式配布全体の約161MB 3D Tiles ZIP、約914MB CityGML ZIPや展開済みcontainerは配信しません。3D payloadは4.31MBのDeep Dive subsetに限定します。Cesium runtime、Natural Earth II、分析JSON、3D Tiles、道路GeoJSONは全てstatic assetで、外部地図・分析APIへ実行時依存しません。

## Current implementation and future work

| Current product | Not implemented |
|---|---|
| mesh中心からの直線距離 | 道路・徒歩network距離 |
| 地域人口に基づく探索 | 建物への人口配分 |
| 公式3D建物Deep Diveと面積を含む属性確認 | 建物単位の居住起点 |
| PLATEAU coverageをQAとして表示 | 公式配布全体の3D配信 |
| 道路面上Top 3と仮想1地点の決定論的再計算 | 道路network、運行、需要、費用の最適化 |
| DEM TINの標高・局所勾配要約 | 歩行経路の勾配、上下移動負荷 |

将来拡張を現行機能としては扱いません。特に建物形状・用途・階数は現時点のCITY GAPスコアへ入っていません。

## Cross-city architecture

```text
analysis/config/{maizuru,fujisawa}.yaml
                  │
                  ▼
          city_config.py (validation)
                  │
                  ▼
         run_city_analysis.py
     mesh ─ population ─ distances
        ranking ─ Pareto ─ QA
          │                 │
          ├─ maizuru_*      └─ fujisawa_*
          │                       │
          ▼                       ▼
 build_web_assets.py     build_city_validation_assets.py
          │                       │
          └──────────┬────────────┘
                     ▼
        React city-aware data loader
          │                       │
   Primary demo             Validation mode
  Story / 3D / What-if      Top 10 / Detail / WHY
```

共通engineはPLATEAU 3D subsetやWhat-ifを知りません。それらは舞鶴の深い実証を担うpublication layerに残し、都市横断分析と分離しています。これにより、藤沢へ舞鶴の3D metadataや候補地を誤って表示しません。

Frontendの `AppData.city` が都市名、mode、cameraを保持します。`loadAppData` は舞鶴Primary、`loadValidationCityData` は藤沢の軽量assetを読みます。Cesium viewerは都市切替時に破棄・再生成され、cameraとlayerを都市ごとに初期化します。
