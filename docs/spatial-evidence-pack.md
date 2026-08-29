# Spatial Evidence Pack

Spatial Evidence Packは、Findingを自治体レビューへ渡すための不変・tenant-scopedな局所証拠delivery unitである。地図表示用の一時cacheではない。

## Canonical Maizuru pack

`maizuru-533513314-plateau-2025-v1` は舞鶴市2025の対象500mメッシュ `533513314` を固定する。

| Object | Actual count | Source semantics |
|---|---:|---|
| target buildings | 296/296 | 公式PLATEAU b3dm batch table。GML ID、用途、高さ、階数、面積、LOD、source bboxを保持 |
| road surfaces | 135 | 公式PLATEAU道路LOD1 polygon。実験network relationとは分離 |
| terrain | 65,232 triangles | 公式 `dem:TINRelief`、EPSG:6697からGSIGEO2011でEPSG:4979/4978へ変換、誇張1.0 |
| facilities | nearest 16 | 追跡済みP04/P11 derivative。舞鶴市公式GTFSは未公開・未使用 |
| mesh analysis | 1 | 既存500m集計。建物固有値として扱わない |
| scenario site | 1 | 既存 `overall-3` の候補。実PLATEAU道路面代表点だが、施設設置・適地・実施済みを意味しない |

`objects.json` は属性・関係とsource bboxを持ち、重い3D geometryはchecksum済みb3dm/GLBを参照する。`sections.json` は同Packから作った断面ready artifactである。manifestは各artifact SHA-256、content hash、source version、privacy boundaryを記録する。

現行manifestのdelivery内訳は、分析artifact 592,729 bytes（gzip 69,869 bytes）、対象building b3dm 4,313,608 bytes、DEM GLB 1,575,692 bytes、道路asset 95,447 bytes、参照core合計6,577,476 bytesである。25MB未満であり、全市streamは含めない。

## Lifecycle and storage

`queued → extracting → building → validating → ready` を実stage eventとして記録し、失敗は `failed`、後継ready Packが採用された旧版は `superseded` とする。進捗率はstage実績なしに生成しない。storageはcontent addressedで、artifact responseはETag/immutable cache/range-capable URIを使う。

DBは `spatial_evidence_packs / spatial_pack_objects / spatial_pack_artifacts` を持ち、すべての参照を `(organization_id, id)` で拘束する。公開・庁内・restrictedを分ける。公開Packの再帰privacy gateは `estimated_population` 等の建物単位人口model fieldを拒否する。

Offlineは明示された単一Pack assignmentだけをService Workerへ渡す。都市全体downloadや暗黙の庁内data cacheは行わない。

## Reproduction

```bash
python -m analysis.scripts.build_spatial_evidence_pack
pytest -q analysis/tests/test_spatial_evidence_pack.py
```

同じ追跡済みinputは同じ `content_sha256` と `pack_manifest_sha256` を生成する。build wall timeは計測するがmanifest hashへ含めない。
