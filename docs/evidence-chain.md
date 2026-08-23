# Evidence Chain

CITY GAPは結果だけでなく、その数値がどの公式データからどう計算されたかを追跡できることを品質要件にする。生成AIの説明やブラックボックス推論は使わない。

## Rank 1の例

公共交通距離:

| 項目 | 値 |
|---|---|
| 起点 | 500m mesh `533512753` centroid |
| 到達先 | 二尾バス停 |
| データ | 国土数値情報 P11 2022 |
| 座標系 | JGD2011 / 平面直角座標系VI、EPSG:6674 |
| 計算 | Euclidean distance |
| 丸め前 | 2321.655609m |

Score C:

```text
elderly_population_percentile
× transport_distance_percentile
× medical_distance_percentile
= Score C
```

画面では3成分の丸め前値、積、公式データ名、計算CRSを表示する。

## 施策案

Evidenceモーダルは、選択中の1〜3地点について次を表示する。

- candidate IDと地点順
- PLATEAU道路LOD1面の道路名
- 緯度・経度（9桁表示）
- 最寄り既存交通と距離
- after距離式
- Score C合計純減少
- 独立再計算済みであること

Web用 `evidence.json` は分析成果物から生成され、手入力しない。`source_data_hashes` に人口・施設・PLATEAU CityGML・監査入力を結びつける。

## 監査方法

```bash
python -m analysis.scripts.verify_decision_studio
```

検証scriptはbuilderと別のpandas-compatible percentile実装で全9案を再計算する。出力は `analysis/outputs/real/maizuru_decision_studio_verification.json`。`exact_match: true`、`plans_checked: 9` が公開前条件である。

Evidence Chainが保証するのは再現性であり、データの最新性、徒歩経路、運行可能性、用地、費用、住民意向までは保証しない。
