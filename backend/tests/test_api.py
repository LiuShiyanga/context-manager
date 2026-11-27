import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint_reports_mock_mode(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["provider"] == "mock"


def test_build_endpoint_returns_partitioned_context_and_retrievable_artifact(client):
    payload = {
        "session_id": "api-test-session",
        "budget": {"input_tokens": 800, "output_tokens": 20},
        "recent_message_count": 2,
        "messages": [
            {"id": "old-user", "role": "user", "content": "Please investigate this issue."},
            {"id": "old-tool", "role": "tool", "tool_name": "search", "content": "full result body " * 100},
            {"id": "current-user", "role": "user", "content": "What is the result?"},
        ],
        "objective": "Investigate the issue.",
        "constraints": ["Do not lose the original tool response."],
        "todos": ["Confirm the root cause."],
    }

    response = client.post("/api/context/build", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["input_tokens"] <= 800
    assert body["partitions"]["system"] == 0
    assert body["partitions"]["summary"] > 0
    tool_message = next(message for message in body["messages"] if message["role"] == "tool")
    assert tool_message["artifact_id"]
    artifact = client.get(f"/api/artifacts/{tool_message['artifact_id']}")
    assert artifact.status_code == 200
    assert artifact.json()["content"] == payload["messages"][1]["content"]


def test_build_endpoint_returns_explicit_budget_error_without_calling_model(client):
    payload = {
        "session_id": "too-small-session",
        "budget": {"input_tokens": 1, "output_tokens": 1},
        "messages": [
            {"id": "system", "role": "system", "content": "Preserve this system instruction."},
            {"id": "user", "role": "user", "content": "Preserve this user goal."},
        ],
    }

    response = client.post("/api/context/build", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "budget_unsatisfiable"
    assert response.json()["error"]["required_message_ids"] == ["system", "user"]


def test_read_artifact_rejects_unknown_id(client):
    response = client.get("/api/artifacts/unknown-id")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "artifact_not_found"
