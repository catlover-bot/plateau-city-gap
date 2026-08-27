"""Streaming real CityGML version-diff validation.

The matcher measures identifier stability first, then uses conservative unique
geometry and attribute fallbacks.  Ambiguous candidates are never forced into a
match.
"""

from __future__ import annotations

import hashlib
import math
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any, BinaryIO

import pandas as pd

GML_ID = "{http://www.opengis.net/gml}id"
TEMPORAL_ALGORITHM_VERSION = "citygap-real-citygml-temporal-diff-v1.0.0"
THEME_FEATURE_TYPES = {
    "bldg": {"Building"},
    "tran": {"Road"},
    "luse": {"LandUse"},
    "urf": None,
}
ATTRIBUTE_NAMES = {
    "bldg": {
        "name", "class", "function", "usage", "measuredHeight", "roofType",
        "storeysAboveGround", "storeysBelowGround", "yearOfConstruction",
        "yearOfDemolition", "buildingFootprintArea", "totalFloorArea",
    },
    "tran": {"name", "class", "function", "usage"},
    "luse": {"name", "class", "function", "usage"},
    "urf": {
        "name", "class", "function", "usage", "areaClassification",
        "urbanPlanType", "prefecture", "city", "reference", "validFrom",
        "validTo", "status", "nominalArea", "floorAreaRate", "buildingCoverageRate",
    },
}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _coordinates(text: str, dimension: int | None) -> list[tuple[float, float]]:
    try:
        values = [float(value) for value in text.replace(",", " ").split()]
    except ValueError:
        return []
    if not values:
        return []
    dimensions = [dimension] if dimension in {2, 3} else []
    dimensions.extend(value for value in (3, 2) if value not in dimensions)
    selected = next((value for value in dimensions if len(values) % value == 0), None)
    if selected is None:
        return []
    return [
        (round(values[index + 1], 6), round(values[index], 6))
        for index in range(0, len(values), selected)
    ]


def iter_citygml_features(
    stream: BinaryIO,
    *,
    theme: str,
    source_member: str,
    source_member_crc32: str,
) -> Iterable[dict[str, Any]]:
    stack: list[str] = []
    current: dict[str, Any] | None = None
    for event, element in ET.iterparse(stream, events=("start", "end")):
        local = _local_name(element.tag)
        if event == "start":
            parent = stack[-1] if stack else None
            stack.append(local)
            allowed = THEME_FEATURE_TYPES[theme]
            if (
                current is None
                and parent == "cityObjectMember"
                and element.get(GML_ID)
                and (allowed is None or local in allowed)
            ):
                current = {
                    "depth": len(stack),
                    "feature_id": str(element.get(GML_ID)),
                    "feature_type": local,
                    "theme": theme,
                    "source_member": source_member,
                    "source_member_crc32": source_member_crc32,
                    "coordinates": [],
                    "attributes": [],
                }
            continue

        if current is not None:
            text = (element.text or "").strip()
            if text and local in {"posList", "pos", "lowerCorner", "upperCorner"}:
                raw_dimension = element.get("srsDimension") or element.get("dimension")
                dimension = int(raw_dimension) if raw_dimension and raw_dimension.isdigit() else None
                current["coordinates"].extend(_coordinates(text, dimension))
            elif text and local in ATTRIBUTE_NAMES[theme] and len(text) <= 1000:
                normalized = " ".join(text.split())
                current["attributes"].append((local, normalized))

            if len(stack) == current["depth"]:
                coordinates = sorted(set(current.pop("coordinates")))
                attributes = sorted(set(current.pop("attributes")))
                geometry_serialized = "|".join(f"{x:.6f},{y:.6f}" for x, y in coordinates)
                attribute_serialized = "|".join(
                    [current["feature_type"]] + [f"{key}={value}" for key, value in attributes]
                )
                if coordinates:
                    xs = [coordinate[0] for coordinate in coordinates]
                    ys = [coordinate[1] for coordinate in coordinates]
                    bbox = [min(xs), min(ys), max(xs), max(ys)]
                    centroid_lon = (bbox[0] + bbox[2]) / 2
                    centroid_lat = (bbox[1] + bbox[3]) / 2
                else:
                    bbox = None
                    centroid_lon = None
                    centroid_lat = None
                yield {
                    **current,
                    "geometry_hash": hashlib.sha256(geometry_serialized.encode()).hexdigest(),
                    "attribute_hash": hashlib.sha256(attribute_serialized.encode()).hexdigest(),
                    "coordinate_count": len(coordinates),
                    "bbox": bbox,
                    "centroid_lon": centroid_lon,
                    "centroid_lat": centroid_lat,
                }
                current = None
        element.clear()
        stack.pop()


