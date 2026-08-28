"""Content-addressed storage for immutable official-source bytes."""

from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from backend.citygap_platform.domain.open_data import RawResourceReceipt
from backend.citygap_platform.open_data.http import SafeHttpClient


class ContentAddressedObjectStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for_key(self, object_key: str) -> Path:
        candidate = (self.root / object_key).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("Object key escapes the configured storage root")
        return candidate

    def fetch(
        self,
        client: SafeHttpClient,
        url: str,
        *,
        max_bytes: int,
    ) -> RawResourceReceipt:
        descriptor, temporary_name = tempfile.mkstemp(prefix="citygap-open-data-", dir=self.root)
        os.close(descriptor)
        temporary = Path(temporary_name)
        temporary.unlink()
        try:
            result = client.download_to(url, temporary, max_bytes=max_bytes)
            object_key = f"sha256/{result.sha256[:2]}/{result.sha256}"
            destination = self.path_for_key(object_key)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                digest = hashlib.sha256()
                with destination.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                if (
                    destination.stat().st_size != result.size_bytes
                    or digest.hexdigest() != result.sha256
                ):
                    raise ValueError("Content-addressed object does not match existing bytes")
                temporary.unlink()
            else:
                temporary.replace(destination)
            return RawResourceReceipt(
                sha256=result.sha256,
                size_bytes=result.size_bytes,
                content_type=result.content_type,
                object_key=object_key,
                retrieved_at=datetime.now(UTC).isoformat(),
            )
        finally:
            temporary.unlink(missing_ok=True)
