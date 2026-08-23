# PLATEAU建物用途の監査

## 出典と再現方法

用途は名称からの推測ではなく、舞鶴市2025 CityGML ZIPに同梱された
`codelists/Building_usage.xml`（CRC32 `85563f25`）を読み、44,640棟の
`bldg:usage`実値へ結合した。結果は
`analysis/outputs/real/maizuru_building_usage_audit.csv`、処理は
`analysis/src/plateau_buildings.py` と
`analysis/scripts/build_building_demographics.py` に固定している。製品仕様はZIP内メタデータが示す
[PLATEAU標準製品仕様書](https://www.mlit.go.jp/plateau/libraries/handbooks/) 5.0、拡張製品仕様書 ADE 3.2である。

## 実在コードと分類

| code | 同梱codelistの公式ラベル | 実棟数 | CITY GAP分類 |
|---:|---|---:|---|
| 401 | 業務施設 | 969 | non_residential |
| 402 | 商業施設 | 1,177 | non_residential |
| 403 | 宿泊施設 | 77 | non_residential |
| 404 | 商業系複合施設 | 110 | non_residential |
| 411 | 住宅 | 27,891 | residential |
| 412 | 共同住宅 | 1,783 | residential |
| 413 | 店舗等併用住宅 | 1,461 | mixed_residential |
| 414 | 店舗等併用共同住宅 | 99 | mixed_residential |
| 415 | 作業所併用住宅 | 104 | mixed_residential |
| 421 | 官公庁施設 | 142 | non_residential |
| 422 | 文教厚生施設 | 1,283 | non_residential |
| 431 | 運輸倉庫施設 | 1,067 | non_residential |
| 441 | 工場 | 1,001 | non_residential |
| 451 | 農林漁業用施設 | 344 | non_residential |
| 452 | 供給処理施設 | 86 | non_residential |
| 453 | 防衛施設 | 0 | non_residential |
| 454 | その他 | 0 | non_residential |
| 461 | 不明 | 7,046 | uncertain |

Primaryの`strict_residential`は411・412だけを使う（29,674棟）。413・414・415は
住宅部分の床面積比を示す公式属性を確認できないためPrimaryへ混ぜない。感度分析
`residential_plus_mixed`でのみ全床面積を容量として加え、住宅比を創作しない。461、空欄、
非住宅を人口保存のための受け皿にはしない。

この分類は、一般的なコード表を手入力したものではなく、この製品に同梱された辞書と実値の
組合せである。別都市・別年度には同じ監査を再実行する。
