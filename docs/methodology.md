# Methodology

## Scope and interpretation

探索仮説は「高齢者の地域ニーズが大きく、公共交通と医療までの距離も相対的に長い地域がある」です。CITY GAPは、その空間的なミスマッチを複数データから見つけるための比較指標です。

結果は「政策課題の確定」「危険度」「施設を設置すべき場所」を意味しません。順位は現地確認、住民・事業者へのヒアリング、より詳細な移動分析を始める候補です。「都市計画の目標値と現実」を直接比較しているわけでもありません。

## Single Source of Truth

Webアプリの分析値は次の実データ成果物から生成します。

- `analysis/outputs/real/maizuru_mesh_metrics.csv`
- `analysis/outputs/real/maizuru_city_gap.geojson`
- `analysis/outputs/real/maizuru_city_gap_top10.csv`
- `analysis/outputs/real/maizuru_summary.json`

`analysis/scripts/build_web_assets.py` は値を再計算せず、公開用属性を選択・検証・変換します。フロントエンドへRankや距離を手入力しません。

## Population and 500m geometry

e-Stat `T001192` の9桁 `KEY_CODE` をJIS X 0410の500m（half）meshとして復号し、JGD2011（EPSG:6668）のpolygonと中心座標を構築します。quadrantと寸法はtest fixtureで検証します。PLATEAU行政界の閉ringをpolygon化し、bboxやmesh接頭辞ではなくpolygon intersectionで舞鶴市対象を抽出します。

65歳以上人口は5歳階級「総数」の `043 + 046 + 049 + 052 + 055 + 058 + 061` です。

```text
elderly_ratio = elderly_population / population
```

### Suppression and aggregation

| `HTKSYORI` | Meaning | Maizuru intersection | Handling |
|---:|---|---:|---|
| 0 | 秘匿・合算影響なし | 286 | percentile比較に使用 |
| 1 | 合算先 | 90 | 表示・raw値保持、比較から除外 |
| 2 | 秘匿元 | 119 | 表示・raw値保持、比較から除外 |

`HTKSYORI=2` の `*` はゼロでなく未知です。`HTKSYORI=1` の年齢人口は合算group値ですが、総人口は当該cell単独値なので、そのまま高齢化率を計算できません。flag 1/2を補完・推定せず、分析用高齢者数・比率・percentile・rankを欠損にします。

## CRS and distances

全layerをJGD2011 / Japan Plane Rectangular CS VI（EPSG:6674）へ変換して距離を計算します。このCRSのarea of useは京都府を含み、舞鶴市は範囲内です。緯度経度degreeのまま距離を測りません。

500m mesh centroidから各pointまでのユークリッド直線距離を計算します。`nearest_public_transport_distance_m` は最寄り駅と最寄りバス停の短い方です。医療PrimaryはP04分類1（病院）と2（一般診療所）の71件で、歯科34件を除外します。

これは徒歩距離、道路距離、所要時間、公共交通での移動時間ではありません。行政界と交差する全meshについて `maizuru_area_fraction` と `centroid_within_maizuru` もQA用に保持します。

## Percentiles and exploratory scores

秘匿・合算影響のない286mesh内で、各componentの経験的percentileを昇順で計算します。同値はaverage rank、percentileは1-based rankを件数で割った値です。

```text
A = elderly_population_percentile × transport_distance_percentile
B = elderly_population_percentile × medical_distance_percentile
C = elderly_population_percentile × transport_distance_percentile
    × medical_distance_percentile
```

距離percentileが高いほど、市内比較で施設から遠い側です。Score Cは「高齢者数」「交通距離」「医療距離」の3componentを等しい積として重ねた探索用指数で、高齢化率そのものは積へ入れません。高齢化率とそのpercentileは説明用componentとして保持します。

積の形式だけに依存しない確認として、3componentを同時に最大化するPareto frontierも計算します。

### Ranking condition

Top 10は286meshからさらに次の明示条件を満たす218meshを対象にします。

```text
population >= 20
elderly_population >= 10
```

単身・数人の遠隔meshだけが上位化しないかを見るための感度条件です。閾値なし、10/5、20/10、50/20の比較結果もsummaryに残し、隠れたfilterにはしません。

## Deterministic explanation

「WHY なぜCITY GAP候補？」の文章はLLMや外部APIを使いません。選択meshの人口、65歳以上人口、最寄り距離、percentileを定型規則で整形します。barの長さも同じpercentile値から生成されるため、文章・数値・地図色の根拠を追跡できます。

## What-if simulation

仮想交通支援拠点はブラウザ内で1点だけ扱います。

1. 公式PLATEAU道路面上の事前計算候補、Cesium上のclick、または診断用Rank 1中心からWGS84座標を得る。
2. proj4でWGS84（EPSG:4326）からEPSG:6674へ変換する。
3. 286meshのcentroidから仮想pointまでのEuclidean距離を計算する。
4. 各meshについて既存交通距離と仮想point距離の小さい方を採用する。
5. 286件全体でafter交通距離percentileを再計算する。
6. baselineの高齢者数percentileと医療距離percentileを固定し、after Score Cを計算する。

```text
d_virtual(i) = Euclidean(centroid_i, virtual_point)
d_after(i)   = min(d_before(i), d_virtual(i))

score_after(i)
  = elderly_population_percentile(i)
  × rank_pct(d_after)(i)
  × medical_distance_percentile(i)
```

UIの「距離が改善するmesh」は `d_after < d_before` の件数です。「対象meshの65歳以上人口」はそのmeshに記録された65歳以上人口の合計であり、利用者数、需要、受益人口の推定ではありません。「改善幅Top 5」は `score_before - score_after` の降順です。

