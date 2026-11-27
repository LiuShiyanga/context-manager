from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_session_api_returns_fixed_fixture_and_requested_slice():
    response = client.get("/api/sessions/synthetic-garden-80?turns=10")

    assert response.status_code == 200
    data = response.json()
    assert data["synthetic"] is True
    assert data["turn_count"] == 10
    assert data["messages"][-1]["id"] == "tool-010"


def test_session_api_validates_turn_count():
    response = client.get("/api/sessions/synthetic-garden-80?turns=81")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_turn_count"


def test_questions_api_returns_versioned_synthetic_questions():
    response = client.get("/api/evaluations/questions")

    assert response.status_code == 200
    data = response.json()
    assert data["synthetic"] is True
    assert data["dataset_version"] == "1.0.0"
    assert len(data["questions"]) == 10
