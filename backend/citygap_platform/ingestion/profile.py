"""Detect the version profile embedded in a PLATEAU delivery package."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

SPEC_PATTERN = re.compile(r"標準製品仕様書\s*第\s*([0-9]+\.[0-9]+)\s*版")
ADE_PATH_PATTERN = re.compile(r"(?:^|/)schemas/iur/(?:uro|urf)/([^/]+)/")


@dataclass(frozen=True)
class ArchiveProfile:
    product_specification_version: str
    ade_schema_versions: tuple[str, ...]
    readme_member: str

    @property
    def ade_schema_version(self) -> str | None:
        return self.ade_schema_versions[0] if len(self.ade_schema_versions) == 1 else None


def detect_archive_profile(archive_path: str | Path) -> ArchiveProfile:
    """Read package metadata without inferring a version from the publication year."""

    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        readmes = [name for name in names if Path(name).name.lower().startswith("readme")]
        if not readmes:
            raise ValueError("PLATEAU archive does not contain a README")
        readme_member = min(readmes)
        readme = archive.read(readme_member).decode("utf-8-sig")
        match = SPEC_PATTERN.search(readme)
        if not match:
            raise ValueError("PLATEAU product specification version was not found in README")
        ade_versions = tuple(
            sorted(
                {
                    version.group(1)
                    for name in names
                    if (version := ADE_PATH_PATTERN.search(name))
                }
            )
        )
    return ArchiveProfile(match.group(1), ade_versions, readme_member)