### Primary placement search and reproducible example

Primary候補は、公式PLATEAU道路LOD1面の内部代表点16,778件から舞鶴市内を抽出し、既存駅・バス停から150m超の12,062点を評価します。目的関数は「286比較メッシュのScore C合計の純減少量最大化」です。上位地点が同じ街区へ集中しないよう候補間を1,500m以上離してTop 3を選びます。道路面上という条件は海上や任意のメッシュ中心を避けるscreeningであり、利用可能な用地・停留所位置を意味しません。

Primary候補1は公式道路「舞鶴和知線」面の内部代表点（135.396649917, 35.447720315）、人間向けラベルは「常団地前バス停周辺」です。

| Measure | Before | After |
|---|---:|---:|
| 最大改善mesh `533513314` transport distance | 562.597m | 29.867m |
| 最大改善mesh Score C | 0.279685 | 0.003609 |
| 改善mesh数 | 5 | — |
| 対象meshの65歳以上人口合計 | 241人 | — |
| 改善meshの平均距離短縮 | 532.856m | — |
| 286mesh Score C合計の純減少 | 0.171527 | — |

241人は利用者・需要・受益人口の予測ではありません。`Rank 1中心で試す` は0mを生じる計算診断として折りたたみ内に残しますが、Primary発表には使いません。

## PLATEAU inspection

### Whole-city verification

公式「3D都市モデル（舞鶴市）2025年度」の3D Tiles/MVT ZIP（160,582,905 bytes、SHA-256 `15cf5e12b507b89e2b86fe0c2968a22e8d770ea36cb8c64cc7e8db578109f2d9`）をraw領域へ取得しました。

LOD2配布コンテナの427 b3dmを読み、batch tableの `gml_id` でtile間重複を除いた一意建物は44,640棟です。Top 10の各polygonに対して建物中心の包含とbuilding bounding boxの交差を確認し、全10meshで0棟でした。建物を推定・補完せず、Webでは「Top 10は公式建物モデル整備範囲外」と表示します。

### PLATEAU-covered candidates and 3D Deep Dive

44,640棟の代表点を同じ500mメッシュへ結合すると、286比較対象のうち154メッシュに公式建物が1棟以上ありました。Score C順の上位5件は `analysis/outputs/real/plateau_covered_candidates.csv` に固定schemaで保存します。全市Rank 1と「PLATEAU 3Dで確認できる候補」を混同しません。

3D Deep Diveには、PLATEAU-covered上位5件でありPrimary配置候補の最大改善meshでもある、全市23位 `533513314`「常団地前バス停周辺」を選びました。leaf regionがこの500mメッシュと交差する3 tileを選択します。

| Item | Verified value |
|---|---:|
| leaf b3dm | 3 |
| b3dm bytes | 4,313,608 |
| subset buildings | 856 |
| Deep Dive mesh内building representatives | 296 |
| actual `_lod=1` | 856 |
| Deep Dive meshと交差する道路LOD1面 | 135 |

クリックでは `gml_id`、用途、計測高さ、地上/地下階数、建築面積、延べ面積、実LODを表示します。属性を推定せず、欠損・sentinelは「属性なし」とします。CITY GAPは500m単位であり、個々の建物にスコアを付けません。

### Road and terrain context

公式CityGML packageには建築物80、道路82、DEM 23、土地利用7、都市計画20、地形名称5、洪水143のGMLが含まれます。Deep Diveでは道路面を表示し、公式DEM TINの20,965三角形を集計しました。標高は26.134〜127.923m（中央値36.968m）、三角形局所勾配は中央値6.961°、p90 37.406°です。これは対象メッシュに急な地形が含まれる注意情報で、歩行経路の勾配や通行可能性ではありません。

道路LOD1は面形状で、接続トポロジー、歩道、横断条件、通行可否を持ちません。そのため、Deep Dive meshの公共交通直線距離562.597mに対する「urban-context-aware経路距離」は計算不能と明記します。見かけの道路polygonをcenterline networkへ変換して経路距離を捏造しません。

## Web publication validation

Web asset生成前に少なくとも次を検証します。

- Top 10 rankが1〜10で重複しない
- mesh codeが全体で一意、Top 10が全体に存在する
- `population >= 0`
- `0 <= elderly_population <= population`
- 使用する距離が0以上
- GeoJSON geometryが有効
- 緯度経度が有効範囲内
- source件数とWeb件数がsummary/manifestに整合する
- PLATEAU inspectionがTop 10全meshを含み、0棟の場合に架空geometryを出さない

`manifest.json` に生成日時、analysis version、source、年次、CRS、record count、input/output hash、limitationsを記録します。

## Limitations

- mesh中心は実際の居住地点ではなく、境界部では居住域や陸地外の場合があります。
- 直線距離は道路接続、坂、横断障害、徒歩可能性を表しません。
- P11は運行頻度、デマンド交通、高速・長距離バス、施設送迎を含みません。
- P04は2020年時点で、施設能力、一般利用可否、現在の開設を保証しません。
- 人口/P04は2020年、P11は2022年、PLATEAUは2025年で時点が一致しません。
- percentileは今回の舞鶴市内相対値で、他都市・時点や政策閾値と直接比較できません。
- 駅の路線別重複は名称・位置で7地点へ除きますが、サービス頻度は評価しません。
- Top 10に公式PLATEAU建物モデルがなく、候補地の建物形状・用途は評価できません。
- Deep Dive subsetの建物属性、道路、DEMは現行スコアへ入力していません。
- 配置候補は道路面上ですが、What-if効果は直線距離で、接続・横断・坂・用地・運行可能性・需要・費用・施設capacityを評価しません。
