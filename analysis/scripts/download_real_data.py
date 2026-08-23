"""Download the four verified official inputs used by the real analysis."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Download:
    url: str
    path: Path
    sha256: str
    extract_to: Path | None = None


MAIZURU_DOWNLOADS = [
    Download(
        "https://www.e-stat.go.jp/gis/statmap-search/data?statsId=T001192&code=26&downloadType=2",
        Path("data/raw/population/tblT001192H26.zip"),
        "693a83a6274b21fdb90710d113e1c8c07c980ec353c67d39eefad1145a7c6d7e",
        Path("data/raw/population/tblT001192H26"),
    ),
    Download(
        "https://www.e-stat.go.jp/help/data-definition-information/downloaddata/T001192.pdf",
        Path("data/raw/population/T001192.pdf"),
        "33509ca18503892b4f7fd66e7afc01c472d8b9fa858eec312c61ea257f07f176",
    ),
    Download(
        "https://nlftp.mlit.go.jp/ksj/gml/data/P11/P11-22/P11-22_26_SHP.zip",
        Path("data/raw/transport/P11-22_26_SHP.zip"),
        "48e7368578c5e95ddd4577761a9d9c76e69b15a4727a51b84b4123ab77322e0d",
        Path("data/raw/transport/P11-22_26_SHP"),
    ),
    Download(
        "https://nlftp.mlit.go.jp/ksj/gml/data/P04/P04-20/P04-20_26_GML.zip",
        Path("data/raw/medical/P04-20_26_GML.zip"),
        "765a4970dc49b1f648e82e063df3d603fdcd24451ceb37b66ff5bd1da5404e62",
        Path("data/raw/medical/P04-20_26_GML"),
    ),
    Download(
        "https://assets.cms.plateau.reearth.io/assets/84/e288ba-d335-4537-86d4-23ddbcbc7413/26202_maizuru-shi_2025_related.zip",
        Path("data/raw/26202_maizuru-shi_2025_related.zip"),
        "475ac888be229f59a8020b463390a5ff625a480f43726aebd993fe6369c5ce4c",
        Path("data/raw/plateau_related"),
    ),
]

FUJISAWA_DOWNLOADS = [
    Download(
        "https://www.e-stat.go.jp/gis/statmap-search/data?statsId=T001192&code=14&downloadType=2",
        Path("data/raw/population/tblT001192H14.zip"),
        "855de51ccd520f2df5ee1cb3e2dcbe0152c278181d883e327a16f9b12ee475de",
        Path("data/raw/population/tblT001192H14"),
    ),
    Download(
        "https://nlftp.mlit.go.jp/ksj/gml/data/P11/P11-22/P11-22_14_SHP.zip",
        Path("data/raw/transport/P11-22_14_SHP.zip"),
        "f7dc18055d771db454416b0292a0c32bd0e4fbd475d1b94f41be8a10eba165f6",
        Path("data/raw/transport/P11-22_14_SHP"),
    ),
    Download(
        "https://nlftp.mlit.go.jp/ksj/gml/data/P04/P04-20/P04-20_14_GML.zip",
        Path("data/raw/medical/P04-20_14_GML.zip"),
        "505b630327c919cc4959d923c53d0ff3601dff63c3d76767be9d207c9cd7eb69",
        Path("data/raw/medical/P04-20_14_GML"),
    ),
    Download(
        "https://assets.cms.plateau.reearth.io/assets/b4/1dc466-782e-47b1-98d1-c7349d400c95/14205_fujisawa-shi_2025_related.zip",
        Path("data/raw/14205_fujisawa-shi_2025_related.zip"),
        "992a2310527c672e0ce7317a2c3cfdd97d53dcb5d5241fe3c3b8bd9a1daead19",
        Path("data/raw/plateau_related_fujisawa"),
    ),
]


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def download(item: Download) -> None:
    item.path.parent.mkdir(parents=True, exist_ok=True)
    if not item.path.exists() or digest(item.path) != item.sha256:
        temporary = item.path.with_suffix(item.path.suffix + ".part")
        request = urllib.request.Request(item.url, headers={"User-Agent": "CITY-GAP/0.1"})
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as out:
            shutil.copyfileobj(response, out)
        if digest(temporary) != item.sha256:
            temporary.unlink(missing_ok=True)
            raise ValueError(f"Checksum mismatch for {item.path}")
        temporary.replace(item.path)
    if item.extract_to is not None:
        item.extract_to.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(item.path) as archive:
            archive.testzip()
            archive.extractall(item.extract_to)
    print(f"verified {item.path} ({item.path.stat().st_size:,} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", choices=("maizuru", "fujisawa", "all"), default="maizuru")
    city = parser.parse_args().city
    downloads = {
        "maizuru": MAIZURU_DOWNLOADS,
        "fujisawa": FUJISAWA_DOWNLOADS,
        "all": MAIZURU_DOWNLOADS + FUJISAWA_DOWNLOADS,
    }[city]
    for item in downloads:
        download(item)


if __name__ == "__main__":
    main()
