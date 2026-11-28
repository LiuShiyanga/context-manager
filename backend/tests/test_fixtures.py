"""验证合成会话的轮次语义、切片边界及文件完整性校验。"""

from pathlib import Path

import pytest

from backend.data.store import FixtureStore, FIXTURES


def test_session_has_80_user_turns_and_synthetic_only_content():
    """确认完整样本标记为合成数据，包含 80 个用户轮次及工具消息。"""

    session = FIXTURES.session_slice(80)

    assert session["synthetic"] is True
    assert session["turn_count"] == 80
    assert len([message for message in session["messages"] if message["role"] == "user"]) == 80
    assert any(message["role"] == "tool" for message in session["messages"])


def test_session_slices_end_on_requested_turn_with_attached_results():
    """确认切片包含末轮关联工具输出，但不会混入下一轮用户消息。"""

    session = FIXTURES.session_slice(10)

    assert session["messages"][-1]["id"].startswith("tool-010")
    assert not any(message["id"] == "user-011" for message in session["messages"])


@pytest.mark.parametrize("turns", [0, 81, -1])
def test_session_rejects_out_of_range_turns(turns):
    """覆盖零、负数和超过总轮数的非法切片参数。"""

    with pytest.raises(ValueError):
        FIXTURES.session_slice(turns)


def test_store_rejects_fixture_hash_mismatch(tmp_path: Path):
    """使用不匹配清单，确认存储器拒绝未经完整性校验的数据。"""

    from backend.data.generate_fixtures import main

    main_in = tmp_path
    (main_in / "manifest.json").write_text('{"files": {}}', encoding="utf-8")
    (main_in / "session-80.json").write_text("{}", encoding="utf-8")
    (main_in / "evaluation-questions.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        FixtureStore(main_in)
