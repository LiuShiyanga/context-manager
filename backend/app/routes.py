"""定义演示应用的 API 路由，并连接领域逻辑、fixture 与本地存储。"""

from pathlib import Path
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from backend.app.schemas import ArtifactStore, ContextAnswerRequest, ContextBuildRequest, ContextBuildResponse, MessageRequest, to_budget, to_conversation
from backend.context.builder import BudgetUnsatisfiableError, build_context
from backend.context.models import Message
from backend.context.providers import AnthropicProvider, MockProvider
from backend.context.service import compress_and_build
from backend.context.usage import UsageRecorder
from backend.data.store import FIXTURES
from backend.evaluation import run_evaluation

router = APIRouter()
# 进程级对象分别持久化完整工具结果、提供确定性输出并记录无正文 usage 元数据。
ARTIFACT_STORE = ArtifactStore(Path(__file__).resolve().parents[2] / "artifacts" / "runtime" / "store")
PROVIDER = MockProvider()
USAGE_RECORDER = UsageRecorder(Path(__file__).resolve().parents[2] / "artifacts" / "runtime" / "usage.jsonl")
DEBUG_ENABLED = False


def get_provider():
    """按环境配置延迟创建 provider，避免健康检查触发真实客户端初始化。"""

    mode = os.getenv("PROVIDER", "mock").lower()
    if mode == "anthropic":
        return AnthropicProvider()
    if mode != "mock":
        raise ValueError("PROVIDER must be mock or anthropic")
    return PROVIDER


class ProviderError(RuntimeError):
    """表示调试端点为演示错误处理而主动模拟的 provider 故障。"""


class RealAnswerRequest(BaseModel):
    """描述绕过构建器、直接验证当前 provider 问答能力的请求。"""

    messages: list[MessageRequest]
    question: str
    max_tokens: int = 300

    @field_validator("max_tokens")
    @classmethod
    def validate_max_tokens(cls, value: int) -> int:
        """限制直接回答端点的输出预算，防止无界请求。"""

        if not 1 <= value <= 512:
            raise ValueError("max_tokens must be between 1 and 512")
        return value


class DebugRequest(BaseModel):
    """选择一个仅在显式开启调试模式后可触发的受控错误场景。"""

    scenario: str

    @field_validator("scenario")
    @classmethod
    def validate_scenario(cls, value: str) -> str:
        """只接受预定义场景，避免把调试入口变成任意异常触发器。"""

        if value not in {"budget_unsatisfiable", "summary_failure", "artifact_missing"}:
            raise ValueError("Unsupported debug scenario")
        return value


def _error(code: str, message: str, **details):
    """构造所有业务端点共用的错误响应结构。"""

    return {"error": {"code": code, "message": message, **details}}


@router.get("/health")
def health():
    """报告服务状态、当前 provider 模式及用量是否为估算值。"""

    mode = os.getenv("PROVIDER", "mock").lower()
    provider = "anthropic" if mode == "anthropic" else PROVIDER.provider_name
    return {
        "status": "ok",
        "provider": provider,
        "mode": mode,
        "estimated_usage": mode != "anthropic",
        "debug_enabled": DEBUG_ENABLED,
    }


@router.post("/api/debug/trigger")
def trigger_debug(request: DebugRequest):
    """在调试开关启用时返回稳定的演示错误，默认对外隐藏该能力。"""

    if not DEBUG_ENABLED:
        raise HTTPException(status_code=404, detail=_error("debug_disabled", "Debug scenarios are disabled.")["error"])
    if request.scenario == "budget_unsatisfiable":
        raise HTTPException(
            status_code=422,
            detail=_error(
                "budget_unsatisfiable",
                "Debug scenario: required messages exceed the input budget.",
                required_tokens=9999,
                required_message_ids=["debug-system", "debug-user"],
            )["error"],
        )
    if request.scenario == "summary_failure":
        raise HTTPException(status_code=503, detail=_error("provider_error", "Debug scenario: mock summary provider failed.")["error"])
    raise HTTPException(status_code=404, detail=_error("artifact_not_found", "Debug scenario: artifact is missing.")["error"])


@router.post("/api/mock/answer")
def mock_answer(payload: dict):
    """生成确定性答案，并把不含消息正文的调用元数据落盘。"""

    question = str(payload.get("question", ""))
    if not isinstance(payload.get("messages", []), list):
        raise HTTPException(status_code=422, detail=_error("invalid_request", "messages must be a list.")["error"])
    try:
        messages = [Message(**message) for message in payload.get("messages", [])]
        result = PROVIDER.answer(messages, question)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=_error("invalid_request", "Invalid mock answer payload.")["error"]) from error
    USAGE_RECORDER.record(result)
    return {"answer": result.text, "usage": result.to_record()}


