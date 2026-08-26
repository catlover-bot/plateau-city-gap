# GTFS-ready, stage jobs and evidence export

## GTFS-ready boundary

CITY GAPにはGTFSのadapter/interfaceとPostGIS schemaがありますが、舞鶴市・藤沢市の実GTFS feedは登録されていません。国土数値情報P11のバス停pointをGTFSへ変換したり、route、trip、運行時刻、頻度を補作したりしません。city registry上のGTFS capabilityは両都市とも`unavailable`です。

adapterは次の6表を受け取ります。

- `stops`
- `routes`
- `trips`
- `stop_times`
- `calendar`
- `calendar_dates`

必須列、主key、route/trip/stop/service参照、緯度経度、trip内時刻順を検証します。GTFSの24時以降表記も秒へ変換できるcontractです。migration 007は同じ表を`dataset_version_id`へ結び、実feedのchecksumがある場合だけ`gtfs_feeds`を作る設計です。将来は現在の停留所距離からfrequency、service hours、time-dependent accessibilityへ拡張できますが、現時点ではそれらの分析値を出していません。

## Stage-based jobs

job typeは次の6種です。

- `plateau_ingestion`
- `building_demographics`
- `network_generation`
- `terrain_enrichment`
- `context_generation`
- `scenario_optimization`

stateは`queued / running / succeeded / failed`です。進捗は各typeに定義した実stageの順序だけで表し、架空のpercentageを返しません。例えばscenario jobは次の順です。

```text
prepare_candidates
→ build_sparse_matrix
→ optimize_objectives
→ independent_verification
→ persist_artifacts
```

stageの飛び越しと、最終stage前の`succeeded`はdomain modelが拒否します。APIでjobを作った時点は`queued`であり、計算済みとは扱いません。

- `POST /registry/cities/{city_id}/jobs`
- `GET /jobs/{job_id}`
- `POST /jobs/{job_id}/transition`

現行実装はdurable state/API frameworkで、process workerやqueue serviceはまだ接続していません。transition endpointはprototype内部用です。自治体pilotで外部公開する前に認証・権限とworker identityを追加する必要があります。

## Evidence Package

`export_scenario_evidence` は任意のcanonical planから次を生成します。

- JSON: scenario、site、impact、PLATEAU IDs、version、source dataset/year、constraints、Evidence Chain、limitations、field checks
- CSV: metric/site/context/flag/source/checklistのlong-form review表
- HTML: script不要の印刷用review sheet

```bash
python -m analysis.scripts.export_scenario_evidence \
  --plan-id network-overall-3
```

実例は`analysis/outputs/real/evidence_packages/network-overall-3/`です。設置可能性は`not_determined`、recommendationは`null`、field checkは`unknown`で開始します。HTMLはPDFを装わず、ブラウザの印刷機能で確認できる静的文書です。個別建物の実人数・推計人数は記載せず、代表建物のGML IDと人口推計method/sourceだけをEvidence Chainに残します。

PostGIS migrationにはexportのformat/path/hashを記録する`evidence_exports`がありますが、この環境ではDBへ登録していません。
