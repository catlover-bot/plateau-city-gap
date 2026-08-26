# Municipal scenario workspace contract

CITY GAPのscenario workspaceは、optimizerの出力をそのまま政策決定に変換せず、version固定された案を自治体レビューへ渡す境界です。分析正本はPythonで生成し、同じ7表をcanonical ParquetとPostGISで共有します。この環境ではParquet生成とloader contractのテストまでを行い、PostGISへの投入成功は主張していません。

## Canonical persistence

`analysis.scripts.build_scenario_canonical` は検証済み30案を次へ正規化します。

| table | 実データ行数 | 内容 |
|---|---:|---|
| `scenario_runs` | 30 | city、dataset、PLATEAU、network、context、algorithm、objective、地点数、runtime、status |
| `scenario_sites` | 90 | 選択候補、road/node/GML、座標、connector、feasibility境界 |
| `scenario_objectives` | 155 | 選択目的と独立した評価軸。balancedのvectorをmetadataで保持 |
| `scenario_constraints` | 630 | 1,500m間隔、claim boundary、6種のreview flag |
| `scenario_impacts` | 390 | 建物、距離、高齢者推計、worst-served、robust、到達不能変化 |
| `scenario_context` | 450 | land use、planning、hazard、terrain、road source |
| `scenario_evidence` | 30 | 代表建物から仮想siteまでのEvidence Chain |

各runは2025年舞鶴市archive SHA-256、PLATEAU標準製品仕様5.0、network version、context algorithm/config hash、scenario config hashを明示します。「最新version」は暗黙選択しません。1地点は`exact`、2〜5地点は`deterministic_greedy_approximation`です。初期statusは必ず`draft`です。

```bash
python -m analysis.scripts.build_scenario_canonical
python -m analysis.scripts.load_scenarios_postgis \
  --database-url "$CITYGAP_DATABASE_URL"
```

後者はmigration 001〜005を適用し、同一dataset/network/context versionを投入済みのDBだけで実行します。loaderはmanifestの各Parquetについて容量、SHA-256、行数を照合してからtransactionを開始します。

## Lifecycle

```text
draft
  ├─ under_review
  │    ├─ field_check_required
  │    │    ├─ under_review
  │    │    ├─ reviewed
  │    │    └─ archived
  │    ├─ reviewed
  │    └─ archived
  └─ archived

reviewed ─ under_review / archived
archived ─ terminal
```

`draft → reviewed`の一括遷移は禁止します。遷移はAPIで期待中statusを指定する明示操作であり、optimisation、import、hazard flagが自動実行することはありません。全遷移は`scenario_lifecycle_events`へ記録します。

## Field check

各siteには次を`unknown / confirmed / attention / not_applicable`で保存できます。

- site access
- road safety
- land ownership unknown
- existing service
- facility condition
- hazard confirmation
- operator consultation
- notes

これは人手の観察記録です。`attention`を不適格へ、`confirmed`を承認へ自動変換しません。

## API

| method | path | boundary |
|---|---|---|
| GET | `/cities/{city_id}/scenarios` | status filter、最大100件 |
| GET | `/cities/{city_id}/scenarios/{scenario_id}` | version・site・objective・impact・context・evidence |
| GET | `/cities/{city_id}/scenario-comparison?scenario_ids=A,B,C` | 2〜3案、recommendationは常にnull |
| PATCH | `/cities/{city_id}/scenarios/{scenario_id}/status` | expected/proposed statusによる明示遷移 |
| GET/PUT | `/cities/{city_id}/scenarios/{scenario_id}/sites/{site_order}/field-check` | 人手checklist |

比較APIは最大3案に制限し、overall、worst-served、robust等の異なる目的を横並びにします。単一の謎scoreや自動推奨は返しません。
