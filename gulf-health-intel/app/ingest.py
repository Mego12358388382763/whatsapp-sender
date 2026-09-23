"""Persist connector output into the RAW layer (scrubbed, de-duplicated)."""
from __future__ import annotations

from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .connectors.base import Connector, FetchRequest, RawPost
from .models import Comment, Community, IngestionRun, Post, Source, utcnow
from .privacy import hash_id, scrub, text_hash

GULF_COUNTRIES = {
    "SA": "Saudi Arabia", "AE": "United Arab Emirates", "KW": "Kuwait",
    "QA": "Qatar", "BH": "Bahrain", "OM": "Oman",
}


def _source(s: Session, name: str, platform: str, kind: str) -> Source:
    src = s.scalar(select(Source).where(Source.name == name, Source.platform == platform, Source.kind == kind))
    if not src:
        src = Source(name=name, platform=platform, kind=kind)
        s.add(src)
        s.flush()
    return src


def _community(s: Session, rp: RawPost, country: str | None, city: str | None, category: str | None) -> Community:
    c = s.scalar(select(Community).where(Community.platform == rp.platform, Community.url == rp.community_url))
    if not c:
        c = Community(platform=rp.platform, url=rp.community_url, name=rp.community_name[:300])
        s.add(c)
    if country and not c.country:
        c.country = country
    if city and not c.city:
        c.city = city
    if category and not c.category:
        c.category = category
    s.flush()
    return c


def store_posts(
    s: Session,
    raw_posts: Iterable[RawPost],
    run: IngestionRun,
    country: str | None = None,
    city: str | None = None,
    category: str | None = None,
) -> dict:
    stats = {"posts_new": 0, "posts_updated": 0, "comments_new": 0, "comments_duplicate": 0, "comments_empty": 0}
    for rp in raw_posts:
        com = _community(s, rp, country, city, category)
        post = s.scalar(select(Post).where(Post.platform == rp.platform, Post.url == rp.url))
        if post is None:
            post = Post(community_id=com.id, platform=rp.platform, url=rp.url, ingestion_run_id=run.id)
            s.add(post)
            stats["posts_new"] += 1
        else:
            stats["posts_updated"] += 1
        for attr in ("external_id", "title", "published_at", "like_count", "comment_count", "share_count", "view_count"):
            val = getattr(rp, attr)
            if val is not None:
                setattr(post, attr, val)
        if rp.text:
            post.text = scrub(rp.text)
        s.flush()

        existing_hashes = set(s.scalars(select(Comment.text_hash).where(Comment.post_id == post.id)))
        existing_ext = set(s.scalars(select(Comment.external_id_hash).where(Comment.post_id == post.id)))
        for rc in rp.comments:
            text = scrub(rc.text or "")
            if not text:
                stats["comments_empty"] += 1
                continue
            th, eh = text_hash(text), hash_id(rp.platform, rc.external_id)
            if th in existing_hashes or (eh and eh in existing_ext):
                stats["comments_duplicate"] += 1
                continue
            s.add(Comment(post_id=post.id, platform=rp.platform, external_id_hash=eh, text=text, text_hash=th,
                          published_at=rc.published_at, like_count=rc.like_count, reply_count=rc.reply_count,
                          is_reply=rc.is_reply, ingestion_run_id=run.id))
            existing_hashes.add(th)
            if eh:
                existing_ext.add(eh)
            stats["comments_new"] += 1
        s.flush()
    return stats


def run_connector(
    s: Session,
    connector: Connector,
    req: FetchRequest,
    source_name: str | None = None,
    category: str | None = None,
) -> IngestionRun:
    src = _source(s, source_name or connector.name, connector.platform, connector.kind)
    params = {
        "urls": req.urls, "keywords": req.keywords, "country": req.country, "city": req.city,
        "platform": req.platform,
        "date_from": req.date_from.isoformat() if req.date_from else None,
        "date_to": req.date_to.isoformat() if req.date_to else None,
    }
    run = IngestionRun(source_id=src.id, params=params)
    s.add(run)
    s.flush()
    try:
        with s.begin_nested():
            run.stats = store_posts(s, connector.fetch(req), run, req.country, req.city, category)
        run.status = "done"
    except Exception as e:  # recorded on the run; the caller decides whether to surface it
        run.status, run.error = "error", str(e)[:1000]
    run.finished_at = utcnow()
    s.flush()
    return run
