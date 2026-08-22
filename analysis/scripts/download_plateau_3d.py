"""Download and safely extract the verified Maizuru 2025 PLATEAU building tiles."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
import zlib
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPOSITORY_ROOT / "data/raw/plateau_3d"
ARCHIVE = RAW_DIR / "26202_maizuru-shi_city_2025_3dtiles_mvt_1_op.zip"
EXTRACTED = RAW_DIR / "extracted"
OFFICIAL_URL = (
    "https://assets.cms.plateau.reearth.io/assets/55/"
    "2c1991-f75e-4bf8-9108-531c27952a2b/"
    "26202_maizuru-shi_city_2025_3dtiles_mvt_1_op.zip"
)
EXPECTED_BYTES = 160_582_905
EXPECTED_SHA256 = (
    "15cf5e12b507b89e2b86fe0c2968a22e8d770ea36cb8c64cc7e8db578109f2d9"
)
BUILDING_DIRECTORIES = (
    "26202_maizuru-shi_city_2025_citygml_1_op_bldg_3dtiles_lod1",
    "26202_maizuru-shi_city_2025_citygml_1_op_bldg_3dtiles_lod2",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def crc32(path: Path) -> int:
    checksum = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum = zlib.crc32(block, checksum)
    return checksum & 0xFFFFFFFF


def validate_archive(path: Path) -> None:
    if path.stat().st_size != EXPECTED_BYTES or sha256(path) != EXPECTED_SHA256:
        raise ValueError("PLATEAU archive does not match the pinned official package")


def download_archive(path: Path = ARCHIVE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("PLATEAU archive target must not be a symlink")
    if path.is_file():
        validate_archive(path)
        return
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".part", dir=path.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    request = Request(OFFICIAL_URL, headers={"User-Agent": "CITY-GAP/0.1"})
    try:
        with urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        validate_archive(temporary)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members: list[zipfile.ZipInfo] = []
    counts = {directory: 0 for directory in BUILDING_DIRECTORIES}
    for member in archive.infolist():
        pure = PurePosixPath(member.filename)
        if pure.is_absolute() or ".." in pure.parts:
            raise ValueError(f"Unsafe path in PLATEAU archive: {member.filename}")
        if not pure.parts or pure.parts[0] not in BUILDING_DIRECTORIES:
            continue
        if member.is_dir():
            continue
        if pure.name != "tileset.json" and pure.suffix != ".b3dm":
            continue
        members.append(member)
        counts[pure.parts[0]] += 1
    if set(counts.values()) != {428}:
        raise ValueError(f"Unexpected PLATEAU building archive contents: {counts}")
    return members


def extract_buildings(
    archive_path: Path = ARCHIVE, output_dir: Path = EXTRACTED
) -> dict[str, int]:
    if output_dir.is_symlink():
        raise ValueError("PLATEAU extraction target must not be a symlink")
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted_files = 0
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("PLATEAU ZIP integrity check failed")
        members = _safe_members(archive)
        for member in members:
            destination = output_dir.joinpath(*PurePosixPath(member.filename).parts)
            if destination.is_symlink():
                raise ValueError(f"Refusing to replace a symlink: {destination}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            parent = destination.parent
            while parent != output_dir.parent:
                if parent.is_symlink():
                    raise ValueError(f"Refusing to traverse a symlink: {parent}")
                parent = parent.parent
            if (
                destination.is_file()
                and destination.stat().st_size == member.file_size
                and crc32(destination) == member.CRC
            ):
                extracted_files += 1
                continue
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.",
                suffix=".part",
                dir=destination.parent,
            )
            os.close(descriptor)
            temporary = Path(temporary_name)
            try:
                with archive.open(member) as source, temporary.open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                if (
                    temporary.stat().st_size != member.file_size
                    or crc32(temporary) != member.CRC
                ):
                    raise ValueError(
                        f"Incomplete PLATEAU extraction: {member.filename}"
                    )
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
            extracted_files += 1
    return {"building_files": extracted_files}


def main() -> None:
    download_archive()
    extracted = extract_buildings()
    print(
        json.dumps(
            {
                "archive": ARCHIVE.relative_to(REPOSITORY_ROOT).as_posix(),
                "bytes": ARCHIVE.stat().st_size,
                "sha256": sha256(ARCHIVE),
                "extracted": extracted,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
