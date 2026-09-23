"""CSV exports. The comment export is anonymous by construction: the schema holds no identity."""
from __future__ import annotations

import csv
import io
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    BusinessAccount,
    Comment,
    CommentAnalysis,
    Community,
    CommunityAnalysis,
    CommunityTopic,
    ContentIdea,
    Post,
    PostAnalysis,
    ScorecardOpportunity,
    Topic,
)
from .text.lexicon import INTENT_LABELS


def _csv(header: list[str], rows: Iterable[list]) -> str:
    buf = io.StringIO()
    buf.write("﻿")  # BOM so Excel opens Arabic correctly
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def _join(items, key) -> str:
    return " | ".join(f"{i[key]} ({i.get('count', i.get('share', ''))})" for i in items or [])


def communities_csv(s: Session) -> str:
    names = {t.id: t.name_en for t in s.scalars(select(Topic))}
    top: dict[int, list[str]] = {}
    for ct in s.scalars(select(CommunityTopic).order_by(CommunityTopic.comment_count.desc())):
        top.setdefault(ct.community_id, []).append(f"{names.get(ct.topic_id)} ({ct.comment_count})")
    rows = []
    for c, a in s.execute(select(Community, CommunityAnalysis).join(CommunityAnalysis)
                          .order_by(CommunityAnalysis.opportunity_score.desc())):
        rows.append([c.name, c.platform, c.country, c.city, c.url, a.posts_analyzed, a.comments_analyzed,
                     a.relevant_comments, a.relevant_pct, "; ".join(top.get(c.id, [])[:5]),
                     _join(a.top_questions, "question"),
                     "; ".join(f"{g['topic']} {g['growth']:+}" for g in a.growth[:5]),
                     a.engagement.get("avg_post_engagement"), a.opportunity_score])
    return _csv(["community", "platform", "country", "city", "url", "posts_analyzed", "comments_analyzed",
                 "relevant_discussions", "relevant_pct", "top_topics", "common_questions", "growing_topics",
                 "avg_post_engagement", "opportunity_score"], rows)


def posts_csv(s: Session) -> str:
    rows = []
    for p, a, c in s.execute(select(Post, PostAnalysis, Community).join(PostAnalysis).join(Community)
                             .order_by(PostAnalysis.relevance_score.desc())):
        rows.append([p.url, p.platform, c.name, c.country, p.title or (p.text or "")[:120], p.published_at,
                     a.total_comments, a.relevant_comments, a.question_comments, _join(a.topic_distribution, "topic"),
                     _join(a.top_questions, "question"), _join(a.top_phrases, "phrase"), a.dominant_language,
                     a.engagement, a.relevance_score])
    return _csv(["post_url", "platform", "community", "country", "title", "published_at", "comments_analyzed",
                 "relevant_comments", "question_comments", "topic_distribution", "common_questions",
                 "repeated_phrases", "dominant_language", "engagement", "score"], rows)


def comments_csv(s: Session, min_relevance: int = 0) -> str:
    names = {t.id: t.name_en for t in s.scalars(select(Topic))}
    q = (select(Comment, CommentAnalysis, Post, Community)
         .join(CommentAnalysis, CommentAnalysis.comment_id == Comment.id)
         .join(Post, Post.id == Comment.post_id).join(Community, Community.id == Post.community_id)
         .where(CommentAnalysis.relevance_score >= min_relevance)
         .order_by(CommentAnalysis.relevance_score.desc()))
    rows = []
    for cm, a, p, c in s.execute(q):
        rows.append([cm.text, names.get(a.primary_topic_id, ""),
                     "; ".join(names.get(t.topic_id, "") for t in a.topics), INTENT_LABELS.get(a.intent, a.intent),
                     round(a.intent_confidence, 2), a.relevance_score, a.is_question, a.language, a.dialect,
                     p.url, p.platform, c.name, c.country, cm.published_at, cm.like_count, a.method])
    return _csv(["comment", "primary_topic", "all_topics", "intent", "confidence", "relevance_score", "is_question",
                 "language", "dialect", "post_url", "platform", "community", "country", "timestamp",
                 "engagement_likes", "method"], rows)


def topics_csv(s: Session, threshold: int = 40) -> str:
    from .analysis.aggregate import load_rows
    from .analysis.textstats import top_phrases, top_questions

    topics = {t.id: t for t in s.scalars(select(Topic))}
    rows_by: dict[int, list] = {}
    for r in load_rows(s):
        if r.relevance >= threshold:
            for t in r.topics:
                rows_by.setdefault(t, []).append(r)
    out = []
    for tid, rs in sorted(rows_by.items(), key=lambda kv: -len(kv[1])):
        t = topics[tid]
        out.append([t.name_en, t.name_ar or "", t.slug, "seed" if t.is_seed else f"discovered ({t.status})", len(rs),
                     len({r.community_id for r in rs}), len({r.post_id for r in rs}),
                     _join(top_questions([(r.question or r.text, r.relevance) for r in rs if r.is_question]), "question"),
                     _join(top_phrases([r.text for r in rs], [r.key_phrases for r in rs]), "phrase")])
    return _csv(["topic", "topic_ar", "slug", "origin", "relevant_discussions", "communities", "posts",
                 "common_questions", "natural_phrases"], out)


def scorecards_csv(s: Session) -> str:
    rows = [[o.country or "ALL", o.suggested_scorecard, o.problem_cluster, o.discussion_count, o.volume_label,
             _join(o.typical_questions, "question"), o.hook, o.cta, o.score, o.method]
            for o in s.scalars(select(ScorecardOpportunity).order_by(ScorecardOpportunity.score.desc()))]
    return _csv(["country", "suggested_scorecard", "problem_cluster", "relevant_discussions", "volume",
                 "typical_questions", "educational_hook", "cta", "score", "method"], rows)


def content_csv(s: Session) -> str:
    names = {t.id: t.name_en for t in s.scalars(select(Topic))}
    rows = [[names.get(c.topic_id), c.kind, c.text, c.method]
            for c in s.scalars(select(ContentIdea).order_by(ContentIdea.topic_id, ContentIdea.kind, ContentIdea.id))]
    return _csv(["topic", "kind", "idea", "method"], rows)


def business_csv(s: Session) -> str:
    rows = [[b.business_name, b.category, b.country, b.public_email, b.website, " | ".join(b.social_profiles or []),
             b.partnership_relevance, b.source_url, b.notes]
            for b in s.scalars(select(BusinessAccount).order_by(BusinessAccount.partnership_relevance.desc()))]
    return _csv(["business_name", "category", "country", "public_business_email", "website", "social_profiles",
                 "partnership_relevance", "source_url", "notes"], rows)


EXPORTS = {
    "communities": communities_csv, "posts": posts_csv, "comments": comments_csv, "topics": topics_csv,
    "scorecards": scorecards_csv, "content_ideas": content_csv, "b2b": business_csv,
}
