# Architecture

```text
official raw data -> CRS/schema validation -> population areas
 -> nearest-target Euclidean distances -> component percentiles
 -> exploratory score/rank -> CSV + GeoJSON + summary.json
 -> (later) CesiumJS explanation UI
```

`accessibility.py`が空間距離、`metrics.py`が正規化・スコアを分離し、CLIはI/Oを担当する。

| 2D GIS MVP | PLATEAU extension |
|---|---|
| 地域代表点 | 属性確認後の居住建物起点 |
| 直線施設距離 | 道路接続、勾配、上下移動負荷 |
| 地域人口のミスマッチ | 建物形状・用途と計画シナリオ比較 |

PLATEAU extensionは設計候補であり実装済みの主張ではない。

## Next phase: Top 5 mesh to PLATEAU buildings

実分析Top 5が得られたため、次Phaseは914 MB全体を無条件展開せず、索引図とCityGML package構成を先に確認して必要tileだけを対象にする。

```text
Top 5 real 500 m meshes
  -> intersect PLATEAU bldg polygons in those meshes
  -> validate actual availability/completeness of usage, height, storeys
  -> attach mesh population/access context to each building
  -> identify probable residential origins only when verified attributes allow
  -> recompute building-to-facility road/slope burden
  -> compare mesh-centroid result with building-weighted result
  -> explain changed/unchanged candidates in Cesium
```

必要な技術検証は、(1) CityGML v5のmesh別ファイル対応、(2) `bldg:usage`, measured height, storeys等の実装率、(3) `tran`道路の歩行ネットワーク接続性、(4) DEM/勾配の出典、(5) 500m人口を建物へ配分する妥当な根拠である。属性が欠損している場合は建物用途を推定して実データのように扱わない。
