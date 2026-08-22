# Data sources

調査・取得日: 2026-08-22。公式配布ファイルを取得し、checksum、schema、CRS、実record数を確認しました。rawファイルはGit管理外です。人口・交通・医療・PLATEAU関連データは `python -m analysis.scripts.download_real_data` で再取得できます。

## Source inventory

| Provider / dataset | Year / CRS | Official download / local area | Size | Records (source → product) | CITY GAP use and limitations |
|---|---|---|---:|---:|---|
| 総務省統計局 e-Stat「令和2年国勢調査 JGD2011 500mメッシュ 5歳階級別人口」`T001192` | 2020-10-01 / JGD2011 | [京都府CSV](https://www.e-stat.go.jp/gis/statmap-search/data?statsId=T001192&code=26&downloadType=2)、[定義書](https://www.e-stat.go.jp/help/data-definition-information/downloaddata/T001192.pdf) / `data/raw/population/` | 256,260 B ZIP; 1,079,925 B TXT | 6,326 → 舞鶴市交差495 | 総人口、65歳以上人口、高齢化率。秘匿・合算影響なし286件だけをpercentileに使用 |
| 国土交通省 国土数値情報「バス停留所 P11 京都府」 | 2022 / EPSG:6668 | [公式ページ](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P11-2022.html)、[ZIP](https://nlftp.mlit.go.jp/ksj/gml/data/P11/P11-22/P11-22_26_SHP.zip) / `data/raw/transport/` | 686,613 B ZIP; 7,838,530 B GeoJSON | 4,685 → 舞鶴市151 | 最寄りバス停。頻度、デマンド、高速・長距離、施設送迎、位置不明停留所は原則対象外 |
| 国土交通省 国土数値情報「医療機関 P04 京都府」 | 2020-07 / EPSG:6668 | [公式ページ](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P04-2020.html)、[ZIP](https://nlftp.mlit.go.jp/ksj/gml/data/P04/P04-20/P04-20_26_GML.zip) / `data/raw/medical/` | 730,337 B ZIP; 1,512,905 B GeoJSON | 3,960 → 舞鶴市105 | 病院8＋診療所63を距離に使用。歯科34は件数のみ。現在の開廃・一般利用可否を保証しない |
| Project PLATEAU「舞鶴市2025 関連データセット」 | 2025 / Web GeoJSONはEPSG:4326として解釈 | [CKAN](https://www.geospatial.jp/ckan/dataset/plateau-26202-maizuru-shi-2025)、[ZIP](https://assets.cms.plateau.reearth.io/assets/84/e288ba-d335-4537-86d4-23ddbcbc7413/26202_maizuru-shi_2025_related.zip) / `data/raw/plateau_related/` | 158,376 B ZIP | stations 9 → 7 unique、boundary 1 | 駅距離と舞鶴市行政界。東舞鶴・西舞鶴の路線別重複を名称＋位置で除外 |
| Project PLATEAU「3D都市モデル（舞鶴市）2025年度」3D Tiles/MVT | 2025 / 3D Tiles 1.0 | [CKAN](https://www.geospatial.jp/ckan/dataset/plateau-26202-maizuru-shi-2025)、[公式ZIP](https://assets.cms.plateau.reearth.io/assets/55/2c1991-f75e-4bf8-9108-531c27952a2b/26202_maizuru-shi_city_2025_3dtiles_mvt_1_op.zip) / `data/raw/plateau_3d/` | 160,582,905 B ZIP | 公式配布内44,640 unique buildings → Web subset 856、Deep Dive mesh内296 | Cesium 3D表示、用途・高さ・階数・面積・LOD、coverage QA。Top 10内は0棟 |
| Project PLATEAU 舞鶴市2025 CityGML | 2025 / CityGML 2.0・標高付きJGD2011 | [CKAN](https://www.geospatial.jp/ckan/dataset/plateau-26202-maizuru-shi-2025) / `data/raw/plateau_citygml/` | 914,222,089 B ZIP | 道路16,778面 → Deep Dive 135面、DEM TIN 20,965三角形集計 | 道路面上の配置anchor、標高・局所勾配文脈。道路network距離には未使用 |

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

用途、`bldg:measuredHeight`、`bldg:storeysAboveGround`、`bldg:storeysBelowGround`、footprint area、total floor area、`_lod` はbatch tableの実値だけを使います。missing/sentinelに架空値を設定しません。

## Terms and attribution

- e-Stat: [統計GIS利用規約](https://www.e-stat.go.jp/gis-terms)。政府標準利用規約2.0 / CC BY 4.0互換。e-Stat政府統計を加工して作成。
- 国土数値情報: [利用約款](https://nlftp.mlit.go.jp/ksj/other/agreement_01.html)。国土数値情報 P11/P04を加工して作成。
- Project PLATEAU: [PLATEAU Site Policy](https://www.mlit.go.jp/plateau/site-policy/)に従い、舞鶴市2025関連データ・3D都市モデルを加工して使用。
- 背景地図: Cesium同梱のNatural Earth II静的tile（外部地図APIへの実行時依存なし）。

ソフトウェアlicenseとデータlicenseは別です。repositoryのコードはMIT Licenseですが、加工・同梱データには上記各配布元の条件が適用されます。
