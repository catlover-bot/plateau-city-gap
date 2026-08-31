"""Build a machine-readable West Maizuru 500m/800m A5 comparison.

The comparison joins the deterministic Area fixture, the census mesh disclosure
state, and the production-browser checkpoint. It never calculates a composite
score or creates field evidence.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[2]
AREA_FIXTURE = ROOT / "frontend/public/data/investigation_area_summary.json"
MESH_SOURCE = ROOT / "frontend/public/data/mesh_metrics.geojson"
BROWSER_MANIFEST = ROOT / "docs/assets/area-checkpoint/manifest.json"
OUTPUT = ROOT / "analysis/outputs/real/maizuru_area_500_800_comparison.json"
ANALYSIS_CRS = "EPSG:6674"
EXPECTED_RADII = (500, 800)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def mesh_disclosure_audit(
    meshes: gpd.GeoDataFrame,
    effective_geometry: dict[str, Any],
) -> dict[str, Any]:
    area = gpd.GeoSeries([shape(effective_geometry)], crs=4326).to_crs(ANALYSIS_CRS).iloc[0]
    intersecting = meshes.loc[meshes.geometry.intersects(area)].copy()
    records: list[dict[str, Any]] = []
    covered_population_area = 0.0
    covered_age_area = 0.0
    status_counts: Counter[str] = Counter()

    for row in intersecting.sort_values("mesh_code").itertuples():
        intersection_area = row.geometry.intersection(area).area
        if intersection_area <= 0:
            continue
        overlap_ratio = min(1.0, intersection_area / row.geometry.area)
        population_available = pd.notna(row.population)
        age_available = pd.notna(row.elderly_population)
        disclosure_status = str(row.disclosure_status)
        status_counts[disclosure_status] += 1
        if population_available:
            covered_population_area += intersection_area
        if age_available:
            covered_age_area += intersection_area
        records.append(
            {
                "mesh_code": str(row.mesh_code),
                "overlap_ratio": round(overlap_ratio, 10),
                "disclosure_status": disclosure_status,
                "primary_eligible": bool(row.primary_eligible),
                "population_available": bool(population_available),
                "age_65_plus_available": bool(age_available),
            }
        )

    affected = [
        record for record in records if record["disclosure_status"] != "unaffected"
    ]
    return {
        "intersecting_mesh_count": len(records),
        "disclosure_status_counts": dict(sorted(status_counts.items())),
        "disclosure_affected_meshes": affected,
        "population_coverage_ratio": round(
            min(1.0, covered_population_area / area.area), 4
        ),
        "age_65_plus_coverage_ratio": round(
            min(1.0, covered_age_area / area.area), 4
        ),
    }


def metric_summary(metric: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": metric["status"],
        "value": metric["value"],
        "unit": metric["unit"],
        "semantics": (
            "estimated"
            if metric["calculation"] == "area_weighted_estimate"
            else "exact_source_object_or_observation_count"
        ),
        "calculation": metric["calculation"],
        "coverage_ratio": metric.get("coverage_ratio"),
        "source": metric["source"],
        "limitation": metric["limitation"],
    }


def area_comparison(
    area: dict[str, Any],
    runtime: dict[str, Any],
    meshes: gpd.GeoDataFrame,
) -> dict[str, Any]:
    metrics = {metric["key"]: metric_summary(metric) for metric in area["metrics"]}
    knowledge_counts = Counter(metric["status"] for metric in area["metrics"])
    tasks = [
        {
            "uncertainty_id": unknown["id"],
            "reason_code": unknown["reason_code"],
            "target_scope": unknown["target"]["scope"],
            "target_object_type": unknown["target"]["object_type"],
            "target_source_object_id": unknown["target"]["source_object_id"],
            "required_check_count": len(unknown["checks"]),
            "status": "unverified",
        }
        for unknown in area["unknowns"]
        if unknown["action_type"] == "field_verification"
    ]
    plateau_targets = [
        task["target_source_object_id"]
        for task in tasks
        if task["target_scope"] == "plateau_object"
    ]
    other_traceable_targets = [
        task["target_source_object_id"]
        for task in tasks
        if task["target_scope"] != "plateau_object"
    ]

    runtime_ids = sorted(runtime["target_ids"])
    source_ids = sorted(task["target_source_object_id"] for task in tasks)
    if runtime_ids != source_ids:
        raise ValueError(
            f"browser/source target mismatch for {area['radius_m']}m: "
            f"{runtime_ids} != {source_ids}"
        )
    if runtime["fake_field_evidence"]:
        raise ValueError("A5 comparison must not contain field evidence")

    disclosure = mesh_disclosure_audit(meshes, area["effective_geometry"])
    if disclosure["population_coverage_ratio"] != metrics["population"]["coverage_ratio"]:
        raise ValueError("population coverage differs from Area fixture")
    if disclosure["age_65_plus_coverage_ratio"] != metrics["age_distribution"]["coverage_ratio"]:
        raise ValueError("age coverage differs from Area fixture")

    return {
        "area_id": area["id"],
        "label": area["label"],
        "origin": area["origin"],
        "radius_m": area["radius_m"],
        "radius_methodology": area["radius_methodology"],
        "clipped_area_ratio": area["clipped_area_ratio"],
        "metrics": metrics,
        "knowledge_counts": {
            status: knowledge_counts.get(status, 0)
            for status in ("known", "partial", "unknown", "unavailable")
        },
        "unknown_count": len(area["unknowns"]),
        "plateau_target_ids": plateau_targets,
        "other_traceable_target_ids": other_traceable_targets,
        "tasks": tasks,
        "task_count": len(tasks),
        "required_checks_per_task": [task["required_check_count"] for task in tasks],
        "total_required_checks": sum(task["required_check_count"] for task in tasks),
        "task_statuses": sorted({task["status"] for task in tasks}),
        "runtime": {
            "direct_area_url_click_count": runtime["direct_area_url_click_count"],
            "landing_to_task_click_count": runtime["landing_to_task_click_count"],
            "first_meaningful_render_scope": runtime[
                "first_meaningful_render_scope"
            ],
            "first_meaningful_render_samples_ms": runtime[
                "first_meaningful_render_samples_ms"
            ],
            "first_meaningful_render_median_ms": runtime[
                "first_meaningful_render_median_ms"
            ],
        },
        "census_disclosure_audit": disclosure,
    }


def build() -> dict[str, Any]:
    fixture = load_json(AREA_FIXTURE)
    browser = load_json(BROWSER_MANIFEST)
    meshes = gpd.read_file(MESH_SOURCE).to_crs(ANALYSIS_CRS)
    areas = {int(area["radius_m"]): area for area in fixture["areas"]}
    if tuple(sorted(areas)) != EXPECTED_RADII:
        raise ValueError(f"expected exactly {EXPECTED_RADII}, got {tuple(sorted(areas))}")
    if any(area["origin"] != areas[500]["origin"] for area in areas.values()):
        raise ValueError("500m and 800m must use the same versioned origin")
    if any(area["status"] != "unverified" for area in areas.values()):
        raise ValueError("A5 fixture status must remain unverified")

    comparison = {
        str(radius): area_comparison(
            areas[radius], browser["comparison"][f"{radius}m"], meshes
        )
        for radius in EXPECTED_RADII
    }
    population_source = areas[500]["metrics"][0]["source"]
    return {
        "schema_version": "citygap.area-500-800-comparison@1",
        "goal_id": "area-known-unknown-to-task-v1",
        "checkpoint": "A5_PRESERVATION_AND_VALIDATION_PREP",
        "captured_at": browser["generated_at"],
        "repository_head_at_capture": browser["repository_head"],
        "comparison_policy": {
            "same_origin": True,
            "same_area_rule_version": fixture["rule_version"],
            "independent_axes_only": True,
            "composite_score": None,
            "ranking": None,
        },
        "input_artifacts": {
            "area_fixture": {
                "path": str(AREA_FIXTURE.relative_to(ROOT)),
                "sha256": sha256(AREA_FIXTURE),
                "schema_version": fixture["schema_version"],
            },
            "browser_manifest": {
                "path": str(BROWSER_MANIFEST.relative_to(ROOT)),
                "sha256": sha256(BROWSER_MANIFEST),
                "schema_version": browser["schema_version"],
            },
            "census_mesh": population_source,
        },
        "population_and_age_methodology": {
            "source_table_id": "T001192",
            "source_title": "2020年国勢調査 JGD2011 500mメッシュ 人口及び世帯",
            "reference_date": "2020-10-01",
            "population_field": "T001192001",
            "age_65_plus_fields": [
                "T001192043",
                "T001192046",
                "T001192049",
                "T001192052",
                "T001192055",
                "T001192058",
                "T001192061",
            ],
            "source_mesh_values": "official_observed_mesh_totals",
            "area_result_semantics": "estimated",
            "modelled": False,
            "aggregation": "sum(value * intersection_area / source_mesh_area)",
            "suppression": (
                "Missing or disclosure-affected age cells are not replaced by zero, "
                "averages, neighbouring values, or building-level estimates."
            ),
            "city_clipping": (
                "Requested point-radius geometry is intersected with the versioned "
                "Maizuru boundary in EPSG:6674; clipped_area_ratio is reported per area."
            ),
            "plateau_building_population_allocation": False,
            "prohibited_operation": (
                "Never disaggregate a suppression-affected census mesh to individual "
                "PLATEAU buildings."
            ),
            "claim_boundary": [
                "Values are AOI area-weighted estimates, not exact AOI resident counts.",
                "They are not household, person, or building-level population locations.",
                "PLATEAU building footprints are used only for building-use counts and targets.",
                "A radius is not a validated pedestrian-network reachability area.",
            ],
        },
        "areas": comparison,
        "validation_status": fixture["validation_status"],
        "field_evidence_present": False,
    }


def main() -> None:
    result = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
