# Data sources

調査日: 2026-08-22。`確認済み` はURL、メタデータ、または実ファイルをこの作業で確認したものだけを指す。

| データ名 | 提供元 | URL | 対象年 | 空間解像度 | 形式/API | 使用予定の属性 | ライセンス/利用条件 | 取得状況 | CITY GAPでの用途 |
|---|---|---|---:|---|---|---|---|---|---|
| 舞鶴市 CityGML v5 | Project PLATEAU / G空間情報センター | [データセット](https://www.geospatial.jp/ckan/dataset/plateau-26202-maizuru-shi-2025) | 2025 | 建物・道路等 | ZIP / CityGML、914 MB（目録記載） | `bldg`, `tran`, `luse`候補。属性未検証 | PLATEAU Site Policy（CKANで確認） | メタデータ確認済み、未取得 | 建物単位分析、道路・用途の検証 |
| 舞鶴市 3D Tiles/MVT v5 | 同上 | [データセット](https://www.geospatial.jp/ckan/dataset/plateau-26202-maizuru-shi-2025) | 2025 | 地物単位 | ZIP、161 MB（目録記載） | 建物、道路、土地利用等 | 同上 | メタデータ確認済み、未取得 | 将来のCesium表示。分析適合性未検証 |
| 舞鶴市 関連データセット | 同上 | [ZIP](https://assets.cms.plateau.reearth.io/assets/84/e288ba-d335-4537-86d4-23ddbcbc7413/26202_maizuru-shi_2025_related.zip) | 2025配布 | 点・線・面 | ZIP / GeoJSON、158,376 bytes | 駅名、路線名、運営会社、鉄道区分、高さ | 同上 | **取得・展開・内容確認済み** | 駅への直線距離。駅9レコード（路線別重複を含む） |
| 国勢調査 総人口・65歳以上人口 | 総務省統計局 e-Stat | [統計GIS](https://www.e-stat.go.jp/gis/statmap-search?page=1&type=1&toukeiCode=00200521) | 候補: 2020 | 候補: 500mメッシュ/小地域 | 未確定 | 総人口、65歳以上人口 | 取得時に確認予定 | 候補ページのみ確認、未取得 | 人口、高齢者数、高齢化率 |
| バス停留所 | 国土交通省 国土数値情報 | [トップ](https://nlftp.mlit.go.jp/ksj/) | 未確認 | 点 | 未確認 | 停留所名、事業者等 | 取得時に確認予定 | 候補のみ、未取得 | 最寄りバス停距離 |
| 医療機関 | 国土数値情報または京都府公式データ | [国土数値情報](https://nlftp.mlit.go.jp/ksj/) | 未確認 | 点 | 未確認 | 種別、名称等 | 取得時に確認予定 | 候補のみ、未取得 | 最寄り医療施設距離 |

## 確認したPLATEAUファイル

CKAN APIの目録にCityGML 914 MB、3D Tiles/MVT 161 MB、関連データ158 kBと記載。大容量2件は取得せず、関連データだけ取得した。内容は `shelter`, `park`, `landmark`, `station`, `railway`, `emergency_route`, `border` の7 GeoJSONで、バス停・医療施設は含まれない。

## 取得ブロッカー

e-Stat統計GISページは確認したが、自動取得では対象ファイルを確定できなかった。未確認URLを推測せず人口は未取得。次は統計GIS UIで2020年国勢調査の500mメッシュ（総人口・65歳以上）を選び、URL、項目定義、利用条件を確認する。
