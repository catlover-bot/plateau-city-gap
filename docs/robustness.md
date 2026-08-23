# Robust CITY GAP

## 目的

CITY GAPの順位が、1つのScore定義だけで決まって見えないようにする。ここでいうRobustnessは、あらかじめ定義した複数条件で候補がTop 10 / Top 20 / Paretoに残る回数である。確率、信頼度、将来予測ではない。

## 9つの分析条件

| ID | 条件 | 主な変更 |
|---|---|---|
| S1 | 高齢者数 × 交通 × 医療 | Primary Score C |
| S2 | 高齢化率 × 交通 × 医療 | needを人数から比率へ変更 |
| S3 | 高齢者数 × 交通 | 医療を積から除外 |
| S4 | 高齢者数 × 医療 | 交通を積から除外 |
| S5 | 一般利用不明の医療を除外 | `uncertain_access`を除外して再順位化 |
| S6 | 市境外2km + 医療利用可否 | 同一府の市境外施設を加え、一般利用不明医療を除外 |
| S7a | 人口閾値なし | 秘匿・合算影響のない比較対象286件を順位化 |
| S7b | 人口50 / 65歳以上20 | Primaryより厳しい人口閾値 |
| S8 | Pareto候補のみ | S1の3要素で劣後しないPrimary候補だけを順位化 |

S7を2条件に分けたため、scenario数は9である。条件を水増しせず、既存のScore監査で意味のあるvariantだけを採用した。

## 指標と順位規則

各meshについて `top10_frequency`、`top20_frequency`、`pareto_frequency`、`median_rank`、`rank_min`、`rank_max`、`scenario_count` を保存する。頑健候補の順序は次の決定論的規則で作る。

1. Top 10出現回数の降順
2. median rankの昇順
3. Top 20出現回数の降順
4. mesh codeの昇順

新しい合成スコアや重み付き平均は作らない。

## 結果

基準Score CのRank 1 `533512753` 二尾バス停周辺は、9/9条件でTop 10、9/9条件でTop 20、7/9条件でParetoに残った。中央値1位、順位範囲1〜5位で、頑健候補でもRank 1だった。

頑健候補Top 5:

| 頑健順位 | mesh | 周辺ラベル | Top 10 | Top 20 | Pareto | median | range |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | 533512753 | 二尾バス停周辺 | 9/9 | 9/9 | 7/9 | 1 | 1–5 |
| 2 | 533522274 | 赤野バス停周辺 | 7/9 | 9/9 | 8/9 | 2 | 2–18 |
| 3 | 533502982 | 京田バス停周辺 | 7/9 | 8/9 | 8/9 | 4 | 1–24 |
| 4 | 533512144 | 中筋小学校口バス停周辺 | 7/9 | 8/9 | 7/9 | 5 | 2–31 |
| 5 | 533512132 | 上福井バス停周辺 | 6/9 | 8/9 | 0/9 | 3 | 3–19 |

## 再生成

```bash
SOURCE_DATE_EPOCH=1787392800 python -m analysis.scripts.build_decision_studio_assets
python -m analysis.scripts.verify_decision_studio
```

出力は `analysis/outputs/real/maizuru_robustness.json`、`maizuru_robust_candidates.csv`、Web用 `frontend/public/data/robustness.json`。入力、順位、scenario定義はすべて追跡可能で、生成AIによる判定はない。

