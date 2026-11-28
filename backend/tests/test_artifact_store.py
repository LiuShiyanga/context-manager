"""验证 artifact 存储的内容碰撞保护与路径安全边界。"""

from pathlib import Path

import pytest

from backend.app.schemas import ArtifactStore


def test_artifact_store_does_not_overwrite_existing_content(tmp_path: Path):
    """确认同一 ID 的不同正文不会覆盖原文件，碰撞后原内容仍可读取。"""

    store = ArtifactStore(tmp_path)
    store.put("artifact-safe123", "original")

    with pytest.raises(ValueError, match="collision"):
        store.put("artifact-safe123", "replacement")
    assert store.get("artifact-safe123") == "original"


def test_artifact_store_rejects_path_like_ids(tmp_path: Path):
    """确认包含路径片段或编码分隔符的 ID 无法访问存储目录之外的文件。"""

    store = ArtifactStore(tmp_path)

    assert store.get("artifact-..%2Fsecret") is None
    with pytest.raises(ValueError, match="Invalid"):
        store.put("artifact-../secret", "nope")
