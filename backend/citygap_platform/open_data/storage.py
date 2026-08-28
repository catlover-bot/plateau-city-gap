"""Content-addressed storage for immutable official-source bytes."""

from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.citygap_platform.domain.open_data import RawResourceReceipt
from backend.citygap_platform.open_data.http import SafeHttpClient


class ContentAddressedObjectStore:
    storage_provider = "local"

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


class S3CompatibleContentAddressedObjectStore(ContentAddressedObjectStore):
    """S3-compatible production store with a bounded local inspection cache."""

    storage_provider = "s3_compatible"

    def __init__(
        self,
        cache_root: str | Path,
        *,
        endpoint_url: str,
        bucket: str,
        prefix: str = "citygap-open-data",
        client: Any | None = None,
    ) -> None:
        super().__init__(cache_root)
        if not endpoint_url.startswith("https://"):
            raise ValueError("S3-compatible endpoint must use HTTPS")
        if not bucket or "/" in bucket or "\\" in bucket:
            raise ValueError("S3-compatible bucket name is invalid")
        normalized_prefix = prefix.strip("/")
        if not normalized_prefix or ".." in normalized_prefix.split("/"):
            raise ValueError("S3-compatible object prefix is invalid")
        self.endpoint_url = endpoint_url
        self.bucket = bucket
        self.prefix = normalized_prefix
        if client is None:
            try:
                import boto3
            except ImportError as error:  # pragma: no cover - production optional dependency
                raise RuntimeError(
                    "boto3 is required for S3-compatible open-data storage"
                ) from error
            client = boto3.client("s3", endpoint_url=endpoint_url)
        self.client = client

    def _remote_key(self, object_key: str) -> str:
        self.path_for_key_local(object_key)
        return f"{self.prefix}/{object_key}"

    def path_for_key_local(self, object_key: str) -> Path:
        return super().path_for_key(object_key)

    @staticmethod
    def _not_found(error: Exception) -> bool:
        response = getattr(error, "response", {})
        code = str(response.get("Error", {}).get("Code", ""))
        return code in {"404", "NoSuchKey", "NotFound"}

    def _head(self, object_key: str) -> dict[str, Any] | None:
        try:
            return self.client.head_object(Bucket=self.bucket, Key=self._remote_key(object_key))
        except Exception as error:
            if self._not_found(error):
                return None
            raise RuntimeError("S3-compatible object metadata check failed") from error

    def _verify_head(self, object_key: str, head: dict[str, Any], size_bytes: int) -> None:
        expected_sha = object_key.rsplit("/", 1)[-1]
        metadata_sha = str(head.get("Metadata", {}).get("sha256", ""))
        if int(head.get("ContentLength", -1)) != size_bytes or metadata_sha != expected_sha:
            raise ValueError("S3-compatible object metadata does not match its content key")

    def path_for_key(self, object_key: str) -> Path:
        local = self.path_for_key_local(object_key)
        if local.exists():
            return local
        head = self._head(object_key)
        if head is None:
            return local
        local.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix="citygap-s3-cache-", dir=self.root)
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            self.client.download_file(self.bucket, self._remote_key(object_key), str(temporary))
            digest = hashlib.sha256()
            with temporary.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != object_key.rsplit("/", 1)[-1]:
                raise ValueError("S3-compatible object bytes do not match their content key")
            self._verify_head(object_key, head, temporary.stat().st_size)
            temporary.replace(local)
        except (RuntimeError, ValueError):
            raise
        except Exception as error:
            raise RuntimeError("S3-compatible object download failed") from error
        finally:
            temporary.unlink(missing_ok=True)
        return local

    def fetch(
        self,
        client: SafeHttpClient,
        url: str,
        *,
        max_bytes: int,
    ) -> RawResourceReceipt:
        receipt = super().fetch(client, url, max_bytes=max_bytes)
        local = self.path_for_key_local(receipt.object_key)
        head = self._head(receipt.object_key)
        if head is None:
            try:
                self.client.upload_file(
                    str(local),
                    self.bucket,
                    self._remote_key(receipt.object_key),
                    ExtraArgs={
                        "ContentType": receipt.content_type,
                        "Metadata": {"sha256": receipt.sha256},
                    },
                )
            except Exception as error:
                raise RuntimeError("S3-compatible object upload failed") from error
            head = self._head(receipt.object_key)
            if head is None:
                raise RuntimeError("S3-compatible object upload was not observable")
        self._verify_head(receipt.object_key, head, receipt.size_bytes)
        return receipt


def content_addressed_store_from_environment(
    default_local_root: str | Path,
) -> ContentAddressedObjectStore:
    """Select local development or S3-compatible production storage explicitly."""

    provider = os.getenv("CITYGAP_OPEN_DATA_STORAGE_PROVIDER", "local")
    if provider == "local":
        return ContentAddressedObjectStore(default_local_root)
    if provider != "s3_compatible":
        raise ValueError("CITYGAP_OPEN_DATA_STORAGE_PROVIDER must be local or s3_compatible")
    endpoint = os.getenv("CITYGAP_OPEN_DATA_S3_ENDPOINT")
    bucket = os.getenv("CITYGAP_OPEN_DATA_S3_BUCKET")
    if not endpoint or not bucket:
        raise RuntimeError(
            "S3-compatible storage requires CITYGAP_OPEN_DATA_S3_ENDPOINT and "
            "CITYGAP_OPEN_DATA_S3_BUCKET"
        )
    return S3CompatibleContentAddressedObjectStore(
        default_local_root,
        endpoint_url=endpoint,
        bucket=bucket,
        prefix=os.getenv("CITYGAP_OPEN_DATA_S3_PREFIX", "citygap-open-data"),
    )
