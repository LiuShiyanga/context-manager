"""验证 Mock 评测的数据可追溯性、结果确定性和质量声明边界。"""

import json

from backend.evaluation import run_evaluation
from backend.data.store import FIXTURES


def test_evaluation_uses_fixed_versioned_synthetic_fixtures():
    """确认报告记录固定数据版本、文件哈希、全部问题和零真实请求。"""

    report = run_evaluation(4096)

    assert report["dataset_version"] == FIXTURES.manifest["dataset_version"]
    assert report["fixture_sha256"] == FIXTURES.manifest["files"]
    assert len(report["results"]) == 10
    assert report["real_provider_requests"] == 0


def test_evaluation_is_deterministic_except_duration_is_not_recorded():
    """确认报告不记录易变化耗时，两次运行产生完全相同的序列化结果。"""

    first = run_evaluation(4096)
    second = run_evaluation(4096)

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["quality_conclusion"].startswith("None.")


def test_report_does_not_misstate_mock_as_quality_result():
    """确认关键词检查附带局限说明，且基线用量明确标注为估算。"""

    report = run_evaluation(4096)

    assert all("not a quality metric" in row["scoring_note"] for row in report["results"])
    assert all(row["baseline"]["estimated"] for row in report["results"])
