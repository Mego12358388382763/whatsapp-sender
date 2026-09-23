"""Provider-neutral LLM interface with structured JSON output."""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    name: str = "base"

    def __init__(self, fast_model: str, strong_model: str):
        self.fast_model = fast_model
        self.strong_model = strong_model

    @abstractmethod
    def complete_json(self, system: str, user: str, schema: dict, *, model: str, max_tokens: int = 4096) -> dict:
        """Return a dict that conforms to `schema`, or raise LLMError."""


def get_provider(settings=None) -> LLMProvider | None:
    """Build the configured provider, or None (heuristic-only mode)."""
    if settings is None:
        from ...config import settings as _s

        settings = _s
    name = settings.llm_provider
    fast, strong = settings.models_for(name)
    if name == "anthropic" and settings.anthropic_api_key:
        from .anthropic import AnthropicProvider

        return AnthropicProvider(settings.anthropic_api_key, fast, strong)
    if name == "openai" and settings.openai_api_key:
        from .openai import OpenAIProvider

        return OpenAIProvider(settings.openai_api_key, fast, strong)
    if name == "mock":
        from .mock import MockProvider

        return MockProvider()
    return None
