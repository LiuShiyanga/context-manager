"""提供统一的上下文模型适配接口及 Anthropic、确定性 Mock 实现。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from time import perf_counter
from typing import Any, Protocol

from backend.context.models import Message
from backend.context.tokens import DEFAULT_TOKEN_COUNTER


@dataclass(frozen=True)
class ProviderResult:
    """封装模型正文及可安全写入 usage 日志的调用元数据。"""

    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated: bool
    duration_ms: float
    status: str = "ok"

    def to_record(self) -> dict:
        """转换为 usage 记录；调用方负责在持久化前移除正文。"""

        return asdict(self)


class ContextProvider(Protocol):
    """约束摘要与问答 provider 的共同能力，便于替换真实和 Mock 实现。"""

    provider_name: str
    model_name: str
    estimated: bool

    def summarize(self, messages: list[Message], *, objective: str = "", constraints: list[str] | None = None,
                  decisions: list[str] | None = None, todos: list[str] | None = None,
                  tool_conclusions: list[str] | None = None, max_tokens: int = 512) -> ProviderResult:
        """把历史消息压缩为可追踪来源的结构化摘要。"""

        ...

    def answer(self, messages: list[Message], question: str, *, max_tokens: int = 512) -> ProviderResult:
        """基于已选上下文回答问题并报告调用 usage。"""

        ...


class AnthropicProvider:
    """通过官方 SDK 调用 Anthropic，且不把提示词或回答写入遥测日志。"""

    provider_name = "anthropic"
    estimated = False

    def __init__(self, api_key: str | None = None, model_name: str | None = None,
                 client: Any | None = None, timeout: float = 30):
        """读取显式参数或环境配置，并允许测试注入兼容 SDK 的客户端。"""

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model_name = model_name or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
        if client is None:
            if not self.api_key:
                raise ValueError("ANTHROPIC_API_KEY is required for the Anthropic provider.")
            from anthropic import Anthropic
            client = Anthropic(api_key=self.api_key, timeout=timeout)
        self.client = client

    @staticmethod
    def _payload(messages: list[Message]) -> tuple[str, list[dict[str, str]]]:
        """把领域角色规范化为 Anthropic 的 system 与交替消息载荷。"""

        system_parts: list[str] = []
        payload: list[dict[str, str]] = []
        for message in messages:
            if message.role == "system":
                system_parts.append(message.content)
                continue
            role = "assistant" if message.role == "assistant" else "user"
            content = message.content
            if message.role in {"tool", "summary"}:
                content = f"[{message.role}{': ' + message.tool_name if message.tool_name else ''}] {content}"
            if payload and payload[-1]["role"] == role:
                payload[-1]["content"] += "\n\n" + content
            else:
                payload.append({"role": role, "content": content})
        return "\n\n".join(system_parts), payload

    def _create(self, *, system: str, messages: list[dict[str, str]], max_tokens: int) -> ProviderResult:
        """执行一次 SDK 调用，提取文本和实际 usage，并隐藏底层异常正文。"""

        started = perf_counter()
        kwargs: dict[str, Any] = {"model": self.model_name, "max_tokens": max_tokens, "messages": messages}
        if system:
            kwargs["system"] = system
        try:
            response = self.client.messages.create(**kwargs)
            text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
            return ProviderResult(
                text=text,
                provider=self.provider_name,
                model=response.model,
                input_tokens=int(response.usage.input_tokens),
                output_tokens=int(response.usage.output_tokens),
                estimated=False,
                duration_ms=round((perf_counter() - started) * 1000, 3),
            )
        except Exception as error:
            raise RuntimeError(f"Anthropic request failed ({type(error).__name__}).") from None

    def answer(self, messages: list[Message], question: str, *, max_tokens: int = 512) -> ProviderResult:
        """将已构建上下文与当前问题发送给模型，并返回 API 实际 usage。"""

        system, payload = self._payload(messages)
        payload.append({"role": "user", "content": question})
        return self._create(system=system, messages=payload, max_tokens=max_tokens)

    def summarize(self, messages: list[Message], *, objective: str = "", constraints: list[str] | None = None,
                  decisions: list[str] | None = None, todos: list[str] | None = None,
                  tool_conclusions: list[str] | None = None, max_tokens: int = 512) -> ProviderResult:
        """要求模型输出固定 JSON 结构，保留记忆字段及原消息来源映射。"""

        notes = {
            "objective": objective,
            "constraints": constraints or [],
            "decisions": decisions or [],
            "todos": todos or [],
            "tool_conclusions": tool_conclusions or [],
        }
        source = "\n".join(f"[id={message.id} role={message.role}] {message.content}" for message in messages)
        prompt = f"Structured notes supplied by the application: {notes}\n\nConversation to compress:\n{source}"
        system = (
            "Return only one valid JSON object with keys objective, constraints, decisions, todos, "
            "tool_conclusions, source_ids, and covered_range. Preserve confirmed facts and unresolved work; "
            "source_ids must contain the exact message IDs supporting the summary. Do not invent facts."
        )
        return self._create(system=system, messages=[{"role": "user", "content": prompt}], max_tokens=max_tokens)


class MockProvider:
    """提供可重复的离线输出，用于验证流程而非评估模型质量。"""

    provider_name = "mock"
    model_name = "deterministic-v1"
    estimated = True

    @staticmethod
    def _usage(prompt: str, response: str, started: float) -> ProviderResult:
        """用离线计数器构造带估算标记的确定性调用结果。"""

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
                  tool_conclusions: list[str] | None = None, max_tokens: int = 512) -> ProviderResult:
        """按固定规则拼接结构化记忆，生成不依赖网络的摘要结果。"""

        started = perf_counter()
        sections = [
            ("Objective", [objective] if objective else []), ("Constraints", constraints or []),
            ("Decisions", decisions or []), ("Todos", todos or []),
            ("Tool conclusions", tool_conclusions or []),
        ]
        content = "\n".join(f"{title}: {'; '.join(values)}" for title, values in sections if values)
        if not content:
            content = "\n".join(f"{message.role}: {message.content[:180]}" for message in messages)
        prompt = f"messages={len(messages)}; objective_chars={len(objective)}"
        return self._usage(prompt, content, started)

    def answer(self, messages: list[Message], question: str, *, max_tokens: int = 512) -> ProviderResult:
        """返回与问题绑定的确定性答案，并用离线计数器估算 usage。"""

        started = perf_counter()
        answer = f"Mock answer for: {question.strip()}" if question.strip() else "Mock answer: no question provided."
        prompt = f"messages={len(messages)}; question_chars={len(question)}"
        return self._usage(prompt, answer, started)
