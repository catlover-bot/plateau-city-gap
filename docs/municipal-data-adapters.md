# Municipal data adapters

CITY GAP accepts five explicit open-data boundaries without inferring a format or municipal
meaning from a filename:

| Adapter | Input boundary | Validation |
|---|---|---|
| PLATEAU CityGML | `.gml` / `.xml` and an explicit theme | streaming city-object events, `gml:id`, geometry parts, CRS, SHA-256 and CRC32 |
| GTFS | `.zip` containing the six declared tables | safe member paths, size limits, required columns, keys, references, coordinates and ordered times |
| CSV | `.csv` plus declared columns/encoding | byte/row limits and string-preserved identifiers such as zero-padded mesh codes |
| GeoJSON | `.geojson` / `.json` plus declared columns | CRS, non-null valid geometry, feature limit and optional bbox |
| GeoPackage | `.gpkg` plus an explicit layer when ambiguous | layer existence, CRS, non-null valid geometry, feature limit and optional bbox |

They are implemented in `backend.citygap_platform.ingestion.adapters`. Every inspection returns a
content SHA-256, byte count, row/feature count and format-specific metadata suitable for a
`dataset_version`. Inspection does not claim that a PostGIS load or an analysis run succeeded.
Missing tables, fields, geometry or records are errors; the adapters never fill them with fake
municipal data.

```python
from backend.citygap_platform.ingestion.adapters import open_municipal_source

source = open_municipal_source(
    "geopackage",
    "data/local/facilities.gpkg",
    layer="medical_facilities",
    required_columns=("facility_id", "name"),
)
inspection = source.inspect().as_dict()
frame = source.dataframe()
```

## Adding another city

The analysis engine is city-independent. A new city is added through a city YAML configuration,
explicit registry rows and source adapters rather than a branch in the score or routing code:

1. add the city code, analysis CRS, boundary and source paths under `analysis/config/`;
2. inspect sources through the appropriate adapter and register immutable dataset versions;
3. run `analysis.src.run_city_analysis --config ...` for screening;
4. run only capabilities backed by registered data, then publish their evidence in the city
   capability matrix.

`analysis/config/fujisawa.yaml` exercises this boundary for a second city. Its 500m screening is
available, while building/network/terrain/planning/hazard/GTFS capabilities remain correctly
partial or unavailable until those real inputs are acquired and computed.

## Security and scale boundary

- Input byte and row limits are enforced before a source is accepted for inspection.
- GTFS ZIP paths containing `..`, absolute paths, encrypted members or duplicate tables are
  rejected; total uncompressed size is bounded.
- Vector features require a declared CRS and valid non-null geometry.
- GeoPackage never silently selects among multiple layers.
- Production citywide delivery should use PostGIS bbox queries, MVT/PMTiles and 3D Tiles. These
  adapters are ingestion boundaries, not an instruction to ship unbounded GeoJSON to a browser.

Fixtures in `backend/tests/test_municipal_adapters.py` are synthetic by design. Published CITY GAP
findings and scenario outputs remain derived only from the recorded official datasets.
