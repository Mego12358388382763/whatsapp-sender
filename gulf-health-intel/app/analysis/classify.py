"""Comment classification pipeline.

Cost controls, in order:
  1. de-duplicate by normalised text hash, so identical comments are classified once
  2. heuristic prefilter: spam, greetings and off-topic comments never reach the LLM
  3. cache lookup (provider|model|prompt version|text hash)
  4. batched calls to the cheap model with structured JSON output
  5. validation, with fallback to the heuristic result on any error
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Comment, CommentAnalysis, CommentTopic, LLMCache, Topic, utcnow
from ..privacy import scrub
from ..text.lexicon import INTENTS, SEED_TOPICS
from .heuristic import HeuristicResult, analyze
from .llm.base import LLMError, LLMProvider
from .llm.prompts import CLASSIFY_SCHEMA, CLASSIFY_SYSTEM, CLASSIFY_VERSION
from .topics import ensure_seed_topics, get_or_create_candidate, promote_candidates

log = logging.getLogger(__name__)

# Guard against diagnosis-like labels sneaking in as discovered topics.
_DIAGNOSIS = re.compile(
    r"(syndrome|disorder|disease|cfs|\bme\b|diabet|cancer|thyroid|anemi|anaemi|depressi|adhd|"
    r"fibromyalgia|arthritis|pcos|متلازمه|مرض|اضطراب|سكري|غده|انيميا|اكتئاب)",
    re.I,
)


@dataclass
class Result:
    topics: list[tuple[str, float]]
    new_topic: str | None
    intent: str
    intent_confidence: float
    relevance_score: int
    is_question: bool
    question: str | None
    language: str
    dialect: str
    key_phrases: list[str]
    method: str
    model: str | None = None

    @classmethod
    def from_heuristic(cls, h: HeuristicResult) -> "Result":
        return cls(h.topics, None, h.intent, h.intent_confidence, h.relevance_score, h.is_question,
                   h.question_text, h.language, h.dialect, h.key_phrases, "heuristic")


def _validate(item: dict, fallback: HeuristicResult, model: str) -> Result:
    topics: list[tuple[str, float]] = []
    new_topic = item.get("new_topic") or None
    for t in item.get("topics") or []:
        slug = str(t.get("slug", "")).strip()
        conf = float(max(0.0, min(1.0, t.get("confidence", 0.5) or 0.5)))
        if slug in SEED_TOPICS:
            topics.append((slug, round(conf, 2)))
        elif slug and not new_topic:
            new_topic = slug.replace("_", " ")
    if new_topic and (_DIAGNOSIS.search(new_topic) or len(new_topic) > 60):
        new_topic = None
    intent = item.get("intent")
    if intent not in INTENTS:
        intent = fallback.intent
    rel = item.get("relevance_score")
    rel = int(max(0, min(100, rel))) if isinstance(rel, (int, float)) else fallback.relevance_score
    q = item.get("question")
    return Result(
        topics=sorted(topics, key=lambda x: -x[1]),
        new_topic=new_topic.strip().lower() if new_topic else None,
        intent=intent,
        intent_confidence=float(max(0.0, min(1.0, item.get("intent_confidence") or 0.5))),
        relevance_score=rel,
        is_question=bool(item.get("is_question")),
        question=scrub(q)[:220] if q else None,
        language=item.get("language") or fallback.language,
        dialect=item.get("dialect") or fallback.dialect,
        key_phrases=[scrub(p)[:80] for p in (item.get("key_phrases") or [])][:5],
        method="llm",
        model=model,
    )


def _cache_key(provider: LLMProvider, model: str, thash: str) -> str:
    return hashlib.sha256(f"{provider.name}|{model}|{CLASSIFY_VERSION}|{thash}".encode()).hexdigest()


def _like_bonus(likes: int | None) -> int:
    return int(min(6, 2 * math.log10(1 + likes))) if likes else 0


def classify_pending(
    s: Session,
    provider: LLMProvider | None = None,
    reanalyze: bool = False,
    batch_size: int = 25,
    limit: int | None = None,
) -> dict:
    ensure_seed_topics(s)
    q = select(Comment)
    if not reanalyze:
        q = q.outerjoin(CommentAnalysis, CommentAnalysis.comment_id == Comment.id).where(CommentAnalysis.id.is_(None))
    if limit:
        q = q.limit(limit)
    comments = list(s.scalars(q))
    stats = {"comments": len(comments), "unique_texts": 0, "prefiltered": 0, "cache_hits": 0,
             "llm_classified": 0, "llm_calls": 0, "llm_errors": 0, "heuristic": 0}
    if not comments:
        return stats

    # 1. dedupe
    by_hash: dict[str, list[Comment]] = {}
    for c in comments:
        by_hash.setdefault(c.text_hash, []).append(c)
    stats["unique_texts"] = len(by_hash)

    heur: dict[str, HeuristicResult] = {h: analyze(cs[0].text) for h, cs in by_hash.items()}
    results: dict[str, Result] = {}
    to_llm: list[str] = []
    for h, hr in heur.items():
        # 2. prefilter
        if provider is None or not hr.needs_llm:
            results[h] = Result.from_heuristic(hr)
            if provider is not None:
                stats["prefiltered"] += 1
            continue
        # 3. cache
        model = provider.fast_model
        cached = s.get(LLMCache, _cache_key(provider, model, h))
        if cached:
            results[h] = _validate(cached.response, hr, model)
            stats["cache_hits"] += 1
        else:
            to_llm.append(h)

    # 4. batch
    if provider is not None:
        model = provider.fast_model
        for i in range(0, len(to_llm), batch_size):
            chunk = to_llm[i : i + batch_size]
            payload = [{"id": n, "text": by_hash[h][0].text[:600]} for n, h in enumerate(chunk)]
            user = "Classify these comments. Input JSON:\n" + json.dumps(payload, ensure_ascii=False)
            try:
                out = provider.complete_json(CLASSIFY_SYSTEM, user, CLASSIFY_SCHEMA, model=model,
                                             max_tokens=min(8000, 300 * len(chunk) + 500))
                stats["llm_calls"] += 1
                items = {int(it.get("id", -1)): it for it in out.get("items", []) if isinstance(it, dict)}
            except (LLMError, ValueError, TypeError) as e:
                log.warning("LLM batch failed, using heuristic fallback: %s", e)
                stats["llm_errors"] += 1
                items = {}
            for n, h in enumerate(chunk):
                item = items.get(n)
                if item is None:
                    results[h] = Result.from_heuristic(heur[h])
                    continue
                results[h] = _validate(item, heur[h], model)
                s.merge(LLMCache(key=_cache_key(provider, model, h), response=item))
                stats["llm_classified"] += 1

    # 5. persist
    topic_ids = {t.slug: t.id for t in s.scalars(select(Topic))}
    for h, cs in by_hash.items():
        r = results[h]
        if r.method == "heuristic":
            stats["heuristic"] += len(cs)
        extra_topic_id = None
        if r.new_topic:
            extra_topic_id = get_or_create_candidate(s, r.new_topic).id
        for c in cs:
            existing = s.scalar(select(CommentAnalysis).where(CommentAnalysis.comment_id == c.id))
            if existing:
                s.delete(existing)
                s.flush()
            rel = r.relevance_score + (_like_bonus(c.like_count) if r.method == "heuristic" else 0)
            ca = CommentAnalysis(
                comment_id=c.id,
                primary_topic_id=topic_ids.get(r.topics[0][0]) if r.topics else extra_topic_id,
                intent=r.intent, intent_confidence=r.intent_confidence,
                relevance_score=min(100, rel), is_question=r.is_question, question_text=r.question,
                language=r.language, dialect=r.dialect, key_phrases=r.key_phrases,
                method=r.method, model=r.model,
                prompt_version=CLASSIFY_VERSION if r.method == "llm" else None, analyzed_at=utcnow(),
            )
            s.add(ca)
            s.flush()
            for slug, conf in r.topics:
                if slug in topic_ids:
                    s.add(CommentTopic(comment_analysis_id=ca.id, topic_id=topic_ids[slug], confidence=conf))
            if extra_topic_id and extra_topic_id not in {topic_ids.get(sl) for sl, _ in r.topics}:
                s.add(CommentTopic(comment_analysis_id=ca.id, topic_id=extra_topic_id, confidence=0.6))
    s.flush()
    promote_candidates(s)
    return stats
