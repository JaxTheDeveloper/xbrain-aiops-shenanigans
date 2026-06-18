"""Structured JSON logger — emits to stdout and appends to audit_log.jsonl."""

import json
import os
from datetime import datetime, timezone


_AUDIT_PATH = os.environ.get("AUDIT_LOG_PATH", "audit_log.jsonl")


class JsonLogger:
    def __init__(self, name: str):
        self._name = name

    def _emit(self, level: str, event_type: str, **kwargs):
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "event_type": event_type,
            **kwargs,
        }
        line = json.dumps(record)
        print(line, flush=True)
        try:
            with open(_AUDIT_PATH, "a") as fh:
                fh.write(line + "\n")
        except OSError:
            pass

    def info(self, event_type: str, **kwargs):
        self._emit("INFO", event_type, **kwargs)

    def warning(self, event_type: str, **kwargs):
        self._emit("WARNING", event_type, **kwargs)

    def error(self, event_type: str, **kwargs):
        self._emit("ERROR", event_type, **kwargs)
