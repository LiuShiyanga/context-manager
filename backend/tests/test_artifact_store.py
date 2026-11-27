from pathlib import Path

import pytest

from backend.app.schemas import ArtifactStore


def test_artifact_store_does_not_overwrite_existing_content(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    store.put("artifact-safe123", "original")

    with pytest.raises(ValueError, match="collision"):
        store.put("artifact-safe123", "replacement")
    assert store.get("artifact-safe123") == "original"


def test_artifact_store_rejects_path_like_ids(tmp_path: Path):
    store = ArtifactStore(tmp_path)

    assert store.get("artifact-..%2Fsecret") is None
    with pytest.raises(ValueError, match="Invalid"):
        store.put("artifact-../secret", "nope")
