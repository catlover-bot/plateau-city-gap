# CITY GAP Spatial Workspace

CITY GAP Spatial OS は、別々の画面へ分析を移し替える仕組みではない。都市、年次、選択地点、分析意図、空間解像度、Scene、主題、2D/3Dを同じ状態として保持し、発見から自治体レビューまで一つの地図で引き継ぐ。

## State contract

| 状態 | 値 | 役割 |
|---|---|---|
| `intent` | `discover / inspect / scenario / resilience / validate` | いま何を判断するか |
| `resolution` | `city / mesh / building / route / site` | 都市→500m→建物→道路→施策の現在位置 |
| `scene` | 8つの `ScenePreset` | camera、必要layer、legend、inspectorを同期 |
| `selection` | mesh / building / road / facility / scenario site / validation sample / temporal change | 全workflowで共有する対象 |
| `urbanState` | 2020 / 2023 / 2025 / 2040 | 現在・過去・将来仮定の識別 |
| `mapMode` | `map2d / plateau3d` | 分析2DとPLATEAU 3Dを同じstateで切替 |

URLはこれらをすべて直列化する。`?city=maizuru&scene=plateau_detail` のようなSceneだけのdeep linkでも、`inspect / building / plateau3d / plateau-detail / plateau-buildings` を決定論的に復元する。従来の `workspace=demo|futures|validation|workspace` も互換入力として残す。

## Eight ScenePresets

| Scene | 意図 / 解像度 | 推奨engine | 必須layer |
|---|---|---|---|
| `city_overview` | 発見 / 都市 | 2D | 地理院淡色、CITY GAP、駅 |
| `gap_discovery` | 発見 / 500m | 2D | 地理院淡色、CITY GAP、駅、医療 |
| `plateau_detail` | 検査 / 建物 | 3D | PLATEAU建物、道路、実DEM |
| `network_access` | 検査 / 道路 | 3D | 交通、建物、道路、実DEM、経路 |
| `scenario_compare` | 施策 / 候補地 | 2D | 施策範囲、候補地、経路 |
| `hazard_stress` | resilience / 道路 | 3D | 建物、道路、実DEM、災害、候補地 |
| `temporal_change` | 検証 / 建物 | 2D | 地理院淡色、年次差分 |
| `validation_disagreement` | 検証 / 道路 | 2D | 地理院淡色、PLATEAU実験経路、OSM参照経路、不一致sample |

Sceneは単なるcamera bookmarkではない。`frontend/src/map/core/scenePresets.ts` が intent、resolution、engine、camera intent、primary layer、required layers、legend、inspector sectionsを一括定義し、`frontend/src/map/layers/layerRegistry.ts` の26 layerだけを参照する。

## Interaction contract

- 上部のResolution Railは現在の空間粒度を示し、前後の粒度へ移動できる。
- 地物選択はtyped selectionとしてContext InspectorとURLへ即時反映する。
- Contribution Inspectorは、PLATEAUのどのテーマが結果へ使われ、画面で確認可能かを同じ語彙で示す。
- Presentation Guideは「全市→候補→PLATEAU 3D→災害stress→自治体レビュー」の5段階を同じworkspace上で再生する。
- 3Dを利用できない場合も2D分析と候補一覧を保持する。これはsilent fallbackではなく、画面上で理由を通知する。

## Truth boundary

Selectionを引き継ぐことは、異なる解像度の値が同じ意味になることを意味しない。500mの記録人口、建物へのモデル配賦、実験的道路面graph、counterfactualな道路利用不可仮定、施策効果、自治体レビュー結果は別のprovenanceを保つ。Spatial OSはこの差を隠さず、比較できる位置に並べる。
