from backend.context.builder import BudgetUnsatisfiableError, build_context
from backend.context.models import Conversation, Message, TokenBudget


def test_preserves_system_and_recent_messages_within_budget():
    conversation = Conversation(
        messages=[
            Message(id="s", role="system", content="You are helpful."),
            Message(id="u1", role="user", content="Earlier request."),
            Message(id="a1", role="assistant", content="Earlier answer."),
            Message(id="u2", role="user", content="Current request."),
        ]
    )

    result = build_context(conversation, TokenBudget(input_tokens=20, output_tokens=4), recent_message_count=2)

    ids = [message.id for message in result.messages]
    assert "s" in ids
    assert "u2" in ids
    assert "u1" not in ids
    assert result.input_tokens <= 20
    assert result.partitions["system"] > 0
    assert result.partitions["recent"] > 0


def test_externalizes_long_tool_result_and_keeps_reference():
    conversation = Conversation(
        messages=[
            Message(id="tool-1", role="tool", content="a very long tool result that should be externalized", tool_name="search"),
            Message(id="user-1", role="user", content="Summarize the search result."),
        ]
    )

    result = build_context(conversation, TokenBudget(input_tokens=100, output_tokens=10), tool_result_char_limit=12)

    tool_message = next(message for message in result.messages if message.role == "tool")
    assert tool_message.artifact_id
    assert tool_message.content != conversation.messages[0].content
    assert result.artifacts[tool_message.artifact_id] == conversation.messages[0].content
    assert result.input_tokens <= 100


def test_builds_traceable_structured_summary_for_omitted_history():
    conversation = Conversation(
        messages=[
            Message(id="u-old", role="user", content="Original goal: migrate the service."),
            Message(id="a-old", role="assistant", content="Decision: keep the API backward compatible."),
            Message(id="tool-old", role="tool", content="Tests passed after migration."),
            Message(id="u-current", role="user", content="What remains?"),
        ],
        objective="Migrate the service.",
        constraints=["Keep the API backward compatible."],
        decisions=["Use a staged migration."],
        todos=["Update deployment docs."],
        tool_conclusions=["Tests passed after migration."],
    )

    result = build_context(conversation, TokenBudget(input_tokens=120, output_tokens=20), recent_message_count=1)

    summary = next(message for message in result.messages if message.role == "summary")
    assert "Migrate the service." in summary.content
    assert "Keep the API backward compatible." in summary.content
    assert "Update deployment docs." in summary.content
    assert "Tests passed after migration." in summary.content
    assert set(summary.source_ids) == {"u-old", "a-old", "tool-old"}
    assert result.partitions["summary"] > 0


def test_artifact_reference_is_stable_for_same_conversation():
    conversation = Conversation(
        session_id="stable-session",
        messages=[Message(id="tool-1", role="tool", content="x" * 100, tool_name="search")],
    )

    first = build_context(conversation, TokenBudget(input_tokens=100, output_tokens=10), tool_result_char_limit=10)
    second = build_context(conversation, TokenBudget(input_tokens=100, output_tokens=10), tool_result_char_limit=10)

    assert first.messages[0].artifact_id == second.messages[0].artifact_id
    assert first.messages[0].content == second.messages[0].content


def test_raises_without_dropping_required_messages_when_budget_is_too_small():
    conversation = Conversation(
        messages=[
            Message(id="s", role="system", content="System requirement."),
            Message(id="u", role="user", content="Current user goal."),
        ]
    )

    try:
        build_context(conversation, TokenBudget(input_tokens=1, output_tokens=1))
    except BudgetUnsatisfiableError as error:
        assert error.required_tokens > 1
        assert error.required_message_ids == ["s", "u"]
    else:
        raise AssertionError("Expected a budget error instead of silently dropping required messages")
