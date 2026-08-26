# Network-aware municipal scenarios

この分析は、舞鶴市の実在する居住系建物を起点に、PLATEAU道路LOD1面の隣接graph上で仮想支援拠点を1〜5地点配置した場合の変化を比較します。施策の採否や用地の利用可能性を決定するものではなく、自治体が現地確認と部局横断レビューを始めるための比較材料です。

## Resolution story

```text
500m国勢調査
  → 実在する居住系建物へのモデル配賦
  → 建物代表点をPLATEAU道路graphへsnap
  → 公共交通までのbaseline network距離
  → 土地利用・都市計画・洪水・土砂・津波・DEMを文脈結合
  → 11,460の道路面候補から1〜5地点のscenarioを比較
```

対象は居住系建物28,448棟、有限baseline 28,443棟、道路node 15,684、辺23,437、有限需要node 6,963です。候補と需要の全組合せ79,795,980件を密行列にせず、距離が実際に改善する1,063,003組だけを保持します。graphは実験的な道路面隣接graphであり、公式または検証済みの歩行者networkではありません。

## Objectives and exactness

主要な比較軸は次の5つです。それぞれ別の目的として表示し、意味の異なる指標を単一の政策スコアに混ぜません。

| mode | 目的 |
|---|---|
| overall | 改善建物のnetwork距離短縮量を最大化 |
| elderly | 500m統計からの高齢者推計で加重した短縮量を最大化 |
| worst_served | baseline距離の下位10%に属する建物の改善を最大化 |
| robust | Robust Top 20 mesh内の高齢者加重改善を最大化 |
| balanced | 4目的を別々に正規化し、最小改善比から辞書式に最大化するmax-min案 |

`reachability` はbaselineでnetwork到達不能だった建物componentを先に扱う補助診断です。新規到達建物数、次にoverall改善量を辞書式に比較します。

1地点案は各modeの記載目的について候補集合内の厳密解です。2〜5地点案は候補間1,500m以上を保つ決定的forward-greedy近似で、全体最適解とは主張しません。各地点数ではPareto非劣解を併記しますが、特定案に「推奨」ラベルは付けません。0〜5地点の系列には総改善、影響建物、高齢者推計、worst-served、新規network到達の増分を保存します。

## Context and review flags

各候補には、実データから得た土地利用、都市計画、洪水、土砂災害、津波、DEM、道路GMLとsource memberを保存します。災害区域との重なりは `additional_confirmation_required` であり、自動的な不適格判定ではありません。次の6項目も審査結果ではなくreview promptです。

- `hazard_attention`
- `planning_attention`
- `landuse_attention`
- `network_component_attention`
- `long_connector_attention`
- `terrain_attention`

土地所有、施工可能性、運行、費用、横断可能性、歩道の有無は確認していないため、すべての候補の `siting_feasibility` は `not_determined` のままです。

## Evidence Chain

各案は代表建物1棟について、建物 `gml:id`、人口推計の出典・配賦法、代表点、snap node、道路edge/node列、PLATEAU道路GML ID、仮想候補、before/after距離、route上のDEM観測を保存します。個別建物の実人数は出力しません。独立検証は全30案の影響値を再計算し、1地点厳密性、200のsample経路、候補間隔、文脈の非決定性、6フラグ、代表routeの全edgeを照合します。

## Reproduce and inspect

```bash
python -m analysis.scripts.build_network_scenarios --max-sites 5
python -m analysis.scripts.verify_network_scenarios
pytest -q analysis/tests/test_network_scenario.py \
  analysis/tests/test_network_scenario_artifacts.py
```

主要成果物は次のとおりです。

- `analysis/outputs/real/maizuru_network_scenarios.json`: 正本となる30案、文脈、Evidence Chain
- `analysis/outputs/real/maizuru_network_scenario_summary.csv`: 案単位の比較表
- `analysis/outputs/real/maizuru_network_scenario_performance.json`: stage実行時間、peak RSS、疎行列・成果物容量
- `analysis/outputs/real/maizuru_network_scenario_verification.json`: 独立再計算の結果
- `frontend/public/data/network_scenario_story.json`: Scenario A/Bに絞り、mesh全件を除いた静的公開subset

詳細なbuilding-level Parquetは、自治体・privacyレビュー前のためGit管理外です。静的GitHub Pagesは既存のScenario A/B storyを維持し、この正本から選択したscenarioだけを公開します。
