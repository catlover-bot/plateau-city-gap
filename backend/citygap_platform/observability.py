"""Request-scoped audit context and secret-safe JSON request logs."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock

from fastapi import Request
from fastapi.responses import JSONResponse

LOGGER = logging.getLogger("citygap.request")
MAX_REQUEST_BODY_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class RequestContext:
    request_id: str = "system"
    actor: str = "system"
    organization_id: str | None = None


_CONTEXT: ContextVar[RequestContext | None] = ContextVar("citygap_request_context", default=None)
_METRIC_LOCK = Lock()
_REQUEST_COUNT: dict[tuple[str, str, str], int] = defaultdict(int)
_REQUEST_DURATION_MS: dict[tuple[str, str], tuple[int, float]] = defaultdict(lambda: (0, 0.0))


def reset_request_metrics() -> None:
    """Clear process-local metrics for isolated tests."""

    with _METRIC_LOCK:
        _REQUEST_COUNT.clear()
        _REQUEST_DURATION_MS.clear()


def render_request_metrics() -> str:
    """Render bounded-cardinality process metrics in Prometheus text format."""

    lines = [
        "# HELP citygap_http_requests_total HTTP requests handled by this API process.",
        "# TYPE citygap_http_requests_total counter",
    ]
    with _METRIC_LOCK:
        for (method, route, status_class), value in sorted(_REQUEST_COUNT.items()):
            lines.append(
                f'citygap_http_requests_total{{method="{method}",route="{route}",'
                f'status_class="{status_class}"}} {value}'
            )
        lines.extend(
            [
                "# HELP citygap_http_request_duration_ms HTTP request duration by route.",
                "# TYPE citygap_http_request_duration_ms summary",
            ]
        )
        for (method, route), (count, duration_sum) in sorted(_REQUEST_DURATION_MS.items()):
            labels = f'method="{method}",route="{route}"'
            lines.append(f"citygap_http_request_duration_ms_count{{{labels}}} {count}")
            lines.append(f"citygap_http_request_duration_ms_sum{{{labels}}} {duration_sum:.3f}")
    return "\n".join(lines) + "\n"


def current_request_context() -> RequestContext:
    return _CONTEXT.get() or RequestContext()


@contextmanager
def operation_context(actor: str, request_id: str, organization_id: str | None = None):
    token = _CONTEXT.set(
        RequestContext(
            request_id=request_id[:200],
            actor=actor[:200],
            organization_id=organization_id,
        )
    )
    try:
        yield
    finally:
        _CONTEXT.reset(token)


async def request_observability_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:200]
    request.state.request_id = request_id
    identity = getattr(request.state, "identity", None)
    actor = identity.actor if identity else "anonymous"
    organization_id = identity.organization_id if identity else None
    token = _CONTEXT.set(
        RequestContext(
            request_id=request_id,
            actor=actor,
            organization_id=organization_id,
        )
    )
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
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        metric_key = (request.method, route_path)
        with _METRIC_LOCK:
            _REQUEST_COUNT[(request.method, route_path, f"{status // 100}xx")] += 1
            count, duration_sum = _REQUEST_DURATION_MS[metric_key]
            _REQUEST_DURATION_MS[metric_key] = (count + 1, duration_sum + duration_ms)
        parts = request.url.path.strip("/").split("/")
        city = parts[1] if len(parts) > 1 and parts[0] == "cities" else None
        LOGGER.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "actor": actor,
                    "organization_id": organization_id,
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
