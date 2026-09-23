"""Anthropic Claude via the Messages API. Structured output via a forced tool call."""
from __future__ import annotations

import httpx

from .base import LLMError, LLMProvider

API = "https://api.anthropic.com/v1/messages"


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, fast_model: str, strong_model: str, client: httpx.Client | None = None):
        super().__init__(fast_model, strong_model)
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=120)

    def complete_json(self, system: str, user: str, schema: dict, *, model: str, max_tokens: int = 4096) -> dict:
        body = {
            "model": model,
            "max_tokens": max_tokens,
            # The system prompt is identical across batches, so mark it cacheable.
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "tools": [{"name": "record_result", "description": "Record the structured result.", "input_schema": schema}],
            "tool_choice": {"type": "tool", "name": "record_result"},
            "messages": [{"role": "user", "content": user}],
        }
        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        r = self.client.post(API, json=body, headers=headers)
        if r.status_code >= 400:
            raise LLMError(f"Anthropic {r.status_code}: {r.text[:300]}")
        for block in r.json().get("content", []):
            if block.get("type") == "tool_use":
                return block.get("input") or {}
        raise LLMError("Anthropic response contained no tool_use block")
