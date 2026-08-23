# PLATEAU建物人口配賦（Priority 2）

## 結論と解釈

舞鶴市2025 PLATEAUの実建物44,640棟を監査し、令和2年国勢調査500mメッシュの
公表人口を、秘匿影響のないメッシュだけで住宅建物へ統計的に配賦する。これは
「500m統計から配賦した推計人口」であり、実居住者、住民票、世帯、個人情報、確認済み入居数ではない。
秘匿元・合算先を含むメッシュは建物へ分解せず、元のメッシュ値だけを保持する。

## 建物属性と床面積監査

全44,640棟で対象属性はXML要素として存在したが、存在と有効性を分離した。

| 属性 | 有効 | 無効sentinel | 中央値 | p95 | p99 | 最大 | 単位 |
|---|---:|---:|---:|---:|---:|---:|---|
| totalFloorArea | 37,623 (84.28%) | 7,017 (`-9999`) | 105.36 | 383.423 | 1,795.502 | 71,998.84 | m² |
| buildingFootprintArea | 37,623 (84.28%) | 7,017 (`-9999`) | 64.47 | 218.256 | 991.46 | 35,999.42 | m² |
| storeysAboveGround | 37,623 (84.28%) | 7,017 (`9999`) | 2 | 2 | 3 | 15 | count |
| measuredHeight | 33,336 (74.68%) | 11,304 (`-9999`) | 8.19 | 13.253 | 21.593 | 78.96 | m |
| storeysBelowGround | 37,623 (84.28%) | 7,017 (`9999`) | 0 | 0 | 0 | 1 | count |

生値、0、負値、numeric parse失敗、単位、上下位外れ例、`totalFloorArea >= footprintArea`、
階数との比は `maizuru_building_attribute_audit.json` に残す。値はclampしない。有効な
`totalFloorArea`を第一順位、なければ有効な`footprint × storeys`、次にfootprintのみ、
最後は`not_allocatable`とする。今回の実データでは37,623棟が`total_floor_area`、
7,017棟が`not_allocatable`となった。
有効値同士37,623棟のうち`totalFloorArea < footprintArea`は277棟あり、異常として例示するが、
公式値の意味を推測して書き換えない。`total / (footprint × storeys)`の中央値は0.9853、p01は
0.5854、p99は1.0588だった。

## 形状と配賦式

実CityGMLのLOD0屋根外形を内周ringも保持して2D投影し、ない場合だけLOD1 Solid投影へfallbackする。
EPSG:6674で500mメッシュと正確に交差し、境界を跨ぐ建物は次で容量を分ける。

```text
intersection_fraction = intersection_area / building_footprint_area
effective_floor_area_in_mesh = verified_floor_area * intersection_fraction

estimated_population_i
  = mesh_population * effective_floor_area_i / sum(effective_floor_area)

estimated_elderly_population_i
  = mesh_elderly_population * effective_floor_area_i / sum(effective_floor_area)
```

Primaryは公式用途411/412だけ、感度は411〜415を使う。混合用途の住宅比は仮定しない。
各配賦成功メッシュで人口・65歳以上人口を独立に合計し、絶対誤差`1e-9`以内でなければ
パイプラインを失敗させる。人口があっても対象住宅がない場合、商業・工業建物へ強制配賦せず
`mesh_fallback_no_residential_building`とする。

## 秘匿、coverage、公開境界

`primary_eligible_disclosure`が真の286比較メッシュだけが詳細配賦候補である。分類は
`building_detail_available`、`building_detail_partial`、`mesh_fallback_no_plateau`、
`mesh_fallback_no_residential_building`、`mesh_fallback_suppression`を全495メッシュへ付ける。
正確な件数・割合、保存誤差、strict/mixed感度、深掘り値は
`maizuru_building_demographics_summary.json`をSingle Source of Truthとする。

実結果は286mesh中、`building_detail_available` 149（52.098%）、
`mesh_fallback_no_plateau` 132（46.154%）、`mesh_fallback_no_residential_building` 5
（1.748%）。全495meshではさらに秘匿・合算影響209を`mesh_fallback_suppression`とした。
部分詳細は0だった。strictは29,603 building-mesh record・149mesh、mixed感度は31,321 record・
150mesh。保存最大絶対誤差はstrict人口`1.14e-13`、65歳以上`5.68e-14`である。

詳細Parquetはローカル分析・将来自治体基盤用でGit対象外。公開Competition Demoへ渡すのは
mesh `533513314`の住宅棟数と加重距離など、500mメッシュ集計だけである。建物別推計人数は
GitHub Pagesへ公開しない。APIもbbox付き最大1,000件の既存一覧を維持し、Priority 2の詳細は
単一meshまたは単一`gml_id`に限定する。

## 公式PLATEAU手法との比較

Project PLATEAUの[都市構造分析ツール](https://github.com/Project-PLATEAU/Urban-structure-analysis)と
[2025年度ユースケース](https://www.mlit.go.jp/plateau/use-case/uc25-09/)は、建物用途と延べ面積を
使って人口等を建物へ配分する点が共通する。公式実装は建物重心をメッシュへ包含判定し、住宅用途に
混合用途も含め、床面積不明住宅への均等配分、住宅がない場合の用途不明建物への均等配分を持つ。

CITY GAPは同等実装ではない。正確な面交差で複数mesh容量を分割し、Primaryでは411/412だけ、
秘匿影響meshを分解せず、用途不明への強制fallbackを行わない。感度分析では混合用途を全床面積で
加えるが住宅割合とは主張しない。この差はプライバシー保護と不確実性の明示を優先した設計判断である。
公式ツールは250m出力・QGIS/GPKGを含む別目的のツールであり、結果の等価性は主張しない。

## 再現と限界

```bash
python -m analysis.scripts.build_building_demographics
python -m analysis.scripts.verify_building_demographics
python -m analysis.scripts.load_building_demographics_postgis \
  --dataset-version-id UUID --database-url "$CITYGAP_DATABASE_URL"
```

独立検証は本体helperをimportせず、深掘りmeshと上位4meshでParquetを直接合計し、NumPy加重平均と
独立inverse-CDF加重分位を再計算する。床面積は居住床面積・入居率ではない。建物内での人口分布、
空き家、世帯構成、昼間人口は分からない。直線距離は歩行経路ではなく、Priority 3で道路networkへ移行する。
