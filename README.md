# CITY GAP

PLATEAUで見つける、都市計画と現実のズレ

Team: まちスコープ

## Background

人口構成、移動手段、生活施設と都市空間を組み合わせ、施策検討候補と判断根拠を説明可能にするPLATEAU CityHack Challenge 2026向けプロトタイプです。

## Problem / Idea

生の人口・距離指標、正規化値、探索スコア、順位を分離し、「高齢者ニーズ × 交通・医療アクセス不足」を検証します。スコアは政策判断の正解や閾値ではありません。

## Why PLATEAU?

2D距離MVP後、実在属性を確認して建物用途・高さ・道路形状を居住建物起点や移動負荷へ拡張します。PLATEAUを単なる3D背景にはしません。詳細は [architecture](docs/architecture.md) へ。

## MVP / Architecture

京都府舞鶴市を対象に、人口地域から駅、バス停、医療施設へのユークリッド直線距離と高齢化率を計算します。公式raw data → CRS/スキーマ検証 → 距離 → 構成指標 → 探索rank → CSV/GeoJSONです。

## Data Sources

確認状況とURLは [data-sources](docs/data-sources.md) に記録。大容量PLATEAU本体は未取得です。

## Quick Start

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
pytest

# 実データ3レイヤーが揃った後
python -m analysis.src.prepare_accessibility areas.geojson --stations stations.geojson --bus-stops bus_stops.geojson --medical medical.geojson
python -m analysis.src.compute_city_gap data/processed/maizuru_areas.geojson
```

## Current Status / Findings

分析モジュール、CLI、テストを実装し、PLATEAU公式の駅データを確認済みです。人口、バス停、医療施設は未取得で、実CITY GAP出力はまだ生成していません。**Analysis in progress.** 架空結果は掲載しません。

## Roadmap

1. e-Stat人口・65歳以上人口の取得と空間単位確定
2. 公式バス停・医療機関点の取得
3. 初回rankと構成指標のレビュー
4. PLATEAU CityGML属性を必要範囲だけ検証
5. React + TypeScript + Vite + CesiumJSで可視化

## Disclaimer

本指標は探索・比較用です。施設の質、運行頻度、個人の移動能力等を網羅せず、政策上の問題判定には使えません。テストfixtureはsyntheticで、舞鶴市の分析結果ではありません。
