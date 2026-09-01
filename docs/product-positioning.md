# Product positioning: 地域の状態と確認すべきことをつなぐツール

最終確認日: 2026-09-01

## 一文で表す価値

**自治体が調べたい場所と範囲について地域の状態を定量化し、データから確認できることと、データだけでは判断できないことを分け、必要な場合だけPLATEAU上の確認場所へつなぐ。**

CITY GAPは、自治体職員が経験的に感じている地域の状態を公開データとPLATEAUで定量化・可視化し、公開データの限界を隠さず次の確認へつなぐ意思決定前処理ツールである。AIが地域を自治体職員より理解しているとは主張せず、政策決定、危険判定、施策推奨、実施効果予測も行わない。

```text
LOCAL INTUITION
  -> QUANTIFIED EVIDENCE
  -> KNOWN / UNKNOWN
  -> source limitation
  -> Finding
  -> versioned PLATEAU target / honest fallback
  -> verification
```

## 主利用者と成果物

主利用者は地域公共交通、都市計画、公共施設等の周辺分析を行う自治体職員である。高齢福祉、GIS/PLATEAU、現地調査運用の各担当が共同利用者となる。

最終成果物は次の3点である。

1. versioned Investigation Areaの地域状態サマリー
2. Known / Partial / Unknown / Unavailableと出典・限界
3. field-verifiableなUnknownに限ったPLATEAU確認対象と3〜5件の未確認項目

## 公式ツールとの比較

比較は機能の優劣ではなく、対象業務と出力の違いを明示するために行う。

| 観点 | 都市構造評価ツール | 都市モニタリングシート / ハンドブック | CITY GAP |
|---|---|---|---|
| 主な対象業務 | 立地適正化計画の策定・更新、都市構造評価 | 都市の現況把握、都市間比較、定量評価 | 任意地点・駅周辺等の状態確認と追加確認準備 |
| 主入力 | PLATEAU建物、各種オープンデータ、自治体独自施設・区域案 | 都市計画現況調査、基幹統計等 | versioned Investigation Area、国勢調査・事業所・交通・計画・PLATEAU等のversioned source |
| 主な分析単位 | 建物、圏域、誘導区域、自治体・隣接自治体 | 自治体、都市類型、指標 | point-radius/source boundary→Known/Unknown→必要時のみPLATEAU対象 |
| 建物人口配分 | 延べ床面積を用いた建物単位配分を実装 | 対象外 | 既存高度分析では推計を保持するが、公開候補の差別化には使わない |
| 指標算出・可視化 | 多様な指標の算出、地図・グラフ表示 | 約400指標、個票、レーダーチャート | 自治体が最初に確認する5領域を短く表示 |
| 自治体データ取込 | 独自施設、区域案等に対応 | Excel等の提供資料を利用 | 実レビュー後の確認情報を内部記録として扱う |
| 複数案比較 | 誘導区域変更前後や複数区域案を比較 | 自治体・都市類型間を比較 | 高度分析にはシナリオ比較を保持するが、公開フローの主目的ではない |
| 主出力 | 都市構造指標、地図、グラフ、CSV等 | 全体表、自治体個票、比較図 | Area Summary、source limitation、未確認のPLATEAU対象・確認項目 |
| 不足データ→確認項目 | 本比較で確認した公式説明上の主出力ではない | 対象外 | source limitationからルール版付きで決定論的に生成 |
| 自治体レビュー状態 | 有用性検証を実施済み | 制度・評価手法として提供 | 未確認を保持し、自動で確認済みにしない |
| 観察・証拠の系譜 | 分析データ・算式を管理 | 指標定義・出典を管理 | Area→Known/Unknown→Finding→targetを保持 |
| 判断との境界 | 計画検討・都市構造評価を支援 | 客観的・定量的な把握を支援 | 次の確認材料。政策判断を代替しない |

## 公式ツールが既に持つため、独自性として主張しないこと

- PLATEAUとオープンデータの統合
- 都市構造指標の算出と地図・グラフ可視化
- 建物への人口配分
- 自治体独自データの取込
- 誘導区域案の前後・複数案比較
- 隣接自治体を含む広域表示
- CSV等の分析結果出力
- 任意地点・半径による範囲指定や集計
- PLATEAU 3D上のオブジェクト表示
- PLATEAU 3D、ボーリング柱状図、液状化・土砂災害等のhazard layerを組み合わせた専門可視化

## 専門viewerとの境界

舞鶴市から、今年度のボーリング可視化ユースケースで、建物を含むPLATEAU 3D都市モデル上の柱状図と、液状化マップ、土砂災害等のhazard dataとの組合せを検討しているという直接Evidenceを得た。

- Evidence status: `DIRECT_MUNICIPAL_USE_CASE_OVERLAP_CONFIRMED`
- Borehole strategy: `INTEGRATE / RESEARCH ONLY`
- CITY GAP独自のborehole viewer、3D column viewer、hazard+borehole viewerは作らない。
- P1で自動実装しない。
- 将来、成果物・公開データ・API・export・dataset version・利用条件を確認できた場合だけ、Investigation Areaのofficial observation sourceとして接続可能性を別Goalで評価する。
- 観測点間の補間、連続地層、地盤安全判断、基礎設計判断は行わない。

## CITY GAPが検証する差分

1. 調べたい場所と範囲をversioned Investigation Areaとして再現できるか。
2. 地域の状態を、出典・時点・coverageとともに定量化できるか。
3. KnownとUnknownを分断せず、source limitationから追跡できるか。
4. field-verifiableなUnknownだけを実在PLATEAU objectまたは正直なfallbackへ具体化できるか。
5. Area→Known/Unknown→Finding→target→未確認項目のchainが自治体業務で意味を持つか。

## 公式一次情報

- [国土交通省: 立地適正化計画とコンパクト・プラス・ネットワーク](https://www.mlit.go.jp/en/toshi/city_plan/compactcity_network.html)
- [Project PLATEAU: 都市構造評価ツールの社会実装](https://www.mlit.go.jp/plateau/use-case/uc25-09/)
- [Project-PLATEAU/Urban-structure-analysis](https://github.com/Project-PLATEAU/Urban-structure-analysis)
- [国土交通省: 都市モニタリングシート](https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000035.html)
- [国土交通省: 都市構造の評価に関するハンドブック](https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000004.html)

公式説明は将来更新されるため、本表の断定範囲は上記ページを確認した内容に限る。
