# Multi-city capability and dataset registry

CITY GAPは都市ごとの実装有無を画面やコードから推測しません。`platform_registry.json` がcity、dataset、dataset version、analysis run、capabilityの正本です。capabilityは必ず `available / partial / unavailable` のいずれかで、`available` と `partial` には実成果物のSHA-256 evidenceが必要です。

## Current capability matrix

| capability | 舞鶴市 | 藤沢市 |
|---|---|---|
| screening | available | available |
| building detail | available | unavailable |
| road network | partial | unavailable |
| terrain | partial | unavailable |
| land use | available | unavailable |
| urban planning | available | unavailable |
| hazard | available | unavailable |
| GTFS | unavailable | unavailable |
| scenario | available | unavailable |

舞鶴市の道路networkは実CityGMLから生成済みですが、検証済み歩行者networkではないため`partial`です。terrainもDEM endpoint観測はありますが、歩行energyやrouting penaltyへ変換していないため`partial`です。

藤沢市は実データの500m screeningだけを`available`とします。PLATEAU dataset metadataに建物・道路・災害themeが記載されていても、このplatformで実データを取得・計算・検証していない機能をavailableにはしません。P11バス停pointはGTFSではなく、GTFS capabilityの根拠にも使いません。

## First-class versions

registryは次を独立entityとして保持します。

- `city`
- `dataset`
- `dataset_version`
- `ingestion_run`（既存CityGML schema）
- `analysis_run`
- `network_version`（既存road schema）
- `scenario_run`（scenario workspace schema）

現行registryは2都市、12 datasets、12 dataset versions、7 verified analysis runs、18 city capability recordsです。各analysis runは入力`dataset_version_id`群、config hash、output artifactとSHA-256を明示します。APIやloaderは「最新」を暗黙選択せず、呼出側がversion UUIDを指定します。

```bash
python -m analysis.scripts.build_platform_registry
python -m analysis.scripts.load_platform_registry_postgis \
  --database-url "$CITYGAP_DATABASE_URL"
```

この環境ではJSON生成とmigration/loader contractを検証し、PostGIS loaderは実行していません。

## API

- `GET /registry/cities`: capability matrixとevidence
- `GET /registry/cities/{city_id}/datasets`: 明示dataset versions
- `GET /registry/cities/{city_id}/analysis-runs`: 入力versionと成果物hash

静的Competition Demoには同じ小容量registryを配布しますが、藤沢の未実装dataや架空scenarioを追加しません。
