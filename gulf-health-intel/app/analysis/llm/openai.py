"""OpenAI Chat Completions with JSON-schema response format."""
from __future__ import annotations

import json

import httpx

from .base import LLMError, LLMProvider

API = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, fast_model: str, strong_model: str, client: httpx.Client | None = None):
        super().__init__(fast_model, strong_model)
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=120)

    def complete_json(self, system: str, user: str, schema: dict, *, model: str, max_tokens: int = 4096) -> dict:
        body = {
            "model": model,
            "max_completion_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "result", "schema": schema}},
        }
        r = self.client.post(API, json=body, headers={"Authorization": f"Bearer {self.api_key}"})
        if r.status_code >= 400:
            raise LLMError(f"OpenAI {r.status_code}: {r.text[:300]}")
        try:
            return json.loads(r.json()["choices"][0]["message"]["content"])
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise LLMError(f"OpenAI returned unparsable JSON: {e}") from e
