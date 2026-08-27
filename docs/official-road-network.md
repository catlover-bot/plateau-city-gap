# Official PLATEAU road-network path

The official source was re-audited at commit
[`5f8d7662a01f58761c98bade02fd065884679b42`](https://github.com/Project-PLATEAU/PLATEAU-RoadNetwork-Generator/tree/5f8d7662a01f58761c98bade02fd065884679b42).

The official README says the tool uses PLATEAU roads, city furniture and bridges to
produce road and footpath node/link datasets as Shapefile or GeoJSON, plus error CSVs.
Its documented runtime is Windows 10/11. The checked application entry point is a
WinForms GUI with `Main()` taking no command-line arguments; the Create button calls a
native wrapper. The repository does not provide a supported batch/headless CLI or a
Windows GitHub Actions workflow. A custom harness might call the wrapper, but CITY GAP
does not claim that unsupported path as automated or verified.

## Production import

CITY GAP can receive the official `node.geojson`/`link.geojson` (or equivalent configured
layers) through `OfficialRoadNetworkAdapter` and `citygap network-import`. The official
source fields observed in source are:

- node: `node_id`;
- link: `link_id`, `start_id`, `end_id`, `distance`.

The adapter requires declared CRS, Point nodes, LineString links, unique IDs, valid
geometries and complete endpoint references. It reprojects into the city's analysis CRS,
content-hashes both inputs and creates an immutable network version. Operators must also
review the generator error CSV and field conditions before use.

Network semantics are stored explicitly as exactly one of:

- `official_walk`;
- `official_drive`;
- `experimental_surface_adjacency`.

The current Maizuru graph remains `experimental_surface_adjacency`; it is not renamed or
promoted to pedestrian routing. `accessibility_metric_versions` stores Euclidean,
experimental, official-drive and official-walk metrics side by side with fixed dataset,
network, algorithm and config versions. Importing official output never overwrites an
experimental result.

Example:

```bash
citygap network-import \
  --dataset-version-id UUID \
  --nodes node.geojson --edges link.geojson \
  --source-type official_walk --analysis-crs EPSG:6674 \
  --generator-commit 5f8d7662a01f58761c98bade02fd065884679b42 \
  --software-commit CITYGAP_COMMIT
```
