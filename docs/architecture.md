# Architecture

```text
official raw data -> CRS/schema validation -> population areas
 -> nearest-target Euclidean distances -> component percentiles
 -> exploratory score/rank -> CSV + GeoJSON + summary.json
 -> (later) CesiumJS explanation UI
```

`accessibility.py`が空間距離、`metrics.py`が正規化・スコアを分離し、CLIはI/Oを担当する。

| 2D GIS MVP | PLATEAU extension |
|---|---|
| 地域代表点 | 属性確認後の居住建物起点 |
| 直線施設距離 | 道路接続、勾配、上下移動負荷 |
| 地域人口のミスマッチ | 建物形状・用途と計画シナリオ比較 |

PLATEAU extensionは設計候補であり実装済みの主張ではない。
