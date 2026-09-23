"""CSV / JSON import, including datasets exported from third-party data providers.

Rows are *comments* (one per row) with post/community context columns, or JSON
objects that are either flat comment records or posts with nested comment
lists. Field names are resolved from a list of common aliases, so exports from
most providers (Apify, Bright Data, Data365, spreadsheets, and so on) load
without code changes. Pass a custom `mapping` to override.

Identity fields (author, username, profile…) are dropped before mapping.
"""
from __future__ import annotations

import csv
import io
import json
from collections import OrderedDict
from typing import Any, Iterable, Iterator

from ..privacy import strip_identity
from .base import Connector, FetchRequest, RawComment, RawPost, in_range, parse_dt, register, to_int
from .urls import community_from_post_url, detect_platform

# canonical field -> aliases (checked case-insensitively, dotted paths allowed)
ALIASES: dict[str, list[str]] = {
    "platform": ["platform", "source", "network"],
    "country": ["country", "country_code", "community_country"],
    "city": ["city", "community_city"],
    "community_name": ["community_name", "community", "page_name", "page", "channel_title",
                       "channelTitle", "subreddit", "group_name", "account_name", "pageName"],
    "community_url": ["community_url", "page_url", "channel_url", "account_url", "pageUrl",
                      "inputUrl", "facebookUrl"],
    "post_url": ["post_url", "postUrl", "url", "post_link", "videoWebUrl", "video_url",
                 "permalink", "link", "tweet_url", "webVideoUrl"],
    "post_id": ["post_id", "postId", "video_id", "videoId", "shortCode", "aweme_id"],
    "post_title": ["post_title", "title", "video_title"],
    "post_text": ["post_text", "caption", "post_caption", "description", "postText", "selftext"],
    "post_date": ["post_date", "post_timestamp", "post_created_at", "postDate", "createTimeISO_post"],
    "post_likes": ["post_likes", "post_like_count", "likesCount_post", "diggCount_post", "post_reactions"],
    "post_comments": ["post_comments", "post_comment_count", "commentsCount", "commentCount", "num_comments"],
    "post_shares": ["post_shares", "shareCount", "sharesCount", "post_share_count"],
    "post_views": ["post_views", "viewCount", "playCount", "videoViewCount", "views"],
    "comment_text": ["comment_text", "comment", "text", "body", "message", "content", "textDisplay",
                     "textOriginal", "full_text"],
    "comment_id": ["comment_id", "commentId", "id", "cid"],
    "comment_date": ["comment_date", "timestamp", "date", "created_at", "createdAt", "createTimeISO",
                     "publishedAt", "created_utc", "time"],
    "comment_likes": ["comment_likes", "likes", "likesCount", "likeCount", "diggCount", "score",
                      "reactionsCount", "favorite_count"],
    "comment_replies": ["comment_replies", "replies_count", "repliesCount", "replyCount",
                        "replyCommentTotal", "totalReplyCount"],
    "is_reply": ["is_reply", "isReply", "parent_id", "parentId", "repliesToId"],
    "nested_comments": ["comments", "latestComments", "replies_list"],
}


def _get(rec: dict, key: str) -> Any:
    cur: Any = rec
    for part in key.split("."):
        if not isinstance(cur, dict):
            return None
        match = next((k for k in cur if str(k).lower() == part.lower()), None)
        if match is None:
            return None
        cur = cur[match]
    return cur


def resolve(rec: dict, field: str, mapping: dict[str, str] | None = None) -> Any:
    keys = [mapping[field]] if mapping and field in mapping else ALIASES.get(field, [field])
    for k in keys:
        v = _get(rec, k)
        if v not in (None, "", []):
            return v
    return None


def _bool(v: Any) -> bool:
    """is_reply flag, or a parent id (any non-empty parent id means it is a reply)."""
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() not in ("", "0", "false", "no", "n", "none", "null")


_COUNTRY_NAMES = {
    "saudi arabia": "SA", "saudi": "SA", "ksa": "SA", "uae": "AE", "united arab emirates": "AE",
    "emirates": "AE", "kuwait": "KW", "qatar": "QA", "bahrain": "BH", "oman": "OM",
}


def _country(v: Any) -> str | None:
    if not v:
        return None
    s = str(v).strip()
    if len(s) == 2:
        return s.upper()
    return _COUNTRY_NAMES.get(s.lower())


