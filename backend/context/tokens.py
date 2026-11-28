"""定义可替换的 token 计数契约及默认离线估算实现。"""

from __future__ import annotations

from typing import Protocol


class TokenCounter(Protocol):
    """Token 计数器契约；是否精确由具体实现通过 ``estimated`` 声明。"""

    estimated: bool

    def count_text(self, text: str) -> int:
        """返回给定文本的 token 数；具体精度由实现决定。"""

        ...


class ApproximateTokenCounter:
    """基于字符数的离线估算器，不等同于任何模型供应商的 tokenizer。"""

    estimated = True

    def count_text(self, text: str) -> int:
        """按约每三个字符一个 token 估算非空文本。"""

        return max(1, (len(text) + 2) // 3) if text else 0


# 默认实现无需网络或模型依赖，便于本地演示和可重复测试。
DEFAULT_TOKEN_COUNTER = ApproximateTokenCounter()
