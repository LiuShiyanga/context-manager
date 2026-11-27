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
    selected: list[Message] = []
    used = 0
    for message in reversed(messages):
        cost = len(message.content) // 3 + max(1, len(message.role) // 3) + 2
        if used + cost > input_budget:
            break
        selected.insert(0, message)
        used += cost
    return selected


def run_evaluation(input_budget: int = 4096) -> dict:
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
        baseline_messages = _baseline(conversation.messages, input_budget)
        managed = build_context(conversation, TokenBudget(input_budget, 512), recent_message_count=16)
        # Same mock answering protocol; this fixture intentionally does not claim semantic model quality.
        baseline_answer = provider.answer(baseline_messages, question["prompt"])
        managed_answer = provider.answer(managed.messages, question["prompt"])
        expected = question["expected_terms"]
        baseline_score = sum(term.casefold() in baseline_answer.text.casefold() for term in expected)
        managed_score = sum(term.casefold() in managed_answer.text.casefold() for term in expected)
        rows.append({
            "question_id": question["id"],
            "baseline": {"answer": baseline_answer.text, "score": baseline_score, "input_tokens": baseline_answer.input_tokens, "estimated": True},
            "managed": {"answer": managed_answer.text, "score": managed_score, "input_tokens": managed.input_tokens, "estimated": managed.estimated},
            "scoring_note": "Expected-term overlap is a deterministic pipeline check, not a quality metric.",
        })
    files = FIXTURES.manifest["files"]
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
