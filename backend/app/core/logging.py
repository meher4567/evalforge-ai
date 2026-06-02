"""
Structured logging for EvalForge AI.

Emits JSON log lines to stdout for Docker/CI log collection.
Every API request and worker task is logged with trace-level detail.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import UTC, datetime
from typing import Any


class _StructuredFormatter(logging.Formatter):
    """Format log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1] is not None:
            payload["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }
        for key, value in record.__dict__.items():
            if key not in {
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
            }:
                if isinstance(value, (str, int, float, bool, dict, list, type(None))):
                    payload[key] = value
        return json.dumps(payload, default=str)


def configure(structured: bool = True, level: str = "INFO") -> None:
    """
    Configure application-wide logging.

    Args:
        structured: If True, emit JSON lines to stdout (Docker-friendly).
                    If False, emit human-readable lines (dev-friendly).
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove any existing handlers
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if structured:
        handler.setFormatter(_StructuredFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)-7s] %(name)s | %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
    root.addHandler(handler)

    # Quiet noisy third-party loggers
    for name in ("sqlalchemy.engine", "httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(name).setLevel(logging.WARNING)


class RequestLogger:
    """
    Middleware-compatible request logger that tracks method, path, status, and latency.

    Usage in FastAPI:
        @app.middleware("http")
        async def log_requests(request, call_next):
            rl = RequestLogger(request)
            response = await call_next(request)
            rl.complete(response.status_code)
            return response
    """

    def __init__(self, method: str, path: str, extra: dict[str, Any] | None = None):
        self._logger = logging.getLogger("api.request")
        self._start = time.perf_counter()
        self._method = method
        self._path = path
        self._extra = extra or {}

    def complete(self, status_code: int) -> None:
        latency_ms = round((time.perf_counter() - self._start) * 1000)
        self._logger.info(
            "request completed",
            extra={
                "method": self._method,
                "path": self._path,
                "status": status_code,
                "latency_ms": latency_ms,
                **self._extra,
            },
        )


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the EvalForge naming convention."""
    return logging.getLogger(f"evalforge.{name}")
