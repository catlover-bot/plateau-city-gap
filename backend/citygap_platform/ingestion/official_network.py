"""Import immutable outputs from the official PLATEAU RoadNetwork Generator."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import geopandas as gpd

OfficialNetworkSource = Literal["official_walk", "official_drive"]


@dataclass(frozen=True, slots=True)
class OfficialNetworkFieldMap:
    node_id: str = "node_id"
    edge_id: str = "link_id"
    source_node_id: str = "start_id"
    target_node_id: str = "end_id"
    length_m: str | None = "distance"


@dataclass(frozen=True, slots=True)
class OfficialNetworkInspection:
    source_type: OfficialNetworkSource
    graph_version: str
    config_hash: str
    node_count: int
    edge_count: int
    component_count: int
    analysis_crs: str


class OfficialRoadNetworkAdapter:
    def __init__(
        self,
        nodes_path: str | Path,
        edges_path: str | Path,
        *,
        source_type: OfficialNetworkSource,
        fields: OfficialNetworkFieldMap,
        analysis_crs: str,
        nodes_layer: str | None = None,
        edges_layer: str | None = None,
    ) -> None:
        if source_type not in {"official_walk", "official_drive"}:
            raise ValueError("Official adapter accepts only official_walk or official_drive")
        self.nodes_path = Path(nodes_path).resolve(strict=True)
        self.edges_path = Path(edges_path).resolve(strict=True)
        self.source_type = source_type
        self.fields = fields
        self.analysis_crs = analysis_crs
        self.nodes_layer = nodes_layer
        self.edges_layer = edges_layer
        self._nodes: gpd.GeoDataFrame | None = None
        self._edges: gpd.GeoDataFrame | None = None

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def frames(self) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        if self._nodes is None or self._edges is None:
            nodes = gpd.read_file(self.nodes_path, layer=self.nodes_layer, engine="pyogrio")
            edges = gpd.read_file(self.edges_path, layer=self.edges_layer, engine="pyogrio")
            if nodes.crs is None or edges.crs is None:
                raise ValueError("Official network inputs must declare CRS")
            required_nodes = {self.fields.node_id}
            required_edges = {
                self.fields.edge_id,
                self.fields.source_node_id,
                self.fields.target_node_id,
            }
            if not required_nodes <= set(nodes.columns) or not required_edges <= set(edges.columns):
                raise ValueError("Official network input is missing configured ID fields")
            if nodes.empty or edges.empty:
                raise ValueError("Official network inputs cannot be empty")
            if nodes.geometry.isna().any() or edges.geometry.isna().any():
                raise ValueError("Official network contains missing geometry")
            if (~nodes.geometry.is_valid).any() or (~edges.geometry.is_valid).any():
                raise ValueError("Official network contains invalid geometry")
            if not set(nodes.geom_type) <= {"Point"}:
                raise ValueError("Official nodes must be Point geometry")
            if not set(edges.geom_type) <= {"LineString"}:
                raise ValueError("Official edges must be LineString geometry")
            nodes = nodes.to_crs(self.analysis_crs)
            edges = edges.to_crs(self.analysis_crs).reset_index(drop=True)
            node_ids = nodes[self.fields.node_id].astype(str)
            edge_ids = edges[self.fields.edge_id].astype(str)
            if node_ids.duplicated().any() or edge_ids.duplicated().any():
                raise ValueError("Official network IDs must be unique after geometry normalization")
            referenced = set(edges[self.fields.source_node_id].astype(str)) | set(
                edges[self.fields.target_node_id].astype(str)
            )
            if not referenced <= set(node_ids):
                raise ValueError("Official edge references an unknown node")
            self._nodes, self._edges = nodes, edges
        return self._nodes.copy(), self._edges.copy()

    def _components(self, nodes: gpd.GeoDataFrame, edges: gpd.GeoDataFrame) -> int:
        parent = {str(value): str(value) for value in nodes[self.fields.node_id]}

        def find(value: str) -> str:
            while parent[value] != value:
                parent[value] = parent[parent[value]]
                value = parent[value]
            return value

        for _, row in edges.iterrows():
            source = str(row[self.fields.source_node_id])
            target = str(row[self.fields.target_node_id])
            source_root, target_root = find(source), find(target)
            if source_root != target_root:
                parent[target_root] = source_root
        return len({find(value) for value in parent})

    def inspect(self) -> OfficialNetworkInspection:
        nodes, edges = self.frames()
        payload = {
            "nodes_sha256": self._sha256(self.nodes_path),
            "edges_sha256": self._sha256(self.edges_path),
            "source_type": self.source_type,
            "fields": asdict(self.fields),
            "analysis_crs": self.analysis_crs,
        }
        config_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return OfficialNetworkInspection(
            source_type=self.source_type,
            graph_version=f"official-{self.source_type.removeprefix('official_')}-{config_hash[:16]}",
            config_hash=config_hash,
            node_count=len(nodes),
            edge_count=len(edges),
            component_count=self._components(nodes, edges),
            analysis_crs=self.analysis_crs,
        )


def load_official_network(
    database_url: str,
    dataset_version_id: str,
    adapter: OfficialRoadNetworkAdapter,
    *,
    generator_commit: str,
    software_commit: str,
) -> dict[str, object]:
    import psycopg

    nodes, edges = adapter.frames()
    inspection = adapter.inspect()
    network_type = "walk" if adapter.source_type == "official_walk" else "road"
    permission = "official_walk" if adapter.source_type == "official_walk" else "official_drive"
    with psycopg.connect(database_url) as connection:
        network_id = connection.execute(
            """INSERT INTO road_network_versions (
                   dataset_version_id, graph_version, graph_method, network_type, source_type,
                   official_generator_repository, official_generator_commit,
                   official_generator_executed, pedestrian_network, route_semantics,
                   analysis_crs, config_hash, node_count, edge_count, component_count,
                   generated_at, software_commit, metadata
               ) VALUES (%s,%s,'PLATEAU-RoadNetwork-Generator',%s,%s,%s,%s,true,%s,%s,%s,
                         %s,%s,%s,%s,now(),%s,%s)
               ON CONFLICT (dataset_version_id, graph_version) DO UPDATE
                   SET graph_version=EXCLUDED.graph_version RETURNING id""",
            (
                dataset_version_id,
                inspection.graph_version,
                network_type,
                adapter.source_type,
                "https://github.com/Project-PLATEAU/PLATEAU-RoadNetwork-Generator",
                generator_commit,
                adapter.source_type == "official_walk",
                "official generator output; verify generator error CSV and field conditions",
                adapter.analysis_crs,
                inspection.config_hash,
                inspection.node_count,
                inspection.edge_count,
                inspection.component_count,
                software_commit,
                json.dumps({"input": asdict(inspection)}, ensure_ascii=False),
            ),
        ).fetchone()[0]
        for _, row in nodes.iterrows():
            node_id = str(row[adapter.fields.node_id])
            connection.execute(
                """INSERT INTO road_network_nodes (
                       network_version_id, node_id, component_id, pedestrian_permission, geom
                   ) VALUES (%s,%s,'official-import',%s,ST_GeomFromWKB(%s,%s))
                   ON CONFLICT (network_version_id,node_id) DO NOTHING""",
                (
                    network_id,
                    node_id,
                    permission,
                    row.geometry.wkb,
                    adapter.analysis_crs.split(":")[-1],
                ),
            )
        for _, row in edges.iterrows():
            edge_id = str(row[adapter.fields.edge_id])
            length = (
                float(row[adapter.fields.length_m])
                if adapter.fields.length_m
                else float(row.geometry.length)
            )
            if length <= 0:
                raise ValueError("Official network edge length must be positive")
            connection.execute(
                """INSERT INTO road_network_edges (
                       network_version_id, edge_id, source_node_id, target_node_id,
                       length_m, topology_relation, pedestrian_permission, geom
                   ) VALUES (%s,%s,%s,%s,%s,'official_generator',%s,
                             ST_GeomFromWKB(%s,%s))
                   ON CONFLICT (network_version_id,edge_id) DO NOTHING""",
                (
                    network_id,
                    edge_id,
                    str(row[adapter.fields.source_node_id]),
                    str(row[adapter.fields.target_node_id]),
                    length,
                    permission,
                    row.geometry.wkb,
                    adapter.analysis_crs.split(":")[-1],
                ),
            )
        connection.commit()
    return {"network_version_id": str(network_id), **asdict(inspection)}
