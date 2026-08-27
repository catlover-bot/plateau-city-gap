from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.citygap_platform.domain.field_sync import (
    FieldSyncConflict,
    OfflineFieldOperation,
    VersionedFieldRecord,
    apply_offline_operation,
    resolve_conflict,
)

NOW = datetime(2026, 8, 27, tzinfo=timezone.utc)


def test_offline_operation_applies_only_to_matching_base_version() -> None:
    server = VersionedFieldRecord(3, NOW, "planner-a", {"notes": "server"})
    applied = apply_offline_operation(
        server,
        OfflineFieldOperation("op-1", 3, "planner-b", NOW, {"notes": "field"}),
    )
    assert isinstance(applied, VersionedFieldRecord)
    assert applied.version == 4
    assert applied.values == {"notes": "field"}


def test_version_conflict_never_silently_uses_last_write() -> None:
    server = VersionedFieldRecord(4, NOW, "planner-a", {"notes": "server"})
    conflict = apply_offline_operation(
        server,
        OfflineFieldOperation("op-2", 3, "planner-b", NOW, {"notes": "field"}),
    )
    assert isinstance(conflict, FieldSyncConflict)
    assert conflict.resolution_status == "unresolved"
    assert conflict.server_record.values != conflict.client_values

    with pytest.raises(ValueError, match="explicit values"):
        resolve_conflict(conflict, "merged", actor="reviewer")
    resolved = resolve_conflict(
        conflict,
        "merged",
        actor="reviewer",
        merged_values={"notes": "reviewed merge"},
    )
    assert resolved.version == 5
    assert resolved.actor == "reviewer"
