from __future__ import annotations

import json
from pathlib import Path
from threading import Lock


class UsageRecorder:
    """Append-only local call metadata; payload text is deliberately excluded."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def record(self, result) -> None:
        payload = result.to_record()
        if set(payload) & {"prompt", "messages", "content", "api_key", "secret"}:
            raise ValueError("Usage records must not contain prompt or secret material")
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(line + "\n")
