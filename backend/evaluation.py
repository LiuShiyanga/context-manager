"""运行可重复的离线 Mock 上下文流程比较，并生成版本化报告。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from backend.context.builder import build_context
from backend.context.models import Conversation, Message, TokenBudget
from backend.context.providers import MockProvider
from backend.data.store import FIXTURES

ROOT = Path(__file__).resolve().parents[2]


def _baseline(messages: list[Message], input_budget: int) -> list[Message]:
    """从会话末尾向前截取消息，形成不含摘要策略的朴素基线。"""

    selected: list[Message] = []
    used = 0
    for message in reversed(messages):
        # 基线沿用简单字符估算，使比较无需真实 tokenizer 或外部服务。
        cost = len(message.content) // 3 + max(1, len(message.role) // 3) + 2
        if used + cost > input_budget:
            break
        selected.insert(0, message)
        used += cost
    return selected


def run_evaluation(input_budget: int = 4096) -> dict:
    """比较朴素截断与受管上下文流程，并返回确定性的报告字典。"""

    session = FIXTURES.session_slice(80)
    questions = FIXTURES.questions["questions"]
    conversation = Conversation(
        session_id=session["session_id"],
        messages=[Message(**message) for message in session["messages"]],
        objective=session["objective"], constraints=session["constraints"],
        decisions=session["decisions"], todos=session["todos"],
    )
    provider = MockProvider()
    rows = []
    for question in questions:
        # 每道题都以相同预算独立构建两个输入，避免前一题状态影响后一题。
        baseline_messages = _baseline(conversation.messages, input_budget)
        managed = build_context(conversation, TokenBudget(input_budget, 512), recent_message_count=16)
        # 两条流程使用同一个 Mock 回答协议；该 fixture 无意证明语义模型质量。
        baseline_answer = provider.answer(baseline_messages, question["prompt"])
        managed_answer = provider.answer(managed.messages, question["prompt"])
        expected = question["expected_terms"]
        # 关键词重叠只检查评测管线是否稳定运行，不应解释为答案质量分数。
        baseline_score = sum(term.casefold() in baseline_answer.text.casefold() for term in expected)
        managed_score = sum(term.casefold() in managed_answer.text.casefold() for term in expected)
        rows.append({
            "question_id": question["id"],
            "baseline": {"answer": baseline_answer.text, "score": baseline_score, "input_tokens": baseline_answer.input_tokens, "estimated": True},
            "managed": {"answer": managed_answer.text, "score": managed_score, "input_tokens": managed.input_tokens, "estimated": managed.estimated},
            "scoring_note": "Expected-term overlap is a deterministic pipeline check, not a quality metric.",
        })
    files = FIXTURES.manifest["files"]
    # 报告携带数据哈希和完整配置，确保离线结果可以追溯到固定输入。
    return {
        "report_version": "1.0.0",
        "dataset_version": FIXTURES.manifest["dataset_version"],
        "fixture_sha256": files,
        "configuration": {"input_budget": input_budget, "output_budget": 512, "provider": "mock", "provider_model": provider.model_name},
        "real_provider_requests": 0,
        "quality_conclusion": "None. Deterministic mock outputs do not measure model answer quality.",
        "results": rows,
    }


def main() -> None:
    """解析命令行参数、写入格式化报告，并打印最终文件哈希。"""

    parser = argparse.ArgumentParser(description="Run reproducible mock context evaluation")
    parser.add_argument("--input-budget", type=int, default=4096)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "mock-evaluation.json")
    args = parser.parse_args()
    if args.input_budget <= 0:
        parser.error("--input-budget must be positive")
    report = run_evaluation(args.input_budget)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(f"Wrote {args.output} (sha256={digest}; real_provider_requests=0)")


if __name__ == "__main__":
    main()
