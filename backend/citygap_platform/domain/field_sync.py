"""Optimistic offline field synchronization with mandatory explicit conflict resolution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Literal

Resolution = Literal["use_server", "use_client", "merged"]


@dataclass(frozen=True, slots=True)
class VersionedFieldRecord:
    version: int
    updated_at: datetime
    actor: str
    values: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.version < 1 or not self.actor.strip():
            raise ValueError("Field record requires a positive version and actor")
        if self.updated_at.tzinfo is None:
            raise ValueError("Field record timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True)
class OfflineFieldOperation:
    operation_id: str
    base_record_version: int
    actor: str
    client_updated_at: datetime
    values: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.operation_id.strip() or not self.actor.strip() or self.base_record_version < 1:
            raise ValueError("Offline operation requires identity, actor and base version")
        if self.client_updated_at.tzinfo is None:
            raise ValueError("Offline operation timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True)
class FieldSyncConflict:
    operation_id: str
    server_record: VersionedFieldRecord
    client_values: Mapping[str, Any]
    resolution_status: Literal["unresolved"] = "unresolved"


def apply_offline_operation(
    server: VersionedFieldRecord, operation: OfflineFieldOperation
) -> VersionedFieldRecord | FieldSyncConflict:
    if operation.base_record_version != server.version:
        return FieldSyncConflict(operation.operation_id, server, dict(operation.values))
    return VersionedFieldRecord(
        version=server.version + 1,
        updated_at=datetime.now(timezone.utc),
        actor=operation.actor,
        values=dict(operation.values),
    )


def resolve_conflict(
    conflict: FieldSyncConflict,
    resolution: Resolution,
    *,
    actor: str,
    merged_values: Mapping[str, Any] | None = None,
) -> VersionedFieldRecord:
    if not actor.strip():
        raise ValueError("Conflict resolution requires an actor")
    if resolution == "use_server":
        return replace(conflict.server_record)
    if resolution == "merged" and merged_values is None:
        raise ValueError("Merged conflict resolution requires explicit values")
    values = conflict.client_values if resolution == "use_client" else merged_values
    assert values is not None
    return VersionedFieldRecord(
        version=conflict.server_record.version + 1,
        updated_at=datetime.now(timezone.utc),
        actor=actor,
        values=dict(values),
    )
