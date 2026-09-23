"""Runtime configuration, read from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_MODELS = {
    # Cheap first-pass classification / stronger synthesis. Override via env.
    "anthropic": ("claude-haiku-4-5-20251001", "claude-sonnet-5"),
    "openai": ("gpt-4o-mini", "gpt-4o"),
}


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", "sqlite:///./data/ghci.db"))
    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "none").lower())
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    llm_fast_model: str = field(default_factory=lambda: _env("LLM_FAST_MODEL"))
    llm_strong_model: str = field(default_factory=lambda: _env("LLM_STRONG_MODEL"))
    llm_batch_size: int = field(default_factory=lambda: int(_env("LLM_BATCH_SIZE", "25")))
    youtube_api_key: str = field(default_factory=lambda: _env("YOUTUBE_API_KEY"))
    reddit_client_id: str = field(default_factory=lambda: _env("REDDIT_CLIENT_ID"))
    reddit_client_secret: str = field(default_factory=lambda: _env("REDDIT_CLIENT_SECRET"))
    reddit_user_agent: str = field(
        default_factory=lambda: _env("REDDIT_USER_AGENT", "gulf-health-intel/0.1")
    )
    x_bearer_token: str = field(default_factory=lambda: _env("X_BEARER_TOKEN"))
    apify_token: str = field(default_factory=lambda: _env("APIFY_TOKEN"))
    relevance_threshold: int = field(default_factory=lambda: int(_env("RELEVANCE_THRESHOLD", "40")))

    # Dashboard protection (HTTP Basic). Required before any lead data can be viewed.
    admin_user: str = field(default_factory=lambda: _env("ADMIN_USER", "admin"))
    admin_password: str = field(default_factory=lambda: _env("ADMIN_PASSWORD"))
    # Public URL of this app, used to build Scorecard links inside suggested replies.
    public_base_url: str = field(default_factory=lambda: _env("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"))
    brand_name: str = field(default_factory=lambda: _env("BRAND_NAME", "Health 360"))

    # Reply queue (drafts only; a person posts every reply by hand)
    reply_min_relevance: int = field(default_factory=lambda: int(_env("REPLY_MIN_RELEVANCE", "55")))
    reply_daily_soft_limit: int = field(default_factory=lambda: int(_env("REPLY_DAILY_SOFT_LIMIT", "30")))

    def models_for(self, provider: str) -> tuple[str, str]:
        fast, strong = DEFAULT_MODELS.get(provider, ("", ""))
        return self.llm_fast_model or fast, self.llm_strong_model or strong


settings = Settings()


def reload_settings() -> Settings:
    global settings
    settings = Settings()
    return settings
