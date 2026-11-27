from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION = "1.0.0"


def build_session() -> dict:
    messages = [{"id": "system-1", "role": "system", "content": "你是一个帮助规划虚构城市花园项目的助手。遵守安全限制，保留用户目标、约束、决定和待办。"}]
    for turn in range(1, 81):
        messages.append({"id": f"user-{turn:03}", "role": "user", "content": f"第 {turn} 轮：请更新虚构社区花园计划。重点关注第 {((turn - 1) % 8) + 1} 个种植区，并说明依据。"})
        messages.append({"id": f"assistant-{turn:03}", "role": "assistant", "content": f"第 {turn} 轮记录：已检查种植区 {((turn - 1) % 8) + 1}。保持低耗水、本地适生和无障碍通行；后续需核对志愿者排班与材料清单。"})
        if turn % 10 == 0:
            messages.append({"id": f"tool-{turn:03}", "role": "tool", "tool_name": "mock_garden_catalog", "content": (f"合成目录记录（第 {turn} 轮）：耐旱植物候选、虚构维护说明、虚构季节备注。" * 40)})
    return {
        "schema_version": "1.0.0",
        "dataset_version": VERSION,
        "session_id": "synthetic-garden-80",
        "synthetic": True,
        "turn_count": 80,
        "objective": "制定一个虚构社区花园的低耗水、无障碍分区与维护计划。",
        "constraints": ["使用合成数据", "优先低耗水植物", "保留无障碍通道", "不提出真实采购或施工建议"],
        "decisions": ["将八个种植区按日照分组", "工具目录结果只作为虚构示例"],
        "todos": ["检查志愿者排班", "复核材料清单"],
        "messages": messages,
    }


def build_questions() -> dict:
    return {
        "schema_version": "1.0.0",
        "dataset_version": VERSION,
        "synthetic": True,
        "questions": [
            {"id": "q01", "prompt": "项目的总体目标是什么？", "expected_terms": ["社区花园", "低耗水"]},
            {"id": "q02", "prompt": "有哪些不可违反的约束？", "expected_terms": ["无障碍", "合成数据"]},
            {"id": "q03", "prompt": "分成多少个种植区？", "expected_terms": ["八个"]},
            {"id": "q04", "prompt": "工具目录结果应如何使用？", "expected_terms": ["虚构"]},
            {"id": "q05", "prompt": "有哪些尚未完成的事项？", "expected_terms": ["志愿者排班", "材料清单"]},
            {"id": "q06", "prompt": "花园计划优先考虑什么植物特征？", "expected_terms": ["低耗水", "本地适生"]},
            {"id": "q07", "prompt": "维护计划应兼顾什么通行要求？", "expected_terms": ["无障碍通道"]},
            {"id": "q08", "prompt": "样本里是否包含真实采购信息？", "expected_terms": ["不", "虚构"]},
            {"id": "q09", "prompt": "目录示例数据是什么性质？", "expected_terms": ["合成", "虚构"]},
            {"id": "q10", "prompt": "本演示可以据此给出现实施工建议吗？", "expected_terms": ["不", "虚构"]},
        ],
    }


def write_json(path: Path, value: dict) -> bytes:
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(data)
    return data


def main() -> None:
    session_bytes = write_json(ROOT / "session-80.json", build_session())
    questions_bytes = write_json(ROOT / "evaluation-questions.json", build_questions())
    manifest = {
        "dataset_version": VERSION,
        "synthetic": True,
        "files": {
            "session-80.json": hashlib.sha256(session_bytes).hexdigest(),
            "evaluation-questions.json": hashlib.sha256(questions_bytes).hexdigest(),
        },
    }
    write_json(ROOT / "manifest.json", manifest)


if __name__ == "__main__":
    main()
