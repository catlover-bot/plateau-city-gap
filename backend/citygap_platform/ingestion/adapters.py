"""Bounded adapters for open municipal data formats.

The adapters stop at a validated, versionable source boundary. They do not
invent missing records, infer municipal meaning from filenames, or mark a
dataset as loaded into PostGIS. Synthetic inputs are used only by unit tests.
"""

from __future__ import annotations

import hashlib
import zipfile
import zlib
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

import geopandas as gpd
import pandas as pd

from backend.citygap_platform.domain.gtfs import GTFS_REQUIRED_COLUMNS, validate_gtfs_adapter
from backend.citygap_platform.ingestion.citygml import (
    CityGMLEvent,
    FeatureEnd,
    FeatureStart,
    GeometryPart,
    iter_citygml_events,
)

SourceFormat = Literal["citygml", "gtfs", "csv", "geojson", "geopackage"]
DEFAULT_FILE_LIMIT = 512 * 1024 * 1024
DEFAULT_ROW_LIMIT = 1_000_000
DEFAULT_GEOMETRY_BYTE_LIMIT = 16 * 1024 * 1024


@dataclass(frozen=True)
class SourceInspection:
    """Auditable facts measured from one source without persisting it."""

    source_format: SourceFormat
    source_identifier: str
    sha256: str
    size_bytes: int
    row_count: int
    columns: tuple[str, ...] = ()
    crs: str | None = None
    layer: str | None = None
    geometry_types: tuple[str, ...] = ()
    feature_count: int | None = None
    geometry_part_count: int | None = None
    duplicate_id_count: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _checked_path(
    path: str | Path,
    *,
    suffixes: Sequence[str],
    max_bytes: int,
    allow_extensionless: bool = False,
) -> Path:
    source = Path(path).resolve(strict=True)
    if not source.is_file():
        raise ValueError("Municipal source must be a regular file")
    if source.suffix.lower() not in suffixes and not (allow_extensionless and source.suffix == ""):
        raise ValueError(f"Expected one of these source extensions: {sorted(suffixes)}")
    size = source.stat().st_size
    if size > max_bytes:
        raise ValueError(f"Municipal source exceeds the {max_bytes}-byte input limit")
    return source


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _crc32(path: Path) -> str:
    checksum = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            checksum = zlib.crc32(chunk, checksum)
    return f"{checksum & 0xFFFFFFFF:08x}"


def _require_columns(frame: pd.DataFrame, required_columns: Sequence[str]) -> None:
    missing = set(required_columns) - set(frame.columns)
    if missing:
        raise ValueError(f"Municipal source is missing columns: {sorted(missing)}")


def _is_formula_like(value: object) -> bool:
    """Detect spreadsheet execution prefixes without misclassifying negative numbers."""

    text = str(value)
    if not text:
        return False
    stripped = text.lstrip(" ")
    if not stripped:
        return False
    if stripped[0] in {"=", "+", "@", "\t", "\r"}:
        return True
    return (
        stripped.startswith("-")
        and len(stripped) > 1
        and not (stripped[1].isdigit() or stripped[1] == ".")
    )


def _reject_formula_like_cells(frame: pd.DataFrame, source_name: str) -> None:
    for value in frame.to_numpy(copy=False).flat:
        if _is_formula_like(value):
            raise ValueError(f"{source_name} contains a formula-like cell and requires review")


