import pytest

from backend.context.builder import BudgetUnsatisfiableError, build_context
from backend.context.models import Conversation, Message, TokenBudget
from backend.context.tokens import ApproximateTokenCounter


def test_duplicate_message_ids_are_rejected():
    conversation = Conversation(messages=[
        Message(id="same", role="user", content="first"),
        Message(id="same", role="assistant", content="second"),
    ])

    with pytest.raises(ValueError, match="unique"):
        build_context(conversation, TokenBudget(100, 10))


def test_caller_artifact_id_is_replaced_with_deterministic_server_id():
    conversation = Conversation(session_id="s", messages=[
        Message(id="tool-1", role="tool", content="private full result " * 10, artifact_id="artifact-caller-controlled"),
        Message(id="user-1", role="user", content="summarize"),
    ])

    result = build_context(conversation, TokenBudget(300, 10), tool_result_char_limit=10)
    artifact_id = next(iter(result.artifacts))
    tool = next(message for message in result.messages if message.role == "tool")

    assert artifact_id.startswith("artifact-")
    assert artifact_id != "artifact-caller-controlled"
    assert tool.artifact_id == artifact_id
    assert result.artifacts[artifact_id] == conversation.messages[0].content


def test_summary_sources_track_omitted_messages_and_system_is_never_omitted():
    conversation = Conversation(
        messages=[
            Message(id="sys", role="system", content="policy"),
            Message(id="u-old", role="user", content="old"),
            Message(id="a-old", role="assistant", content="reply"),
            Message(id="u-current", role="user", content="now"),
        ],
        objective="finish garden plan",
        todos=["check schedule"],
    )

    result = build_context(conversation, TokenBudget(100, 10), recent_message_count=1)
    summary = next(message for message in result.messages if message.role == "summary")

    assert "sys" not in result.omitted_message_ids
    assert summary.source_ids == ["u-old", "a-old"]
    assert "finish garden plan" in summary.content


def test_counter_is_injected_and_estimation_metadata_is_preserved():
    class ExactTestCounter(ApproximateTokenCounter):
        estimated = False

        def count_text(self, text: str) -> int:
            return len(text)

    result = build_context(
        Conversation(messages=[Message(id="u", role="user", content="hi")]),
        TokenBudget(20, 0),
        token_counter=ExactTestCounter(),
    )

    assert result.input_tokens == 8
    assert result.estimated is False


def test_too_small_budget_lists_hard_required_message_ids():
    with pytest.raises(BudgetUnsatisfiableError) as error:
        build_context(
            Conversation(messages=[Message(id="s", role="system", content="system"), Message(id="u", role="user", content="goal")]),
            TokenBudget(1, 0),
        )

    assert error.value.required_message_ids == ["s", "u"]
