# Methodology

## MVP hypothesis

探索仮説は「高齢人口の必要度が高いにもかかわらず、公共交通と医療へのアクセスが低い地域」。政策上の問題を断定せず、追加調査候補を並べる探索指標として扱う。

## Components and distance

人口取得後に500mメッシュまたは小地域を確定する。`population`, `elderly_population`, `elderly_ratio`, `station_distance_m`, `bus_stop_distance_m`, `medical_distance_m` を保存する。距離は地域ポリゴンのrepresentative pointから最寄り施設まで、JGD2011 / 平面直角座標系VI（EPSG:6674）で計算するユークリッド直線距離である。

## Exploratory score

各指標を舞鶴市内の経験的percentile（昇順、同値は平均rank）へ変換する。

```text
demographic_need = percentile(elderly_ratio)
transport_deficit = mean(percentile(station_distance), percentile(bus_stop_distance))
accessibility_deficit = mean(transport_deficit, percentile(medical_distance))
gap_score = demographic_need * accessibility_deficit
```

根拠ある重みが未確立なため等重みとする。欠損がある行は複合値も欠損とし、利用可能な値だけで過大評価しない。構成percentile、複合値、最終percentile、rankは別列に保存し、固定閾値は設けない。

## Limitations

- 直線距離は道路接続、運行頻度、坂、横断障害、施設能力を表さない。
- 地域代表点は実際の居住位置ではない。
- percentileは市内相対値で、他都市・時点と直接比較できない。
- 人口「数」と高齢化「率」は異なる必要度。MVPは率を使うが双方を出力する。
- 駅は路線別重複を含む。距離には影響しないが集計時は座標等で重複排除する。

## PLATEAU extension (not implemented)

2D GISでも直線距離は計算可能。PLATEAU固有価値は、CityGMLの建物用途・高さ・階数の実在/欠損率を確認後、居住建物単位の起点、`tran`道路ネットワーク、標高・勾配による移動負荷へ段階的に拡張する。いずれも未実装で、属性検証前には採用しない。
