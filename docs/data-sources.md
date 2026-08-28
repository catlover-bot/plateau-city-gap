# Data sources

初回調査・取得日: 2026-08-22、Urban Futures追加検証: 2026-08-27、地理空間・レジリエンス追加検証: 2026-08-28。公式配布ファイルを取得し、checksum、schema、CRS、実record数を確認しました。rawファイルはGit管理外です。人口・交通・医療・PLATEAU関連データは `python -m analysis.scripts.download_real_data` で再取得できます。

## Source inventory

| Provider / dataset | Year / CRS | Official download / local area | Size | Records (source → product) | CITY GAP use and limitations |
|---|---|---|---:|---:|---|
| 総務省統計局 e-Stat「令和2年国勢調査 JGD2011 500mメッシュ 5歳階級別人口」`T001192` | 2020-10-01 / JGD2011 | [京都府CSV](https://www.e-stat.go.jp/gis/statmap-search/data?statsId=T001192&code=26&downloadType=2)、[定義書](https://www.e-stat.go.jp/help/data-definition-information/downloaddata/T001192.pdf) / `data/raw/population/` | 256,260 B ZIP; 1,079,925 B TXT | 6,326 → 舞鶴市交差495 | 総人口、65歳以上人口、高齢化率。秘匿・合算影響なし286件だけをpercentileに使用 |
| 国土交通省 国土数値情報「バス停留所 P11 京都府」 | 2022 / EPSG:6668 | [公式ページ](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P11-2022.html)、[ZIP](https://nlftp.mlit.go.jp/ksj/gml/data/P11/P11-22/P11-22_26_SHP.zip) / `data/raw/transport/` | 686,613 B ZIP; 7,838,530 B GeoJSON | 4,685 → 舞鶴市151 | 最寄りバス停。頻度、デマンド、高速・長距離、施設送迎、位置不明停留所は原則対象外 |
| 国土交通省 国土数値情報「医療機関 P04 京都府」 | 2020-07 / EPSG:6668 | [公式ページ](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P04-2020.html)、[ZIP](https://nlftp.mlit.go.jp/ksj/gml/data/P04/P04-20/P04-20_26_GML.zip) / `data/raw/medical/` | 730,337 B ZIP; 1,512,905 B GeoJSON | 3,960 → 舞鶴市105 | 病院8＋診療所63を距離に使用。歯科34は件数のみ。現在の開廃・一般利用可否を保証しない |
| Project PLATEAU「舞鶴市2025 関連データセット」 | 2025 / Web GeoJSONはEPSG:4326として解釈 | [CKAN](https://www.geospatial.jp/ckan/dataset/plateau-26202-maizuru-shi-2025)、[ZIP](https://assets.cms.plateau.reearth.io/assets/84/e288ba-d335-4537-86d4-23ddbcbc7413/26202_maizuru-shi_2025_related.zip) / `data/raw/plateau_related/` | 158,376 B ZIP | stations 9 → 7 unique、boundary 1 | 駅距離と舞鶴市行政界。東舞鶴・西舞鶴の路線別重複を名称＋位置で除外 |
| Project PLATEAU「3D都市モデル（舞鶴市）2025年度」3D Tiles/MVT | 2025 / 3D Tiles 1.0 | [CKAN](https://www.geospatial.jp/ckan/dataset/plateau-26202-maizuru-shi-2025)、[公式ZIP](https://assets.cms.plateau.reearth.io/assets/55/2c1991-f75e-4bf8-9108-531c27952a2b/26202_maizuru-shi_city_2025_3dtiles_mvt_1_op.zip) / `data/raw/plateau_3d/` | 160,582,905 B ZIP | 公式配布内44,640 unique buildings → Web subset 856、Deep Dive mesh内296 | Cesium 3D表示、用途・高さ・階数・面積・LOD、coverage QA。Top 10内は0棟 |
| Project PLATEAU 舞鶴市2025 CityGML | 2025 / CityGML 2.0・標高付きJGD2011 | [CKAN](https://www.geospatial.jp/ckan/dataset/plateau-26202-maizuru-shi-2025) / `data/raw/plateau_citygml/` | 914,222,089 B ZIP | 8テーマ97,140地物。建物44,640、道路15,684、DEM 23、土地利用31,067、都市計画394、土砂4,643、洪水666、津波23 | 建物人口、実験道路network、DEM、公式コード表付き土地利用・計画・災害文脈。歩行networkとは扱わない |
| 国土交通省「250mメッシュ別将来推計人口（R6国政局推計）」 | 2020基準、2025–2070試算 / EPSG:6668 | [公式ページ](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-mesh250r6.html) / `data/raw/open_data/` | 京都16,805,431 B、神奈川30,757,702 B | 15,174 → 舞鶴1,053、20,880 → 藤沢963 | 公式試算。秘匿前・公開用集約値と合算先を分離し、市外合算がある公開用市合計は利用不可 |
| e-Stat「令和3年経済センサス‐活動調査 500mメッシュ」`T001162` | 2021-06-01 / JGD2011 | [公式検索](https://www.e-stat.go.jp/gis/statmap-search?aggregateUnit=H&datum=2011&serveyId=H002005112021&statsId=T001162&toukeiCode=00200553&toukeiYear=2021&type=1)、[定義書](https://www.e-stat.go.jp/help/data-definition-information/downloaddata/T001162.pdf) / `data/raw/open_data/` | 京都133,517 B、神奈川249,155 B | 4,828 → 舞鶴287、6,346 → 藤沢326 | 46の事業所・従業者指標。活動文脈のみ。未掲載mesh・秘匿値を0へ補完しない |
| 防災科研 J-SHIS V4 表層地盤250m | 2020 model / EPSG:4612 | [公式仕様](https://www.j-shis.bosai.go.jp/api-sstruct-meshinfo) / `data/raw/open_data/` | 5335: 166,684 B、5339: 871,840 B | 44,747 → 舞鶴1,980、93,474 → 藤沢1,084 | 微地形、AVS、ARVのmodel文脈。海域0をground値にせず、地震確率・riskを生成しない |
| 警察庁 交通事故統計2024年本票 | annual file 2024 / world-geodetic DMS | [公式年次ページ](https://www.npa.go.jp/publications/statistics/koutsuu/opendata/2024/opendata_2024.html) / `data/raw/open_data/` | CSV 62,252,803 B | 290,895 → 舞鶴59、藤沢982 | 人身・死亡事故履歴。物損のみを含まず、発生時刻と年次fileを分離。予測ではない |

## Checksums and lineage

3D Tiles/MVT公式ZIPのSHA-256は次の通りです。

```text
15cf5e12b507b89e2b86fe0c2968a22e8d770ea36cb8c64cc7e8db578109f2d9
```

分析入力およびWeb outputのbyte数とSHA-256は `frontend/public/data/manifest.json` に記録します。公開assetは次の実分析成果物を参照し、ブラウザ側へ値を再入力しません。

- `analysis/outputs/real/maizuru_city_gap.geojson`
- `analysis/outputs/real/maizuru_city_gap_top10.csv`
- `analysis/outputs/real/maizuru_summary.json`
- `analysis/outputs/real/maizuru_plateau_building_inspection.json`
- `analysis/outputs/real/fujisawa_summary.json`
- `analysis/outputs/real/final_audit.json`

約914MBのCityGML全体はWeb配信せず、道路135面のGeoJSONと集計JSONだけを配信します。公式3D Tiles ZIPと展開物もraw領域に保ち、Gitへcommitしません。

3D建物を含む完全再生成は、repository rootで次の順に実行します。

```bash
python -m analysis.scripts.download_plateau_3d
python -m analysis.scripts.inspect_plateau_buildings
python -m analysis.scripts.build_plateau_web_subset
SOURCE_DATE_EPOCH=1787392800 python -m analysis.scripts.build_web_assets
```

inspectionはLOD1/LOD2の全854 b3dmについてbatch metadataの代表点とbuilding bounding boxを検査します。CityGML filenameによるcoverage判定は主張・使用していません。

## e-Stat schema and disclosure quality

CSVはCP932、69列、9桁の `KEY_CODE` が500m mesh codeで全件一意です。総人口は `T001192001`、65歳以上人口は `T001192043 + 046 + 049 + 052 + 055 + 058 + 061`。京都府総人口の実測合計2,578,087人は令和2年国勢調査値と整合しました。

| `HTKSYORI` | Meaning | Kyoto | Maizuru intersection | Product handling |
|---:|---|---:|---:|---|
| 0 | 秘匿・合算影響なし | 3,978 | 286 | percentile比較に使用 |
| 1 | 合算先（`GASSAN`に元mesh） | 1,000 | 90 | 表示するが比較から除外 |
| 2 | 秘匿元（`HTKSAKI`に先mesh） | 1,348 | 119 | 表示するが比較から除外 |

`HTKSYORI=2` の `*` はゼロではありません。flag 1の年齢列は合算group値ですが、総人口は当該cell単独値なので高齢化率を計算できません。該当行の分析用 `elderly_population` / `elderly_ratio` は欠損とし、元の報告値を `reported_elderly_population` に分離しました。

## Spatial filtering and attribution

PLATEAU `border` は1 MultiLineString（74閉ring）のためpolygon化し、全mesh/pointを実際の行政界との `intersects` で抽出しました。bboxやmesh接頭辞では判定していません。P04の舞鶴市105件は所在地文字列による抽出結果とも一致しました。

PLATEAU駅のraw 9件は路線単位で東舞鶴駅・西舞鶴駅が重複します。距離への重複影響はありませんが、名称＋座標で7地点へdeduplicateして表示・集計します。

P04の分類1/2は一般利用可否を保証しません。`医務室`、`健康管理室`、`事業所診療所`等の名称規則で舞鶴6件・藤沢13件を`uncertain_access`としてflagし、Primary sourceからは削除せず除外感度を別計算します。舞鶴Rank 1の隅山医院は[舞鶴市の在宅医療機関資料](https://www.city.maizuru.kyoto.jp/kenkou/cmsfiles/contents/0000000/775/zaitakuryouyou.pdf)、藤沢Rank 1の山口クリニックは[藤沢市の在宅療養支援診療所資料](https://www.city.fujisawa.kanagawa.jp/iryou/documents/202406-iryoukikan-ichiran.pdf)との名称照合を記録しました。いずれも現在の外来条件は受診時確認が必要です。

## PLATEAU building inspection

LOD2配布コンテナには427 b3dm、46,986 batch instanceがありました。`gml_id` のtile間重複を除くと44,640棟です。実際の `_lod=2` は1,504棟（3.369%）、LOD1 fallbackは43,136棟です。Top 10の全500m polygonについて建物代表点の包含とbuilding bounding boxの交差がともに0でした。

これは現地に建物が存在しないという意味ではありません。今回の公式2025建物モデルがその範囲を収録していないことを意味します。geometryや属性を推定して補いません。

静的配信用には、PLATEAU-coveredの全市23位 `533513314` と交差するleaf content regionを持つ3 b3dmを選択しました。

| Subset property | Verified value |
|---|---:|
| b3dm payload | 4,313,608 B |
| subset buildings | 856 |
| Deep Dive mesh内building representatives | 296 |
| actual LOD1 | 856 |
| actual LOD2 | 0 |
| Deep Dive road LOD1 surfaces | 135 |
| DEM TIN triangles summarized | 20,965 |

道路CityGMLにはLOD1外周15,684、LOD2交通面1,090、内周4があります。`16,778`という旧値は
全`posList`を数えたもので、LOD1面数ではありません。配置候補とnetwork nodeはLOD1外周だけを
使用し、内周をholeとして保持します。全市道路node標高処理ではDEM TIN 16,310,504三角形を走査し、
15,684 nodeすべてを補間できました。Deep Diveの20,965は別途500m mesh内の局所地形要約件数です。

用途、`bldg:measuredHeight`、`bldg:storeysAboveGround`、`bldg:storeysBelowGround`、footprint area、total floor area、`_lod` はbatch tableの実値だけを使います。missing/sentinelに架空値を設定しません。

## Terms and attribution

- e-Stat: [統計GIS利用規約](https://www.e-stat.go.jp/gis-terms)。政府標準利用規約2.0 / CC BY 4.0互換。e-Stat政府統計を加工して作成。
- 国土数値情報: [利用約款](https://nlftp.mlit.go.jp/ksj/other/agreement_01.html)。国土数値情報 P11/P04を加工して作成。
- Project PLATEAU: [PLATEAU Site Policy](https://www.mlit.go.jp/plateau/site-policy/)に従い、舞鶴市2025関連データ・3D都市モデルを加工して使用。
- 背景地図: Cesium同梱のNatural Earth II静的tile（外部地図APIへの実行時依存なし）。

ソフトウェアlicenseとデータlicenseは別です。repositoryのコードはMIT Licenseですが、加工・同梱データには上記各配布元の条件が適用されます。

## Fujisawa validation sources

| Source | Official URL | Year | Source CRS | Source / city records | Use |
|---|---|---:|---|---:|---|
| e-Stat `T001192` Kanagawa | <https://www.e-stat.go.jp/gis/statmap-search/data?statsId=T001192&code=14&downloadType=2> | 2020 | JGD2011 | 6,250 / 327 mesh | population, 65+ |
| MLIT P11 Kanagawa | <https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P11-2022.html> | 2022 | EPSG:6668 | 10,706 / 446 | bus distance |
| MLIT P04 Kanagawa | <https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P04-2020.html> | 2020 | EPSG:6668 | 12,364 / 718（primary 436） | medical distance |
| PLATEAU Fujisawa related v5 | <https://www.geospatial.jp/ckan/dataset/plateau-14205-fujisawa-shi-2025> | 2025 | EPSG:4326 | boundary 1, station raw 21 / 20 points | city extent, station distance |

取得ZIPのSHA-256は人口 `855de51c…75de`、P11 `f7dc1805…65f6`、P04 `505b6303…eb69`、PLATEAU関連 `992a2310…ad19` です。完全値は `analysis/scripts/download_real_data.py` に固定しています。PLATEAU藤沢2025 CityGMLも共通pipelineへ投入し、全11テーマ399,271地物、建物169,856、道路53,658をinventory/実分析しました。3D Tiles/MVTは公開demoへ使用済みとは扱いません。

## Official future population and shelters

| Source | Official URL | Published/target years | Verified SHA-256 | Use and boundary |
|---|---|---|---|---|
| IPSS Regional Population Projections 2023 | <https://www.ipss.go.jp/pp-shicyoson/j/shicyoson23/t-page.asp> | 2020–2050, 5-year | `dc503ef87559db7f45d6baa754c8920de0be0d6073d00cef84705219ea9b2b92` | Maizuru/Fujisawa official totals and 65+; fixed-service spatial allocation, not prediction |
| Fujisawa future population projection | <https://www.city.fujisawa.kanagawa.jp/kikaku/shise/kekaku/kakushu/kako/jinkosuikei.html> | 2020–2050, 5-year | `f21a46d2eef70c01b7a3d43239cddff4a954c18866a9eb7d094e2376641608c4` | second official Fujisawa scenario; no interpolation to unpublished years |
| PLATEAU Maizuru designated shelters | <https://www.geospatial.jp/ckan/dataset/plateau-26202-maizuru-shi-2025> | 2025 | `faa9e4523f1f268cc833d0a8a78da841d6b6e37be0525bb315a3683750e8bcdd` | 126 facilities, published capacity retained; network reachability only |
| PLATEAU Fujisawa designated shelters | <https://www.geospatial.jp/ckan/dataset/plateau-14205-fujisawa-shi-2025> | 2025 | `d06294e9a72739a574a21b0b1fd12086d03b279043342f4c86f80dd6b60a6124` | 81 facilities, published capacity/hazard applicability retained |

The adapters reject unverified sources and do not fill missing capacity, targets, service changes
or costs. Shelter snapping is recorded as model QA. Maizuru’s large snap distances require
municipal review before operational use. The result is not evacuation or crowd simulation.
