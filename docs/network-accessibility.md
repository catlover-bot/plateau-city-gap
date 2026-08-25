# Road network and 3D accessibility

CITY GAPには、舞鶴市2025 CityGMLを使った建物起点の道路ネットワーク比較を実装して
います。ただし、現在の実データ成果物は**実験的な道路面隣接グラフ**であり、徒歩経路
ではありません。公式ジェネレータ出力とフォールバックをschema・表示上とも分離します。

## Official-tool-first boundary

優先入力は公式
[PLATEAU RoadNetwork Generator](https://github.com/Project-PLATEAU/PLATEAU-RoadNetwork-Generator)
のnode/link GeoJSONまたはShapefileです。公式ツールは道路ネットワークと歩行者ネットワーク
を出力でき、後者には道路CityGMLに加えて都市設備・橋梁を使用します。実行環境はWindows
10/11です。仕様・操作条件は国土交通省の
[道路ネットワーク生成関連技術資料](https://www.mlit.go.jp/plateau/file/libraries/doc/plateau_doc_0007_ver03.pdf)
および公式repositoryを参照しました。

`read_official_generator_output` は公式列 `node_id`、`link_id`、`start_id`、`end_id`、
`distance` を正規化します。`network_type=walk` を明示した公式歩行者出力だけを
`pedestrian_network=true` にできます。現在のWSL環境ではWindows GUIを実行していないため、
公式出力を生成済みとは報告しません。

## Experimental Maizuru graph

CityGML監査では道路オブジェクト15,684、LOD1外周15,684、LOD2交通面1,090、内周4でした。
旧抽出器の16,778は全`posList`を同列に数えた値です。現行パーサはLOD1外周だけを使い、
内周を穴として保持し、LOD2を除外します。

各LOD1道路面の内部代表点をnodeとし、面が交差するか0.05m以内にある場合だけundirected edge
を作ります。0.05mはCityGML境界の微小な数値ずれを吸収する明示的なtopology toleranceで、
1,647辺が`tolerance_bridge`です。

| Graph quality | Real value |
|---|---:|
| Nodes / edges | 15,684 / 23,437 |
| Connected components | 19 |
| Largest component | 15,563 nodes (99.2285%) |
| Strict demographic buildings | 28,448 |
| Transport reachable | 28,443 |
| Medical reachable | 28,435 |
| Building → road-surface snap median / p95 | 7.99m / 20.55m |
| Building → representative-node connector median / p95 | 18.40m / 48.63m |

距離は`building connector + graph edge lengths + facility connector`です。面内移動を正確に
復元するcenterlineではなく、横断条件・歩道・通行可否・所要時間を持ちません。APIと成果物は
常に`pedestrian_network=false`、`pedestrian_permission=unknown`、
`route_semantics=PLATEAU LOD1 road-surface adjacency path; mode not validated`を返します。

## Comparison and verification

`maizuru_network_accessibility_meshes.csv` は同じ149メッシュについて次を並べます。

- 500m mesh centroidの直線距離
- PLATEAU居住建物分布による高齢者人口加重Euclidean距離
- 実験道路面隣接グラフによる高齢者人口加重network距離

本体は決定論的multi-source Dijkstraです。別の証明器が全23,437辺の最適性不等式、全前任辺の
距離方程式、seed上界、sample route realizationを検査します。公共交通・医療ともcertificateは
passし、network距離が建物―施設の直線距離を下回るrecordは0です。

## PLATEAU DEM terrain component

道路15,684 nodeを公式LOD1 DEM TINへbarycentric interpolationしました。23 DEM member中、道路
nodeを含む10 member、16,310,504三角形をstream処理し、node/edge terrain coverageは100%です。

| Terrain quality | Real value |
|---|---:|
| Node elevation coverage | 15,684 / 15,684 |
| Edge endpoint coverage | 23,437 / 23,437 |
| Absolute endpoint grade median / p90 / p99 | 1.10% / 6.13% / 19.45% |
| Maximum | 65.07% |

各nodeはDEM member、CRC32、triangle indexを保持します。各routeはgraph edge区間だけの
`ascent`、`descent`、`maximum observed grade`を持ち、建物・施設connectorのterrainは
`not_computed`です。勾配は離れた道路面代表点間の端点差で、測量された道路中心線勾配では
ありません。最大値を歩行可能性や道路勾配として解釈しません。

距離と地形負荷は別column・別成果物です。地形をrouting penaltyや単一scoreへ混ぜていません。
独立検証は全辺の標高差・gradeを再計算して残差0、Deep Dive公共交通29辺・医療57辺の距離、
上り、下り、最大gradeを最大残差4.6e-13で再現しました。

## Artifacts and reproduction

Tracked audit artifacts:

- `analysis/outputs/real/maizuru_road_network_summary.json`
- `analysis/outputs/real/maizuru_network_accessibility_meshes.csv`
- `analysis/outputs/real/maizuru_network_deep_dive_evidence.json`
- `analysis/outputs/real/maizuru_terrain_network_summary.json`
- `analysis/outputs/real/maizuru_terrain_accessibility_meshes.csv`
- `analysis/outputs/real/maizuru_network_deep_dive_terrain.json`
- `analysis/outputs/real/maizuru_terrain_verification.json`

大きなnode/edge/building ParquetはGit管理外です。再生成順は次の通りです。

```bash
python -m analysis.scripts.build_road_network_accessibility
python -m analysis.scripts.build_terrain_accessibility
python -m analysis.scripts.verify_terrain_accessibility
```

PostGIS migration `003_road_network_terrain.sql` はgraph version、node、edge、施設、建物到達性、
terrain、provenanceをロード可能にします。DB未実行を成功とは報告しません。FastAPIはversion
一覧、bbox必須edge query、単一建物network accessibilityの契約を持ちます。
