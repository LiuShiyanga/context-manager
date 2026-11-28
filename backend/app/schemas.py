"""定义 HTTP 请求/响应模型、领域模型转换及本地 artifact 存储。"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from backend.context.models import Conversation, Message, TokenBudget


class MessageRequest(BaseModel):
    """表示 API 边界上的消息，并限制角色和 ID 的基本合法性。"""

    id: str
    role: str
    content: str
    tool_name: str | None = None
    artifact_id: str | None = None
    source_ids: list[str] = Field(default_factory=list)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        """拒绝领域模型无法识别的消息角色。"""

        if value not in {"system", "user", "assistant", "tool", "summary", "memory"}:
            raise ValueError("Unsupported message role")
        return value

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        """要求每条消息提供非空稳定 ID，以支持来源追踪和去重。"""

        if not value.strip():
            raise ValueError("Message id cannot be empty")
        return value


class ContextBuildRequest(BaseModel):
    """收集构建上下文所需的会话、预算、记忆和截断策略。"""

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
        """在构建前拒绝重复消息 ID，避免选择和来源映射产生歧义。"""

        ids = [message.id for message in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Message IDs must be unique within a conversation")
        return value

    @field_validator("budget")
    @classmethod
    def validate_budget(cls, value: dict[str, int]) -> dict[str, int]:
        """限制预算字段集合，并拒绝负数 token 上限。"""

        if set(value) - {"input_tokens", "output_tokens"}:
            raise ValueError("Budget only accepts input_tokens and output_tokens")
        if value.get("input_tokens", 0) < 0 or value.get("output_tokens", 0) < 0:
            raise ValueError("Token budgets must be non-negative")
        return value


class ContextAnswerRequest(ContextBuildRequest):
    """在构建参数基础上增加当前问题和是否强制压缩的开关。"""

    question: str
    force_compress: bool = False

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        """要求回答请求包含非空问题。"""

        if not value.strip():
            raise ValueError("Question cannot be empty")
        return value


class ContextBuildResponse(BaseModel):
    """描述已选上下文、预算分区、外置 artifact 和省略消息。"""

    session_id: str
    messages: list[MessageRequest]
    input_tokens: int
    output_tokens: int
    partitions: dict[str, int]
    omitted_message_ids: list[str]
    artifacts: list[str]
    estimated: bool = True


def to_conversation(request: ContextBuildRequest) -> Conversation:
    """把经过 Pydantic 校验的 API 请求转换为不可变领域会话。"""

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
    """从已校验请求中提取领域层使用的输入和输出预算。"""

    return TokenBudget(
        input_tokens=request.budget.get("input_tokens", 0),
        output_tokens=request.budget.get("output_tokens", 0),
    )


class ArtifactStore:
    """在受控目录中按服务端生成的稳定 ID 保存和读取完整工具正文。"""

    def __init__(self, root: Path):
        """创建存储目录并保存其规范化根路径，用于后续越界检查。"""

        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, artifact_id: str, content: str) -> None:
        """幂等写入 artifact；同一 ID 对应不同正文时拒绝覆盖。"""

        if not artifact_id.startswith("artifact-") or not artifact_id[9:].isalnum():
            raise ValueError("Invalid artifact id")
        path = (self.root / f"{artifact_id}.txt").resolve()
        if self.root not in path.parents:
            raise ValueError("Artifact path escaped store")
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise ValueError("Artifact ID collision")
            return
        path.write_text(content, encoding="utf-8")

    def get(self, artifact_id: str) -> str | None:
        """读取合法且位于存储根目录内的 artifact，不存在时返回 ``None``。"""

        if not artifact_id.startswith("artifact-") or not artifact_id[9:].isalnum():
            return None
        path = (self.root / f"{artifact_id}.txt").resolve()
        if self.root not in path.parents or not path.is_file():
            return None
        return path.read_text(encoding="utf-8")
