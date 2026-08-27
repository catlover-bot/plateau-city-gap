"""Content fingerprints, version diffs and impacted-analysis selection."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

ChangeType = Literal[
    "added",
    "removed",
    "geometry_changed",
    "attribute_changed",
    "geometry_and_attribute_changed",
    "unchanged",
]
MatchMethod = Literal["gml_id", "geometry_hash", "important_attribute_hash"]


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
    important_attributes_json: str

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
        canonical_attributes = _canonical_attributes(important_attributes)
        attributes_hash = _digest(canonical_attributes)
        # gml:id is an identity signal, not feature content. Keeping it outside the
        # content digest lets a source-system identifier change be reconciled using
        # geometry and important-attribute fingerprints.
        feature_hash = _digest(f"{feature_type}\0{geometry_hash}\0{attributes_hash}".encode())
        return cls(
            gml_id,
            feature_type,
            geometry_hash,
            attributes_hash,
            feature_hash,
            canonical_attributes.decode(),
        )


@dataclass(frozen=True, slots=True)
class FeatureChange:
    feature_key: str
    change_type: ChangeType
    before_sha256: str | None
    after_sha256: str | None
    feature_type: str
    before_gml_id: str | None
    after_gml_id: str | None
    matched_by: MatchMethod
    geometry_changed: bool
    attributes_changed: bool
    changed_attributes: tuple[str, ...] = ()

    @property
    def gml_id(self) -> str:
        """Backward-compatible display identity, preferring the current source id."""

        return self.after_gml_id or self.before_gml_id or self.feature_key


def _attribute_changes(
    previous: FeatureFingerprint | None, current: FeatureFingerprint | None
) -> tuple[str, ...]:
    if previous is None or current is None:
        return ()
    before = json.loads(previous.important_attributes_json)
    after = json.loads(current.important_attributes_json)
    return tuple(
        key for key in sorted(before.keys() | after.keys()) if before.get(key) != after.get(key)
    )


def _classify(
    previous: FeatureFingerprint | None, current: FeatureFingerprint | None
) -> ChangeType:
    if previous is None:
        return "added"
    if current is None:
        return "removed"
    geometry_changed = previous.geometry_sha256 != current.geometry_sha256
    attributes_changed = previous.attributes_sha256 != current.attributes_sha256
    if geometry_changed and attributes_changed:
        return "geometry_and_attribute_changed"
    if geometry_changed:
        return "geometry_changed"
    if attributes_changed:
        return "attribute_changed"
    return "unchanged"


def _unique_unmatched_index(
    rows: dict[str, FeatureFingerprint], attribute: str
) -> dict[tuple[str, str], str]:
    grouped: dict[tuple[str, str], list[str]] = {}
    for gml_id, row in rows.items():
        key = (row.feature_type, str(getattr(row, attribute)))
        grouped.setdefault(key, []).append(gml_id)
    return {key: ids[0] for key, ids in grouped.items() if len(ids) == 1}


def diff_fingerprints(
    before: Iterable[FeatureFingerprint], after: Iterable[FeatureFingerprint]
) -> list[FeatureChange]:
    before_rows = list(before)
    after_rows = list(after)
    old_by_id = {row.gml_id: row for row in before_rows}
    new_by_id = {row.gml_id: row for row in after_rows}
    if len(old_by_id) != len(before_rows) or len(new_by_id) != len(after_rows):
        raise ValueError("Fingerprint inputs must contain unique gml:id values")
    if any(
        old_by_id[gml_id].feature_type != new_by_id[gml_id].feature_type
        for gml_id in old_by_id.keys() & new_by_id.keys()
    ):
        raise ValueError("A stable gml:id cannot change feature type between versions")

    matches: list[tuple[str, str, MatchMethod]] = [
        (gml_id, gml_id, "gml_id") for gml_id in sorted(old_by_id.keys() & new_by_id.keys())
    ]
    unmatched_old = {key: value for key, value in old_by_id.items() if key not in new_by_id}
    unmatched_new = {key: value for key, value in new_by_id.items() if key not in old_by_id}

    # Reconcile source identifier changes only when a fingerprint is unique on both
    # sides. Exact geometry is the strongest fallback; unique important attributes
    # can then reconcile a geometry edit. Ambiguous records remain added/removed.
    for attribute, method in (
        ("geometry_sha256", "geometry_hash"),
        ("attributes_sha256", "important_attribute_hash"),
    ):
        old_index = _unique_unmatched_index(unmatched_old, attribute)
        new_index = _unique_unmatched_index(unmatched_new, attribute)
        for key in sorted(old_index.keys() & new_index.keys()):
            old_id = old_index[key]
            new_id = new_index[key]
            if old_id not in unmatched_old or new_id not in unmatched_new:
                continue
            matches.append((old_id, new_id, method))  # type: ignore[arg-type]
            unmatched_old.pop(old_id)
            unmatched_new.pop(new_id)

    changes: list[FeatureChange] = []
    paired: list[tuple[FeatureFingerprint | None, FeatureFingerprint | None, MatchMethod]] = [
        (old_by_id[old_id], new_by_id[new_id], method) for old_id, new_id, method in matches
    ]
    paired.extend((row, None, "gml_id") for row in unmatched_old.values())
    paired.extend((None, row, "gml_id") for row in unmatched_new.values())
    for previous, current, matched_by in paired:
        kind = _classify(previous, current)
        before_id = previous.gml_id if previous else None
        after_id = current.gml_id if current else None
        feature_key = (
            after_id
            if before_id is None or before_id == after_id
            else f"{before_id}=>{after_id}"
        ) or before_id
        assert feature_key is not None
        changes.append(
            FeatureChange(
                feature_key=feature_key,
                change_type=kind,
                before_sha256=previous.feature_sha256 if previous else None,
                after_sha256=current.feature_sha256 if current else None,
                feature_type=(current or previous).feature_type,  # type: ignore[union-attr]
                before_gml_id=before_id,
                after_gml_id=after_id,
                matched_by=matched_by,
                geometry_changed=(
                    previous is not None
                    and current is not None
                    and previous.geometry_sha256 != current.geometry_sha256
                ),
                attributes_changed=(
                    previous is not None
                    and current is not None
                    and previous.attributes_sha256 != current.attributes_sha256
                ),
                changed_attributes=_attribute_changes(previous, current),
            )
        )
    return sorted(changes, key=lambda row: row.feature_key)


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
