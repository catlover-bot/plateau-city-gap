# Road network and accessibility design (Priority 3–4)

Network accessibility is not implemented or displayed as a measured result in Priority 1. The
existing competition metric remains centroid-to-facility Euclidean distance.

## Official-tool-first boundary

The preferred source is output from the official
[PLATEAU RoadNetwork Generator](https://github.com/Project-PLATEAU/PLATEAU-RoadNetwork-Generator),
which accepts road-related CityGML and emits road/walk node-link data as Shapefile or GeoJSON plus
error CSV. Its documented execution platform is Windows. CITY GAP should therefore provide an
open-format output adapter. A Linux/WSL fallback extractor, if built, must be labelled separately
and must not be presented as official-generator output.

## Planned schema and rules

`road_nodes` stores geometry/elevation; `road_edges` stores source, target, geometry, length,
elevation change, slope, road type, pedestrian permission and source `gml:id`. Unknown pedestrian
permission remains unknown, never silently true. Road polygons alone are not a routable or
walkable graph.

A building gets a `building origin representative point`, not an entrance, unless an official
entrance attribute exists. Snapping records node and distance; excessive distances create an
unconnected flag rather than a forced link.

Terrain sampling should attach start/end elevation, gain and mean slope to edges. Network length,
walking-time assumption and elevation burden remain separate outputs. Every detail view should
show Euclidean distance, network distance and elevation component independently, and call a
rendered route a network path only after topology-based routing succeeds.