class CsvSourceAdapter:
    """Read a bounded CSV while preserving identifiers such as zero-padded mesh codes."""

    source_format: SourceFormat = "csv"

    def __init__(
        self,
        path: str | Path,
        *,
        required_columns: Sequence[str] = (),
        encoding: str = "utf-8-sig",
        max_bytes: int = DEFAULT_FILE_LIMIT,
        max_rows: int = DEFAULT_ROW_LIMIT,
        allow_extensionless: bool = False,
    ) -> None:
        self.path = _checked_path(
            path,
            suffixes=(".csv",),
            max_bytes=max_bytes,
            allow_extensionless=allow_extensionless,
        )
        self.required_columns = tuple(required_columns)
        self.encoding = encoding
        self.max_rows = max_rows
        self._frame: pd.DataFrame | None = None

    @property
    def source_identifier(self) -> str:
        return f"csv:{_sha256(self.path)}"

    def dataframe(self) -> pd.DataFrame:
        if self._frame is None:
            frame = pd.read_csv(
                self.path,
                encoding=self.encoding,
                dtype=str,
                keep_default_na=False,
                nrows=self.max_rows + 1,
            )
            if len(frame) > self.max_rows:
                raise ValueError(f"CSV exceeds the {self.max_rows}-row inspection limit")
            _require_columns(frame, self.required_columns)
            _reject_formula_like_cells(frame, "CSV")
            self._frame = frame
        return self._frame.copy()

    def inspect(self) -> SourceInspection:
        frame = self.dataframe()
        digest = _sha256(self.path)
        return SourceInspection(
            source_format=self.source_format,
            source_identifier=f"csv:{digest}",
            sha256=digest,
            size_bytes=self.path.stat().st_size,
            row_count=len(frame),
            columns=tuple(str(column) for column in frame.columns),
        )


class VectorSourceAdapter:
    """Bounded GeoJSON/GeoPackage reader with explicit layer and CRS checks."""

    def __init__(
        self,
        path: str | Path,
        *,
        source_format: Literal["geojson", "geopackage"],
        layer: str | None = None,
        required_columns: Sequence[str] = (),
        declared_crs: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
        max_bytes: int = DEFAULT_FILE_LIMIT,
        max_rows: int = DEFAULT_ROW_LIMIT,
        max_geometry_bytes: int = DEFAULT_GEOMETRY_BYTE_LIMIT,
    ) -> None:
        suffixes = (".geojson", ".json") if source_format == "geojson" else (".gpkg",)
        self.path = _checked_path(path, suffixes=suffixes, max_bytes=max_bytes)
        self.source_format: SourceFormat = source_format
        self.layer = layer
        self.required_columns = tuple(required_columns)
        self.declared_crs = declared_crs
        self.bbox = bbox
        self.max_rows = max_rows
        self.max_geometry_bytes = max_geometry_bytes
        self._frame: gpd.GeoDataFrame | None = None

    def _resolved_layer(self) -> str | None:
        if self.source_format != "geopackage":
            return self.layer
        import pyogrio

        layers = tuple(str(row[0]) for row in pyogrio.list_layers(self.path))
        if not layers:
            raise ValueError("GeoPackage contains no readable layers")
        if self.layer is None and len(layers) > 1:
            raise ValueError("GeoPackage layer is required when multiple layers exist")
        selected = self.layer or layers[0]
        if selected not in layers:
            raise ValueError(f"GeoPackage layer does not exist: {selected}")
        return selected

    @property
    def source_identifier(self) -> str:
        layer = self._resolved_layer()
        suffix = f":{layer}" if layer else ""
        return f"{self.source_format}:{_sha256(self.path)}{suffix}"

    def dataframe(self) -> gpd.GeoDataFrame:
        if self._frame is None:
            selected_layer = self._resolved_layer()
            frame = gpd.read_file(
                self.path,
                layer=selected_layer,
                bbox=self.bbox,
                rows=slice(0, self.max_rows + 1),
                engine="pyogrio",
            )
            if len(frame) > self.max_rows:
                raise ValueError(f"Vector source exceeds the {self.max_rows}-feature limit")
            _require_columns(frame, self.required_columns)
            if frame.crs is None and self.declared_crs:
                frame = frame.set_crs(self.declared_crs, allow_override=False)
            if frame.crs is None:
                raise ValueError("Vector source must declare a coordinate reference system")
            if frame.geometry.name not in frame.columns:
                raise ValueError("Vector source has no geometry column")
            if frame.geometry.isna().any() or (~frame.geometry.is_valid).any():
                raise ValueError("Vector source contains missing or invalid geometry")
            if any(len(geometry.wkb) > self.max_geometry_bytes for geometry in frame.geometry):
                raise ValueError("Vector source contains an oversized geometry")
            self.layer = selected_layer
            self._frame = frame
        return self._frame.copy()

    def inspect(self) -> SourceInspection:
        frame = self.dataframe()
        digest = _sha256(self.path)
        suffix = f":{self.layer}" if self.layer else ""
        geometry_types = tuple(sorted(str(value) for value in frame.geom_type.unique()))
        return SourceInspection(
            source_format=self.source_format,
            source_identifier=f"{self.source_format}:{digest}{suffix}",
            sha256=digest,
            size_bytes=self.path.stat().st_size,
            row_count=len(frame),
            columns=tuple(str(column) for column in frame.columns),
            crs=str(frame.crs),
            layer=self.layer,
            geometry_types=geometry_types,
            feature_count=len(frame),
        )


