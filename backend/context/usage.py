"""将 provider 调用元数据以不含正文的 JSONL 形式记录到本地。"""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock


class UsageRecorder:
    """追加写入本地调用元数据，并刻意排除提示词和消息正文。"""

    def __init__(self, path: Path):
        """准备记录目录，并创建保护同一进程内并发写入的锁。"""

        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def record(self, result) -> None:
        """校验记录不含敏感字段后，在实例锁保护下追加一行 JSON。"""

        payload = result.to_record()
        # 即使未来 ProviderResult 扩展字段，也要阻止常见正文或密钥字段落盘。
        if set(payload) & {"prompt", "messages", "content", "api_key", "secret"}:
            raise ValueError("Usage records must not contain prompt or secret material")
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        # 锁覆盖打开与写入过程，避免并发请求把两条 JSON 记录交错在一起。
        with self._lock:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(line + "\n")
