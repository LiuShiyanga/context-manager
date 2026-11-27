from __future__ import annotations

from typing import Protocol


class TokenCounter(Protocol):
    """Token counting contract; exactness is implementation-specific."""

    estimated: bool

    def count_text(self, text: str) -> int: ...


class ApproximateTokenCounter:
    """Offline character-based estimate, not a provider tokenizer."""

    estimated = True

    def count_text(self, text: str) -> int:
        return max(1, (len(text) + 2) // 3) if text else 0


DEFAULT_TOKEN_COUNTER = ApproximateTokenCounter()
