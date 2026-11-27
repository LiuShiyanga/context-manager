from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from backend.app.schemas import ArtifactStore, ContextBuildRequest, ContextBuildResponse, MessageRequest, to_budget, to_conversation
from backend.context.builder import BudgetUnsatisfiableError, build_context
from backend.context.models import Message
from backend.context.providers import MockProvider
from backend.context.usage import UsageRecorder
from backend.data.store import FIXTURES
from backend.evaluation import run_evaluation

router = APIRouter()
ARTIFACT_STORE = ArtifactStore(Path(__file__).resolve().parents[2] / "artifacts" / "runtime" / "store")
PROVIDER = MockProvider()
USAGE_RECORDER = UsageRecorder(Path(__file__).resolve().parents[2] / "artifacts" / "runtime" / "usage.jsonl")
DEBUG_ENABLED = False


class ProviderError(RuntimeError):
    """Raised when a mock provider failure is simulated for the demo."""


class DebugRequest(BaseModel):
    scenario: str

    @field_validator("scenario")
    @classmethod
    def validate_scenario(cls, value: str) -> str:
        if value not in {"budget_unsatisfiable", "summary_failure", "artifact_missing"}:
            raise ValueError("Unsupported debug scenario")
        return value


def _error(code: str, message: str, **details):
    return {"error": {"code": code, "message": message, **details}}


@router.get("/health")
def health():
    return {"status": "ok", "provider": PROVIDER.provider_name, "mode": "mock", "estimated_usage": True, "debug_enabled": DEBUG_ENABLED}


@router.post("/api/debug/trigger")
def trigger_debug(request: DebugRequest):
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
    try:
        session = FIXTURES.session_slice(turns)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=_error("invalid_turn_count", str(error))["error"]) from error
    return session


@router.get("/api/evaluations/questions")
def read_evaluation_questions():
    return FIXTURES.questions


@router.get("/api/evaluations/run")
def get_mock_evaluation(input_budget: int = 4096):
    if input_budget < 1:
        raise HTTPException(status_code=422, detail=_error("invalid_budget", "input_budget must be positive.")["error"])
    return run_evaluation(input_budget)


@router.post("/api/context/build", response_model=ContextBuildResponse)
def build(request: ContextBuildRequest):
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


@router.get("/api/artifacts/{artifact_id}")
def read_artifact(artifact_id: str):
    content = ARTIFACT_STORE.get(artifact_id)
    if content is None:
        raise HTTPException(status_code=404, detail=_error("artifact_not_found", "Artifact was not found.")["error"])
    return {"artifact_id": artifact_id, "content": content}
