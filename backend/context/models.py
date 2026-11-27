from dataclasses import dataclass, field
from typing import Literal


Role = Literal["system", "user", "assistant", "tool", "summary"]


@dataclass(frozen=True)
class Message:
    id: str
    role: Role
    content: str
    tool_name: str | None = None
    artifact_id: str | None = None
    source_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Conversation:
    messages: list[Message]
    session_id: str = "demo-session"
    objective: str = ""
    constraints: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
    tool_conclusions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TokenBudget:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class ContextResult:
    messages: list[Message]
    input_tokens: int
    partitions: dict[str, int]
    artifacts: dict[str, str]
    omitted_message_ids: list[str]
    estimated: bool = True
