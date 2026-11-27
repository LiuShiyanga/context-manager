from __future__ import annotations

import hashlib
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent


class FixtureStore:
    def __init__(self, root: Path = DATA_DIR):
        self.root = root.resolve()
        self.manifest = self._load_json("manifest.json")
        self._verify("session-80.json")
        self._verify("evaluation-questions.json")
        self.session = self._load_json("session-80.json")
        self.questions = self._load_json("evaluation-questions.json")

    def _load_json(self, name: str) -> dict:
        return json.loads((self.root / name).read_text(encoding="utf-8"))

    def _verify(self, name: str) -> None:
        data = (self.root / name).read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != self.manifest["files"].get(name):
            raise ValueError(f"Synthetic fixture hash mismatch: {name}")

    def session_slice(self, turns: int) -> dict:
        if turns < 1 or turns > self.session["turn_count"]:
            raise ValueError("turns must be between 1 and 80")
        last_user_id = f"user-{turns:03}"
        messages = self.session["messages"]
        end = next(i for i, message in enumerate(messages) if message["id"] == last_user_id)
        # Include that turn's assistant response and any tool output attached to it.
        while end + 1 < len(messages) and messages[end + 1]["role"] != "user":
            end += 1
        return {**self.session, "messages": messages[:end + 1], "turn_count": turns}


FIXTURES = FixtureStore()
