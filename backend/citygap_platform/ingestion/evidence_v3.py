"""Deterministic Temporal/Resilience Evidence Package V3 export."""

from __future__ import annotations

import csv
import hashlib
import html
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class EvidenceV3Artifacts:
    manifest_path: Path
    csv_path: Path
    html_path: Path
    sha256: Mapping[str, str]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _flatten(prefix: str, value: object, rows: list[tuple[str, str]]) -> None:
    if isinstance(value, dict):
        for key in sorted(value):
            _flatten(f"{prefix}.{key}" if prefix else str(key), value[key], rows)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _flatten(f"{prefix}[{index}]", item, rows)
    else:
        rows.append((prefix, "" if value is None else str(value)))


def export_evidence_v3(
    package: Mapping[str, Any], output_dir: str | Path, *, package_key: str
) -> EvidenceV3Artifacts:
    required = {
        "city",
        "urban_state",
        "dataset_years",
        "network",
        "assumptions",
        "stress_test",
        "affected_areas",
        "critical_roads",
        "scenario_alternatives",
        "limitations",
        "field_verification",
    }
    missing = required - set(package)
    if missing:
        raise ValueError(f"Evidence V3 is missing required sections: {sorted(missing)}")
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    stem = f"{package_key}-evidence-v3"
    manifest_path = target / f"{stem}.json"
    csv_path = target / f"{stem}.csv"
    html_path = target / f"{stem}.html"
    manifest = {
        "schema_version": "evidence-v3.0.0",
        "generation_method": "deterministic structured export",
        **dict(package),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rows: list[tuple[str, str]] = []
    _flatten("", manifest, rows)
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("field", "value"))
        writer.writerows(rows)
    body = "\n".join(
        f"<tr><th>{html.escape(field)}</th><td>{html.escape(value)}</td></tr>"
        for field, value in rows
    )
    html_path.write_text(
        "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>CITY GAP Evidence V3</title><style>body{font-family:sans-serif;margin:24px}"
        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #bbb;padding:6px;"
        "text-align:left;vertical-align:top}th{width:35%}@media print{body{margin:8mm}}</style>"
        f"</head><body><h1>CITY GAP Evidence V3</h1><table>{body}</table></body></html>\n",
        encoding="utf-8",
    )
    return EvidenceV3Artifacts(
        manifest_path,
        csv_path,
        html_path,
        {path.suffix.removeprefix("."): _digest(path) for path in (manifest_path, csv_path, html_path)},
    )
