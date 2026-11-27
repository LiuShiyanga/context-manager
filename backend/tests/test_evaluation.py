import json

from backend.evaluation import run_evaluation
from backend.data.store import FIXTURES


def test_evaluation_uses_fixed_versioned_synthetic_fixtures():
    report = run_evaluation(4096)

    assert report["dataset_version"] == FIXTURES.manifest["dataset_version"]
    assert report["fixture_sha256"] == FIXTURES.manifest["files"]
    assert len(report["results"]) == 10
    assert report["real_provider_requests"] == 0


def test_evaluation_is_deterministic_except_duration_is_not_recorded():
    first = run_evaluation(4096)
    second = run_evaluation(4096)

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["quality_conclusion"].startswith("None.")


def test_report_does_not_misstate_mock_as_quality_result():
    report = run_evaluation(4096)

    assert all("not a quality metric" in row["scoring_note"] for row in report["results"])
    assert all(row["baseline"]["estimated"] for row in report["results"])