def read_citygml_theme(archive_path: str | Path, theme: str) -> pd.DataFrame:
    if theme not in THEME_FEATURE_TYPES:
        raise ValueError(f"Unsupported temporal theme: {theme}")
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive_path) as archive:
        members = sorted(
            (
                info for info in archive.infolist()
                if info.filename.startswith(f"udx/{theme}/") and info.filename.endswith(".gml")
            ),
            key=lambda item: item.filename,
        )
        if not members:
            raise ValueError(f"Archive has no {theme} CityGML members")
        for info in members:
            with archive.open(info) as stream:
                rows.extend(
                    iter_citygml_features(
                        stream,
                        theme=theme,
                        source_member=info.filename,
                        source_member_crc32=f"{info.CRC:08x}",
                    )
                )
    frame = pd.DataFrame(rows)
    if frame.empty or frame["feature_id"].duplicated().any():
        raise ValueError(f"{theme} extraction is empty or has duplicate feature IDs")
    return frame.sort_values("feature_id").reset_index(drop=True)


def _distance_m(left: pd.Series, right: pd.Series) -> float:
    if any(pd.isna(value) for value in (left.centroid_lon, left.centroid_lat, right.centroid_lon, right.centroid_lat)):
        return math.inf
    latitude = math.radians((float(left.centroid_lat) + float(right.centroid_lat)) / 2)
    dx = (float(left.centroid_lon) - float(right.centroid_lon)) * 111_320 * math.cos(latitude)
    dy = (float(left.centroid_lat) - float(right.centroid_lat)) * 110_540
    return math.hypot(dx, dy)


def match_versions(old: pd.DataFrame, new: pd.DataFrame) -> dict[str, Any]:
    """Return conservative matches plus explicit ambiguous and unmatched sets."""

    old_by_id = old.set_index("feature_id", drop=False)
    new_by_id = new.set_index("feature_id", drop=False)
    same_ids = sorted(set(old_by_id.index) & set(new_by_id.index))
    matches: list[dict[str, str]] = [
        {"old_id": feature_id, "new_id": feature_id, "method": "same_gml_id"}
        for feature_id in same_ids
    ]
    remaining_old = set(old_by_id.index) - set(same_ids)
    remaining_new = set(new_by_id.index) - set(same_ids)
    ambiguous_old: set[str] = set()
    ambiguous_new: set[str] = set()

    def unique_hash_matches(column: str, method: str) -> None:
        nonlocal remaining_old, remaining_new
        old_groups: dict[str, list[str]] = {}
        new_groups: dict[str, list[str]] = {}
        for feature_id in remaining_old:
            old_groups.setdefault(str(old_by_id.loc[feature_id, column]), []).append(str(feature_id))
        for feature_id in remaining_new:
            new_groups.setdefault(str(new_by_id.loc[feature_id, column]), []).append(str(feature_id))
        found_old: set[str] = set()
        found_new: set[str] = set()
        for digest in sorted(set(old_groups) & set(new_groups)):
            old_ids = sorted(old_groups[digest])
            new_ids = sorted(new_groups[digest])
            if len(old_ids) == len(new_ids) == 1:
                old_id, new_id = old_ids[0], new_ids[0]
                if (
                    old_by_id.loc[old_id, "feature_type"]
                    == new_by_id.loc[new_id, "feature_type"]
                    and (
                        method != "attribute_hash_centroid"
                        or _distance_m(old_by_id.loc[old_id], new_by_id.loc[new_id]) <= 5.0
                    )
                ):
                    matches.append({"old_id": old_id, "new_id": new_id, "method": method})
                    found_old.add(old_id)
                    found_new.add(new_id)
            else:
                ambiguous_old.update(old_ids)
                ambiguous_new.update(new_ids)
        remaining_old -= found_old
        remaining_new -= found_new

    unique_hash_matches("geometry_hash", "geometry_hash")
    unique_hash_matches("attribute_hash", "attribute_hash_centroid")
    ambiguous_old &= remaining_old
    ambiguous_new &= remaining_new
    return {
        "matches": sorted(matches, key=lambda item: (item["old_id"], item["new_id"])),
        "ambiguous_old": sorted(ambiguous_old),
        "ambiguous_new": sorted(ambiguous_new),
        "unmatched_old": sorted(remaining_old),
        "unmatched_new": sorted(remaining_new),
    }


