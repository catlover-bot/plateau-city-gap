"""Content fingerprints, version diffs and impacted-analysis selection."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

ChangeType = Literal["added", "removed", "changed", "unchanged"]


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_attributes(attributes: dict[str, Any]) -> bytes:
    return json.dumps(
        attributes,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()


@dataclass(frozen=True, slots=True)
class FeatureFingerprint:
    gml_id: str
    feature_type: str
    geometry_sha256: str
    attributes_sha256: str
    feature_sha256: str

    @classmethod
    def create(
        cls,
        gml_id: str,
        feature_type: str,
        geometry_wkb: bytes,
        important_attributes: dict[str, Any],
    ) -> FeatureFingerprint:
        if not gml_id or not feature_type or not geometry_wkb:
            raise ValueError("Fingerprint requires gml:id, feature type and normalized geometry WKB")
        geometry_hash = _digest(geometry_wkb)
        attributes_hash = _digest(_canonical_attributes(important_attributes))
        feature_hash = _digest(
            f"{gml_id}\0{feature_type}\0{geometry_hash}\0{attributes_hash}".encode()
        )
        return cls(gml_id, feature_type, geometry_hash, attributes_hash, feature_hash)


@dataclass(frozen=True, slots=True)
class FeatureChange:
    gml_id: str
    change_type: ChangeType
    before_sha256: str | None
    after_sha256: str | None
    feature_type: str


def diff_fingerprints(
    before: Iterable[FeatureFingerprint], after: Iterable[FeatureFingerprint]
) -> list[FeatureChange]:
    before_rows = list(before)
    after_rows = list(after)
    old = {row.gml_id: row for row in before_rows}
    new = {row.gml_id: row for row in after_rows}
    if len(old) != len(before_rows) or len(new) != len(after_rows):
        raise ValueError("Fingerprint inputs must contain unique gml:id values")
    changes: list[FeatureChange] = []
    for gml_id in sorted(old.keys() | new.keys()):
        previous = old.get(gml_id)
        current = new.get(gml_id)
        if previous is None:
            kind: ChangeType = "added"
        elif current is None:
            kind = "removed"
        elif previous.feature_sha256 == current.feature_sha256:
            kind = "unchanged"
        else:
            kind = "changed"
        changes.append(
            FeatureChange(
                gml_id=gml_id,
                change_type=kind,
                before_sha256=previous.feature_sha256 if previous else None,
                after_sha256=current.feature_sha256 if current else None,
                feature_type=(current or previous).feature_type,  # type: ignore[union-attr]
            )
        )
    return changes


@dataclass(frozen=True, slots=True)
class AnalysisDependency:
    dependent_type: Literal["analysis", "network", "scenario"]
    dependent_id: str
    feature_types: frozenset[str] = frozenset()


def impacted_dependencies(
    changes: Iterable[FeatureChange], dependencies: Iterable[AnalysisDependency]
) -> list[AnalysisDependency]:
    changed_types = {
        change.feature_type for change in changes if change.change_type != "unchanged"
    }
    return sorted(
        (
            dependency
            for dependency in dependencies
            if changed_types
            and (not dependency.feature_types or dependency.feature_types & changed_types)
        ),
        key=lambda item: (item.dependent_type, item.dependent_id),
    )
