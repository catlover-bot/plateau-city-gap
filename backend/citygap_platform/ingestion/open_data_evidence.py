"""Deterministic evidence export for municipal open-data investigations."""

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
class OpenDataEvidenceArtifacts:
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


def _csv_safe(value: str) -> str:
    return f"'{value}" if value.startswith(("=", "+", "-", "@")) else value


def export_open_data_evidence(
    package: Mapping[str, Any], output_dir: str | Path, *, package_key: str
) -> OpenDataEvidenceArtifacts:
    required = {
        "cities",
        "urban_states",
        "source_timeline",
        "analyses",
        "findings",
        "source_contributions",
        "lineage",
        "missing_data",
        "limitations",
        "review_status",
        "human_workflow",
        "public_distribution",
    }
    missing = required - set(package)
    if missing:
        raise ValueError(f"Open-data evidence is missing required sections: {sorted(missing)}")
    if package["public_distribution"] is not False:
        raise ValueError("Municipal open-data evidence contains internal mesh context")
    workflow = package["human_workflow"]
    if not isinstance(workflow, Mapping):
        raise TypeError("human_workflow must be an object")
    if workflow.get("investigations_created") is not False:
        raise ValueError("Evidence export must not auto-create investigations")
    if workflow.get("decisions_created") is not False:
        raise ValueError("Evidence export must not auto-create decisions")

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    manifest_path = target / f"{package_key}_evidence.json"
    csv_path = target / f"{package_key}_evidence.csv"
    html_path = target / f"{package_key}_evidence.html"
    manifest = {
        "schema_version": "municipal-open-data-evidence-1.0.0",
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
        writer.writerows((_csv_safe(field), _csv_safe(value)) for field, value in rows)
    body = "\n".join(
        f"<tr><th>{html.escape(field)}</th><td>{html.escape(value)}</td></tr>"
        for field, value in rows
    )
    html_path.write_text(
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>CITY GAP Municipal Open Data Evidence</title>"
        "<style>body{font-family:sans-serif;margin:24px}table{border-collapse:collapse;"
        "width:100%}th,td{border:1px solid #bbb;padding:6px;text-align:left;"
        "vertical-align:top;overflow-wrap:anywhere}th{width:35%}"
        "@media print{body{margin:8mm}}</style></head><body>"
        f"<h1>CITY GAP Municipal Open Data Evidence</h1><table>{body}</table>"
        "</body></html>\n",
        encoding="utf-8",
    )
    return OpenDataEvidenceArtifacts(
        manifest_path=manifest_path,
        csv_path=csv_path,
        html_path=html_path,
        sha256={
            path.suffix.removeprefix("."): _digest(path)
            for path in (manifest_path, csv_path, html_path)
        },
    )
