"""Build a truthful multi-city dataset/capability registry from existing real artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from backend.citygap_platform.domain.registry import CAPABILITIES, validate_platform_registry

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "analysis/outputs/real"
RESULT = OUTPUT / "platform_registry.json"
WEB_RESULT = ROOT / "frontend/public/data/platform_registry.json"
NAMESPACE = uuid.UUID("f7c2f938-3b5d-51ed-886e-79e1cfd8948f")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _generated_at() -> str:
    epoch = os.getenv("SOURCE_DATE_EPOCH")
    value = (
        datetime.fromtimestamp(int(epoch), tz=timezone.utc) if epoch else datetime.now(timezone.utc)
    )
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _identifier(kind: str, *parts: Any) -> str:
    return str(uuid.uuid5(NAMESPACE, ":".join([kind, *(str(part) for part in parts)])))


def _artifact(path: str) -> dict[str, Any]:
    source = ROOT / path
    if not source.exists():
        raise FileNotFoundError(source)
    return {"artifact": path, "sha256": _sha256(source), "verified_present": True}


def _capability(
    city_code: str,
    capability: str,
    status: str,
    note: str,
    evidence: list[dict[str, Any]] | None = None,
    dataset_version_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "city_code": city_code,
        "capability": capability,
        "status": status,
        "note": note,
        "evidence": evidence or [],
        "dataset_version_ids": dataset_version_ids or [],
    }


def build() -> dict[str, Any]:
    configurations = {}
    summaries = {}
    for slug in ("maizuru", "fujisawa"):
        config_path = ROOT / f"analysis/config/{slug}.yaml"
        summary_path = OUTPUT / f"{slug}_summary.json"
        configurations[slug] = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        summaries[slug] = json.loads(summary_path.read_text(encoding="utf-8"))

    inventory = json.loads((OUTPUT / "maizuru_plateau_inventory.json").read_text(encoding="utf-8"))
    cities = []
    datasets = []
    versions = []
    version_by_city_key: dict[tuple[str, str], str] = {}
    for slug, config in configurations.items():
        city_code = str(config["city_code"])
        cities.append(
            {
                "city_id": slug,
                "city_code": city_code,
                "name": config["city_name"],
                "prefecture_code": str(config["prefecture_code"]),
                "prefecture_name": config["prefecture_name"],
                "analysis_crs": config["analysis_crs"],
                "mode": config["mode"],
            }
        )
        summary_datasets = summaries[slug]["datasets"]
        for key, source in summary_datasets.items():
            dataset_id = _identifier("dataset", city_code, key)
            datasets.append(
                {
                    "dataset_id": dataset_id,
                    "city_code": city_code,
                    "dataset_key": key,
                    "title": source["title"],
                    "provider": source.get("provider", "Project PLATEAU"),
                }
            )
            year = int(source["year"])
            version_key = f"{year}:{source.get('version', 'source')}"
            version_id = _identifier("dataset-version", dataset_id, version_key)
            version_by_city_key[(city_code, key)] = version_id
            archive_sha256 = None
            archive_file = None
            if slug == "maizuru" and key == "plateau":
                archive_sha256 = inventory["archive"]["sha256"]
                archive_file = inventory["archive"]["file_name"]
            versions.append(
                {
                    "dataset_version_id": version_id,
                    "dataset_id": dataset_id,
                    "version_key": version_key,
                    "year": year,
                    "format": "CityGML" if key == "plateau" else "source GIS/statistics",
                    "source_url": source.get("source_url", source.get("url")),
                    "license": source.get("license"),
                    "declared_source_crs": source.get("declared_source_crs"),
                    "archive_file": archive_file,
                    "archive_sha256": archive_sha256,
                    "verification_status": (
                        "checksum_verified" if archive_sha256 else "metadata_registered"
                    ),
                }
            )

    maizuru_versions = [
        version_id
        for (city_code, _), version_id in version_by_city_key.items()
        if city_code == "26202"
    ]
    fujisawa_versions = [
        version_id
        for (city_code, _), version_id in version_by_city_key.items()
        if city_code == "14205"
    ]
    screening_evidence = {
        "26202": [_artifact("analysis/outputs/real/maizuru_summary.json")],
        "14205": [_artifact("analysis/outputs/real/fujisawa_summary.json")],
    }
    capabilities = [
        _capability(
            "26202",
            "screening",
            "available",
            "Real 500m census/facility screening is generated and validated.",
            screening_evidence["26202"],
            maizuru_versions,
        ),
        _capability(
            "26202",
            "building_detail",
            "available",
            "Actual CityGML buildings affect demographic allocation and accessibility.",
            [_artifact("analysis/outputs/real/maizuru_building_demographics_summary.json")],
            [version_by_city_key[("26202", "plateau")]],
        ),
        _capability(
            "26202",
            "road_network",
            "partial",
            "Experimental LOD1 surface-adjacency graph; not a validated pedestrian network.",
            [_artifact("analysis/outputs/real/maizuru_road_network_summary.json")],
            [version_by_city_key[("26202", "plateau")]],
        ),
        _capability(
            "26202",
            "terrain",
            "partial",
            "DEM endpoint observations are available; no walking-energy penalty is inferred.",
            [_artifact("analysis/outputs/real/maizuru_terrain_network_summary.json")],
            [version_by_city_key[("26202", "plateau")]],
        ),
    ]
    context_evidence = [_artifact("analysis/outputs/real/maizuru_plateau_context_summary.json")]
    for name in ("land_use", "urban_planning", "hazard"):
        capabilities.append(
            _capability(
                "26202",
                name,
                "available",
                "Official PLATEAU context is parsed and spatially joined; it remains review evidence.",
                context_evidence,
                [version_by_city_key[("26202", "plateau")]],
            )
        )
    capabilities.extend(
        [
            _capability(
                "26202",
                "gtfs",
                "unavailable",
                "P11 stop points are not GTFS; no feed is loaded and no service is fabricated.",
            ),
            _capability(
                "26202",
                "scenario",
                "available",
                "Verified network-aware 1-5 site alternatives are available.",
                [_artifact("analysis/outputs/real/maizuru_network_scenario_verification.json")],
                maizuru_versions,
            ),
        ]
    )
    capabilities.append(
        _capability(
            "14205",
            "screening",
            "available",
            "Real-data cross-city 500m screening is generated and validated.",
            screening_evidence["14205"],
            fujisawa_versions,
        )
    )
    for name in CAPABILITIES:
        if name == "screening":
            continue
        note = (
            "No GTFS feed is registered; P11 points are not represented as GTFS."
            if name == "gtfs"
            else "Capability has not been computed from Fujisawa source data in this platform."
        )
        capabilities.append(_capability("14205", name, "unavailable", note))

    run_specs = (
        ("26202", "screening", "analysis/outputs/real/maizuru_summary.json"),
        ("14205", "screening", "analysis/outputs/real/fujisawa_summary.json"),
        (
            "26202",
            "building_detail",
            "analysis/outputs/real/maizuru_building_demographics_summary.json",
        ),
        ("26202", "road_network", "analysis/outputs/real/maizuru_road_network_summary.json"),
        ("26202", "terrain", "analysis/outputs/real/maizuru_terrain_network_summary.json"),
        (
            "26202",
            "spatial_context",
            "analysis/outputs/real/maizuru_plateau_context_summary.json",
        ),
        (
            "26202",
            "scenario",
            "analysis/outputs/real/maizuru_network_scenarios.json",
        ),
    )
    analysis_runs = []
    for city_code, analysis_type, artifact_name in run_specs:
        artifact_path = ROOT / artifact_name
        config_slug = "maizuru" if city_code == "26202" else "fujisawa"
        config_path = ROOT / f"analysis/config/{config_slug}.yaml"
        analysis_runs.append(
            {
                "analysis_run_id": _identifier(
                    "analysis-run", city_code, analysis_type, _sha256(artifact_path)
                ),
                "city_code": city_code,
                "analysis_type": analysis_type,
                "status": "succeeded",
                "dataset_version_ids": (
                    maizuru_versions if city_code == "26202" else fujisawa_versions
                ),
                "config_hash": _sha256(config_path),
                "output_artifact": artifact_name,
                "output_sha256": _sha256(artifact_path),
            }
        )

    registry = {
        "schema_version": "1.0.0",
        "generated_at": _generated_at(),
        "cities": sorted(cities, key=lambda row: row["city_code"]),
        "datasets": sorted(datasets, key=lambda row: (row["city_code"], row["dataset_key"])),
        "dataset_versions": sorted(versions, key=lambda row: row["dataset_version_id"]),
        "analysis_runs": analysis_runs,
        "capabilities": sorted(capabilities, key=lambda row: (row["city_code"], row["capability"])),
        "policy": {
            "version_selection": "explicit dataset_version_id; never implicit latest",
            "unavailable_capabilities": "not fabricated",
            "gtfs": "P11 stop points do not establish GTFS availability",
        },
    }
    validate_platform_registry(registry)
    text = json.dumps(registry, ensure_ascii=False, indent=2) + "\n"
    RESULT.write_text(text, encoding="utf-8")
    WEB_RESULT.write_text(text, encoding="utf-8")
    return registry


def main() -> None:
    registry = build()
    print(
        json.dumps(
            {
                "cities": len(registry["cities"]),
                "datasets": len(registry["datasets"]),
                "dataset_versions": len(registry["dataset_versions"]),
                "analysis_runs": len(registry["analysis_runs"]),
                "capabilities": len(registry["capabilities"]),
                "output": str(RESULT.relative_to(ROOT)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
