"""加载版本化合成 fixture，并在使用前验证文件完整性。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent


class FixtureStore:
    """提供经过清单哈希校验的会话和评测问题读取接口。"""

    def __init__(self, root: Path = DATA_DIR):
        """固定数据根目录，先验证内容，再把 fixture 加载到内存。"""

        self.root = root.resolve()
        self.manifest = self._load_json("manifest.json")
        # 必须先通过清单校验，避免应用使用被篡改或未同步更新的数据。
        self._verify("session-80.json")
        self._verify("evaluation-questions.json")
        self.session = self._load_json("session-80.json")
        self.questions = self._load_json("evaluation-questions.json")

    def _load_json(self, name: str) -> dict:
        """从固定根目录读取 UTF-8 JSON 对象。"""

        return json.loads((self.root / name).read_text(encoding="utf-8"))

    def _verify(self, name: str) -> None:
        """比对文件实际 SHA-256 与版本化清单中的预期值。"""

        data = (self.root / name).read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != self.manifest["files"].get(name):
            raise ValueError(f"Synthetic fixture hash mismatch: {name}")

    def session_slice(self, turns: int) -> dict:
        """返回前 N 个用户轮次，并包含第 N 轮关联的后续响应和工具输出。"""

        if turns < 1 or turns > self.session["turn_count"]:
            raise ValueError("turns must be between 1 and 80")
        last_user_id = f"user-{turns:03}"
        messages = self.session["messages"]
        end = next(i for i, message in enumerate(messages) if message["id"] == last_user_id)
        # 包含该轮的助手回复，以及附属于这一轮的所有工具输出。
        while end + 1 < len(messages) and messages[end + 1]["role"] != "user":
            end += 1
        return {**self.session, "messages": messages[:end + 1], "turn_count": turns}


# 应用导入时创建只读单例，使启动阶段就能发现 fixture 完整性问题。
FIXTURES = FixtureStore()
