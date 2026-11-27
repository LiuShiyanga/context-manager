from pathlib import Path

from backend.context.models import Message
from backend.context.providers import MockProvider
from backend.context.usage import UsageRecorder


def test_mock_provider_returns_stable_text_and_estimated_usage():
    provider = MockProvider()
    messages = [Message(id="m1", role="user", content="secret prompt body")]

    first = provider.answer(messages, "what is next?")
    second = provider.answer(messages, "what is next?")

    assert first.text == second.text
    assert first.provider == "mock"
    assert first.model == "deterministic-v1"
    assert first.estimated is True
    assert first.input_tokens > 0 and first.output_tokens > 0
    assert "secret prompt body" not in str(first.to_record())


def test_mock_summary_preserves_structured_memory_fields():
    result = MockProvider().summarize(
        [], objective="ship demo", constraints=["offline"], decisions=["use mock"], todos=["test"],
        tool_conclusions=["fixture only"],
    )

    assert "Objective: ship demo" in result.text
    assert "Constraints: offline" in result.text
    assert "Decisions: use mock" in result.text
    assert "Todos: test" in result.text
    assert "Tool conclusions: fixture only" in result.text


def test_usage_recorder_writes_metadata_without_prompt_content(tmp_path: Path):
    path = tmp_path / "usage.jsonl"
    result = MockProvider().answer([Message(id="m1", role="user", content="unique-secret-text")], "question")
    UsageRecorder(path).record(result)

    record = path.read_text(encoding="utf-8")
    assert '"provider": "mock"' in record
    assert "unique-secret-text" not in record
    assert '"estimated": true' in record
