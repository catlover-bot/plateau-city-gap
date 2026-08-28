"""Bounded HTTPS client for allowlisted official data hosts."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

Resolver = Callable[..., list[tuple[Any, ...]]]


def validate_public_https_url(
    url: str,
    *,
    allowed_hosts: Iterable[str],
    resolver: Resolver = socket.getaddrinfo,
) -> str:
    """Reject credentials, non-HTTPS, non-allowlisted hosts and non-public DNS answers."""

    parsed = urlsplit(url)
    host = (parsed.hostname or "").rstrip(".").lower()
    allowed = {item.rstrip(".").lower() for item in allowed_hosts}
    if parsed.scheme != "https" or not host:
        raise ValueError("Official resource URL must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Official resource URL must not contain credentials")
    if parsed.port not in (None, 443):
        raise ValueError("Official resource URL must use the standard HTTPS port")
    if host not in allowed:
        raise ValueError(f"Official resource host is not allowlisted: {host}")
    addresses = {
        item[4][0].split("%", maxsplit=1)[0]
        for item in resolver(host, 443, type=socket.SOCK_STREAM)
    }
    if not addresses:
        raise ValueError("Official resource host did not resolve")
    for address in addresses:
        if not ipaddress.ip_address(address).is_global:
            raise ValueError("Official resource host resolved to a non-public address")
    return url


class _ValidatedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, validator: Callable[[str], str]) -> None:
        super().__init__()
        self._validator = validator

    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> urllib.request.Request | None:
        self._validator(new_url)
        return super().redirect_request(request, file_pointer, code, message, headers, new_url)


@dataclass(frozen=True, slots=True)
class DownloadResult:
    sha256: str
    size_bytes: int
    content_type: str
    etag: str | None
    last_modified: str | None
    final_url: str


class SafeHttpClient:
    def __init__(
        self,
        *,
        allowed_hosts: Iterable[str],
        user_agent: str = "CITY-GAP-open-data/1.0",
        timeout_seconds: float = 30,
        resolver: Resolver = socket.getaddrinfo,
    ) -> None:
        self.allowed_hosts = frozenset(item.lower() for item in allowed_hosts)
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.resolver = resolver
        self._opener = urllib.request.build_opener(_ValidatedRedirectHandler(self.validate_url))

    def validate_url(self, url: str) -> str:
        return validate_public_https_url(
            url, allowed_hosts=self.allowed_hosts, resolver=self.resolver
        )

    def _open(self, url: str) -> Any:
        self.validate_url(url)
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json,text/csv,application/zip,*/*;q=0.5",
                "User-Agent": self.user_agent,
            },
        )
        try:
            return self._opener.open(request, timeout=self.timeout_seconds)
        except urllib.error.HTTPError as error:
            raise ValueError(f"Official resource returned HTTP {error.code}") from error
        except urllib.error.URLError as error:
            raise ValueError("Official resource retrieval failed") from error

    @staticmethod
    def _checked_length(headers: Any, max_bytes: int) -> None:
        declared = headers.get("Content-Length")
        if declared is not None and int(declared) > max_bytes:
            raise ValueError(f"Official resource exceeds the {max_bytes}-byte limit")

    def get_bytes(self, url: str, *, max_bytes: int) -> tuple[bytes, dict[str, str]]:
        with self._open(url) as response:
            self._checked_length(response.headers, max_bytes)
            payload = response.read(max_bytes + 1)
            if len(payload) > max_bytes:
                raise ValueError(f"Official resource exceeds the {max_bytes}-byte limit")
            headers = {str(key).lower(): str(value) for key, value in response.headers.items()}
            headers["final-url"] = response.geturl()
            return payload, headers

    def get_json(self, url: str, *, max_bytes: int = 32 * 1024 * 1024) -> dict[str, Any]:
        payload, _ = self.get_bytes(url, max_bytes=max_bytes)
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Official catalog did not return valid JSON") from error
        if not isinstance(value, dict):
            raise TypeError("Official catalog JSON must be an object")
        return value

    def download_to(self, url: str, destination: Path, *, max_bytes: int) -> DownloadResult:
        digest = hashlib.sha256()
        size = 0
        with self._open(url) as response:
            self._checked_length(response.headers, max_bytes)
            with destination.open("xb") as stream:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError(f"Official resource exceeds the {max_bytes}-byte limit")
                    digest.update(chunk)
                    stream.write(chunk)
            return DownloadResult(
                sha256=digest.hexdigest(),
                size_bytes=size,
                content_type=response.headers.get_content_type(),
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
                final_url=response.geturl(),
            )
