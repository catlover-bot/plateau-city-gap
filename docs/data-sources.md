# Data sources

調査・取得日: 2026-08-22。4ソースとも公式配布ファイルを取得し、チェックサム、属性、CRS、実レコード数を確認した。rawファイルはGit管理外で、`python -m analysis.scripts.download_real_data` により再取得できる。

| Provider / dataset | Year / CRS | Official download / local file | Size | Records (source → Maizuru) | License / use | CITY GAP use and limitations |
|---|---|---|---:|---:|---|---|
| 総務省統計局 e-Stat「令和2年国勢調査 JGD2011 500mメッシュ 5歳階級別人口」`T001192` | 2020-10-01 / JGD2011 | [京都府CSV](https://www.e-stat.go.jp/gis/statmap-search/data?statsId=T001192&code=26&downloadType=2) / `tblT001192H26.zip`、[定義書](https://www.e-stat.go.jp/help/data-definition-information/downloaddata/T001192.pdf) | 256,260 B ZIP; 1,079,925 B TXT | 6,326 → 495 intersection meshes | [統計GIS利用規約](https://www.e-stat.go.jp/gis-terms)、政府標準利用規約2.0/CC BY 4.0互換。加工を明記 | 総人口、65歳以上人口、高齢化率。秘匿・合算影響なし286件のみPrimary rankに使用 |
| 国土交通省 国土数値情報「バス停留所 P11 京都府」 | 2022 / EPSG:6668 | [公式ページ](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P11-2022.html)、[ZIP](https://nlftp.mlit.go.jp/ksj/gml/data/P11/P11-22/P11-22_26_SHP.zip) / `P11-22_26_SHP.zip` | 686,613 B ZIP; 7,838,530 B GeoJSON | 4,685 → 151 stops | CC BY 4.0。国土数値情報を加工して作成 | `P11_001`名称、`P11_002`事業者。デマンド、高速・長距離、施設送迎、位置不明停留所は原則対象外 |
| 国土交通省 国土数値情報「医療機関 P04 京都府」 | 2020-07 / EPSG:6668 | [公式ページ](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P04-2020.html)、[ZIP](https://nlftp.mlit.go.jp/ksj/gml/data/P04/P04-20/P04-20_26_GML.zip) / `P04-20_26_GML.zip` | 730,337 B ZIP; 1,512,905 B GeoJSON | 3,960 → 105 facilities | [利用規約](https://nlftp.mlit.go.jp/ksj/other/agreement_01.html)、CC BY 4.0相当。加工を明記 | 病院8、診療所63をPrimary距離に使用。歯科34は件数のみ。2020時点で現在の開廃・一般利用可否を保証しない |
| Project PLATEAU「舞鶴市2025 関連データセット」 | 2025配布 / GeoJSON `crs` memberなし、RFC 7946としてEPSG:4326解釈 | [CKAN](https://www.geospatial.jp/ckan/dataset/plateau-26202-maizuru-shi-2025)、[ZIP](https://assets.cms.plateau.reearth.io/assets/84/e288ba-d335-4537-86d4-23ddbcbc7413/26202_maizuru-shi_2025_related.zip) | 158,376 B ZIP | stations 9 → 9 raw; 7 unique locations/names | PLATEAU Site Policy | 駅距離と舞鶴市行政界。路線別に東舞鶴・西舞鶴が重複するため名称＋位置で7件へ重複排除 |

## e-Stat schema and disclosure quality

CSVはCP932、69列、9桁の `KEY_CODE` が500m mesh codeで全件一意。総人口は `T001192001`、65歳以上は `T001192043 + 046 + 049 + 052 + 055 + 058 + 061`。京都府総人口の実測合計2,578,087人は令和2年国勢調査値と整合した。

| `HTKSYORI` | Meaning | Kyoto | Maizuru intersection | Primary handling |
|---:|---|---:|---:|---|
| 0 | 秘匿・合算影響なし | 3,978 | 286 | 使用 |
| 1 | 合算先（`GASSAN`に元mesh） | 1,000 | 90 | 保持するが除外 |
| 2 | 秘匿元（`HTKSAKI`に先mesh） | 1,348 | 119 | 保持するが除外 |

`HTKSYORI=2` の `*` はゼロではない。flag 1の年齢列は合算グループ値だが、総人口は当該セル単独値なので、そのまま高齢化率を計算できない。該当行の分析用 `elderly_population` / `elderly_ratio` は欠損とし、元の報告値を `reported_elderly_population` に分離した。

## Spatial filtering and attribution

PLATEAU `border` は1 MultiLineString（74閉リング）のため面化し、全mesh/pointを実際の行政界との `intersects` で抽出した。bboxやmesh接頭辞では判定していない。P04の舞鶴市105件は所在地文字列による抽出結果とも完全一致した。加工物には「e-Stat政府統計を加工」「国土数値情報（P11/P04）を加工」「Project PLATEAU関連データを加工」と表示する。

914 MBのCityGMLと161 MBの3D Tiles/MVTは今回も取得していない。今回の実分析成立後にTop 5 meshだけを対象として建物属性を検証する。