@router.post("/api/mock/summarize")
def mock_summarize(payload: dict):
    """用结构化记忆生成确定性摘要，并记录估算 usage。"""

    try:
        messages = [Message(**message) for message in payload.get("messages", [])]
        result = PROVIDER.summarize(
            messages,
            objective=str(payload.get("objective", "")),
            constraints=list(payload.get("constraints", [])),
            decisions=list(payload.get("decisions", [])),
            todos=list(payload.get("todos", [])),
            tool_conclusions=list(payload.get("tool_conclusions", [])),
        )
    except ProviderError as error:
        raise HTTPException(status_code=503, detail=_error("provider_error", str(error))["error"]) from error
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=_error("invalid_request", "Invalid mock summary payload.")["error"]) from error
    USAGE_RECORDER.record(result)
    return {"summary": result.text, "usage": result.to_record()}


@router.get("/api/sessions/synthetic-garden-80")
def read_synthetic_session(turns: int = 80):
    """返回指定轮数的合成会话，并把越界参数转换成业务错误。"""

    try:
        session = FIXTURES.session_slice(turns)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=_error("invalid_turn_count", str(error))["error"]) from error
    return session


@router.get("/api/evaluations/questions")
def read_evaluation_questions():
    """返回版本化的固定合成评测问题集。"""

    return FIXTURES.questions


@router.get("/api/evaluations/run")
def get_mock_evaluation(input_budget: int = 4096):
    """运行离线确定性流程比较，不发起任何真实 provider 请求。"""

    if input_budget < 1:
        raise HTTPException(status_code=422, detail=_error("invalid_budget", "input_budget must be positive.")["error"])
    return run_evaluation(input_budget)


@router.post("/api/context/build", response_model=ContextBuildResponse)
def build(request: ContextBuildRequest):
    """按预算构建上下文，并将外置工具正文保存到本地 artifact store。"""

    try:
        result = build_context(
            to_conversation(request),
            to_budget(request),
            recent_message_count=request.recent_message_count,
            tool_result_char_limit=request.tool_result_char_limit,
        )
    except BudgetUnsatisfiableError as error:
        raise HTTPException(
            status_code=422,
            detail=_error(
                "budget_unsatisfiable",
                str(error),
                required_tokens=error.required_tokens,
                required_message_ids=error.required_message_ids,
            )["error"],
        ) from error

    for artifact_id, content in result.artifacts.items():
        ARTIFACT_STORE.put(artifact_id, content)
    return ContextBuildResponse(
        session_id=request.session_id,
        messages=[MessageRequest.model_validate(message.__dict__) for message in result.messages],
        input_tokens=result.input_tokens,
        output_tokens=request.budget.get("output_tokens", 0),
        partitions=result.partitions,
        omitted_message_ids=result.omitted_message_ids,
        artifacts=list(result.artifacts),
        estimated=result.estimated,
    )


@router.post("/api/context/answer")
def context_answer(request: ContextAnswerRequest):
    """压缩历史、构建预算内上下文、调用 provider，并返回完整审计元数据。"""

    provider = get_provider()
    conversation = to_conversation(request)
    budget = to_budget(request)
    try:
        result, summary, summary_usage = compress_and_build(
            conversation,
            budget,
            provider,
            force_compress=request.force_compress,
            recent_message_count=request.recent_message_count,
            tool_result_char_limit=request.tool_result_char_limit,
        )
    except BudgetUnsatisfiableError as error:
        raise HTTPException(
            status_code=422,
            detail=_error(
                "budget_unsatisfiable",
                "Required context exceeds the input budget; no answer request was sent.",
                required_tokens=error.required_tokens,
                required_message_ids=error.required_message_ids,
                excess_tokens=error.excess_tokens,
                suggestions=error.suggestions,
            )["error"],
        ) from error
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=503, detail=_error("provider_error", str(error))["error"]) from error

    for artifact_id, content in result.artifacts.items():
        ARTIFACT_STORE.put(artifact_id, content)
    try:
        answer = provider.answer(result.messages, request.question, max_tokens=budget.output_tokens)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=_error("provider_error", str(error))["error"]) from error
    if summary_usage:
        USAGE_RECORDER.record(summary_usage)
    USAGE_RECORDER.record(answer)
    return {
        "session_id": request.session_id,
        "answer": answer.text,
        "usage": answer.to_record(),
        "context": {
            "messages": [MessageRequest.model_validate(message.__dict__).model_dump() for message in result.messages],
            "input_tokens": result.input_tokens,
            "output_tokens": budget.output_tokens,
            "partitions": result.partitions,
            "omitted_message_ids": result.omitted_message_ids,
            "artifacts": list(result.artifacts),
            "estimated": result.estimated,
        },
        "compression": {
            "performed": summary is not None,
            "summary": MessageRequest.model_validate(summary.__dict__).model_dump() if summary else None,
            "usage": summary_usage.to_record() if summary_usage else None,
        },
    }


@router.get("/api/artifacts/{artifact_id}")
def read_artifact(artifact_id: str):
    """按服务端生成的 ID 读取完整工具结果，不存在或格式非法时返回 404。"""

    content = ARTIFACT_STORE.get(artifact_id)
    if content is None:
        raise HTTPException(status_code=404, detail=_error("artifact_not_found", "Artifact was not found.")["error"])
    return {"artifact_id": artifact_id, "content": content}
