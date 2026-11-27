from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from backend.context.models import Conversation, Message, TokenBudget


class MessageRequest(BaseModel):
    id: str
    role: str
    content: str
    tool_name: str | None = None
    artifact_id: str | None = None
    source_ids: list[str] = Field(default_factory=list)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in {"system", "user", "assistant", "tool", "summary"}:
            raise ValueError("Unsupported message role")
        return value

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message id cannot be empty")
        return value


class ContextBuildRequest(BaseModel):
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
        ids = [message.id for message in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Message IDs must be unique within a conversation")
        return value

    @field_validator("budget")
    @classmethod
    def validate_budget(cls, value: dict[str, int]) -> dict[str, int]:
        if set(value) - {"input_tokens", "output_tokens"}:
            raise ValueError("Budget only accepts input_tokens and output_tokens")
        if value.get("input_tokens", 0) < 0 or value.get("output_tokens", 0) < 0:
            raise ValueError("Token budgets must be non-negative")
        return value


class ContextBuildResponse(BaseModel):
    session_id: str
    messages: list[MessageRequest]
    input_tokens: int
    output_tokens: int
    partitions: dict[str, int]
    omitted_message_ids: list[str]
    artifacts: list[str]
    estimated: bool = True


def to_conversation(request: ContextBuildRequest) -> Conversation:
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
    return TokenBudget(
        input_tokens=request.budget.get("input_tokens", 0),
        output_tokens=request.budget.get("output_tokens", 0),
    )


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, artifact_id: str, content: str) -> None:
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
        if not artifact_id.startswith("artifact-") or not artifact_id[9:].isalnum():
            return None
        path = (self.root / f"{artifact_id}.txt").resolve()
        if self.root not in path.parents or not path.is_file():
            return None
        return path.read_text(encoding="utf-8")
