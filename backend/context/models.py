"""上下文管理领域使用的不可变数据模型。"""

from dataclasses import dataclass, field
from typing import Literal


# 消息角色同时覆盖原始会话消息与构建阶段生成的摘要消息。
Role = Literal["system", "user", "assistant", "tool", "summary"]


@dataclass(frozen=True)
class Message:
    """表示一条可参与上下文选择的消息及其追踪元数据。"""

    id: str
    role: Role
    content: str
    # 工具消息可记录工具名和外置后的完整结果标识。
    tool_name: str | None = None
    artifact_id: str | None = None
    # 摘要消息通过来源 ID 保留其与被省略原消息之间的可追踪关系。
    source_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Conversation:
    """聚合原始消息及构建摘要所需的结构化会话记忆。"""

    messages: list[Message]
    session_id: str = "demo-session"
    objective: str = ""
    constraints: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
    tool_conclusions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TokenBudget:
    """分别记录允许使用的输入与输出 token 上限。"""

    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class ContextResult:
    """描述完成预算筛选后的上下文、统计结果与外置内容。"""

    messages: list[Message]
    input_tokens: int
    # 分区统计帮助调用方了解 token 分别消耗在何种消息上。
    partitions: dict[str, int]
    # artifact 字典只在当前构建结果中携带待持久化的完整工具正文。
    artifacts: dict[str, str]
    omitted_message_ids: list[str]
    # 当前默认计数器是离线估算器，因此默认将统计标记为估算值。
    estimated: bool = True
