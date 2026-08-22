# Methodology

## MVP hypothesis

探索仮説は「高齢人口の必要度が高いにもかかわらず、公共交通と医療へのアクセスが低い地域」。政策上の問題を断定せず、追加調査候補を並べる探索指標として扱う。

## Population and 500 m geometry

e-Stat `T001192` の9桁 `KEY_CODE` をJIS X 0410の500m（half）meshとして復号し、JGD2011（EPSG:6668）のpolygonと中心緯度経度を構築する。独自復号はquadrantと寸法をテストする。PLATEAU行政界を面化し、polygon intersectionで舞鶴市対象を抽出する。

65歳以上人口は5歳階級「総数」の `043 + 046 + 049 + 052 + 055 + 058 + 061`。`elderly_ratio = elderly_population / population` とする。

### Suppression and aggregation

- `HTKSYORI=0`: 年齢構成をmesh位置へ対応でき、Primary analysisに使用。
- `HTKSYORI=1`: `GASSAN`元の年齢人口を含む合算先。総人口はセル単独値なので比率計算不可。
- `HTKSYORI=2`: 秘匿元。年齢列の `*` はゼロでなく未知。

flag 1/2を補完・推定せず、行と参照列は出力に保持するが、分析用高齢者数・比率とrankを欠損にする。将来使う場合は合算元・先のgeometry unionと総人口合計を一体として扱う必要がある。

## CRS and straight-line distance

全レイヤーを JGD2011 / Japan Plane Rectangular CS VI（EPSG:6674）へ変換する。このCRSの公式area of useは京都府を含み、舞鶴市全域が範囲内である。緯度経度degreeでは距離計算しない。

500m mesh centroidから各点までのユークリッド直線距離を計算する。行政界と交差する全meshについて `maizuru_area_fraction` と `centroid_within_maizuru` もQA用に保持する。`nearest_public_transport_distance_m = min(station, bus stop)`。医療PrimaryはP04分類1（病院）と2（一般診療所）で、歯科を除外する。これは徒歩距離・道路距離・実際の移動距離ではない。

## Component rankings

Primary対象286meshの経験的percentile（昇順、tieは平均rank）を別列として保持する。

```text
A = elderly_population_percentile * transport_distance_percentile
B = elderly_population_percentile * medical_distance_percentile
C = elderly_population_percentile * transport_distance_percentile
    * medical_distance_percentile
```

各積は `exploratory_score_a/b/c` であり、政策的正解や公式指標ではない。高齢者数・交通距離・医療距離を全て最大化する3目的Pareto frontierも計算し、積の重みに依存しない候補を併記する。

Primary Top 10は、単身・数人だけの遠隔meshを上位候補にしない感度確認として `population >= 20` かつ `elderly_population >= 10` を明示的に適用する。閾値なし、10/5、20/10、50/20のTop 10もsummaryに残し、隠れたフィルタにしない。

## Limitations

- 直線距離は道路接続、運行頻度、坂、横断障害、施設能力を表さない。
- mesh中心は実際の居住位置ではなく、境界部では居住域や陸地外の場合もある。
- percentileは市内相対値で、他都市・時点と直接比較できない。
- Primary scoreは高齢者「数」を使う。高齢化「率」もcomponentとして保存するが総合積には入れない。
- 駅は路線別重複を含む。距離には影響しないが集計時は座標等で重複排除する。
- P11は2022年、P04は2020年、人口は2020年、駅は2025年配布で時点が一致しない。
- 運行頻度、診療能力、現在の営業状態、公共利用可否は評価していない。

## PLATEAU extension (not implemented)

2D GISでも直線距離は計算可能。PLATEAU固有価値は、CityGMLの建物用途・高さ・階数の実在/欠損率を確認後、居住建物単位の起点、`tran`道路ネットワーク、標高・勾配による移動負荷へ段階的に拡張する。いずれも未実装で、属性検証前には採用しない。
