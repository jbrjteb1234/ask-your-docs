"""Structured JSON-lines logger — Python variant of /kit/ts/logger.

Emits one JSON object per line with the same event shape as the TS logger:
{ts, level, component, event, ...payload}. info/debug go to stdout,
warn/error to stderr, so hosted platforms (Railway, Vercel) can filter them.
"""

import json
import sys
from datetime import datetime, timezone

__all__ = ["Logger", "create_logger"]


def _emit(level: str, component: str, event: str, payload: dict) -> None:
    line = json.dumps(
        {
            "ts": datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": level,
            "component": component,
            "event": event,
            **payload,
        },
        default=str,
    )
    stream = sys.stderr if level in ("warn", "error") else sys.stdout
    print(line, file=stream, flush=True)


class Logger:
    def __init__(self, component: str):
        self._component = component

    def debug(self, event: str, **payload) -> None:
        _emit("debug", self._component, event, payload)

    def info(self, event: str, **payload) -> None:
        _emit("info", self._component, event, payload)

    def warn(self, event: str, **payload) -> None:
        _emit("warn", self._component, event, payload)

    def error(self, event: str, **payload) -> None:
        _emit("error", self._component, event, payload)


def create_logger(component: str) -> Logger:
    return Logger(component)
