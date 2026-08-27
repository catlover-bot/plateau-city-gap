"""Archive and upload inspection shared by CLI and future admin endpoints."""

from __future__ import annotations

import hashlib
import stat
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from backend.citygap_platform.ingestion.adapters import (
    DEFAULT_FILE_LIMIT,
    CityGmlSourceAdapter,
    CsvSourceAdapter,
    GeoJsonSourceAdapter,
    GeoPackageSourceAdapter,
    GtfsZipSourceAdapter,
)

UploadFormat = Literal["csv", "geojson", "geopackage", "gtfs", "citygml", "citygml_zip"]


@dataclass(frozen=True, slots=True)
class UploadInspection:
    source_format: str
    sha256: str
    size_bytes: int
    feature_or_row_count: int
    crs: str | None
    archive_member_count: int | None = None
    expanded_size_bytes: int | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_zip(
    path: str | Path,
    *,
    expected: Literal["gtfs", "citygml"],
    max_bytes: int = DEFAULT_FILE_LIMIT * 4,
    max_expanded_bytes: int = DEFAULT_FILE_LIMIT * 32,
    max_members: int = 20_000,
    max_compression_ratio: float = 200.0,
) -> UploadInspection:
    source = Path(path).resolve(strict=True)
    if source.suffix.lower() != ".zip" or not source.is_file():
        raise ValueError("Expected a regular ZIP file")
    if source.stat().st_size > max_bytes:
        raise ValueError("Archive exceeds compressed size limit")
    total = 0
    count = 0
    gtfs_names: set[str] = set()
    gml_count = 0
    with zipfile.ZipFile(source) as archive:
        infos = archive.infolist()
        if len(infos) > max_members:
            raise ValueError("Archive member count exceeds limit")
        for info in infos:
            normalized = info.filename.replace("\\", "/")
            member = PurePosixPath(normalized)
            mode = info.external_attr >> 16
            if member.is_absolute() or ".." in member.parts:
                raise ValueError("Archive contains path traversal")
            if stat.S_ISLNK(mode):
                raise ValueError("Archive symbolic links are prohibited")
            if info.flag_bits & 0x1:
                raise ValueError("Encrypted archive members are prohibited")
            total += info.file_size
            count += 1
            if total > max_expanded_bytes:
                raise ValueError("Archive expanded size exceeds limit")
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > max_compression_ratio:
                raise ValueError("Archive member compression ratio exceeds limit")
            if len(member.parts) == 1 and member.suffix.lower() == ".txt":
                gtfs_names.add(member.stem.lower())
            if member.suffix.lower() in {".gml", ".xml"}:
                gml_count += 1
                with archive.open(info) as stream:
                    prefix = stream.read(64 * 1024).upper()
                if b"<!DOCTYPE" in prefix or b"<!ENTITY" in prefix:
                    raise ValueError("CityGML DTD and entity declarations are prohibited")
    if expected == "gtfs":
        required = {"stops", "routes", "trips", "stop_times", "calendar", "calendar_dates"}
        if not required <= gtfs_names:
            raise ValueError(f"GTFS archive is missing tables: {sorted(required - gtfs_names)}")
        rows = 0
    else:
        if gml_count == 0:
            raise ValueError("CityGML archive contains no GML/XML members")
        rows = gml_count
    return UploadInspection(
        source_format="gtfs" if expected == "gtfs" else "citygml_zip",
        sha256=_sha256(source),
        size_bytes=source.stat().st_size,
        feature_or_row_count=rows,
        crs=None,
        archive_member_count=count,
        expanded_size_bytes=total,
    )


def inspect_upload(
    source_format: UploadFormat,
    path: str | Path,
    *,
    theme: str | None = None,
    layer: str | None = None,
) -> UploadInspection:
    if source_format == "citygml_zip":
        return inspect_zip(path, expected="citygml")
    if source_format == "gtfs":
        archive = inspect_zip(path, expected="gtfs")
        detail = GtfsZipSourceAdapter(path).inspect()
        return UploadInspection(
            source_format="gtfs",
            sha256=detail.sha256,
            size_bytes=detail.size_bytes,
            feature_or_row_count=detail.row_count,
            crs="EPSG:4326",
            archive_member_count=archive.archive_member_count,
            expanded_size_bytes=archive.expanded_size_bytes,
        )
    if source_format == "csv":
        result = CsvSourceAdapter(path).inspect()
    elif source_format == "geojson":
        result = GeoJsonSourceAdapter(path).inspect()
    elif source_format == "geopackage":
        result = GeoPackageSourceAdapter(path, layer=layer).inspect()
    elif source_format == "citygml":
        result = CityGmlSourceAdapter(path, theme=theme or "").inspect()
    else:
        raise ValueError(f"Unsupported upload format: {source_format}")
    return UploadInspection(
        source_format=source_format,
        sha256=result.sha256,
        size_bytes=result.size_bytes,
        feature_or_row_count=result.feature_count or result.row_count,
        crs=result.crs,
    )
