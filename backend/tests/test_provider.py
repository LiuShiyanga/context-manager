"""验证离线 Mock 输出、结构化摘要和 usage 记录的隐私约束。"""

from pathlib import Path

from backend.context.models import Message
from backend.context.providers import AnthropicProvider, MockProvider
from backend.context.usage import UsageRecorder


def test_mock_provider_returns_stable_text_and_estimated_usage():
    """确认相同问题产生稳定答案和估算用量，记录中不泄漏消息正文。"""

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
    """确认摘要包含目标、约束、决定、待办和工具结论五类结构化记忆。"""

    result = MockProvider().summarize(
        [], objective="ship demo", constraints=["offline"], decisions=["use mock"], todos=["test"],
        tool_conclusions=["fixture only"],
    )

    assert "Objective: ship demo" in result.text
    assert "Constraints: offline" in result.text
    assert "Decisions: use mock" in result.text
    assert "Todos: test" in result.text
    assert "Tool conclusions: fixture only" in result.text



def test_anthropic_provider_translates_messages_and_reports_actual_usage():
    class FakeMessages:
        def __init__(self):
            self.kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs
            content = type("Block", (), {"type": "text", "text": "real answer"})()
            usage = type("Usage", (), {"input_tokens": 123, "output_tokens": 17})()
            return type("Response", (), {"content": [content], "usage": usage, "model": "claude-test"})()

    fake_messages = FakeMessages()
    fake_client = type("Client", (), {"messages": fake_messages})()
    provider = AnthropicProvider(api_key="test-key", model_name="claude-test", client=fake_client)

    result = provider.answer(
        [Message(id="s", role="system", content="system rules"), Message(id="u", role="user", content="business input")],
        "final question",
        max_tokens=200,
    )

    assert result.text == "real answer"
    assert result.input_tokens == 123
    assert result.output_tokens == 17
    assert result.estimated is False
    assert fake_messages.kwargs == {
        "model": "claude-test",
        "max_tokens": 200,
        "system": "system rules",
        "messages": [
            {"role": "user", "content": "business input"},
            {"role": "user", "content": "final question"},
        ],
    }
    assert "business input" not in str(result.to_record())


def test_anthropic_summary_requests_structured_source_linked_output():
    class FakeMessages:
        def create(self, **kwargs):
            self.kwargs = kwargs
            content = type("Block", (), {"type": "text", "text": '{"objective":"ship","source_ids":["u1"]}'})()
            usage = type("Usage", (), {"input_tokens": 20, "output_tokens": 8})()
            return type("Response", (), {"content": [content], "usage": usage, "model": "claude-test"})()

    messages_api = FakeMessages()
    provider = AnthropicProvider(api_key="test-key", model_name="claude-test", client=type("Client", (), {"messages": messages_api})())

    result = provider.summarize([Message(id="u1", role="user", content="ship it")], objective="ship")

    assert result.text.startswith("{")
    assert "source_ids" in messages_api.kwargs["system"]
    assert "[id=u1 role=user] ship it" in messages_api.kwargs["messages"][0]["content"]


def test_usage_recorder_writes_metadata_without_prompt_content(tmp_path: Path):
    """确认落盘记录包含 provider 元数据，但不包含输入消息中的私密正文。"""

    path = tmp_path / "usage.jsonl"
    result = MockProvider().answer([Message(id="m1", role="user", content="unique-secret-text")], "question")
    UsageRecorder(path).record(result)

    record = path.read_text(encoding="utf-8")
    assert '"provider": "mock"' in record
    assert "unique-secret-text" not in record
    assert '"estimated": true' in record
