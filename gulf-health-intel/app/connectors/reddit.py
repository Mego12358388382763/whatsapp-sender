"""Reddit official Data API connector (OAuth app-only / client credentials).

Free for low-volume non-commercial use. Commercial use requires an agreement
with Reddit. Author fields are ignored.
"""
from __future__ import annotations

from typing import Iterator

import httpx

from ..config import settings
from .base import Connector, ConnectorError, FetchRequest, RawComment, RawPost, in_range, parse_dt, register, to_int
from .urls import detect_platform, reddit_post_id, reddit_subreddit, url_kind

AUTH_URL = "https://www.reddit.com/api/v1/access_token"
API = "https://oauth.reddit.com"

GULF_SUBREDDITS = {
    "SA": ["saudiarabia", "Riyadh", "jeddah"],
    "AE": ["dubai", "UAE", "abudhabi"],
    "KW": ["Kuwait"],
    "QA": ["qatar", "doha"],
    "BH": ["Bahrain"],
    "OM": ["Oman"],
}


@register
class RedditConnector(Connector):
    name = "reddit_api"
    platform = "reddit"
    kind = "api"

    def __init__(self, client_id: str | None = None, client_secret: str | None = None,
                 client: httpx.Client | None = None):
        self.client_id = client_id if client_id is not None else settings.reddit_client_id
        self.client_secret = client_secret if client_secret is not None else settings.reddit_client_secret
        self.client = client or httpx.Client(timeout=30)
        self._token: str | None = None

    def available(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def supports_url(self, url: str) -> bool:
        return detect_platform(url) == "reddit"

    def supports_keywords(self) -> bool:
        return True

    def _headers(self) -> dict:
        if not self._token:
            r = self.client.post(AUTH_URL, data={"grant_type": "client_credentials"},
                                 auth=(self.client_id, self.client_secret),
                                 headers={"User-Agent": settings.reddit_user_agent})
            if r.status_code >= 400:
                raise ConnectorError(f"Reddit auth failed {r.status_code}")
            self._token = r.json()["access_token"]
        return {"Authorization": f"bearer {self._token}", "User-Agent": settings.reddit_user_agent}

    def _get(self, path: str, **params):
        r = self.client.get(f"{API}{path}", params={"raw_json": 1, **params}, headers=self._headers())
        if r.status_code >= 400:
            raise ConnectorError(f"Reddit API {path} {r.status_code}: {r.text[:200]}")
        return r.json()

    def _listing_post_ids(self, sub: str | None, req: FetchRequest) -> list[str]:
        if req.keywords:
            path = f"/r/{sub}/search" if sub else "/search"
            params = {"q": " OR ".join(req.keywords), "sort": "relevance", "t": "year", "limit": min(100, req.max_posts)}
            if sub:
                params["restrict_sr"] = 1
        else:
            path, params = f"/r/{sub}/new", {"limit": min(100, req.max_posts)}
        data = self._get(path, **params)
        ids = []
        for ch in data.get("data", {}).get("children", []):
            d = ch.get("data", {})
            if in_range(parse_dt(d.get("created_utc")), req):
                ids.append(d["id"])
        return ids[: req.max_posts]

    @staticmethod
    def _flatten(children: list, out: list[RawComment], req: FetchRequest, depth: int = 0) -> None:
        for ch in children:
            if ch.get("kind") != "t1":
                continue  # skip "more" stubs
            d = ch["data"]
            body = d.get("body") or ""
            if body not in ("[deleted]", "[removed]") and in_range(parse_dt(d.get("created_utc")), req):
                out.append(RawComment(text=body, external_id=d.get("id"), published_at=parse_dt(d.get("created_utc")),
                                      like_count=to_int(d.get("score")), is_reply=depth > 0))
            replies = d.get("replies")
            if isinstance(replies, dict):
                RedditConnector._flatten(replies.get("data", {}).get("children", []), out, req, depth + 1)

    def _post(self, post_id: str, req: FetchRequest) -> RawPost | None:
        data = self._get(f"/comments/{post_id}", limit=min(500, req.max_comments_per_post), depth=5)
        if not isinstance(data, list) or not data:
            return None
        p = data[0]["data"]["children"][0]["data"]
        comments: list[RawComment] = []
        if len(data) > 1:
            self._flatten(data[1]["data"]["children"], comments, req)
        sub = p.get("subreddit")
        return RawPost(
            platform="reddit",
            url=f"https://www.reddit.com{p.get('permalink')}",
            community_url=f"https://www.reddit.com/r/{sub}",
            community_name=f"r/{sub}",
            external_id=p.get("id"),
            title=p.get("title"),
            text=(p.get("selftext") or "")[:4000],
            published_at=parse_dt(p.get("created_utc")),
            like_count=to_int(p.get("score")),
            comment_count=to_int(p.get("num_comments")),
            comments=comments[: req.max_comments_per_post],
        )

    def fetch(self, req: FetchRequest) -> Iterator[RawPost]:
        if not self.available():
            raise ConnectorError("REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET are not configured")
        ids: list[str] = []
        for url in req.urls:
            if detect_platform(url) != "reddit":
                continue
            if url_kind(url) == "post" and (pid := reddit_post_id(url)):
                ids.append(pid)
            elif sub := reddit_subreddit(url):
                ids.extend(self._listing_post_ids(sub, req))
        if req.keywords and not req.urls:
            subs = GULF_SUBREDDITS.get(req.country or "", []) or [None]
            for sub in subs:
                ids.extend(self._listing_post_ids(sub, req))
        seen: set[str] = set()
        for pid in ids:
            if pid in seen:
                continue
            seen.add(pid)
            post = self._post(pid, req)
            if post:
                yield post
