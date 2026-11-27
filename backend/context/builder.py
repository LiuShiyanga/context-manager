from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

from backend.context.models import ContextResult, Conversation, Message, TokenBudget
from backend.context.tokens import DEFAULT_TOKEN_COUNTER, TokenCounter


class BudgetUnsatisfiableError(ValueError):
    def __init__(self, required_tokens: int, required_message_ids: list[str]):
        self.required_tokens = required_tokens
        self.required_message_ids = required_message_ids
        super().__init__(f"Required messages need {required_tokens} tokens")


def estimate_tokens(text: str) -> int:
    """Conservative, clearly approximate offline token estimate."""
    return DEFAULT_TOKEN_COUNTER.count_text(text)


def _message_tokens(message: Message, counter: TokenCounter) -> int:
    return counter.count_text(message.content) + counter.count_text(message.role) + 2


def build_context(
    conversation: Conversation,
    budget: TokenBudget,
    *,
    recent_message_count: int = 8,
    tool_result_char_limit: int = 1200,
    token_counter: TokenCounter = DEFAULT_TOKEN_COUNTER,
) -> ContextResult:
    if budget.input_tokens < 0 or budget.output_tokens < 0:
        raise ValueError("Token budgets must be non-negative")
    if recent_message_count < 0 or tool_result_char_limit < 0:
        raise ValueError("Message count and tool result limit must be non-negative")
    ids = [message.id for message in conversation.messages]
    if len(ids) != len(set(ids)):
        raise ValueError("Message IDs must be unique within a conversation")

    artifacts: dict[str, str] = {}
    prepared: list[Message] = []
    for message in conversation.messages:
        if message.role == "tool" and len(message.content) > tool_result_char_limit:
            # Never trust an artifact ID supplied by the caller.
            artifact_id = f"artifact-{sha256(f'{conversation.session_id}:{message.id}:{message.content}'.encode()).hexdigest()[:24]}"
            artifacts[artifact_id] = message.content
            excerpt = message.content[:tool_result_char_limit]
            prepared.append(replace(message, content=f"{excerpt}\n[Full result stored as {artifact_id}]", artifact_id=artifact_id))
        else:
            prepared.append(message)

    system = [message for message in prepared if message.role == "system"]
    latest_user = next((message for message in reversed(prepared) if message.role == "user"), None)
    required = system + ([latest_user] if latest_user and latest_user not in system else [])
    required_tokens = sum(_message_tokens(message, token_counter) for message in required)
    if required_tokens > budget.input_tokens:
        raise BudgetUnsatisfiableError(required_tokens, [message.id for message in required])

    selected: list[Message] = list(required)
    selected_ids = {message.id for message in selected}
    remaining = budget.input_tokens - required_tokens

    # The recent window is based on the source conversation, including required messages.
    recent_window = prepared[-recent_message_count:] if recent_message_count else []
    candidates = [message for message in recent_window if message.id not in selected_ids and message.role != "summary"]
    for message in reversed(candidates):
        cost = _message_tokens(message, token_counter)
        if cost <= remaining:
            selected.append(message)
            selected_ids.add(message.id)
            remaining -= cost

    omitted = [message for message in prepared if message.id not in selected_ids and message.role != "system"]
    summary = None
    if omitted:
        source_ids = [message.id for message in omitted]
        summary_content = "\n".join(
            part for part in [
                f"Objective: {conversation.objective}" if conversation.objective else "",
                "Constraints: " + "; ".join(conversation.constraints) if conversation.constraints else "",
                "Decisions: " + "; ".join(conversation.decisions) if conversation.decisions else "",
                "Todos: " + "; ".join(conversation.todos) if conversation.todos else "",
                "Tool conclusions: " + "; ".join(conversation.tool_conclusions) if conversation.tool_conclusions else "",
            ] if part
        )
        if summary_content:
            summary = Message(id="summary-generated", role="summary", content=summary_content, source_ids=source_ids)
            summary_cost = _message_tokens(summary, token_counter)
            if summary_cost <= remaining:
                selected.append(summary)
                selected_ids.add(summary.id)
                remaining -= summary_cost

    selected.sort(key=lambda message: next((index for index, source in enumerate(prepared) if source.id == message.id), len(prepared)))
    counts = {"system": 0, "summary": 0, "recent": 0, "tools": 0}
    for message in selected:
        key = "system" if message.role == "system" else "summary" if message.role == "summary" else "tools" if message.role == "tool" else "recent"
        counts[key] += _message_tokens(message, token_counter)
    total = sum(counts.values())
    return ContextResult(
        messages=selected,
        input_tokens=total,
        partitions=counts,
        artifacts=artifacts,
        omitted_message_ids=[message.id for message in prepared if message.id not in selected_ids],
        estimated=token_counter.estimated,
    )
