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
6. `build_plateau_web_subset.py` が、公式建物の存在する東舞鶴駅・西舞鶴駅周辺について、LOD2配布コンテナのleaf content regionが駅から100m以内となる5 tileを選ぶ。
7. 選択したtilesetと5 b3dmをchecksum検証済み公式ZIP内の同一memberへ直接hash照合し、12,723,708 bytesのpayloadとpruned `tileset.json` をステージング後に公開する。

現在のsubset全体は12,729,687 bytes、重複排除後2,152棟です。配布コンテナ名はLOD2ですが、各featureの実際の `_lod` はLOD2が937棟、LOD1が1,215棟です。用途・計測高さ・地上/地下階数等はbatch tableに存在する値だけを表示します。

このsubsetはCITY GAP Top 10の周辺ではありません。Story Mode Step 3は公式3D建物の整備済み範囲へ移動し、候補地が建物モデル範囲外であることも画面上で説明します。

## Frontend

`frontend/src/` の主な責務は次の通りです。

| Area | Responsibility |
|---|---|
| `lib/data.ts` | 相対base pathからassetをloadし、必須・任意layerを区別 |
| `CesiumMap` | 500m polygon、point、行政界、3D Tiles、camera、pick |
| `RankingPanel` / `DetailPanel` | Top 10、実測値、最寄り施設、percentile、説明 |
| `MetricSelector` / `LayerPanel` | 指標色分けとlayer表示状態 |
| `StoryMode` | 4分デモ向けの決定論的な4ステップ |
| `ScenarioPanel` / `lib/scenario.ts` | 仮想交通支援拠点とBefore / After |
| `MethodologyModal` | source、計算式、coverage、限界 |

Cesiumは500m polygonと施設pointをローカルGeoJSONから、PLATEAU建物をローカル3D Tilesから読みます。背景にはCesium同梱のNatural Earth II静的tileを使い、外部地図APIへ実行時依存しません。地図を操作できなくても、ranking/detailから同じ数値へ到達できます。

## What-if data flow

```text
map click（EPSG:4326）
  → proj4でEPSG:6674
  → 秘匿・合算影響のない286比較meshの中心までのEuclidean距離
  → min(既存交通距離, 仮想地点距離)
  → 286件で交通距離percentileを再計算
  → Score C after
  → selected mesh Before/After
     + 改善mesh数
     + 対象meshの65歳以上人口合計
     + 改善幅Top 5
```

再計算はブラウザ内だけで完結し、サーバへ保存しません。同じassetと同じ座標なら同じ結果になります。これは直線距離だけの感度確認で、交通計画の最適化モデルではありません。

## Deployment and performance

Viteのbase pathは `/plateau-city-gap/`。GitHub ActionsはmainへのpushでNode install、typecheck、test、production buildを実行し、GitHub Pages artifactを配信します。

公式配布全体の約161MB ZIPや240MB超の展開済み建物containerは配信しません。3Dは12.7MBの参照subsetに限定し、分析GeoJSONもブラウザ用属性へ絞ります。raw packageは再現・inspection用であり、repositoryにはcommitしません。

## Current implementation and future work

| Current product | Not implemented |
|---|---|
| mesh中心からの直線距離 | 道路・徒歩network距離 |
| 地域人口に基づく探索 | 建物への人口配分 |
| 公式3D建物subsetの表示・属性確認 | 建物単位の居住起点 |
| PLATEAU coverageをQAとして表示 | 公式配布全体の3D配信 |
| 仮想1地点の決定論的再計算 | 運行、需要、費用の最適化 |
| 楕円体terrain上の3D表示 | DEM、勾配、上下移動負荷 |

将来拡張を現行機能としては扱いません。特に建物形状・用途・階数は現時点のCITY GAPスコアへ入っていません。