class GeoJsonSourceAdapter(VectorSourceAdapter):
    def __init__(self, path: str | Path, **kwargs: Any) -> None:
        super().__init__(path, source_format="geojson", **kwargs)


class GeoPackageSourceAdapter(VectorSourceAdapter):
    def __init__(self, path: str | Path, **kwargs: Any) -> None:
        super().__init__(path, source_format="geopackage", **kwargs)


class GtfsZipSourceAdapter:
    """Read the six declared GTFS tables from a bounded, traversal-safe ZIP."""

    source_format: SourceFormat = "gtfs"

    def __init__(
        self,
        path: str | Path,
        *,
        max_bytes: int = DEFAULT_FILE_LIMIT,
        max_uncompressed_bytes: int = 2 * DEFAULT_FILE_LIMIT,
        max_rows_per_table: int = DEFAULT_ROW_LIMIT,
    ) -> None:
        self.path = _checked_path(path, suffixes=(".zip",), max_bytes=max_bytes)
        self.max_uncompressed_bytes = max_uncompressed_bytes
        self.max_rows_per_table = max_rows_per_table
        self._members = self._validate_archive()
        self._tables: dict[str, pd.DataFrame] = {}

    @property
    def source_identifier(self) -> str:
        return f"gtfs:{_sha256(self.path)}"

    def _validate_archive(self) -> dict[str, str]:
        members: dict[str, str] = {}
        total_size = 0
        with zipfile.ZipFile(self.path) as archive:
            for info in archive.infolist():
                normalized = info.filename.replace("\\", "/")
                member_path = PurePosixPath(normalized)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise ValueError("GTFS archive contains an unsafe member path")
                if info.flag_bits & 0x1:
                    raise ValueError("Encrypted GTFS members are not supported")
                total_size += info.file_size
                if total_size > self.max_uncompressed_bytes:
                    raise ValueError("GTFS archive exceeds the uncompressed input limit")
                if len(member_path.parts) == 1 and member_path.suffix.lower() == ".txt":
                    key = member_path.stem.lower()
                    if key in members:
                        raise ValueError(f"GTFS archive contains duplicate table: {key}")
                    members[key] = info.filename
        missing = set(GTFS_REQUIRED_COLUMNS) - set(members)
        if missing:
            raise ValueError(f"GTFS archive is missing tables: {sorted(missing)}")
        return members

    def table(self, name: str) -> pd.DataFrame:
        if name not in GTFS_REQUIRED_COLUMNS:
            raise KeyError(f"Unknown GTFS table: {name}")
        if name not in self._tables:
            with zipfile.ZipFile(self.path) as archive, archive.open(self._members[name]) as stream:
                frame = pd.read_csv(
                    stream,
                    dtype=str,
                    keep_default_na=False,
                    nrows=self.max_rows_per_table + 1,
                )
            if len(frame) > self.max_rows_per_table:
                raise ValueError(
                    f"GTFS {name} exceeds the {self.max_rows_per_table}-row inspection limit"
                )
            _reject_formula_like_cells(frame, f"GTFS {name}")
            self._tables[name] = frame
        return self._tables[name].copy()

    def inspect(self) -> SourceInspection:
        counts = validate_gtfs_adapter(self)
        digest = _sha256(self.path)
        return SourceInspection(
            source_format=self.source_format,
            source_identifier=f"gtfs:{digest}",
            sha256=digest,
            size_bytes=self.path.stat().st_size,
            row_count=sum(counts.values()),
            columns=tuple(sorted(GTFS_REQUIRED_COLUMNS)),
        )


