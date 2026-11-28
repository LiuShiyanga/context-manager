"""编排 provider 摘要生成与确定性预算构建，隔离网络调用和选择策略。"""

from __future__ import annotations

import json

from backend.context.builder import build_context
from backend.context.models import Conversation, Message, TokenBudget
from backend.context.providers import ContextProvider, ProviderResult


def provider_summary_message(result: ProviderResult, fallback_source_ids: list[str]) -> Message:
    """校验 provider 的结构化摘要，并转换为带来源 ID 的领域消息。"""

    raw = result.text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].strip().lower() in {"```", "```json"}:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("Summary provider did not return valid JSON.") from error
    required = {"objective", "constraints", "decisions", "todos", "tool_conclusions", "source_ids", "covered_range"}
    if not isinstance(payload, dict) or not required.issubset(payload):
        raise ValueError("Summary provider response is missing required fields.")
    source_ids = [str(item) for item in payload["source_ids"]] or fallback_source_ids
    return Message(
        id="summary-provider",
        role="summary",
        content=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        source_ids=source_ids,
    )


def compress_and_build(
    conversation: Conversation,
    budget: TokenBudget,
    provider: ContextProvider,
    *,
    force_compress: bool,
    recent_message_count: int,
    tool_result_char_limit: int,
) -> tuple[object, Message | None, ProviderResult | None]:
    """按需压缩非近期历史，再把摘要交给纯本地构建器完成预算选择。"""

    summary_message = None
    summary_usage = None
    should_compress = force_compress or len(conversation.messages) > recent_message_count
    if should_compress:
        system_ids = {message.id for message in conversation.messages if message.role == "system"}
        latest_user = next((message for message in reversed(conversation.messages) if message.role == "user"), None)
        recent_ids = {message.id for message in conversation.messages[-recent_message_count:]} if recent_message_count else set()
        source = [
            message for message in conversation.messages
            if message.id not in system_ids and message.id not in recent_ids and message is not latest_user
        ]
        if source:
            summary_usage = provider.summarize(
                source,
                objective=conversation.objective,
                constraints=conversation.constraints,
                decisions=conversation.decisions,
                todos=conversation.todos,
                tool_conclusions=conversation.tool_conclusions,
                max_tokens=min(512, max(256, budget.output_tokens)),
            )
            summary_message = provider_summary_message(summary_usage, [message.id for message in source])
    result = build_context(
        conversation,
        budget,
        recent_message_count=recent_message_count,
        tool_result_char_limit=tool_result_char_limit,
        summary=summary_message,
    )
    return result, summary_message, summary_usage
