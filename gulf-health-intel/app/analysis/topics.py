"""Seed topics + automatic topic discovery.

Two discovery paths feed `topics` with status='candidate':
  * LLM classification can propose a `new_topic` label for a comment.
  * N-gram mining over relevant comments whose wording is not covered by any
    existing topic keyword.
Candidates with enough supporting comments across several posts are promoted
to status='active'.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Comment, CommentAnalysis, CommentTopic, Topic
from ..text.lexicon import SEED_TOPICS
from ..text.normalize import STOPWORDS, normalize, tokens


def ensure_seed_topics(s: Session) -> None:
    existing = {t.slug for t in s.scalars(select(Topic))}
    for slug, (en, ar, kws) in SEED_TOPICS.items():
        if slug not in existing:
            s.add(Topic(slug=slug, name_en=en, name_ar=ar, is_seed=True, status="active", keywords=kws))
    s.flush()


def slugify(label: str) -> str:
    base = re.sub(r"[^\w]+", "_", normalize(label)).strip("_")
    return base[:70] or "topic"


def get_or_create_candidate(s: Session, label: str) -> Topic:
    slug = slugify(label)
    t = s.scalar(select(Topic).where(Topic.slug == slug))
    if t is None:
        t = Topic(slug=slug, name_en=label.strip()[:120], is_seed=False, status="candidate", keywords=[label])
        s.add(t)
        s.flush()
    return t


def _ngrams(toks: list[str], n: int) -> list[str]:
    return [" ".join(toks[i : i + n]) for i in range(len(toks) - n + 1)]


def _content_tokens(text: str) -> list[str]:
    return [t for t in tokens(text) if t not in STOPWORDS and len(t) > 1 and not t.isdigit()]


def discover_topics(
    s: Session, min_count: int = 5, min_posts: int = 2, min_relevance: int = 30, limit: int = 15
) -> list[Topic]:
    """Mine recurring phrases not covered by existing topic keywords."""
    known = set()
    for t in s.scalars(select(Topic)):
        for kw in t.keywords or []:
            known.update(_content_tokens(kw))

    rows = s.execute(
        select(Comment.text, Comment.post_id, CommentAnalysis.id)
        .join(CommentAnalysis, CommentAnalysis.comment_id == Comment.id)
        .where((CommentAnalysis.relevance_score >= min_relevance) | (CommentAnalysis.is_question.is_(True)))
    ).all()
    counts: Counter[str] = Counter()
    posts: dict[str, set[int]] = defaultdict(set)
    members: dict[str, set[int]] = defaultdict(set)
    for text, post_id, analysis_id in rows:
        toks = _content_tokens(text)
        grams = set(_ngrams(toks, 2)) | {t for t in toks if len(t) >= 5}
        for g in grams:
            if all(w in known for w in g.split()):
                continue
            counts[g] += 1
            posts[g].add(post_id)
            members[g].add(analysis_id)

    created: list[Topic] = []
    for phrase, c in counts.most_common(200):
        if c < min_count or len(posts[phrase]) < min_posts:
            continue
        # skip phrases subsumed by an already chosen, more frequent phrase
        if any(phrase in t.name_en or t.name_en in phrase for t in created):
            continue
        t = get_or_create_candidate(s, phrase)
        linked = set(s.scalars(select(CommentTopic.comment_analysis_id).where(CommentTopic.topic_id == t.id)))
        for aid in members[phrase] - linked:
            s.add(CommentTopic(comment_analysis_id=aid, topic_id=t.id, confidence=0.5))
        created.append(t)
        if len(created) >= limit:
            break
    promote_candidates(s, min_count=min_count)
    return created


def promote_candidates(s: Session, min_count: int = 5) -> None:
    counts = dict(
        s.execute(
            select(CommentTopic.topic_id, func.count()).group_by(CommentTopic.topic_id)
        ).all()
    )
    for t in s.scalars(select(Topic).where(Topic.status == "candidate")):
        if counts.get(t.id, 0) >= min_count:
            t.status = "active"
    s.flush()
