# Evidence Chain

## Spatial evidence artifacts

InvestigationのEvidence Chainは `Finding → mesh → Spatial Evidence Pack → transect/section → selected object → scenario relation → Decision Record / report` を保存する。Pack manifestのcontent hash、source dataset versions、network version、analysis runs、classificationをEvidence Centerとreport manifestへ参照させる。同じSaved Viewはpack ID、transect ID、camera、layer、selection、counterfactual stateを復元し、後のversionで暗黙に置換しない。

公開Evidenceへはprivacy gateを通ったPackだけを出し、建物単位人口model、restricted field observation、庁内overrideを含めない。対象オブジェクトが不足する場合はEvidenceを生成済みにせず `unavailable` とする。

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

## V2: 建物推計人口

Priority 2の1 recordは次を辿れる。

```text
PLATEAU gml:id
  → ZIP内source CityGML member + member CRC32 + archive SHA-256
  → bldg:usage + 同梱Building_usage.xmlの公式ラベル
  → totalFloorArea（または明示したfallback source）
  → EPSG:6674の建物・500m mesh交差面積とallocation_fraction
  → e-Stat 2020国勢調査500m mesh code・人口・65歳以上人口
  → strict_residential式
  → estimated_population / estimated_elderly_population
```

例をAPIで参照する場合も`estimated_`名、source mesh、配賦method、weight、fraction、source yearを返す。
秘匿・合算影響meshにはこのchain自体を生成せず、`mesh_fallback_suppression`で停止する。

## V2: 建物アクセシビリティ

```text
building_origin_representative_point
  → nearest facility name/type
  → PLATEAU駅2025 / 国土数値情報P11 2022 / P04 2020
  → JGD2011 平面直角座標系VI（EPSG:6674）
  → Euclidean straight-line formula
  → distance_m + facility_policy
```

代表点は入口ではなく、距離はwalking routeではない。mesh集計はParquetの推計65歳以上人口を重みにした
平均・inverse-CDF中央値・p90まで辿り、`verify_building_demographics.py`が5つの実meshを別実装で再計算する。
