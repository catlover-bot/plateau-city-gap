from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from backend.citygap_platform.ingestion.profile import detect_archive_profile


def test_profile_uses_embedded_versions_instead_of_year(tmp_path: Path) -> None:
    archive = tmp_path / "package.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("README_op.md", "準拠\n3D都市モデル標準製品仕様書 第5.0版")
        target.writestr("schemas/iur/uro/3.2/urbanObject.xsd", "<schema />")
        target.writestr("schemas/iur/urf/3.2/urbanFunction.xsd", "<schema />")

    profile = detect_archive_profile(archive)

    assert profile.product_specification_version == "5.0"
    assert profile.ade_schema_versions == ("3.2",)
    assert profile.ade_schema_version == "3.2"


def test_profile_rejects_an_unversioned_package(tmp_path: Path) -> None:
    archive = tmp_path / "package.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("README.md", "version is intentionally absent")

    with pytest.raises(ValueError, match="specification version"):
        detect_archive_profile(archive)