def records_to_posts(
    records: Iterable[dict],
    default_platform: str | None = None,
    default_community: str | None = None,
    mapping: dict[str, str] | None = None,
    req: FetchRequest | None = None,
) -> list[RawPost]:
    posts: "OrderedDict[str, RawPost]" = OrderedDict()
    req = req or FetchRequest()

    def post_for(rec: dict) -> RawPost | None:
        url = resolve(rec, "post_url", mapping)
        if not url:
            pid = resolve(rec, "post_id", mapping)
            url = f"import://{default_community or 'dataset'}/{pid or 'unknown'}"
        url = str(url).strip()
        if url in posts:
            return posts[url]
        platform = (resolve(rec, "platform", mapping) or default_platform or detect_platform(url)).lower()
        if platform == "twitter":
            platform = "x"
        c_url = resolve(rec, "community_url", mapping)
        c_name = resolve(rec, "community_name", mapping) or default_community
        if not c_url:
            guess_url, guess_name = community_from_post_url(url)
            c_url = guess_url if not c_name else f"{platform}://{c_name}"
            c_name = c_name or guess_name
        p = RawPost(
            platform=platform,
            url=url,
            community_url=str(c_url),
            community_name=str(c_name or c_url),
            external_id=str(resolve(rec, "post_id", mapping) or "") or None,
            title=resolve(rec, "post_title", mapping),
            text=resolve(rec, "post_text", mapping),
            published_at=parse_dt(resolve(rec, "post_date", mapping)),
            like_count=to_int(resolve(rec, "post_likes", mapping)),
            comment_count=to_int(resolve(rec, "post_comments", mapping)),
            share_count=to_int(resolve(rec, "post_shares", mapping)),
            view_count=to_int(resolve(rec, "post_views", mapping)),
            community_country=_country(resolve(rec, "country", mapping)),
            community_city=resolve(rec, "city", mapping),
        )
        posts[url] = p
        return p

    def add_comment(post: RawPost, rec: dict) -> None:
        text = resolve(rec, "comment_text", mapping)
        if not text or not isinstance(text, str):
            return
        dt = parse_dt(resolve(rec, "comment_date", mapping))
        if not in_range(dt, req):
            return
        post.comments.append(
            RawComment(
                text=text,
                external_id=str(resolve(rec, "comment_id", mapping) or "") or None,
                published_at=dt,
                like_count=to_int(resolve(rec, "comment_likes", mapping)),
                reply_count=to_int(resolve(rec, "comment_replies", mapping)),
                is_reply=_bool(resolve(rec, "is_reply", mapping) or False),
            )
        )

    for raw in records:
        if not isinstance(raw, dict):
            continue
        rec = strip_identity(raw)
        nested = resolve(rec, "nested_comments", mapping)
        post = post_for(rec)
        if post is None:
            continue
        if isinstance(nested, list):
            # A post object with embedded comments; its own text is the caption.
            if post.text is None:
                post.text = resolve(rec, "comment_text", mapping)
            for c in nested:
                if isinstance(c, dict):
                    add_comment(post, strip_identity(c))
                elif isinstance(c, str):
                    add_comment(post, {"text": c})
        else:
            add_comment(post, rec)
    return list(posts.values())


def load_records(content: bytes | str, filename: str = "") -> list[dict]:
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    stripped = text.lstrip()
    if filename.lower().endswith((".json", ".jsonl", ".ndjson")) or stripped[:1] in "[{":
        if stripped.startswith("["):
            data = json.loads(stripped)
        else:
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError:
                data = [json.loads(line) for line in stripped.splitlines() if line.strip()]
        if isinstance(data, dict):
            data = data.get("items") or data.get("data") or data.get("results") or [data]
        return [d for d in data if isinstance(d, dict)]
    return list(csv.DictReader(io.StringIO(text)))


@register
class TabularImport(Connector):
    """Not fetched over the network: wraps pre-loaded records so imports share the pipeline."""

    name = "file_import"
    platform = "any"
    kind = "csv"

    def __init__(self, records: list[dict], default_platform: str | None = None,
                 default_community: str | None = None, mapping: dict[str, str] | None = None):
        self.records = records
        self.default_platform = default_platform
        self.default_community = default_community
        self.mapping = mapping

    def fetch(self, req: FetchRequest) -> Iterator[RawPost]:
        yield from records_to_posts(
            self.records, self.default_platform or req.platform, self.default_community, self.mapping, req
        )
