"""定义上下文管理领域中的不可变消息、会话、预算和构建结果模型。"""

from dataclasses import dataclass, field
from typing import Literal


Role = Literal["system", "user", "assistant", "tool", "summary", "memory"]


@dataclass(frozen=True)
class Message:
    """表示一条可参与预算选择、摘要追踪或 artifact 外置的消息。"""

    id: str
    role: Role
    content: str
    tool_name: str | None = None
    artifact_id: str | None = None
    source_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Conversation:
    """聚合原始消息及必须跨轮次保留的结构化记忆字段。"""

    messages: list[Message]
    session_id: str = "demo-session"
    objective: str = ""
    constraints: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
    tool_conclusions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TokenBudget:
    """声明一次回答允许使用的输入与输出 token 上限。"""

    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class ContextResult:
    """返回最终上下文、分区成本、外置正文和被省略消息的审计信息。"""

    messages: list[Message]
    input_tokens: int
    partitions: dict[str, int]
    artifacts: dict[str, str]
    omitted_message_ids: list[str]
    estimated: bool = True
