from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PUBLIC = Path("frontend/public")
IDENTIFIER_KEYS = {"gml_id", "building_gml_id", "building_id", "origin_reference"}
PER_BUILDING_MODEL_KEYS = {
    "estimated_population",
    "estimated_elderly_population",
    "estimated_future_population",
    "estimated_future_elderly_population",
}
MUNICIPAL_ONLY_KEYS = {
    "actor",
    "actor_id",
    "reviewer",
    "reviewer_identity",
    "field_note",
    "field_notes",
    "confidential_note",
    "municipal_only_metadata",
}


def _walk(value: Any, path: str = "$"):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def test_public_assets_do_not_expose_per_building_model_values_or_municipal_identity() -> None:
    violations: list[str] = []
    parsed_files = 0
    for source in sorted((PUBLIC / "data").rglob("*")):
        if source.suffix.lower() not in {".json", ".geojson"}:
            continue
        parsed_files += 1
        payload = json.loads(source.read_text(encoding="utf-8"))
        for path, value in _walk(payload):
            if not isinstance(value, dict):
                continue
            keys = {str(key).lower() for key in value}
            if keys & MUNICIPAL_ONLY_KEYS:
                violations.append(f"{source}:{path}:municipal-only key")
            if keys & IDENTIFIER_KEYS and keys & PER_BUILDING_MODEL_KEYS:
                violations.append(f"{source}:{path}:per-building modeled persons")
    assert parsed_files > 10
    assert violations == []


def test_public_validation_assets_have_no_email_actor_or_raw_parquet() -> None:
    validation = PUBLIC / "data" / "validation"
    assert validation.is_dir()
    assert not list(PUBLIC.rglob("*.parquet"))
    email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    for source in sorted(validation.rglob("*")):
        if source.is_file():
            text = source.read_text(encoding="utf-8")
            assert not email.search(text), source
            assert '"actor"' not in text.lower(), source
            assert '"confidential' not in text.lower(), source