class CityGmlSourceAdapter:
    """Expose the existing event-oriented PLATEAU CityGML reader as an adapter."""

    source_format: SourceFormat = "citygml"

    def __init__(
        self,
        path: str | Path,
        *,
        theme: str,
        source_member: str | None = None,
        coordinate_dimension: int = 3,
        max_bytes: int = 2 * DEFAULT_FILE_LIMIT,
    ) -> None:
        if not theme.strip():
            raise ValueError("CityGML adapter requires an explicit theme")
        self.path = _checked_path(path, suffixes=(".gml", ".xml"), max_bytes=max_bytes)
        self.theme = theme.strip().lower()
        self.source_member = source_member or self.path.name
        self.coordinate_dimension = coordinate_dimension
        self._sha256 = _sha256(self.path)
        self._crc32 = _crc32(self.path)

    @property
    def source_identifier(self) -> str:
        return f"citygml:{self._sha256}:{self.source_member}"

    def events(self) -> Iterator[CityGMLEvent]:
        with self.path.open("rb") as stream:
            yield from iter_citygml_events(
                stream,
                theme=self.theme,
                source_member=self.source_member,
                source_member_crc32=self._crc32,
                coordinate_dimension=self.coordinate_dimension,
            )

    def inspect(self) -> SourceInspection:
        ids: set[str] = set()
        feature_count = 0
        geometry_part_count = 0
        duplicate_id_count = 0
        crs_names: set[str] = set()
        for event in self.events():
            if isinstance(event, FeatureStart):
                if event.gml_id in ids:
                    duplicate_id_count += 1
                ids.add(event.gml_id)
            elif isinstance(event, GeometryPart):
                geometry_part_count += 1
                if event.source_crs:
                    crs_names.add(event.source_crs)
            elif isinstance(event, FeatureEnd):
                feature_count += 1
                crs_names.update(event.source_crs)
        return SourceInspection(
            source_format=self.source_format,
            source_identifier=self.source_identifier,
            sha256=self._sha256,
            size_bytes=self.path.stat().st_size,
            row_count=feature_count,
            crs=" | ".join(sorted(crs_names)) or None,
            layer=self.theme,
            feature_count=feature_count,
            geometry_part_count=geometry_part_count,
            duplicate_id_count=duplicate_id_count,
        )


def open_municipal_source(
    source_format: SourceFormat,
    path: str | Path,
    **kwargs: Any,
) -> CsvSourceAdapter | VectorSourceAdapter | GtfsZipSourceAdapter | CityGmlSourceAdapter:
    """Create an explicit adapter; format detection from a filename is intentionally avoided."""

    adapters = {
        "citygml": CityGmlSourceAdapter,
        "gtfs": GtfsZipSourceAdapter,
        "csv": CsvSourceAdapter,
        "geojson": GeoJsonSourceAdapter,
        "geopackage": GeoPackageSourceAdapter,
    }
    try:
        adapter = adapters[source_format]
    except KeyError as error:
        raise ValueError(f"Unsupported municipal source format: {source_format}") from error
    return adapter(path, **kwargs)
