# PLATEAU Urban Section

Urban Sectionは、保存されたtransectに沿って同じSpatial Evidence Packの都市構造を垂直断面として読む調査面である。装飾的profileではない。

## Algorithm

1. GeoJSON LineStringを舞鶴市の分析CRS EPSG:6674へ投影する。
2. 5m間隔の点を、追跡済みPLATEAU DEM GLBから復元したsource TINへ照合する。
3. 三角形内は平面重心座標でellipsoidal elevationを補間し、`distance / elevation / source_triangle_id / quality`を保持する。
4. TIN外は `no_coverage` としてNULLを保持する。補間、平滑化、誇張、fallback terrainは使わない。
5. 建物source bboxはtransect直接交差と12m近傍を分け、距離範囲、offset、GML ID、実測高さ・用途を保持する。高さ不明は不明のまま表示する。
6. 道路LOD1 polygon交差、facility offset、都市計画属性帯、実値がある災害帯を別layerにする。災害深がない場合に深さを作らない。

canonical transectは決定論的候補群から建物・道路の実交差数で選び、94 terrain samples、63 building relations、14 road intersectionsを持つ。

Counterfactual Sectionは既存 `overall-3` の対象mesh結果を固定する。現況562.597m、scenario 29.867m、差532.73mは500m mesh中心からの直線距離で、徒歩経路・network route・所要時間ではない。候補地点は実PLATEAU道路面代表点へ投影するが、siting feasibilityは未判定である。296棟は関連building groupとして示し、個別棟の改善とは呼ばない。

## UI contract

SVG断面は左右矢印による建物移動、Enter/Space選択、screen-reader text summaryを持ち、reduced motionでも完全に読める。建物を選ぶと3DとObject Lensの同じGML IDを選択する。Cesiumの半透明断面面は同じLineStringと実TIN elevation rangeから作り、誇張1.0を保持する。

Planning、Hazard、Service、Route/Scenario relationを意味layerとして分ける。Counterfactualは建物geometryを変えず、実scenarioで変化したrelationだけを表示する。該当relationがない場合は空を実値で埋めず、利用不可として扱う。

永続面は左navigation、右Object/Evidence、必要時の下Urban Sectionの最大3面を基本とする。toolbarは小型controlであり主要情報面を増やさない。
