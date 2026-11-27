from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_declares_mock_only_mode():
    response = client.get("/health")

    assert response.json() == {
        "status": "ok",
        "provider": "mock",
        "mode": "mock",
        "estimated_usage": True,
    }


def test_mock_answer_route_returns_estimated_usage_without_real_provider():
    response = client.post("/api/mock/answer", json={"question": "what next?", "messages": []})

    assert response.status_code == 200
    data = response.json()
    assert data["usage"]["provider"] == "mock"
    assert data["usage"]["estimated"] is True
    assert "what next?" in data["answer"]


def test_mock_summary_route_has_structured_fields():
    response = client.post("/api/mock/summarize", json={"objective": "demo", "todos": ["test"]})

    assert response.status_code == 200
    assert "Objective: demo" in response.json()["summary"]
    assert "Todos: test" in response.json()["summary"]
