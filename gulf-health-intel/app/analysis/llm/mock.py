"""Deterministic offline provider for tests/demos. Mirrors the heuristic output and counts calls."""
from __future__ import annotations

import json

from ..heuristic import analyze
from .base import LLMProvider


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(self, fail: bool = False):
        super().__init__("mock-fast", "mock-strong")
        self.calls: list[dict] = []
        self.fail = fail

    def complete_json(self, system: str, user: str, schema: dict, *, model: str, max_tokens: int = 4096) -> dict:
        self.calls.append({"model": model, "user": user})
        if self.fail:
            from .base import LLMError

            raise LLMError("mock failure")
        props = schema.get("properties", {})
        if "items" in props:
            items = []
            for it in json.loads(user.split("\n", 1)[1]):
                h = analyze(it["text"])
                items.append({
                    "id": it["id"], "topics": [{"slug": s, "confidence": c} for s, c in h.topics],
                    "new_topic": "fasting energy" if "صيام" in it["text"] else None,
                    "intent": h.intent, "intent_confidence": h.intent_confidence,
                    "relevance_score": h.relevance_score, "is_question": h.is_question,
                    "question": h.question_text, "language": h.language if h.language != "unknown" else "other",
                    "dialect": h.dialect, "key_phrases": h.key_phrases,
                })
            return {"items": items}
        if "suggested_scorecard" in props:
            return {"suggested_scorecard": "Mock Scorecard", "hook": "Mock hook", "cta": "Take the mock assessment"}
        return {k: [f"mock {k} {i}" for i in range(10)] for k in props}
