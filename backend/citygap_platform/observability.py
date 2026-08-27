"""Request-scoped audit context and secret-safe JSON request logs."""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse

LOGGER = logging.getLogger("citygap.request")
MAX_REQUEST_BODY_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class RequestContext:
    request_id: str = "system"
    actor: str = "system"


_CONTEXT: ContextVar[RequestContext | None] = ContextVar("citygap_request_context", default=None)


def current_request_context() -> RequestContext:
    return _CONTEXT.get() or RequestContext()


@contextmanager
def operation_context(actor: str, request_id: str):
    token = _CONTEXT.set(RequestContext(request_id=request_id[:200], actor=actor[:200]))
    try:
        yield
    finally:
        _CONTEXT.reset(token)


async def request_observability_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:200]
    identity = getattr(request.state, "identity", None)
    actor = identity.actor if identity else "anonymous"
    token = _CONTEXT.set(RequestContext(request_id=request_id, actor=actor))
    started = time.perf_counter()
    status = 500
    try:
        content_length = request.headers.get("content-length")
        if content_length is not None and not content_length.isdecimal():
            status = 400
            response = JSONResponse(status_code=400, content={"detail": "invalid content-length"})
            response.headers["X-Request-ID"] = request_id
            return response
        if (
            request.method in {"POST", "PUT", "PATCH"}
            and content_length is not None
            and int(content_length) > MAX_REQUEST_BODY_BYTES
        ):
            status = 413
            response = JSONResponse(
                status_code=413,
                content={"detail": "request body exceeds the 1 MiB platform limit"},
            )
            response.headers["X-Request-ID"] = request_id
            return response
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        parts = request.url.path.strip("/").split("/")
        city = parts[1] if len(parts) > 1 and parts[0] == "cities" else None
        LOGGER.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "actor": actor,
                    "method": request.method,
                    "path": request.url.path,
                    "city": city,
                    "dataset_version": None,
                    "job": parts[1] if len(parts) > 1 and parts[0] == "jobs" else None,
                    "scenario": parts[3] if len(parts) > 3 and parts[2] == "scenarios" else None,
                    "duration_ms": duration_ms,
                    "result": status,
                },
                ensure_ascii=False,
            )
        )
        _CONTEXT.reset(token)
