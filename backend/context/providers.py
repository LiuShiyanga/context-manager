"""定义上下文 provider 契约及可重复运行的离线 Mock 实现。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Protocol

from backend.context.models import Message
from backend.context.tokens import DEFAULT_TOKEN_COUNTER


@dataclass(frozen=True)
class ProviderResult:
    """统一承载 provider 输出、用量估算与调用状态。"""

    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated: bool
    duration_ms: float
    status: str = "ok"

    def to_record(self) -> dict:
        """转换为适合序列化和 usage 记录的普通字典。"""

        return asdict(self)


class ContextProvider(Protocol):
    """上下文摘要和问答 provider 必须实现的最小接口。"""

    provider_name: str
    model_name: str
    estimated: bool

    def summarize(self, messages: list[Message], *, objective: str = "", constraints: list[str] | None = None,
                  decisions: list[str] | None = None, todos: list[str] | None = None,
                  tool_conclusions: list[str] | None = None) -> ProviderResult: ...

    def answer(self, messages: list[Message], question: str) -> ProviderResult: ...


class MockProvider:
    """确定性的离线 provider；输出仅用于验证流程，不代表模型质量。"""

    provider_name = "mock"
    model_name = "deterministic-v1"
    estimated = True

    @staticmethod
    def _usage(prompt: str, response: str, started: float) -> ProviderResult:
        """为确定性结果生成统一的离线用量与耗时记录。"""

        return ProviderResult(
            text=response,
            provider="mock",
            model="deterministic-v1",
            input_tokens=DEFAULT_TOKEN_COUNTER.count_text(prompt),
            output_tokens=DEFAULT_TOKEN_COUNTER.count_text(response),
            estimated=True,
            duration_ms=round((perf_counter() - started) * 1000, 3),
        )

    def summarize(self, messages: list[Message], *, objective: str = "", constraints: list[str] | None = None,
                  decisions: list[str] | None = None, todos: list[str] | None = None,
                  tool_conclusions: list[str] | None = None) -> ProviderResult:
        """优先拼接结构化记忆；缺少记忆时使用消息片段形成固定摘要。"""

        started = perf_counter()
        # 固定的分区顺序确保相同输入始终产生相同摘要文本。
        sections = [
            ("Objective", [objective] if objective else []),
            ("Constraints", constraints or []),
            ("Decisions", decisions or []),
            ("Todos", todos or []),
            ("Tool conclusions", tool_conclusions or []),
        ]
        content = "\n".join(f"{title}: {'; '.join(values)}" for title, values in sections if values)
        if not content:
            content = "\n".join(f"{message.role}: {message.content[:180]}" for message in messages)
        # 遥测内容不包含提示词或结果正文，只记录数量和长度。
        prompt = f"messages={len(messages)}; objective_chars={len(objective)}; metadata_items={sum(len(v or []) for _, v in sections)}"
        return self._usage(prompt, content, started)

    def answer(self, messages: list[Message], question: str) -> ProviderResult:
        """返回包含问题文本的固定格式答案，用于离线评测链路。"""

        started = perf_counter()
        answer = f"Mock answer for: {question.strip()}" if question.strip() else "Mock answer: no question provided."
        # 同样只用消息数量和问题长度估算输入，避免 usage 记录泄漏正文。
        prompt = f"messages={len(messages)}; question_chars={len(question)}"
        return self._usage(prompt, answer, started)
