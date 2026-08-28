# Municipal Open Data Platform

CITY GAPのオープンデータ基盤は、公式カタログの「発見」と、分析入力としての
「採用」を分離する。カタログに存在するだけでは品質、利用許諾、時点整合、分析適合を
保証しない。Data Managerが検証結果を確認し、既存のDataset lifecycleを通して
`analysis_ready` / `promoted` にした版だけをUrban Stateと分析が参照する。

## 公式ソースレジストリ

2026-08-28時点で、次の入口を版付きで登録している。

| source key | 公式提供主体・入口 | adapter | 初期license policy | 範囲 |
|---|---|---|---|---|
| `digital-agency-municipal-standard-ods` | [デジタル庁 自治体標準オープンデータセット](https://www.digital.go.jp/resources/open_data/municipal-standard-data-set-test) | `municipal-standard-ods@2026-08` | unknown（resourceごとの確認が必要） | 全国schema |
| `bodik-maizuru` | [舞鶴市 / BODIK](https://data.bodik.jp/organization/262021) | `ckan-v3@1` | CC BY 4.0 | 舞鶴市 |
| `fujisawa-open-data-library` | [藤沢市オープンデータライブラリ](https://www.city.fujisawa.kanagawa.jp/kyoso/shise/kekaku/kakushu/datalibrary.html) | `municipal-standard-ods@2026-08` | CC BY 4.0 | 藤沢市 |
| `mhlw-medical-information-network` | [厚生労働省 医療情報ネット](https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/newpage_43373.html) | `mhlw-medical@2026-06` | PDL 1.0 | 全国 |
| `mhlw-care-service` | [厚生労働省 介護サービス情報公表システム](https://www.mhlw.go.jp/stf/kaigo-kouhyou_opendata.html) | `mhlw-care@2026-06` | CC BY 4.0 | 全国 |

コード上のSingle Source of Truthは
`backend/citygap_platform/open_data/registry.py`、永続化の初期値はforward-only migration
`018_open_data_foundation.sql`である。将来の定義変更では既存migrationを書き換えず、新しい
adapter IDとmigrationを追加する。

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
