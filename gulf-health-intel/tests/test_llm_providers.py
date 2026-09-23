import json

import httpx

from app.analysis.llm.anthropic import AnthropicProvider
from app.analysis.llm.base import get_provider
from app.analysis.llm.openai import OpenAIProvider
from app.config import Settings

SCHEMA = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}


def test_anthropic_forced_tool_call():
    seen = {}

    def handler(req):
        seen.update(json.loads(req.content))
        assert req.headers["x-api-key"] == "k"
        return httpx.Response(200, json={"content": [{"type": "tool_use", "name": "record_result", "input": {"x": "ok"}}]})

    p = AnthropicProvider("k", "fast", "strong", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert p.complete_json("sys", "hi", SCHEMA, model="fast") == {"x": "ok"}
    assert seen["tool_choice"] == {"type": "tool", "name": "record_result"}
    assert seen["tools"][0]["input_schema"] == SCHEMA


def test_openai_json_schema():
    def handler(req):
        body = json.loads(req.content)
        assert body["response_format"]["type"] == "json_schema"
        return httpx.Response(200, json={"choices": [{"message": {"content": "{\"x\": \"ok\"}"}}]})

    p = OpenAIProvider("k", "fast", "strong", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert p.complete_json("sys", "hi", SCHEMA, model="fast") == {"x": "ok"}


def test_factory():
    s = Settings()
    s.llm_provider, s.anthropic_api_key = "none", ""
    assert get_provider(s) is None
    s.llm_provider, s.anthropic_api_key = "anthropic", "k"
    p = get_provider(s)
    assert p.name == "anthropic" and p.fast_model and p.strong_model
