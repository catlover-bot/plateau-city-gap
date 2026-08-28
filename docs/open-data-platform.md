# Municipal Open Data Platform

CITY GAPのオープンデータ基盤は、公式カタログの「発見」と、分析入力としての
「採用」を分離する。カタログに存在するだけでは品質、利用許諾、時点整合、分析適合を
保証しない。Data Managerが検証結果を確認し、既存のDataset lifecycleを通して
`analysis_ready` / `promoted` にした版だけをUrban Stateと分析が参照する。

## 公式ソースレジストリ

2026-08-29時点で、次の入口を版付きで登録している。

| source key | 公式提供主体・入口 | adapter | 初期license policy | 範囲 |
|---|---|---|---|---|
| `digital-agency-municipal-standard-ods` | [デジタル庁 自治体標準オープンデータセット](https://www.digital.go.jp/resources/open_data/municipal-standard-data-set-test) | `municipal-standard-ods@2026-08` | unknown（resourceごとの確認が必要） | 全国schema |
| `bodik-maizuru` | [舞鶴市 / BODIK](https://data.bodik.jp/organization/262021) | `ckan-v3@1` | CC BY 4.0 | 舞鶴市 |
| `fujisawa-open-data-library` | [藤沢市オープンデータライブラリ](https://www.city.fujisawa.kanagawa.jp/kyoso/shise/kekaku/kakushu/datalibrary.html) | `official-static-catalog@1` | CC BY 4.0 | 藤沢市 |
| `mhlw-medical-information-network` | [厚生労働省 医療情報ネット](https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/newpage_43373.html) | `mhlw-medical@2026-06` | PDL 1.0 | 全国 |
| `mhlw-care-service` | [厚生労働省 介護サービス情報公表システム](https://www.mhlw.go.jp/stf/kaigo-kouhyou_opendata.html) | `mhlw-care@2026-06` | CC BY 4.0 | 全国 |
| `mlit-future-population-250m-r6` | [国土交通省 250mメッシュ別将来推計人口（R6国政局推計）](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-mesh250r6.html) | `mlit-future-population-250m@2024` | CC BY 4.0 | 全国・都道府県別配布 |
| `estat-economic-census-2021-500m` | [e-Stat 令和3年経済センサス 500mメッシュ](https://www.e-stat.go.jp/gis/statmap-search?aggregateUnit=H&datum=2011&serveyId=H002005112021&statsId=T001162&toukeiCode=00200553&toukeiYear=2021&type=1) | `estat-economic-census-500m@2021` | 政府標準利用規約2.0 | 全国・都道府県別配布 |
| `gsi-fundamental-geospatial-data` | [国土地理院 基盤地図情報](https://service.gsi.go.jp/kiban/app/help/) | `gsi-foundation-map@5.3` | 認証・測量法review | 全国・要認証 |
| `jshis-surface-ground-v4` | [J-SHIS 250m表層地盤](https://www.j-shis.bosai.go.jp/api-sstruct-meshinfo) | `jshis-surface-ground-v4@2020` | J-SHIS利用規約 | 全国・1次mesh別配布 |
| `npa-traffic-accident-2024` | [警察庁 交通事故統計オープンデータ](https://www.npa.go.jp/publications/statistics/koutsuu/opendata/2024/opendata_2024.html) | `npa-traffic-accident@2024` | PDL 1.0 | 全国年次本票 |
| `mlit-pedestrian-network-catalog` | [国交省 歩行空間ネットワーク](https://ckan.hokonavi.go.jp/dataset/) | `mlit-pedestrian-ckan@2024` | PDL 1.0 | 公開範囲のみ |
| `xroad-open-traffic-api` | [xROAD/JARTIC道路交通情報API](https://www.jartic-open-traffic.org/) | `xroad-traffic-api@2026-01` | 個別API規約 | rolling参照値 |
| `mhlw-kayoi-no-ba` | [厚生労働省 通いの場のオープンデータ](https://www.mhlw.go.jp/stf/kayoinoba_opendata_00002.html) | `mhlw-kayoi-no-ba@2026-06` | 利用規約review | 全国公開、対象2市は行なし |
| `wam-disability-welfare-open-data` | [WAM NET 障害福祉オープンデータ](https://www.wam.go.jp/content/wamnet/pcpub/top/sfkopendata/) | `wam-disability-welfare@2026-03` | resource条件review | 全国catalog、未取込 |
| `mlit-station-passenger-count-s12` | [国土数値情報 駅別乗降客数S12](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-S12-v3_1.html) | `mlit-station-passenger-s12@2021` | 国土数値情報利用約款review | 全国、2021観測 |
| `mlit-person-trip-study-catalog` | [国土交通省 パーソントリップ調査](https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000031.html) | `mlit-person-trip-catalog@2026-03` | 公開単位・survey条件review | 実施都市圏catalog |

コード上のSingle Source of Truthは
`backend/citygap_platform/open_data/registry.py`、永続化の初期値はforward-only migration
`018_open_data_foundation.sql`である。公式static catalog拡張は`019`、人口・経済は`020`、
地理空間・レジリエンスは`021`、6つの自治体open-data分析と3段階dataset requirementは`022`で
forward-onlyに追加した。将来の定義変更では既存migrationを書き換えず、新しいadapter IDと
migrationを追加する。

## Adapter contract

各adapterは、提供主体、dataset family、公式URL、発見・取得方法、schema version、
license model、形式、空間・時間粒度、CRS方針、版検出信号、品質規則、提供capabilityを宣言する。
実装は共通の`OpenDataAdapter` protocolに従い、次の境界を持つ。

1. `discover`: 自治体コードを公式カタログへ対応させ、候補resourceと原metadataを返す。
2. `download`: 上限付きで取得し、content-addressed raw objectのSHA-256 receiptを返す。
3. `inspect_schema`: encoding、列、CRS、件数、品質gateを記録する。
4. `normalize`: 検証済みrawから正規化行を作る。曖昧な列や座標は推測せずquarantineする。

## Data flow and lineage

```text
official catalog
  -> discovered source/resource metadata
  -> immutable raw blob (SHA-256)
  -> schema and licence quality gates
  -> normalized rows
  -> canonical records
  -> versioned spatial links (city / mesh / PLATEAU / road / facility)
  -> promoted DatasetVersion + Urban State
  -> analysis -> Finding -> Investigation -> Evidence
```

Canonical recordは必ず、tenant、city、DatasetVersion、resource、transformation run、
source row locator、adapter/canonical versionへ逆参照できる。公式値は上書きせず、自治体補正は
reviewed local overrideとして別層に保存し、新しい公式版とのreconciliationを記録する。

## Coverage and truthful absence

都市×dataset familyごとに`available`、`partial`、`unavailable`、`unknown`、
`requires_review`を保存する。`unavailable`と`requires_review`には、未公開、対象外、
license不許可、未対応schema、取得失敗、認証必須、時点不一致、未検証のいずれかを必須とする。
利用できないデータを0件や推定値へ置き換えない。分析はversion付きrequirementsを満たす場合だけ
有効化する。

実データを既存Urban Stateへ接続する6分析、`BASE` / `ENHANCED`降格、レビュー候補、混在時点、
Contribution/lineage、内部Evidenceの境界は[Municipal open-data analysis](municipal-open-data-analysis.md)
に記録する。

## Licence and tenant boundary

license policyはcommercial use、redistribution、attribution、share-alike、derivative、
unknown termsを機械判定可能に保持する。条件未確認は公開許諾として扱わない。raw byteのtenant間
deduplicationは、再配布確認済みpublic objectだけに限定する。tenant限定objectは所有Organizationを
必須とし、canonical record、spatial link、coverage、overrideは複合foreign keyで同じOrganizationへ
閉じる。GitHub Pagesにはprivacy/license review済み集約成果だけを置く。

## Update operation

通常更新は、source discovery、metadata refresh、bounded download、validation、normalization、
canonicalization、spatial linkage、capability refresh、dependency-based recomputationの実stageで
進める。更新前Urban StateとFindingは履歴として残し、新版で再現したか、解消したか、比較不能かを
明示する。架空の進捗率や「最新」という無根拠な表示は行わない。

## 2026-08-28 official catalog audit

`python -m analysis.scripts.build_municipal_open_data_inventory --observed-at <ISO-8601>`
は、allowlist済み公式入口を再取得し、
`analysis/outputs/real/open_data/municipal_catalog_inventory.json`を決定論的に生成する。
現在の実監査では、舞鶴市BODIKから30 dataset / 31 resource、藤沢市公式ライブラリの
「掲載データ一覧」から9 linked datasetを発見した。

舞鶴市の30 datasetは全件でBODIK metadata上のCC BY 4.0を確認した。藤沢市ページ自体の
利用規約はCC BY 4.0だが、リンク先resourceの条件を一律に継承したとは扱わない。そのため
藤沢9件のlinked-resource licenseは`unknown`、状態は`requires_review / not_verified`である。
どちらの都市もこの段階ではcatalog発見だけなので、`analysis_ready_dataset_count`は0である。

取得clientはHTTPS、明示host allowlist、credential URL拒否、標準443 port、DNSのglobal IP、
redirect先再検査、Content-Lengthと実byte上限を強制する。raw取得後はSHA-256 object keyへ
原子的に移動し、既存objectを再利用する際もhashとsizeを再検証する。

## Maizuru P0 real canonical run

`python -m analysis.scripts.build_maizuru_open_data_canonical --observed-at <ISO-8601>`
は、舞鶴市の医療、介護、人口、AED、公共施設、教育機関、児童生徒数、子育て施設、
指定緊急避難場所の9 resourceを実取得する。2026-08-28 runでは合計3,546 source rowを
すべてcanonical化し、rejectは0件だった。AEDのCP932と他8件のUTF-8 BOMを別々に検出している。

Canonical内訳は、facility 1,076、行政区人口時系列2,120、学校活動観測350である。人口identityは
公式の行政区コードと調査年月日の複合keyであり、年度違いを重複として捨てない。facilityのうち
1,012件には公開緯度経度があり、973件を既存の監査済み500m meshへ接続した。

公式PLATEAU 2025 archiveのSHA-256を再検証して44,640棟を再読込し、全1,076 facilityへ
建物link結果を付けた。675件は30m以内の最寄りfootprint候補、401件はunmatchedである。
住所や座標が近くても同一建物の公式確認ではないため、候補675件はすべて`ambiguous`とし、
自動同定や施設能力の推定には使わない。

成果物はsource report、canonical JSONL、canonical summaryの3点で、相互SHA-256を持つ。
canonical attributesから電話、email、contact form、画像、備考を除き、建物別人口推計も含めない。
datum、reference date、建物identityのreviewが残るためpromotion状態は`requires_review`のままである。

## MHLW medical and care real canonical run

`python -m analysis.scripts.build_mhlw_health_open_data --observed-at <ISO-8601>`は、厚生労働省の
[医療情報ネット・オープンデータ](https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/newpage_43373.html)
と[介護サービス情報公表システム・オープンデータ](https://www.mhlw.go.jp/stf/kaigo-kouhyou_opendata.html)
のページをversion manifestとして読む。日付付きsectionのうち最新日を選び、医療8 ZIPと介護35 CSVを
HTTPS allowlist、byte上限、ZIP安全性、UTF-8 BOM、列重複、行形状、最大行数のgateを通して
content-addressed raw storageへ保存する。

2026-08-28の実行では、医療は2026-06-01時点、介護は2026-06-30時点（2026-07-09出力）で、
43 resourceすべてのSHA-256が異なり、全schemaが合格した。対象自治体コードで絞ったcanonicalは
舞鶴741件、藤沢7,182件、計7,923件で、対象行のrejectは0件だった。医療は病院、診療所、歯科、
助産所、薬局、診療科と公開診療時間を、介護は公式35サービスコードと公開定員・利用可能曜日を保持する。
医療はPDL 1.0、介護はCC BY 4.0としてresource単位で記録する。

公開診療時間や公開定員は、現在の受入、予約枠、空床、緊急受入、利用資格を証明しない。これらの現在値は
常に`unknown`とし、分析readyへの自動昇格を行わない。canonicalには電話、FAX、URL、法人連絡情報、
自由記載備考を含めず、raw bytesもpublic assetsへ置かない。

全7,923件を自治体および監査済み500m meshへ接続し、施設1,650件をPLATEAU 2025建物へ評価した。
30m以内の最寄りfootprint 1,582件はすべて`ambiguous`な候補であり、施設と建物の同一性ではない。
MHLW医療918施設とP04 2020、舞鶴市標準ODSを比較した結果は、`ambiguous` 18、`probable` 481、
`unmatched` 419、uniqueな公的ID共有による`matched` 0だった。自動mergeは無効である。

PLATEAU 2025、医療2026-06-01、介護2026-06-30を単一年度に見せず、`mixed`なtemporal alignmentとして
保存する。成果物は`mhlw_health_source_report.json`、`mhlw_health_canonical.jsonl`、
`mhlw_medical_identity_comparison.json`、`mhlw_health_summary.json`で相互SHA-256を持つ。
水平datum未宣言、候補identity、現在availability未検証が残るため、状態は`requires_review`、
unavailable reasonは`not_verified`である。

## Demographic and economic real canonical run

`python -m analysis.scripts.build_demographic_economic_open_data --observed-at <ISO-8601>`は、国土数値情報の
R6将来人口GeoJSONとe-Stat `T001162`を京都府・神奈川県について公式入口から再発見し、安全なZIP検査、
SHA-256保存、schema/CRS/文字コード検査を行う。実スナップショットは将来人口が京都15,174 feature、
神奈川20,880 feature（EPSG:6668、343属性）、経済センサスが京都4,828 data row、神奈川6,346 data row
（CP932、KEY_CODE＋46指標）である。e-Statの先頭項目名行は検証後にdata rowから除外する。

行政区域コードで抽出した将来人口は舞鶴1,053件、藤沢963件、監査済み500m meshへ親子規則で全件接続した。
2020値は観測国勢調査ではなくモデル基準値、2025〜2070値は公式試算であり、予測保証や自動選択した
best scenarioではない。秘匿前値、公開用集約値、秘匿記号、250m合算先を別々に保持する。舞鶴2件、藤沢4件の
合算先が行政区域コード抽出外にあるため、公開用の市合計は`unavailable`とし、部分和を市合計として表示しない。

経済センサスは既存500m meshとの`KEY_CODE`完全一致だけを採用し、舞鶴287件、藤沢326件をcanonical化した。
未掲載は舞鶴208 mesh、藤沢1 meshで、0へ補完しない。46項目は事業所数・従業者数と産業大分類の公式定義を保持し、
活動文脈としてのみ使う。需要、必要度、収容力、施策scoreには読み替えない。

成果物はsource report、2,629件のcanonical JSONL、822件の統合500m GeoJSON、summaryである。同じ観測時刻の
再実行で4成果物のSHA-256が一致する。PLATEAU 2025集約は同じ500m keyのモデル文脈として接続するが、
建物人口の観測値とは扱わない。2020基準、2021経済、2025 PLATEAU、2025〜2070試算は常に`mixed`表示する。

## Geospatial resilience and safety real canonical run

`python -m analysis.scripts.build_geospatial_resilience_open_data --observed-at <ISO-8601>`は、
J-SHIS V4 250m表層地盤と警察庁2024年交通事故本票を公式入口から取得し、計4,105件をcanonical化する。
J-SHISは舞鶴1,980、藤沢1,084、事故履歴は舞鶴59、藤沢982である。海域のencoded zero、
JGD2000からEPSG:4326への変換、年次ファイル年と発生時刻、監査mesh外5件を失わず保持する。

GSI基盤地図情報、歩行空間ネットワーク、xROAD、GTFSは、取得・許諾・都市coverageの確認結果だけを
記録し、利用できないsourceの架空行を生成しない。詳細、公式URL、都市別状態、ライセンス境界は
[geospatial resilience sources](open-data-geospatial-resilience.md)を参照する。

## 2026-08-29 secondary official capability audit

追加調査した4入口は、発見可能性と分析採用を分離してmigration `026`へ登録した。厚労省「通いの場」
2026-06 CSVは6,195,590 byte、15,486 data row、SHA-256
`d909b5a013756ed09cb0635e75acf9c65628588f26f2702ab2e6cbea6bcd31f1`を検証したが、公開自治体名の
完全一致では舞鶴市・藤沢市とも0行だった。これは活動量0ではなく`outside_coverage`であり、canonical
行を生成しない。

WAM NETは2026-03の29 package linkを公式ページで確認したが、pilot city行、schema、resourceごとの
再配布条件をまだ検証していない。S12はproduct specification 3.1と2021年乗降客数を確認したが、
version-pinned raw/canonicalを未取込で、利用者数を駅容量・混雑・live需要へ読み替えない。PT調査は
2026-03時点の実施都市圏catalogまでを確認し、対象2市のlicensed spatial aggregateを未確認とした。
個人軌跡の取込は許可しない。3入口はいずれも`requires_review / not_verified`であり、分析capabilityを
自動有効化しない。

機械可読な観測receiptと境界は
`analysis/outputs/real/open_data/official_capability_audit.json`に保存する。raw CSV/ZIPや個人情報になり得る
項目はrepositoryおよびPublic Showcaseへ配布しない。

Goal 1〜120の最終対応、実データ件数、CI証跡、外部作業境界は
[Municipal Open Data Platform final audit](open-data-platform-final-audit.md)を参照する。
