"""Replaceable object-storage boundary for municipal attachments.

The database owns authorization metadata.  This module owns bytes only and never
accepts a caller-provided path, so object identifiers cannot become filesystem paths.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from collections.abc import AsyncIterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredAttachment:
    object_key: str
    size_bytes: int
    sha256: str


class AttachmentStore(Protocol):
    provider: str

    async def put(
        self,
        chunks: AsyncIterable[bytes],
        *,
        organization_id: str,
        city_id: str,
        max_bytes: int,
    ) -> StoredAttachment: ...

    def iter_bytes(self, object_key: str, chunk_size: int = 64 * 1024) -> Iterator[bytes]: ...

    def exists(self, object_key: str) -> bool: ...

    def delete(self, object_key: str) -> None: ...


class LocalAttachmentStore:
    """Local-volume implementation suitable for a single service deployment."""

    provider = "local"

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, object_key: str) -> Path:
        candidate = (self.root / object_key).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("Attachment object key escaped the configured storage root")
        return candidate

    async def put(
        self,
        chunks: AsyncIterable[bytes],
        *,
        organization_id: str,
        city_id: str,
        max_bytes: int,
    ) -> StoredAttachment:
        object_key = f"{organization_id}/{city_id}/{uuid.uuid4().hex}"
        target = self._path(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
        digest = hashlib.sha256()
        size = 0
        try:
            with temporary.open("xb") as output:
                async for chunk in chunks:
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError(f"Attachment exceeds the {max_bytes} byte limit")
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if size == 0:
                raise ValueError("Attachment body must not be empty")
            os.replace(temporary, target)
        except BaseException:
            temporary.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            raise
        return StoredAttachment(object_key=object_key, size_bytes=size, sha256=digest.hexdigest())

    def iter_bytes(self, object_key: str, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
        path = self._path(object_key)
        with path.open("rb") as source:
            while chunk := source.read(chunk_size):
                yield chunk

    def delete(self, object_key: str) -> None:
        self._path(object_key).unlink(missing_ok=True)

    def exists(self, object_key: str) -> bool:
        return self._path(object_key).is_file()


class UnavailableS3CompatibleAttachmentStore:
    """Explicit S3-compatible boundary until credentials/client are configured."""

    provider = "s3_compatible"
    message = "S3-compatible attachment storage is configured but unavailable"

    async def put(
        self,
        chunks: AsyncIterable[bytes],
        *,
        organization_id: str,
        city_id: str,
        max_bytes: int,
    ) -> StoredAttachment:
        del chunks, organization_id, city_id, max_bytes
        raise RuntimeError(self.message)

    def iter_bytes(self, object_key: str, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
        del object_key, chunk_size
        raise RuntimeError(self.message)
        yield b""  # pragma: no cover - keeps this method an iterator

    def delete(self, object_key: str) -> None:
        del object_key
        raise RuntimeError(self.message)

    def exists(self, object_key: str) -> bool:
        del object_key
        return False


def attachment_store_from_environment() -> AttachmentStore:
    provider = os.getenv("CITYGAP_ATTACHMENT_PROVIDER", "local").lower()
    if provider == "local":
        return LocalAttachmentStore(os.getenv("CITYGAP_ATTACHMENT_DIRECTORY", "var/attachments"))
    if provider == "s3_compatible":
        return UnavailableS3CompatibleAttachmentStore()
    raise RuntimeError(f"Unsupported CITYGAP_ATTACHMENT_PROVIDER: {provider}")
