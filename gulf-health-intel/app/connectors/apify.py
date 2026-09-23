"""Optional live adapter for a third-party data provider (Apify).

Runs a provider "actor" synchronously and maps its dataset items with the
tabular field mapper. Actor IDs and input shapes differ per actor, so they are
configured rather than hard-coded:

    APIFY_ACTORS='{"instagram": {"actor": "<owner>~<actor>", "input": {"directUrls": "{urls}", "resultsLimit": "{max_comments}"}}}'

The operator is responsible for choosing providers whose collection methods
comply with the platform's terms and applicable law (e.g. KSA/UAE PDPL).
"""
from __future__ import annotations

import json
import os
from typing import Iterator

import httpx

from ..config import settings
from .base import Connector, ConnectorError, FetchRequest, RawPost, register
from .tabular import records_to_posts
from .urls import detect_platform

API = "https://api.apify.com/v2"


def _actors() -> dict:
    try:
        return json.loads(os.environ.get("APIFY_ACTORS", "{}") or "{}")
    except json.JSONDecodeError:
        return {}


def _fill(template, req: FetchRequest, urls: list[str]):
    if isinstance(template, dict):
        return {k: _fill(v, req, urls) for k, v in template.items()}
    if isinstance(template, list):
        return [_fill(v, req, urls) for v in template]
    if template == "{urls}":
        return urls
    if template == "{url_objects}":
        return [{"url": u} for u in urls]
    if template == "{keywords}":
        return req.keywords
    if template == "{max_comments}":
        return req.max_comments_per_post
    if template == "{max_posts}":
        return req.max_posts
    return template


@register
class ApifyConnector(Connector):
    name = "apify_provider"
    platform = "any"
    kind = "provider"

    def __init__(self, token: str | None = None, actors: dict | None = None, client: httpx.Client | None = None):
        self.token = token if token is not None else settings.apify_token
        self.actors = actors if actors is not None else _actors()
        self.client = client or httpx.Client(timeout=300)

    def available(self) -> bool:
        return bool(self.token and self.actors)

    def supports_url(self, url: str) -> bool:
        return detect_platform(url) in self.actors

    def fetch(self, req: FetchRequest) -> Iterator[RawPost]:
        if not self.available():
            raise ConnectorError("APIFY_TOKEN / APIFY_ACTORS are not configured")
        by_platform: dict[str, list[str]] = {}
        for u in req.urls:
            by_platform.setdefault(detect_platform(u), []).append(u)
        for platform, urls in by_platform.items():
            cfg = self.actors.get(platform)
            if not cfg:
                continue
            r = self.client.post(
                f"{API}/acts/{cfg['actor']}/run-sync-get-dataset-items",
                params={"token": self.token},
                json=_fill(cfg.get("input", {"directUrls": "{urls}"}), req, urls),
            )
            if r.status_code >= 400:
                raise ConnectorError(f"Apify actor {cfg['actor']} failed {r.status_code}: {r.text[:200]}")
            yield from records_to_posts(r.json(), default_platform=platform, mapping=cfg.get("mapping"), req=req)
