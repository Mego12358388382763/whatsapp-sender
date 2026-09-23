"""Database schema.

Three deliberately separate groups:

* RAW layer: collected public content. Comments have NO author/identity columns.
* ANALYSIS layer: derived output, fully rebuildable from the raw layer.
* B2B layer: public business accounts, with no link to any comment or health data.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- RAW


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    platform: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(20))  # api | provider | csv | manual
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("name", "platform", "kind"),)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="running")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Community(Base):
    """A public page / channel / subreddit / forum. Never a private individual."""

    __tablename__ = "communities"
    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(40), index=True)
    url: Mapped[str] = mapped_column(String(500))
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name: Mapped[str] = mapped_column(String(300))
    country: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    posts: Mapped[list["Post"]] = relationship(back_populates="community")
    __table_args__ = (UniqueConstraint("platform", "url"),)


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("communities.id"), index=True)
    platform: Mapped[str] = mapped_column(String(40), index=True)
    url: Mapped[str] = mapped_column(String(500))
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    like_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    share_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    view_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ingestion_run_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_runs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    community: Mapped[Community] = relationship(back_populates="posts")
    comments: Mapped[list["Comment"]] = relationship(back_populates="post")
    __table_args__ = (UniqueConstraint("platform", "url"),)


class Comment(Base):
    """A public comment. There are intentionally NO author / username / profile columns.

    `text` is stored after PII scrubbing (mentions, emails, phones, URLs removed).
    `external_id_hash` is a one-way hash used only for de-duplication on re-import.
    """

    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    platform: Mapped[str] = mapped_column(String(40))
    external_id_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    text_hash: Mapped[str] = mapped_column(String(64), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    like_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reply_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    ingestion_run_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_runs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    post: Mapped[Post] = relationship(back_populates="comments")
    analysis: Mapped["CommentAnalysis | None"] = relationship(back_populates="comment", uselist=False)
    __table_args__ = (UniqueConstraint("post_id", "text_hash"),)


# ---------------------------------------------------------------------- ANALYSIS


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name_en: Mapped[str] = mapped_column(String(120))
    name_ar: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_seed: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | candidate
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CommentAnalysis(Base):
    __tablename__ = "comment_analysis"
    id: Mapped[int] = mapped_column(primary_key=True)
    comment_id: Mapped[int] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"), unique=True)
    primary_topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"), nullable=True, index=True)
    intent: Mapped[str] = mapped_column(String(40), index=True)
    intent_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    relevance_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_question: Mapped[bool] = mapped_column(Boolean, default=False)
    question_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dialect: Mapped[str | None] = mapped_column(String(20), nullable=True)
    key_phrases: Mapped[list] = mapped_column(JSON, default=list)
    method: Mapped[str] = mapped_column(String(20), default="heuristic")
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    comment: Mapped[Comment] = relationship(back_populates="analysis")
    primary_topic: Mapped[Topic | None] = relationship()
    topics: Mapped[list["CommentTopic"]] = relationship(cascade="all, delete-orphan")


class CommentTopic(Base):
    __tablename__ = "comment_topics"
    comment_analysis_id: Mapped[int] = mapped_column(
        ForeignKey("comment_analysis.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), primary_key=True, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    topic: Mapped[Topic] = relationship()


class PostAnalysis(Base):
    __tablename__ = "post_analysis"
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
    total_comments: Mapped[int] = mapped_column(Integer, default=0)
    relevant_comments: Mapped[int] = mapped_column(Integer, default=0)
    question_comments: Mapped[int] = mapped_column(Integer, default=0)
    dominant_language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    engagement: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relevance_score: Mapped[int] = mapped_column(Integer, default=0)
    topic_distribution: Mapped[list] = mapped_column(JSON, default=list)
    top_questions: Mapped[list] = mapped_column(JSON, default=list)
    top_phrases: Mapped[list] = mapped_column(JSON, default=list)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PostTopic(Base):
    __tablename__ = "post_topics"
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), primary_key=True)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    share: Mapped[float] = mapped_column(Float, default=0.0)


class CommunityAnalysis(Base):
    __tablename__ = "community_analysis"
    community_id: Mapped[int] = mapped_column(
        ForeignKey("communities.id", ondelete="CASCADE"), primary_key=True
    )
    posts_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    comments_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    relevant_comments: Mapped[int] = mapped_column(Integer, default=0)
    relevant_pct: Mapped[float] = mapped_column(Float, default=0.0)
    top_questions: Mapped[list] = mapped_column(JSON, default=list)
    engagement: Mapped[dict] = mapped_column(JSON, default=dict)
    growth: Mapped[list] = mapped_column(JSON, default=list)
    opportunity_score: Mapped[int] = mapped_column(Integer, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CommunityTopic(Base):
    __tablename__ = "community_topics"
    community_id: Mapped[int] = mapped_column(
        ForeignKey("communities.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), primary_key=True)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    share: Mapped[float] = mapped_column(Float, default=0.0)
    growth: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_post_engagement: Mapped[float | None] = mapped_column(Float, nullable=True)


class ScorecardOpportunity(Base):
    __tablename__ = "scorecard_opportunities"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(60))
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    problem_cluster: Mapped[str] = mapped_column(String(300))
    topics: Mapped[list] = mapped_column(JSON, default=list)
    discussion_count: Mapped[int] = mapped_column(Integer, default=0)
    volume_label: Mapped[str] = mapped_column(String(10), default="Low")
    typical_questions: Mapped[list] = mapped_column(JSON, default=list)
    suggested_scorecard: Mapped[str] = mapped_column(String(200))
    hook: Mapped[str] = mapped_column(Text)
    cta: Mapped[str] = mapped_column(String(300))
    score: Mapped[int] = mapped_column(Integer, default=0)
    method: Mapped[str] = mapped_column(String(20), default="heuristic")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ContentIdea(Base):
    __tablename__ = "content_ideas"
    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # reel|hook|faq|carousel|article|lead_magnet|scorecard
    text: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(20), default="heuristic")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LLMCache(Base):
    __tablename__ = "llm_cache"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# --------------------------------------------------------------------------- B2B


class BusinessAccount(Base):
    """Public professional/business accounts for potential B2B partnerships.

    Stored separately; there is intentionally no relationship to comments or
    comment analysis.
    """

    __tablename__ = "business_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    business_name: Mapped[str] = mapped_column(String(300))
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    public_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    website: Mapped[str | None] = mapped_column(String(300), nullable=True)
    social_profiles: Mapped[list] = mapped_column(JSON, default=list)
    partnership_relevance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
