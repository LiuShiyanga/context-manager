from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Protocol

from backend.context.models import Message
from backend.context.tokens import DEFAULT_TOKEN_COUNTER


@dataclass(frozen=True)
class ProviderResult:
    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated: bool
    duration_ms: float
    status: str = "ok"

    def to_record(self) -> dict:
        return asdict(self)


class ContextProvider(Protocol):
    provider_name: str
    model_name: str
    estimated: bool

    def summarize(self, messages: list[Message], *, objective: str = "", constraints: list[str] | None = None,
                  decisions: list[str] | None = None, todos: list[str] | None = None,
                  tool_conclusions: list[str] | None = None) -> ProviderResult: ...

    def answer(self, messages: list[Message], question: str) -> ProviderResult: ...


class MockProvider:
    """Deterministic offline provider; output is a workflow fixture, not model-quality evidence."""

    provider_name = "mock"
    model_name = "deterministic-v1"
    estimated = True

    @staticmethod
    def _usage(prompt: str, response: str, started: float) -> ProviderResult:
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
        started = perf_counter()
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
        # Keep telemetry content-free: record counts only, never prompts/results.
        prompt = f"messages={len(messages)}; objective_chars={len(objective)}; metadata_items={sum(len(v or []) for _, v in sections)}"
        return self._usage(prompt, content, started)

    def answer(self, messages: list[Message], question: str) -> ProviderResult:
        started = perf_counter()
        answer = f"Mock answer for: {question.strip()}" if question.strip() else "Mock answer: no question provided."
        prompt = f"messages={len(messages)}; question_chars={len(question)}"
        return self._usage(prompt, answer, started)