def classify_version_diff(old: pd.DataFrame, new: pd.DataFrame) -> dict[str, Any]:
    audit = match_versions(old, new)
    old_by_id = old.set_index("feature_id", drop=False)
    new_by_id = new.set_index("feature_id", drop=False)
    changes: list[dict[str, Any]] = []
    counts = {
        "added": 0,
        "removed": 0,
        "geometry_changed": 0,
        "attribute_changed": 0,
        "unchanged": 0,
    }
    both_geometry_and_attribute_changed = 0
    for match in audit["matches"]:
        before = old_by_id.loc[match["old_id"]]
        after = new_by_id.loc[match["new_id"]]
        geometry_changed = before.geometry_hash != after.geometry_hash
        attribute_changed = before.attribute_hash != after.attribute_hash
        if geometry_changed:
            change_type = "geometry_changed"
            both_geometry_and_attribute_changed += int(attribute_changed)
        elif attribute_changed:
            change_type = "attribute_changed"
        else:
            change_type = "unchanged"
        counts[change_type] += 1
        changes.append(
            {
                **match,
                "change_type": change_type,
                "attribute_changed_also": bool(geometry_changed and attribute_changed),
                "centroid_lon": after.centroid_lon,
                "centroid_lat": after.centroid_lat,
                "bbox": after.bbox,
            }
        )
    matched_old = {item["old_id"] for item in audit["matches"]}
    matched_new = {item["new_id"] for item in audit["matches"]}
    for feature_id in sorted(set(old_by_id.index) - matched_old):
        row = old_by_id.loc[feature_id]
        counts["removed"] += 1
        changes.append(
            {
                "old_id": feature_id,
                "new_id": None,
                "method": "unmatched",
                "change_type": "removed",
                "attribute_changed_also": False,
                "centroid_lon": row.centroid_lon,
                "centroid_lat": row.centroid_lat,
                "bbox": row.bbox,
            }
        )
    for feature_id in sorted(set(new_by_id.index) - matched_new):
        row = new_by_id.loc[feature_id]
        counts["added"] += 1
        changes.append(
            {
                "old_id": None,
                "new_id": feature_id,
                "method": "unmatched",
                "change_type": "added",
                "attribute_changed_also": False,
                "centroid_lon": row.centroid_lon,
                "centroid_lat": row.centroid_lat,
                "bbox": row.bbox,
            }
        )
    methods = pd.Series([item["method"] for item in audit["matches"]]).value_counts().to_dict()
    audit_summary = {
        "old_feature_count": len(old),
        "new_feature_count": len(new),
        "matched_count": len(audit["matches"]),
        "same_gml_id_count": int(methods.get("same_gml_id", 0)),
        "same_gml_id_fraction_of_smaller_version": int(methods.get("same_gml_id", 0)) / min(len(old), len(new)),
        "geometry_hash_fallback_count": int(methods.get("geometry_hash", 0)),
        "geometry_hash_fallback_fraction_of_matches": int(methods.get("geometry_hash", 0)) / max(len(audit["matches"]), 1),
        "attribute_hash_fallback_count": int(methods.get("attribute_hash_centroid", 0)),
        "attribute_hash_fallback_fraction_of_matches": int(methods.get("attribute_hash_centroid", 0)) / max(len(audit["matches"]), 1),
        "ambiguous_old_count": len(audit["ambiguous_old"]),
        "ambiguous_new_count": len(audit["ambiguous_new"]),
        "ambiguous_fraction_of_both_versions": (len(audit["ambiguous_old"]) + len(audit["ambiguous_new"])) / (len(old) + len(new)),
        "unmatched_old_count": len(audit["unmatched_old"]),
        "unmatched_new_count": len(audit["unmatched_new"]),
        "unmatched_fraction_of_both_versions": (len(audit["unmatched_old"]) + len(audit["unmatched_new"])) / (len(old) + len(new)),
    }
    return {
        "counts": counts,
        "both_geometry_and_attribute_changed": both_geometry_and_attribute_changed,
        "match_audit": audit_summary,
        "changes": changes,
    }


def state_digest(features: pd.DataFrame) -> str:
    rows = [
        f"{row.feature_id}|{row.feature_type}|{row.geometry_hash}|{row.attribute_hash}"
        for row in features.sort_values("feature_id").itertuples(index=False)
    ]
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()


def incremental_rebuild_check(old: pd.DataFrame, new: pd.DataFrame) -> dict[str, Any]:
    """Apply the actual identifier-level delta and compare it with a full state rebuild."""

    old_rows = {row.feature_id: row._asdict() for row in old.itertuples(index=False)}
    new_rows = {row.feature_id: row._asdict() for row in new.itertuples(index=False)}
    incremental = dict(old_rows)
    removed = sorted(set(old_rows) - set(new_rows))
    added = sorted(set(new_rows) - set(old_rows))
    updated = sorted(
        feature_id for feature_id in set(old_rows) & set(new_rows)
        if old_rows[feature_id]["geometry_hash"] != new_rows[feature_id]["geometry_hash"]
        or old_rows[feature_id]["attribute_hash"] != new_rows[feature_id]["attribute_hash"]
    )
    for feature_id in removed:
        incremental.pop(feature_id)
    for feature_id in added + updated:
        incremental[feature_id] = new_rows[feature_id]
    incremental_frame = pd.DataFrame(incremental.values())
    incremental_digest = state_digest(incremental_frame)
    full_digest = state_digest(new)
    return {
        "removed_applied": len(removed),
        "added_applied": len(added),
        "updated_applied": len(updated),
        "incremental_count": len(incremental_frame),
        "full_rebuild_count": len(new),
        "incremental_sha256": incremental_digest,
        "full_rebuild_sha256": full_digest,
        "count_agreement": len(incremental_frame) == len(new),
        "hash_agreement": incremental_digest == full_digest,
    }
