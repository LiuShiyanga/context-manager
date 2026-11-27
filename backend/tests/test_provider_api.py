from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import routes

client = TestClient(app)


def test_health_declares_mock_only_mode():
    response = client.get("/health")

    assert response.json() == {
        "status": "ok",
        "provider": "mock",
        "mode": "mock",
        "estimated_usage": True,
        "debug_enabled": False,
    }


def test_mock_answer_route_returns_estimated_usage_without_real_provider():
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


def test_missing_artifact_returns_structured_404():
    response = client.get("/api/artifacts/artifact-missing123")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "artifact_not_found"
