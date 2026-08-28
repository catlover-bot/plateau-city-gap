"""Small process-local cache for immutable, version-explicit vector tiles."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class VectorTileKey:
    city_id: str
    dataset_version_id: str
    network_version_id: str | None
    scenario_id: str | None
    algorithm_version: str | None
    layer: str
    z: int
    x: int
    y: int
    urban_state_id: str | None = None


@dataclass(frozen=True, slots=True)
class CachedVectorTile:
    content: bytes
    etag: str


class VersionedTileCache:
    """Bounded LRU cache; mutable/current aliases are deliberately unsupported."""

    def __init__(self, maximum_items: int = 512):
        if maximum_items <= 0:
            raise ValueError("maximum_items must be positive")
        self.maximum_items = maximum_items
        self._items: OrderedDict[VectorTileKey, CachedVectorTile] = OrderedDict()
        self._lock = RLock()

    def get(self, key: VectorTileKey) -> CachedVectorTile | None:
        with self._lock:
            value = self._items.get(key)
            if value is not None:
                self._items.move_to_end(key)
            return value

    def put(self, key: VectorTileKey, value: CachedVectorTile) -> None:
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self.maximum_items:
                self._items.popitem(last=False)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
