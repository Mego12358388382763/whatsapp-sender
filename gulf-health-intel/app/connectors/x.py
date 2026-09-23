"""X (Twitter) API v2 connector (official, bearer token, paid tiers).

* Post URL      → replies via recent search `conversation_id:<id>`
* Profile URL   → the account's recent posts plus their replies
* Keywords only → matching posts are grouped as comments under one synthetic
                  "search" post, because on X the posts themselves are the
                  discussion units

Recent search covers only the last ~7 days on lower tiers.
"""
from __future__ import annotations

from typing import Iterator

import httpx

from ..config import settings
from .base import Connector, ConnectorError, FetchRequest, RawComment, RawPost, in_range, parse_dt, register, to_int
from .urls import detect_platform, url_kind, x_handle, x_status_id

API = "https://api.x.com/2"
_TWEET_FIELDS = "created_at,public_metrics,conversation_id,lang"


@register
class XConnector(Connector):
    name = "x_api"
    platform = "x"
    kind = "api"

    def __init__(self, bearer: str | None = None, client: httpx.Client | None = None):
        self.bearer = bearer if bearer is not None else settings.x_bearer_token
        self.client = client or httpx.Client(timeout=30)

    def available(self) -> bool:
        return bool(self.bearer)

    def supports_url(self, url: str) -> bool:
        return detect_platform(url) == "x"

    def supports_keywords(self) -> bool:
        return True

    def _get(self, path: str, **params) -> dict:
        r = self.client.get(f"{API}{path}", params=params, headers={"Authorization": f"Bearer {self.bearer}"})
        if r.status_code >= 400:
            raise ConnectorError(f"X API {path} {r.status_code}: {r.text[:200]}")
        return r.json()

    def _search(self, query: str, req: FetchRequest, limit: int) -> list[dict]:
        out: list[dict] = []
        token = None
        while len(out) < limit:
            params = {"query": query, "max_results": 100, "tweet.fields": _TWEET_FIELDS}
            if token:
                params["next_token"] = token
            data = self._get("/tweets/search/recent", **params)
            out.extend(data.get("data", []))
            token = data.get("meta", {}).get("next_token")
            if not token:
                break
        return [t for t in out if in_range(parse_dt(t.get("created_at")), req)][:limit]

    @staticmethod
    def _as_comment(t: dict) -> RawComment:
        m = t.get("public_metrics", {})
        return RawComment(text=t.get("text", ""), external_id=t.get("id"), published_at=parse_dt(t.get("created_at")),
                          like_count=to_int(m.get("like_count")), reply_count=to_int(m.get("reply_count")),
                          is_reply=True)

    def _thread(self, tweet_id: str, req: FetchRequest) -> RawPost:
        data = self._get(f"/tweets/{tweet_id}", **{"tweet.fields": _TWEET_FIELDS, "expansions": "author_id",
                                                  "user.fields": "username,name"})
        t = data["data"]
        acct = (data.get("includes", {}).get("users") or [{}])[0]
        handle = acct.get("username", "unknown")
        m = t.get("public_metrics", {})
        replies = self._search(f"conversation_id:{t.get('conversation_id', tweet_id)} is:reply", req,
                               req.max_comments_per_post)
        return RawPost(
            platform="x", url=f"https://x.com/{handle}/status/{t['id']}",
            community_url=f"https://x.com/{handle}", community_name=acct.get("name") or handle,
            external_id=t["id"], text=t.get("text"), published_at=parse_dt(t.get("created_at")),
            like_count=to_int(m.get("like_count")), comment_count=to_int(m.get("reply_count")),
            share_count=to_int(m.get("retweet_count")), view_count=to_int(m.get("impression_count")),
            comments=[self._as_comment(r) for r in replies],
        )

    def fetch(self, req: FetchRequest) -> Iterator[RawPost]:
        if not self.available():
            raise ConnectorError("X_BEARER_TOKEN is not configured")
        for url in req.urls:
            if detect_platform(url) != "x":
                continue
            if url_kind(url) == "post" and (tid := x_status_id(url)):
                yield self._thread(tid, req)
            elif handle := x_handle(url):
                for t in self._search(f"from:{handle} -is:reply -is:retweet", req, req.max_posts):
                    yield self._thread(t["id"], req)
        if req.keywords and not req.urls:
            q = "(" + " OR ".join(f'"{k}"' if " " in k else k for k in req.keywords) + ") -is:retweet"
            if req.language:
                q += f" lang:{req.language}"
            tweets = self._search(q, req, req.max_comments_per_post)
            label = " ".join(req.keywords)[:80]
            yield RawPost(
                platform="x", url=f"x-search://{req.country or 'all'}/{label}",
                community_url=f"x-search://{req.country or 'all'}", community_name=f"X search ({req.country or 'all'})",
                title=f"Search: {label}", comments=[self._as_comment(t) for t in tweets],
            )
