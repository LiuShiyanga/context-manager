"""定义 API 请求/响应模型、领域转换函数和本地 artifact 存储。"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from backend.context.models import Conversation, Message, TokenBudget


class MessageRequest(BaseModel):
    """API 层的消息结构，与领域消息保持字段兼容。"""

    id: str
    role: str
    content: str
    tool_name: str | None = None
    artifact_id: str | None = None
    source_ids: list[str] = Field(default_factory=list)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        """只接受上下文构建器能够识别的消息角色。"""

        if value not in {"system", "user", "assistant", "tool", "summary"}:
            raise ValueError("Unsupported message role")
        return value

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        """拒绝空白消息 ID，确保后续选择与来源追踪可靠。"""

        if not value.strip():
            raise ValueError("Message id cannot be empty")
        return value


class ContextBuildRequest(BaseModel):
    """描述一次上下文构建所需的消息、预算和结构化记忆。"""

    session_id: str = "demo-session"
    messages: list[MessageRequest]
    budget: dict[str, int]
    recent_message_count: int = Field(default=8, ge=0)
    tool_result_char_limit: int = Field(default=1200, ge=0)
    objective: str = ""
    constraints: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    todos: list[str] = Field(default_factory=list)
    tool_conclusions: list[str] = Field(default_factory=list)

    @field_validator("messages")
    @classmethod
    def validate_unique_message_ids(cls, value: list[MessageRequest]) -> list[MessageRequest]:
        """在进入领域层前拒绝会造成选择歧义的重复消息 ID。"""

        ids = [message.id for message in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Message IDs must be unique within a conversation")
        return value

    @field_validator("budget")
    @classmethod
    def validate_budget(cls, value: dict[str, int]) -> dict[str, int]:
        """限制预算字段集合，并确保输入、输出预算均为非负数。"""

        if set(value) - {"input_tokens", "output_tokens"}:
            raise ValueError("Budget only accepts input_tokens and output_tokens")
        if value.get("input_tokens", 0) < 0 or value.get("output_tokens", 0) < 0:
            raise ValueError("Token budgets must be non-negative")
        return value


class ContextBuildResponse(BaseModel):
    """向前端返回所选消息、预算分区和可回读 artifact 标识。"""

    session_id: str
    messages: list[MessageRequest]
    input_tokens: int
    output_tokens: int
    partitions: dict[str, int]
    omitted_message_ids: list[str]
    artifacts: list[str]
    estimated: bool = True


def to_conversation(request: ContextBuildRequest) -> Conversation:
    """把已校验的 API 请求转换为不依赖 Pydantic 的领域会话。"""

    return Conversation(
        session_id=request.session_id,
        messages=[Message(**message.model_dump()) for message in request.messages],
        objective=request.objective,
        constraints=request.constraints,
        decisions=request.decisions,
        todos=request.todos,
        tool_conclusions=request.tool_conclusions,
    )


def to_budget(request: ContextBuildRequest) -> TokenBudget:
    """从字典形式的 API 字段构造强类型 token 预算。"""

    return TokenBudget(
        input_tokens=request.budget.get("input_tokens", 0),
        output_tokens=request.budget.get("output_tokens", 0),
    )


class ArtifactStore:
    """使用受限 artifact ID 在指定目录内幂等保存完整工具正文。"""

    def __init__(self, root: Path):
        """固定并创建存储根目录，后续路径都必须位于该目录之下。"""

        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, artifact_id: str, content: str) -> None:
        """保存正文；同 ID 同内容视为幂等，不同内容则判定为碰撞。"""

        # ID 只允许固定前缀和字母数字后缀，先从语法上排除路径片段。
        if not artifact_id.startswith("artifact-") or not artifact_id[9:].isalnum():
            raise ValueError("Invalid artifact id")
        path = (self.root / f"{artifact_id}.txt").resolve()
        # 解析后的路径仍需位于根目录下，以防未来 ID 规则变化引入路径逃逸。
        if self.root not in path.parents:
            raise ValueError("Artifact path escaped store")
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise ValueError("Artifact ID collision")
            return
        path.write_text(content, encoding="utf-8")

    def get(self, artifact_id: str) -> str | None:
        """安全读取 artifact；格式非法、路径越界或文件不存在时统一返回 ``None``。"""

        if not artifact_id.startswith("artifact-") or not artifact_id[9:].isalnum():
            return None
        path = (self.root / f"{artifact_id}.txt").resolve()
        if self.root not in path.parents or not path.is_file():
            return None
        return path.read_text(encoding="utf-8")
