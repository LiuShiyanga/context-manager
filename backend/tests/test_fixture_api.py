"""验证版本化会话与问题集读取端点的响应契约。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_session_api_returns_fixed_fixture_and_requested_slice():
    """确认 API 返回指定轮数的固定合成会话及该轮附属工具结果。"""

    response = client.get("/api/sessions/synthetic-garden-80?turns=10")

    assert response.status_code == 200
    data = response.json()
    assert data["synthetic"] is True
    assert data["turn_count"] == 10
    assert data["messages"][-1]["id"] == "tool-010"


def test_session_api_validates_turn_count():
    """确认超出范围的轮数被映射为 422 及明确业务错误码。"""

    response = client.get("/api/sessions/synthetic-garden-80?turns=81")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_turn_count"


def test_questions_api_returns_versioned_synthetic_questions():
    """确认问题集携带数据版本和合成标记，且包含全部十道题。"""

    response = client.get("/api/evaluations/questions")

    assert response.status_code == 200
    data = response.json()
    assert data["synthetic"] is True
    assert data["dataset_version"] == "1.0.0"
    assert len(data["questions"]) == 10
