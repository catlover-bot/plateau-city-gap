# CITY GAP Validation & Municipal Evidence

CITY GAPのValidationはtest suiteの別名ではなく、claim、method、reference、sample、result、disagreement、uncertainty、field reviewを版付きで保持するdomainです。自動testの成功は`externally_validated`や`municipally_reviewed`へ昇格させません。

## Validation chain

```text
primary model
  → independent reference model
  → bounded assumption sensitivity
  → real multi-year official data
  → explicit field/municipal review status
  → 18-stage public-data pilot rehearsal
```

公開UIの`検証Evidence`はCompetition Demo、自治体Workspace、時間・レジリエンスとは別画面です。実座標の差異経路、同一OD指標、S1–S5仮定、国立市2023/2025差分、9 claimのEvidence strengthを表示します。OSMも公式データも現地のground truthとは呼びません。

## Network reference boundary

- Primary: PLATEAU CityGML LOD1道路面の実験的隣接graph。歩行networkではありません。
- Official generator: [PLATEAU-RoadNetwork-Generator](https://github.com/Project-PLATEAU/PLATEAU-RoadNetwork-Generator)を2026-08-27に再確認しましたが、舞鶴・藤沢の生成済みwalk/drive出力は公開されておらず、現行配布はWindows GUI workflowのため`NOT_AVAILABLE`です。manual-export adapterは維持しています。
- Independent reference: 2026-08-27T00:00Zを固定したOverpass highway extractです。[OpenStreetMap ODbL attribution](https://www.openstreetmap.org/copyright/)を保持し、本番networkの置換には使いません。
- Public alternatives: [Geofabrik Japan](https://download.geofabrik.de/asia/japan.html)は再取得経路として調査済みですが、今回の比較はquery・bboxを固定できるOverpass extractを採用しました。

層化条件はshort / medium / long / coastal / mountainous / urban center / high detour / disconnected / high elderly-weightedです。手動cherry-pickはありません。

| City | routes | MAE | median abs. | p90 abs. | Spearman | connectivity agreement |
|---|---:|---:|---:|---:|---:|---:|
| 舞鶴 | 125 | 306.8m | 68.8m | 320.7m | 0.957 | 88.0% |
| 藤沢 | 126 | 101.0m | 45.4m | 210.9m | 0.912 | 88.9% |

一致率はconfidenceでも正解率でもありません。差異は`distance_similar`、`moderate_difference`、`large_difference`、`connectivity_disagreement`に分け、topology / crossing / bridge / road coverage / snap / one-way / pedestrian permission / geometry resolutionの決定的原因候補を保存します。

## Assumption and temporal validation

災害stress testはhazard type × S1–S5について、対象edge、到達不能建物、集約された高齢者推計、医療・避難所到達性、fragmentationを比較します。Criticalityはtopology tolerance、network処理、component、snap thresholdを変えた5モデルの`present_in_n_models`と範囲を保持し、合成scoreを作りません。

Temporal engineはproduct cityを増やさず、[国立市2023公式PLATEAU](https://www.geospatial.jp/ckan/dataset/plateau-13215-kunitachi-shi-2023)と[国立市2025公式PLATEAU](https://www.geospatial.jp/ckan/dataset/plateau-13215-kunitachi-shi-2025)をvalidation-only datasetとして実処理しました。building / road / land use / urban planningのadded、removed、geometry、attribute、unchangedを算出し、同一ID・unique geometry hash・bounded attribute fallbackの割合を記録しています。曖昧matchは強制していません。全4テーマでincremental stateとfull rebuildのcount/state hashが一致しました。人口配分とmesh metricsは国立市をproduct setupしていないため`NOT_AVAILABLE`です。

## Evidence and reproduction

Validation Evidence PackageはJSON、CSV、print HTMLとSHA-256付きmanifestを`analysis/outputs/real/validation/evidence_package/`へ生成します。再現bundleは`analysis/outputs/real/validation/reproducibility/`にenvironment、source manifest、raw source hashes、commands、algorithm versions、expected summary hashesを保持します。巨大rawは追跡しません。

```bash
pip install -e ".[platform,dev]"
citygap validate reproduce --city maizuru
citygap validate reproduce --city fujisawa
```

コマンドはsource SHA-256を検証し、分析・validationを再実行し、都市別metricsのcanonical hashが期待値と一致しなければ失敗します。

## Governance boundary

現状は`awaiting_field_validation`かつ`not_reviewed`です。実地確認や自治体承認をfixtureで代用しません。Public Pagesには建物別人口推計、field note、actor identity、municipal-only scenario metadataを出さず、再帰privacy testで検査します。詳細は[day-2 runbook](validation-day2-runbook.md)と[STRIDE threat model](validation-security-threat-model.md)を参照してください。
