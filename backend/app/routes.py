from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.app.schemas import ArtifactStore, ContextBuildRequest, ContextBuildResponse, MessageRequest, to_budget, to_conversation
from backend.context.builder import BudgetUnsatisfiableError, build_context
from backend.context.models import Message

router = APIRouter()
ARTIFACT_STORE = ArtifactStore(Path(__file__).resolve().parents[2] / "artifacts" / "runtime" / "store")


def _error(code: str, message: str, **details):
    return {"error": {"code": code, "message": message, **details}}


@router.get("/health")
def health():
    return {"status": "ok", "provider": "mock"}


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
