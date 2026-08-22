# 審査観点との対応

CITY GAPは、Project PLATEAU CityHack Challenge 2026の3つの観点を「実装済み」と「今後の検証」に分けて説明します。将来案を現在の成果としては扱いません。

## 1. 3D都市モデル活用

### 実装済み

1. **分析範囲と駅accessibility**
   PLATEAU舞鶴市2025関連データの行政界をpolygon化し、人口mesh・バス停・医療施設を実際の市境で抽出しました。駅9 recordは名称＋位置で7地点へdeduplicateし、最寄り駅距離に使っています。

2. **公式3D Tilesの実表示**
   舞鶴市2025の公式3D Tiles/MVT ZIPを取得し、CesiumJSで東舞鶴駅・西舞鶴駅周辺の公式建物を表示します。配信するのはLOD2配布コンテナのleaf b3dm 5件、12.7MB、2,152 unique buildingsです。公式配布container全体を無制限配信しません。

3. **建物の実属性**
   clickした建物について、公式batch tableに存在する `gml_id`、用途、計測高さ、地上/地下階数、LODを表示します。欠損を推定せず「属性なし」とします。subset内で用途（「不明」を除く）は88.429%、計測高さは80.762%、階数は88.429%の建物に実値があります。

4. **coverage QA**
   公式配布全427 b3dm、配布内44,640 unique buildingsをinspectionし、CITY GAP Top 10との空間照合が0棟であることを確認しました。候補地へ架空3D建物を置かず、「公式2025建物モデル整備範囲外」としてUIとmethodologyに出します。これは3Dデータを信頼できる範囲で使うための品質管理です。

### 現在の限界

- 公式PLATEAU建物モデルはTop 10を覆っていないため、Rank 1の建物形状・用途は表示も分析もできません。
- 3D参照subsetは東・西舞鶴駅周辺であり、Top 10周辺や舞鶴市全域のWeb配信ではありません。
- 建物属性は現行Score Cへ入力していません。
- Cesiumはellipsoid terrainで、DEM・勾配は未実装です。

### 今後の検証

- 追加の公式整備範囲や自治体保有データが得られた場合の建物単位居住起点
- `tran`道路network、横断可能性、DEM勾配を使う移動負荷
- 人口を建物へ配分する根拠と不確実性
- 建物用途・階数・床面積を使う需要scenario

これらは設計候補であり、現行プロダクトの機能ではありません。

## 2. 独自性

### 単独の地図ではなく「発見から施策感度まで」

一般的なlayer viewerは人口、交通、医療を表示して終わります。CITY GAPは次を1つのdeterministicなflowにします。

```text
指標を切り替える
  → 複数条件のズレからTop 10を発見
  → 実測値とpercentileで「なぜ？」を説明
  → PLATEAUで実在3Dとcoverageを確認
  → 仮想交通支援拠点でBefore / Afterを再計算
```

- 「高齢人口」「交通アクセス」「医療アクセス」「CITY GAP」の切替で、複数データを重ねる意味を体験できる
- Rank、実測距離、percentile、Paretoを分離し、スコアだけを権威化しない
- 説明文はLLM生成でなく分析値から決定論的に生成する
- What-ifは地図clickをEPSG:6674へ変換し、baselineと同じ距離定義で全286meshの交通percentileを再計算する
- 同じasset・同じ座標なら同じ結果になり、固定のBefore / After演出値を使わない
- データが存在しないこと自体をcoverage情報として提示する

独自性は複雑なAIではなく、異種の都市データ、説明可能性、3Dデータ品質、施策感度を途切れない市民向け体験へまとめた点にあります。

## 3. 地域課題への貢献

### 舞鶴市の実データに限定した具体性

- 舞鶴市と交差する実在500m mesh 495件を使用
- e-Stat 2020、P11 2022、P04 2020、PLATEAU 2025の公式データを使用
- Rank 1 mesh `533512753` は人口91人、65歳以上56人、公共交通2,322m、医療3,317m
- Top 10の人口条件、秘匿・合算除外、データ年次、距離定義を公開
- Top候補の現地確認、運行頻度、P11対象外交通、現在の医療提供を次の調査項目として具体化

### 想定利用

| User | Product value | Required follow-up |
|---|---|---|
| 自治体職員 | 部門を跨ぐデータから追加調査候補を共有 | 保有交通data、費用、制度、現地条件の確認 |
| 交通・医療事業者 | 距離が長い候補と人口規模を同じ画面で確認 | 運行・診療capacity、利用実態の確認 |
| 地域住民 | Rankの理由と出典を確認し対話を始める | 生活上の障壁、非公開service、移動手段の聞き取り |
| 審査員・研究者 | lineage、計算式、coverage、限界を再現 | 指標設計と外的妥当性の評価 |

CITY GAPは施策を自動決定しません。「どこを、なぜ、次に調べるか」を共有することで、限られた調査資源を具体的な対話へつなげます。

## 「普通の2D GISだけでよくないか？」への回答

### 2Dで十分な部分

正直に言えば、現行の500m mesh距離、percentile、Top 10、What-ifの数値計算は2D GISで実現できます。建物3Dを使ったからScore Cが計算できた、とは主張しません。

### PLATEAUが現在追加している価値

1. **数字から都市objectへの接続**
   meshの集計値から、実在する建物形状と用途・高さ・階数という都市objectへzoomできます。統計polygonだけでは見えない都市形態を、同じ操作環境で確認できます。

2. **属性の有無を建物単位で確認**
   2D背景画像では、建物の公式ID、用途、高さ、階数、LODと欠損を機械可読に扱えません。PLATEAU batch tableにより、使える実属性だけを明示できます。

3. **coverageを検証可能なdataとして扱う**
   Top 10が3D整備範囲外だと全tile inspectionで確認できました。建物が表示されない理由を推測せず、「現実に建物がない」と「データに収録されていない」を区別できます。

4. **次の分析単位を用意**
   現行mesh中心モデルの限界を、将来の建物単位居住起点、道路接続、階数・床面積へ進める具体的なschemaとgeometryがあります。

つまり、現行の数値ランキングには2D GISが必要十分ですが、**結果を実在都市objectへ接続し、3Dデータの適用可能範囲を検証し、次の詳細化を可能にする部分がPLATEAU固有の価値**です。

## Evidence checklist

| Claim | Repository evidence |
|---|---|
| 分析値は実データ | `analysis/outputs/real/`、`frontend/public/data/manifest.json` |
| 500m mesh 495 / comparison 286 / ranking 218 | `maizuru_summary.json`、`docs/findings.md` |
| PLATEAU公式配布内44,640 / Top 10内0 | PLATEAU inspection metadata、`plateau_metadata.json` |
| Web subset 5 tile / 2,152棟 / 12.7MB | subset selection metadata、Web `tileset.json` |
| 実属性だけを表示 | 3D Tiles batch table inspection、building detail UI |
| What-ifは同じ距離定義 | `frontend/src/lib/scenario.ts`、scenario tests |
| 手法と限界を開示 | `docs/methodology.md`、アプリの `データと計算方法` |
| 再現可能なstatic app | `build_web_assets.py`、Vite config、Pages workflow |

## One-sentence position

CITY GAPは、PLATEAUを万能な答えとして扱うのではなく、舞鶴市の実データから「必要と届き方のズレ」を説明可能に発見し、3D都市の実在範囲とデータ限界を確認し、仮想施策の感度まで対話できるCivic Techプロダクトです。
