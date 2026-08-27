# Multi-city capability and dataset registry

CITY GAPは都市ごとの実装有無を画面やコードから推測しません。`platform_registry.json` がcity、dataset、dataset version、analysis run、capabilityの正本です。capabilityは必ず `available / partial / unavailable` のいずれかで、`available` と `partial` には実成果物のSHA-256 evidenceが必要です。

## Current capability matrix

| capability | 舞鶴市 | 藤沢市 |
|---|---|---|
| screening | available | available |
| building detail | available | available |
| road network | partial | partial |
| terrain | partial | partial |
| land use | available | available |
| urban planning | available | available |
| hazard | available | available |
| GTFS | unavailable | unavailable |
| scenario | available | unavailable |
| temporal diff | partial | partial |
| future population | available | available |
| hazard stress test | available | available |
| criticality | available | available |
| evacuation reachability | available | available |
| planning monitoring | available | available |
| field mode | partial | partial |
| outcome monitoring | partial | partial |

舞鶴市の道路networkは実CityGMLから生成済みですが、検証済み歩行者networkではないため`partial`です。terrainもDEM endpoint観測はありますが、歩行energyやrouting penaltyへ変換していないため`partial`です。

藤沢市でも建物人口、実験的道路graph、地形、土地利用、都市計画、災害文脈、将来人口、flood stress test、criticality、避難所到達性、計画比較を同じcoreで実データ処理しました。一方、最適化済みscenarioとGTFSは未登録のため`unavailable`です。P11バス停pointはGTFSではなく、GTFS capabilityの根拠にも使いません。

`temporal_diff`はengineと同一version correctness checkが利用可能ですが、両都市とも公式PLATEAUが1版だけなので年次差分実績は`partial`です。`field_mode`は選択地点PWA/syncまで、`outcome_monitoring`はdomain/schema/APIまで実装済みで、自治体現地運用と実施施策＋後年度観測が未登録のため`partial`です。

## First-class versions

registryは次を独立entityとして保持します。

- `city`
- `dataset`
- `dataset_version`
- `ingestion_run`（既存CityGML schema）
- `analysis_run`
- `network_version`（既存road schema）
- `scenario_run`（scenario workspace schema）

現行registryは2都市、12 datasets、12 dataset versions、13 verified analysis runs、34 city capability recordsです。各analysis runは入力`dataset_version_id`群、config hash、output artifactとSHA-256を明示します。APIやloaderは「最新」を暗黙選択せず、呼出側がversion UUIDを指定します。

```bash
python -m analysis.scripts.build_platform_registry
python -m analysis.scripts.load_platform_registry_postgis \
  --database-url "$CITYGAP_DATABASE_URL"
```

静的registryとPostGIS loader contractの双方をテストし、CIのPostGIS fixtureでmigration/transactionを検証します。全量2都市データを自治体承認DBへ投入したこととは区別します。

## API

- `GET /registry/cities`: capability matrixとevidence
- `GET /registry/cities/{city_id}/datasets`: 明示dataset versions
- `GET /registry/cities/{city_id}/analysis-runs`: 入力versionと成果物hash

静的Competition Demoには同じ小容量registryを配布しますが、藤沢の未実装dataや架空scenarioを追加しません。
