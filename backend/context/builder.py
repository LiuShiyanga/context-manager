from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

from backend.context.models import ContextResult, Conversation, Message, TokenBudget


class BudgetUnsatisfiableError(ValueError):
    def __init__(self, required_tokens: int, required_message_ids: list[str]):
        self.required_tokens = required_tokens
        self.required_message_ids = required_message_ids
        super().__init__(f"Required messages need {required_tokens} tokens")


def estimate_tokens(text: str) -> int:
    """Conservative, clearly approximate offline token estimate."""
    return max(1, (len(text) + 2) // 3) if text else 0


def _message_tokens(message: Message) -> int:
    return estimate_tokens(message.content) + estimate_tokens(message.role) + 2


def build_context(
    conversation: Conversation,
    budget: TokenBudget,
    *,
    recent_message_count: int = 8,
    tool_result_char_limit: int = 1200,
) -> ContextResult:
    if budget.input_tokens < 0 or budget.output_tokens < 0:
        raise ValueError("Token budgets must be non-negative")

    artifacts: dict[str, str] = {}
    prepared: list[Message] = []
    for message in conversation.messages:
        if message.role == "tool" and len(message.content) > tool_result_char_limit:
            artifact_id = message.artifact_id or f"artifact-{sha256(f'{conversation.session_id}:{message.id}'.encode()).hexdigest()[:20]}"
            artifacts[artifact_id] = message.content
            excerpt = message.content[:tool_result_char_limit]
            prepared.append(
                replace(
                    message,
                    content=f"{excerpt}\n[Truncated; read_artifact({artifact_id}) for full result.]",
                    artifact_id=artifact_id,
                )
            )
        else:
            prepared.append(message)

    system_messages = [message for message in prepared if message.role == "system"]
    non_system = [message for message in prepared if message.role != "system"]
    recent = non_system[-max(0, recent_message_count):] if recent_message_count else []
    latest_user = next((message for message in reversed(non_system) if message.role == "user"), None)
    omitted = [message for message in non_system if message not in recent and message is not latest_user]
    summary_message = None
    if omitted and any((conversation.objective, conversation.constraints, conversation.decisions, conversation.todos, conversation.tool_conclusions)):
        summary_parts = ([f"Objective: {conversation.objective}"] if conversation.objective else [])
        summary_parts.extend(f"Constraint/decision: {item}" for item in conversation.constraints + conversation.decisions)
        summary_parts.extend(f"Open todo: {item}" for item in conversation.todos)
        summary_parts.extend(f"Tool conclusion: {item}" for item in conversation.tool_conclusions)
        summary_content = "\n".join(summary_parts)
        summary_message = Message(
            id=f"summary-{omitted[0].id}-{omitted[-1].id}",
            role="summary",
            content=summary_content,
            source_ids=[message.id for message in omitted],
        )
    required = system_messages + ([latest_user] if latest_user else [])
    required_tokens = sum(_message_tokens(message) for message in required)
    if required_tokens > budget.input_tokens:
        raise BudgetUnsatisfiableError(required_tokens, [message.id for message in required])

    if summary_message:
        summary_tokens = _message_tokens(summary_message)
        if summary_tokens <= budget.input_tokens - required_tokens:
            required.append(summary_message)
            required_tokens += summary_tokens
        else:
            summary_message = None

    selected_ids = {message.id for message in required}
    selected = list(required)
    remaining = budget.input_tokens - sum(_message_tokens(message) for message in selected)
    for message in reversed(recent):
        if message.id in selected_ids:
            continue
        cost = _message_tokens(message)
        if cost <= remaining:
            selected.append(message)
            selected_ids.add(message.id)
            remaining -= cost

    selected.sort(key=lambda message: next((index for index, source in enumerate(prepared) if source.id == message.id), -1))
    counts = {"system": 0, "summary": 0, "recent": 0, "tools": 0}
    for message in selected:
        key = "system" if message.role == "system" else "summary" if message.role == "summary" else "tools" if message.role == "tool" else "recent"
        counts[key] += _message_tokens(message)
    total = sum(counts.values())
    return ContextResult(
        messages=selected,
        input_tokens=total,
        partitions=counts,
        artifacts=artifacts,
        omitted_message_ids=[message.id for message in prepared if message.id not in selected_ids],
        estimated=True,
    )
