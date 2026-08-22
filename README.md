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
python -m analysis.scripts.download_real_data
python -m analysis.src.run_real_analysis
```

## Current Status / Findings

e-Stat人口、P11バス停、P04医療、PLATEAU駅を結合し、舞鶴市495人口meshから実データTop 10を生成済みです。秘匿・合算影響のない286meshだけをPrimary比較に使い、結果は [findings](docs/findings.md) と `analysis/outputs/real/` に保存しています。

## Roadmap

1. Top 5 meshに必要なPLATEAU CityGML tileだけを特定
2. 建物用途・高さ・階数の実装率を検証
3. 居住建物起点・道路/勾配を使った距離へ詳細化
4. mesh-centroid結果とのranking差を検証
5. 根拠が成立した後にCesiumJSで説明可能に可視化

## Disclaimer

本指標は探索・比較用です。施設の質、運行頻度、個人の移動能力等を網羅せず、政策上の問題判定には使えません。テストfixtureはsyntheticで、舞鶴市の分析結果ではありません。
