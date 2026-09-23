"""Post and community analysis, opportunity scoring and growth trends.

All ranking is of POSTS and COMMUNITIES. There is no person-level aggregation.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import (
    Comment,
    CommentAnalysis,
    CommentTopic,
    Community,
    CommunityAnalysis,
    CommunityTopic,
    Post,
    PostAnalysis,
    PostTopic,
    Topic,
    utcnow,
)
from .textstats import top_phrases, top_questions

NEED_INTENTS = {"asking_for_help", "asking_question", "looking_for_practitioner", "looking_for_information",
                "did_not_work"}


@dataclass
class Row:
    comment_id: int
    post_id: int
    community_id: int
    text: str
    published_at: datetime | None
    like_count: int | None
    relevance: int
    intent: str
    is_question: bool
    question: str | None
    language: str | None
    primary_topic: int | None
    key_phrases: list
    topics: set[int] = field(default_factory=set)


def load_rows(s: Session) -> list[Row]:
    q = (
        select(Comment.id, Comment.post_id, Post.community_id, Comment.text, Comment.published_at,
               Comment.like_count, CommentAnalysis.relevance_score, CommentAnalysis.intent,
               CommentAnalysis.is_question, CommentAnalysis.question_text, CommentAnalysis.language,
               CommentAnalysis.primary_topic_id, CommentAnalysis.key_phrases, CommentAnalysis.id)
        .join(CommentAnalysis, CommentAnalysis.comment_id == Comment.id)
        .join(Post, Post.id == Comment.post_id)
    )
    rows: dict[int, Row] = {}
    for r in s.execute(q):
        rows[r[13]] = Row(*r[:13])
    for aid, tid in s.execute(select(CommentTopic.comment_analysis_id, CommentTopic.topic_id)):
        if aid in rows:
            rows[aid].topics.add(tid)
    for row in rows.values():
        if row.primary_topic:
            row.topics.add(row.primary_topic)
    return list(rows.values())


def _engagement(p: Post) -> int | None:
    vals = [v for v in (p.like_count, p.comment_count, p.share_count) if v is not None]
    return sum(vals) if vals else None


def _log_norm(v: float, vmax: float) -> float:
    if v <= 0 or vmax <= 0:
        return 0.0
    return min(1.0, math.log10(1 + v) / math.log10(1 + vmax))


def topic_distribution(rel_rows: list[Row], names: dict[int, str], top: int = 4) -> list[dict]:
    c = Counter(r.primary_topic for r in rel_rows if r.primary_topic)
    total = sum(c.values())
    if not total:
        return []
    out = [{"topic": names.get(t, "?"), "count": n, "share": round(100 * n / total, 1)} for t, n in c.most_common(top)]
    rest = total - sum(o["count"] for o in out)
    if rest:
        out.append({"topic": "Other", "count": rest, "share": round(100 * rest / total, 1)})
    return out


def growth_by_topic(rel_rows: list[Row], names: dict[int, str], min_days: int = 14, min_rows: int = 10) -> list[dict]:
    dated = [r for r in rel_rows if r.published_at]
    if len(dated) < min_rows:
        return []
    lo, hi = min(r.published_at for r in dated), max(r.published_at for r in dated)
    if (hi - lo).days < min_days:
        return []
    mid = lo + (hi - lo) / 2
    early, late = Counter(), Counter()
    for r in dated:
        for t in r.topics:
            (early if r.published_at < mid else late)[t] += 1
    out = []
    for t in set(early) | set(late):
        e, l = early[t], late[t]
        if e + l < 3:
            continue
        out.append({"topic": names.get(t, "?"), "topic_id": t, "early": e, "late": l,
                    "growth": round((l - e) / max(e, 1), 2)})
    return sorted(out, key=lambda x: (x["growth"], x["late"]), reverse=True)


def compute_all(s: Session, threshold: int = 40) -> dict:
    for tbl in (PostTopic, PostAnalysis, CommunityTopic, CommunityAnalysis):
        s.execute(delete(tbl))
    names = {t.id: t.name_en for t in s.scalars(select(Topic))}
    rows = load_rows(s)
    posts = {p.id: p for p in s.scalars(select(Post))}
    by_post: dict[int, list[Row]] = defaultdict(list)
    by_comm: dict[int, list[Row]] = defaultdict(list)
    for r in rows:
        by_post[r.post_id].append(r)
        by_comm[r.community_id].append(r)

    # ---- posts
    max_eng = max([_engagement(p) or 0 for p in posts.values()] or [0])
    post_scores: dict[int, int] = {}
    post_dominant: dict[int, int | None] = {}
    for pid, prs in by_post.items():
        rel = [r for r in prs if r.relevance >= threshold]
        eng = _engagement(posts[pid])
        avg_rel = sum(r.relevance for r in rel) / len(rel) if rel else 0
        need = sum(1 for r in rel if r.intent in NEED_INTENTS) / len(rel) if rel else 0
        parts = [(avg_rel / 100, 0.35), (_log_norm(len(rel), 100), 0.35), (need, 0.15)]
        if eng is not None:
            parts.append((_log_norm(eng, max_eng), 0.15))
        score = round(100 * sum(v * w for v, w in parts) / sum(w for _, w in parts)) if rel else 0
        langs = Counter(r.language for r in prs if r.language and r.language != "unknown")
        dist = topic_distribution(rel, names)
        s.add(PostAnalysis(
            post_id=pid, total_comments=len(prs), relevant_comments=len(rel),
            question_comments=sum(1 for r in rel if r.is_question),
            dominant_language=langs.most_common(1)[0][0] if langs else None,
            engagement=eng, relevance_score=score, topic_distribution=dist,
            top_questions=top_questions([(r.question or r.text, r.relevance) for r in rel if r.is_question]),
            top_phrases=top_phrases([r.text for r in rel], [r.key_phrases for r in rel]),
            computed_at=utcnow(),
        ))
        tc = Counter(t for r in rel for t in r.topics)
        for t, n in tc.items():
            s.add(PostTopic(post_id=pid, topic_id=t, comment_count=n, share=round(n / len(rel), 3)))
        post_scores[pid] = score
        pc = Counter(r.primary_topic for r in rel if r.primary_topic)
        post_dominant[pid] = pc.most_common(1)[0][0] if pc else None

    # ---- communities
    comm_stats = {}
    for cid, crs in by_comm.items():
        rel = [r for r in crs if r.relevance >= threshold]
        pids = {r.post_id for r in crs}
        engs = [e for e in (_engagement(posts[p]) for p in pids) if e is not None]
        comm_stats[cid] = (crs, rel, pids, engs)
    max_avg_eng = max([sum(e) / len(e) for *_, e in comm_stats.values() if e] or [0])

    for cid, (crs, rel, pids, engs) in comm_stats.items():
        pct = len(rel) / len(crs) if crs else 0
        need = sum(1 for r in rel if r.intent in NEED_INTENTS) / len(rel) if rel else 0
        avg_eng = sum(engs) / len(engs) if engs else None
        growth = growth_by_topic(rel, names)
        pc = Counter(r.primary_topic for r in rel if r.primary_topic)
        focus = pc.most_common(1)[0][1] / sum(pc.values()) if pc else 0
        top_growth = max([g["growth"] for g in growth] or [0])
        parts = [
            (min(1.0, pct / 0.6), 30),
            (_log_norm(len(rel), 500), 25),
            (need, 20),
            ((max(0.0, min(1.0, top_growth)) + focus) / 2 if growth else focus, 10),
        ]
        if avg_eng is not None:
            parts.append((_log_norm(avg_eng, max_avg_eng), 15))
        opp = round(100 * sum(v * w for v, w in parts) / sum(w for _, w in parts)) if rel else 0

        weekday = Counter(r.published_at.strftime("%A") for r in rel if r.published_at)
        likes = [r.like_count for r in crs if r.like_count is not None]
        engagement = {
            "avg_post_engagement": round(avg_eng, 1) if avg_eng is not None else None,
            "avg_comments_per_post": round(len(crs) / len(pids), 1) if pids else 0,
            "avg_relevant_per_post": round(len(rel) / len(pids), 1) if pids else 0,
            "avg_comment_likes": round(sum(likes) / len(likes), 1) if likes else None,
            "most_active_weekday": weekday.most_common(1)[0][0] if weekday else None,
            "need_share": round(need, 3),
        }
        s.add(CommunityAnalysis(
            community_id=cid, posts_analyzed=len(pids), comments_analyzed=len(crs), relevant_comments=len(rel),
            relevant_pct=round(100 * pct, 1),
            top_questions=top_questions([(r.question or r.text, r.relevance) for r in rel if r.is_question], n=8),
            engagement=engagement, growth=[{k: v for k, v in g.items() if k != "topic_id"} for g in growth[:8]],
            opportunity_score=opp, computed_at=utcnow(),
        ))
        gmap = {g["topic_id"]: g["growth"] for g in growth}
        tc = Counter(t for r in rel for t in r.topics)
        for t, n in tc.items():
            dom_posts = [p for p in pids if post_dominant.get(p) == t and _engagement(posts[p]) is not None]
            s.add(CommunityTopic(
                community_id=cid, topic_id=t, comment_count=n, share=round(n / len(rel), 3), growth=gmap.get(t),
                avg_post_engagement=(sum(_engagement(posts[p]) for p in dom_posts) / len(dom_posts)) if dom_posts else None,
            ))
    s.flush()
    return {"posts": len(by_post), "communities": len(by_comm), "comments": len(rows),
            "relevant": sum(1 for r in rows if r.relevance >= threshold)}


def community_country(s: Session) -> dict[int, str | None]:
    return {c.id: c.country for c in s.scalars(select(Community))}
