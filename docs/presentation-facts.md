# CITY GAP presentation facts

2026-09-05の発表で使用してよい固定数字です。このファイルを発表資料のSingle Source of Truthとし、丸め前の値は記載した生成元を参照します。

## 舞鶴市 Primary Demo

| Fact | 発表値 | Source |
|---|---:|---|
| 市境交差mesh | 495 | `maizuru_summary.json` → `record_counts.population_meshes_intersecting_city` |
| percentile比較mesh | 286 | 同 `population_unaffected` |
| Primary順位対象 | 218 | 同 `primary_rank_eligible_meshes` |
| Rank 1 | `533512753` 二尾バス停周辺 | `maizuru_city_gap_top10.csv` rank 1 |
| Rank 1人口 | 91人 | 同 `population` |
| Rank 1 65歳以上 | 56人 / 61.5% | 同 `elderly_population`, `elderly_ratio` |
| 最寄り収録交通 | 二尾バス停 2.32km | 同 `nearest_public_transport_*` |
| 最寄り収録医療 | 隅山医院 3.32km | 同 `nearest_medical_*` |
| Score C | 0.498 | 同 `exploratory_score_c`。発表では補助情報のみ |
| Deep Dive | 全市23位 常団地前バス停周辺 | `final_demo.json` → `deep_dive` |
| Deep Dive建物 | 対象mesh内296棟 | 同 `deep_dive.plateau_building_count` |
| Deep Dive道路面 | 135件 | 同 `deep_dive.plateau_road_surfaces_intersecting_mesh` |

### What-if候補1

Source: `frontend/public/data/final_demo.json` と独立再計算 `analysis/outputs/real/final_audit.json`。両者はexact match。

- 舞鶴和知線付近のPLATEAU道路面代表点
- 最大改善mesh `533513314`: 562.597m → 29.867m、差532.730m（画面表示563m → 30m、−533m）
- 距離が短くなるmesh: 5
- その5meshに記録された65歳以上人口合計: 241人
- 改善meshの平均距離短縮: 532.856m
- Score C合計純減少: 0.171526845

241人は利用者、受益者、需要、乗客の予測ではありません。道路面代表点は用地や設置可能地点の確認結果ではありません。

## 藤沢市 Cross-city Validation

| Fact | 発表値 | Source |
|---|---:|---|
| 市境交差mesh | 327 | `fujisawa_summary.json` |
| percentile比較mesh | 263 | 同 `record_counts.population_unaffected` |
| Primary順位対象 | 261 | 同 `primary_rank_eligible_meshes` |
| Rank 1 | `533913073` 県営サンハイツ渋谷前バス停周辺 | `fujisawa_city_gap_top10.csv` |
| 人口 / 65歳以上 | 3,590人 / 921人 | 同 |
| 市内施設baselineの収録交通 | 593m | 同 `nearest_public_transport_distance_m` |
| 市内施設baselineの収録医療 | 734m | 同 `nearest_medical_distance_m` |
| 藤沢市内相対位置 | 交通約97、医療約95 percentile | 同 percentile列 |

藤沢のScore C `0.869`は発表で舞鶴`0.498`と比較しません。市外2km・利用可否不確かな医療を除く感度では交通346m、医療506m、Top 10一致7/10ですが、Rank 1自体は維持されました。593m/734mを絶対的な交通空白・医療空白とは呼びません。

## データ年次

- 人口: e-Stat 2020年国勢調査
- 医療: 国土数値情報P04 2020年
- バス停: 国土数値情報P11 2022年
- PLATEAU: 舞鶴市・藤沢市2025年度

これは2026年現在の状況そのものではありません。

