"""验证 provider 端点的模式声明、错误协议与调试场景。"""

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import routes

client = TestClient(app)


def test_health_declares_mock_only_mode():
    """确认健康检查完整声明 Mock 模式，不暗示真实模型调用。"""

    response = client.get("/health")

    assert response.json() == {
        "status": "ok",
        "provider": "mock",
        "mode": "mock",
        "estimated_usage": True,
        "debug_enabled": False,
    }


def test_health_reports_anthropic_mode_without_creating_client(monkeypatch):
    monkeypatch.setenv("PROVIDER", "anthropic")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["provider"] == "anthropic"
    assert response.json()["mode"] == "anthropic"
    assert response.json()["estimated_usage"] is False



def test_mock_answer_route_returns_estimated_usage_without_real_provider():
    """确认问答端点返回确定性答案及明确标记的 Mock 用量。"""

    response = client.post("/api/mock/answer", json={"question": "what next?", "messages": []})

    assert response.status_code == 200
    data = response.json()
    assert data["usage"]["provider"] == "mock"
    assert data["usage"]["estimated"] is True
    assert "what next?" in data["answer"]


def test_summary_provider_failure_returns_structured_error(monkeypatch):
    def fail_summary(*args, **kwargs):
        raise routes.ProviderError("mock summary failed")

    monkeypatch.setattr(routes.PROVIDER, "summarize", fail_summary)
    response = client.post("/api/mock/summarize", json={"objective": "demo"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_error"


def test_invalid_mock_payload_returns_structured_error():
    response = client.post("/api/mock/answer", json={"question": "x", "messages": ["not a message"]})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_debug_scenarios_are_disabled_by_default():
    response = client.post("/api/debug/trigger", json={"scenario": "summary_failure"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "debug_disabled"


def test_debug_scenarios_return_structured_errors_when_enabled(monkeypatch):
    monkeypatch.setattr(routes, "DEBUG_ENABLED", True)

    expectations = {
        "budget_unsatisfiable": (422, "budget_unsatisfiable"),
        "summary_failure": (503, "provider_error"),
        "artifact_missing": (404, "artifact_not_found"),
    }
    for scenario, (status, code) in expectations.items():
        response = client.post("/api/debug/trigger", json={"scenario": scenario})
        assert response.status_code == status
        assert response.json()["error"]["code"] == code


def test_debug_rejects_unknown_scenarios():
    response = client.post("/api/debug/trigger", json={"scenario": "anything_else"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"



def test_context_answer_builds_compresses_and_calls_injected_provider(monkeypatch):
    class FakeProvider:
        provider_name = "fake"
        model_name = "fake-model"
        estimated = False

        def __init__(self):
            self.answer_messages = None

        def summarize(self, messages, **kwargs):
            from backend.context.providers import ProviderResult
            return ProviderResult(
                text='{"objective":"preserve goal","constraints":["safe"],"decisions":[],"todos":["ship"],"tool_conclusions":[],"source_ids":["u-old","a-old"],"covered_range":"u-old..a-old"}',
                provider="fake", model="fake-model", input_tokens=40, output_tokens=20,
                estimated=False, duration_ms=2.0,
            )

        def answer(self, messages, question, *, max_tokens=512):
            from backend.context.providers import ProviderResult
            self.answer_messages = messages
            return ProviderResult(
                text="verified answer", provider="fake", model="fake-model",
                input_tokens=150, output_tokens=30, estimated=False, duration_ms=3.0,
            )

    provider = FakeProvider()
    monkeypatch.setattr(routes, "get_provider", lambda: provider)
    response = client.post("/api/context/answer", json={
        "session_id": "api-flow",
        "messages": [
            {"id": "u-old", "role": "user", "content": "old context " * 100},
            {"id": "a-old", "role": "assistant", "content": "old answer " * 100},
            {"id": "u-now", "role": "user", "content": "current request"},
        ],
        "budget": {"input_tokens": 500, "output_tokens": 80},
        "recent_message_count": 1,
        "tool_result_char_limit": 200,
        "objective": "preserve goal",
        "constraints": ["safe"],
        "decisions": [],
        "todos": ["ship"],
        "tool_conclusions": [],
        "question": "what next?",
        "force_compress": True,
    })

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "verified answer"
    assert data["usage"]["input_tokens"] == 150
    assert data["compression"]["performed"] is True
    assert data["compression"]["summary"]["source_ids"] == ["u-old", "a-old"]
    assert any(message["id"] == "summary-provider" for message in data["context"]["messages"])
    assert provider.answer_messages


def test_provider_summary_accepts_fenced_json():
    from backend.context.providers import ProviderResult
    from backend.context.service import provider_summary_message

    result = ProviderResult(
        text='```json\n{"objective":"goal","constraints":[],"decisions":[],"todos":[],"tool_conclusions":[],"source_ids":["u1"],"covered_range":"u1..u1"}\n```',
        provider="fake", model="fake", input_tokens=1, output_tokens=1,
        estimated=False, duration_ms=1.0,
    )

    summary = provider_summary_message(result, ["fallback"])

    assert summary.source_ids == ["u1"]
    assert '"objective": "goal"' in summary.content



def test_budget_failure_never_calls_answer_provider(monkeypatch):
    class NeverCallProvider:
        provider_name = "fake"
        model_name = "fake-model"
        estimated = False

        def answer(self, *args, **kwargs):
            raise AssertionError("provider must not be called")

    monkeypatch.setattr(routes, "get_provider", lambda: NeverCallProvider())
    response = client.post("/api/context/answer", json={
        "messages": [{"id": "u", "role": "user", "content": "required current request"}],
        "budget": {"input_tokens": 1, "output_tokens": 10},
        "objective": "required objective",
        "question": "answer",
    })

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "budget_unsatisfiable"
    assert response.json()["error"]["excess_tokens"] > 0


def test_missing_artifact_returns_structured_404():
    response = client.get("/api/artifacts/artifact-missing123")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "artifact_not_found"
