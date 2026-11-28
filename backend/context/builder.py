"""按硬保留规则和 token 预算构建可审计的模型上下文。"""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

from backend.context.models import ContextResult, Conversation, Message, TokenBudget
from backend.context.tokens import DEFAULT_TOKEN_COUNTER, TokenCounter


class BudgetUnsatisfiableError(ValueError):
    """表示硬保留消息已超过输入预算，附带可供 API 诊断的明细。"""

    def __init__(self, required_tokens: int, required_message_ids: list[str], input_budget: int = 0):
        """记录必需 token、消息 ID、超额量和可执行的调整建议。"""
        self.required_tokens = required_tokens
        self.required_message_ids = required_message_ids
        self.excess_tokens = max(0, required_tokens - input_budget)
        self.suggestions = ["Increase the input budget", "Shorten required memory fields"]
        super().__init__(f"Required messages need {required_tokens} tokens")


def estimate_tokens(text: str) -> int:
    """使用默认离线计数器保守估算文本 token 数。"""
    return DEFAULT_TOKEN_COUNTER.count_text(text)


def _message_tokens(message: Message, counter: TokenCounter) -> int:
    """计算消息正文、角色标签和固定封装开销。"""

    return counter.count_text(message.content) + counter.count_text(message.role) + 2


def build_context(
    conversation: Conversation,
    budget: TokenBudget,
    *,
    recent_message_count: int = 8,
    tool_result_char_limit: int = 1200,
    token_counter: TokenCounter = DEFAULT_TOKEN_COUNTER,
    summary: Message | None = None,
) -> ContextResult:
    """外置超长工具正文，硬保留关键消息，并以近期优先顺序填充剩余预算。"""

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

    memory_parts = [
        f"Objective: {conversation.objective}" if conversation.objective else "",
        f"Constraints: {'; '.join(conversation.constraints)}" if conversation.constraints else "",
        f"Decisions: {'; '.join(conversation.decisions)}" if conversation.decisions else "",
        f"Unfinished todos: {'; '.join(conversation.todos)}" if conversation.todos else "",
        f"Tool conclusions: {'; '.join(conversation.tool_conclusions)}" if conversation.tool_conclusions else "",
    ]
    memory_content = "\n".join(part for part in memory_parts if part)
    memory = Message(id="memory-required", role="summary", content=memory_content) if memory_content else None
    system = [message for message in prepared if message.role == "system"]
    latest_user = next((message for message in reversed(prepared) if message.role == "user"), None)
    required = system + ([memory] if memory else []) + ([latest_user] if latest_user and latest_user not in system else [])
    required_tokens = sum(_message_tokens(message, token_counter) for message in required)
    if required_tokens > budget.input_tokens:
        raise BudgetUnsatisfiableError(required_tokens, [message.id for message in required], budget.input_tokens)

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
    if memory:
        selected = [replace(message, source_ids=[item.id for item in omitted]) if message.id == memory.id else message for message in selected]
    candidate_summary = summary
    if candidate_summary is None and omitted and not memory:
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
            candidate_summary = Message(id="summary-generated", role="summary", content=summary_content, source_ids=source_ids)
    if candidate_summary and candidate_summary.id not in selected_ids:
        summary_cost = _message_tokens(candidate_summary, token_counter)
        if summary_cost <= remaining:
            selected.append(candidate_summary)
            selected_ids.add(candidate_summary.id)
            remaining -= summary_cost

    selected.sort(key=lambda message: next((index for index, source in enumerate(prepared) if source.id == message.id), len(prepared)))
    counts = {"system": 0, "memory": 0, "summary": 0, "recent": 0, "tools": 0}
    for message in selected:
        key = "system" if message.role == "system" else "memory" if message.id == "memory-required" else "summary" if message.role == "summary" else "tools" if message.role == "tool" else "recent"
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
