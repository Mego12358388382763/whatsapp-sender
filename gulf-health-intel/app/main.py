"""FastAPI application: JSON API, CSV exports and the static dashboard."""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import connectors
from .analysis.llm.base import get_provider
from .analysis.pipeline import run_analysis
from .config import settings
from .connectors.base import FetchRequest, parse_dt
from .connectors.tabular import TabularImport, load_records
from .db import get_db
from .export import EXPORTS
from .ingest import GULF_COUNTRIES, run_connector
from .models import (
    BusinessAccount,
    Comment,
    CommentAnalysis,
    CommentTopic,
    Community,
    CommunityAnalysis,
    CommunityTopic,
    ContentIdea,
    IngestionRun,
    Post,
    PostAnalysis,
    ScorecardOpportunity,
    Source,
    Topic,
)
from .search import search as run_search
from .text.lexicon import INTENT_LABELS

STATIC = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(title="Gulf Health Community Intelligence", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


# --------------------------------------------------------------------- meta


@app.get("/api/meta")
def meta():
    p = get_provider()
    return {
        "countries": GULF_COUNTRIES,
        "platforms": ["instagram", "facebook", "tiktok", "youtube", "reddit", "x", "web"],
        "connectors": connectors.status(),
        "llm_provider": p.name if p else "none (heuristic)",
        "llm_models": {"fast": p.fast_model, "strong": p.strong_model} if p else None,
        "relevance_threshold": settings.relevance_threshold,
        "intents": INTENT_LABELS,
    }


# ------------------------------------------------------------------- ingest


class IngestRequest(BaseModel):
    urls: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    country: str | None = None
    city: str | None = None
    platform: str | None = None
    category: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    max_posts: int = 20
    max_comments_per_post: int = 300
    language: str | None = "ar"
    analyze: bool = True


def _run_view(r: IngestionRun) -> dict:
    return {"id": r.id, "status": r.status, "stats": r.stats, "error": r.error, "params": r.params,
            "started_at": r.started_at, "finished_at": r.finished_at}


@app.post("/api/ingest/urls")
def ingest_urls(body: IngestRequest, db: Session = Depends(get_db)):
    if not body.urls and not body.keywords:
        raise HTTPException(400, "Provide at least one URL or keyword")
    base = dict(keywords=body.keywords, country=(body.country or None), city=body.city, platform=body.platform,
                date_from=parse_dt(body.date_from), date_to=parse_dt(body.date_to), max_posts=body.max_posts,
                max_comments_per_post=body.max_comments_per_post, language=body.language)
    runs, unsupported = [], []
    grouped: dict[str, tuple] = {}
    for url in [u.strip() for u in body.urls if u.strip()]:
        c = connectors.connector_for_url(url)
        if c is None:
            unsupported.append({"url": url, "reason": connectors.unsupported_reason(url)})
        else:
            grouped.setdefault(c.name, (c, []))[1].append(url)
    for c, urls in grouped.values():
        runs.append(run_connector(db, c, FetchRequest(urls=urls, **base), category=body.category))
    if body.keywords and not body.urls:
        cs = connectors.connectors_for_keywords(body.platform)
        if not cs:
            unsupported.append({"keywords": body.keywords,
                                "reason": "No keyword-capable connector is configured (YouTube/Reddit/X API keys)."})
        for c in cs:
            runs.append(run_connector(db, c, FetchRequest(**base), category=body.category))
    db.commit()
    analysis = run_analysis(db) if body.analyze and any(r.status == "done" for r in runs) else None
    return {"runs": [_run_view(r) for r in runs], "unsupported": unsupported, "analysis": analysis}


@app.post("/api/ingest/file")
async def ingest_file(
    file: UploadFile = File(...),
    platform: str | None = Form(None),
    community_name: str | None = Form(None),
    country: str | None = Form(None),
    city: str | None = Form(None),
    category: str | None = Form(None),
    date_from: str | None = Form(None),
    date_to: str | None = Form(None),
    mapping: str | None = Form(None),
    analyze: bool = Form(True),
    db: Session = Depends(get_db),
):
    content = await file.read()
    try:
        records = load_records(content, file.filename or "")
        field_map = json.loads(mapping) if mapping else None
    except (ValueError, UnicodeDecodeError) as e:
        raise HTTPException(400, f"Could not parse file: {e}") from e
    conn = TabularImport(records, default_platform=platform or None, default_community=community_name or None,
                         mapping=field_map)
    req = FetchRequest(country=country or None, city=city or None, platform=platform or None,
                       date_from=parse_dt(date_from), date_to=parse_dt(date_to))
    run = run_connector(db, conn, req, source_name=f"upload:{file.filename}", category=category)
    db.commit()
    analysis = run_analysis(db) if analyze and run.status == "done" else None
    return {"run": _run_view(run), "records": len(records), "analysis": analysis}


@app.post("/api/analyze")
def analyze(reanalyze: bool = False, synthesize: bool = True, db: Session = Depends(get_db)):
    return run_analysis(db, reanalyze=reanalyze, synthesize=synthesize)


@app.get("/api/runs")
def runs(db: Session = Depends(get_db)):
    q = select(IngestionRun, Source).join(Source).order_by(IngestionRun.id.desc()).limit(50)
    return [{**_run_view(r), "source": s.name, "kind": s.kind} for r, s in db.execute(q)]


# ---------------------------------------------------------------- dashboard


def _filters(q, country: str | None, platform: str | None):
    if country:
        q = q.where(Community.country == country)
    if platform:
        q = q.where(Community.platform == platform)
    return q


@app.get("/api/overview")
def overview(country: str | None = None, platform: str | None = None, db: Session = Depends(get_db)):
    thr = settings.relevance_threshold
    base = select(func.count()).select_from(Comment).join(Post).join(Community)
    comm_q = _filters(select(func.count()).select_from(Community), country, platform)
    posts_q = _filters(select(func.count()).select_from(Post).join(Community), country, platform)
    analysed_q = _filters(base.join(CommentAnalysis, CommentAnalysis.comment_id == Comment.id), country, platform)
    relevant_q = analysed_q.where(CommentAnalysis.relevance_score >= thr)
    countries = db.execute(select(Community.country, func.count()).group_by(Community.country)).all()
    platforms = db.execute(select(Community.platform, func.count()).group_by(Community.platform)).all()
    return {
        "communities": db.scalar(comm_q), "posts": db.scalar(posts_q),
        "comments": db.scalar(_filters(base, country, platform)), "comments_analyzed": db.scalar(analysed_q),
        "relevant": db.scalar(relevant_q),
        "countries": {c or "unknown": n for c, n in countries}, "platforms": dict(platforms),
        "threshold": thr,
    }


@app.get("/api/topics/top")
def top_topics(country: str | None = None, platform: str | None = None, limit: int = 15,
               db: Session = Depends(get_db)):
    q = (select(Topic.id, Topic.name_en, Topic.name_ar, Topic.is_seed, func.count(), CommentAnalysis.intent)
         .select_from(CommentTopic).join(Topic, Topic.id == CommentTopic.topic_id)
         .join(CommentAnalysis, CommentAnalysis.id == CommentTopic.comment_analysis_id)
         .join(Comment, Comment.id == CommentAnalysis.comment_id).join(Post).join(Community)
         .where(CommentAnalysis.relevance_score >= settings.relevance_threshold)
         .group_by(Topic.id, CommentAnalysis.intent))
    agg: dict[int, dict] = {}
    for tid, en, ar, seed, n, intent in db.execute(_filters(q, country, platform)):
        a = agg.setdefault(tid, {"id": tid, "topic": en, "topic_ar": ar, "discovered": not seed, "count": 0,
                                 "questions": 0})
        a["count"] += n
        if intent in ("asking_question", "asking_for_help", "looking_for_information", "looking_for_practitioner"):
            a["questions"] += n
    return sorted(agg.values(), key=lambda x: -x["count"])[:limit]


@app.get("/api/communities")
def communities(country: str | None = None, platform: str | None = None, db: Session = Depends(get_db)):
    names = {t.id: t.name_en for t in db.scalars(select(Topic))}
    tops: dict[int, list] = {}
    for ct in db.scalars(select(CommunityTopic).order_by(CommunityTopic.comment_count.desc())):
        tops.setdefault(ct.community_id, []).append(
            {"topic": names.get(ct.topic_id), "count": ct.comment_count, "share": ct.share, "growth": ct.growth,
             "avg_post_engagement": ct.avg_post_engagement})
    q = _filters(select(Community, CommunityAnalysis).join(CommunityAnalysis), country, platform)
    out = []
    for c, a in db.execute(q.order_by(CommunityAnalysis.opportunity_score.desc())):
        topics = tops.get(c.id, [])
        best = sorted([t for t in topics if t["avg_post_engagement"]], key=lambda t: -t["avg_post_engagement"])[:3]
        out.append({
            "id": c.id, "name": c.name, "platform": c.platform, "country": c.country, "city": c.city, "url": c.url,
            "posts_analyzed": a.posts_analyzed, "comments_analyzed": a.comments_analyzed,
            "relevant": a.relevant_comments, "relevant_pct": a.relevant_pct, "top_topics": topics[:5],
            "top_questions": a.top_questions, "growth": a.growth, "engagement": a.engagement,
            "best_performing_topics": [t["topic"] for t in best], "opportunity_score": a.opportunity_score,
        })
    return out


@app.get("/api/posts")
def posts(country: str | None = None, platform: str | None = None, community_id: int | None = None,
          topic_id: int | None = None, limit: int = 50, db: Session = Depends(get_db)):
    q = _filters(select(Post, PostAnalysis, Community).join(PostAnalysis).join(Community), country, platform)
    if community_id:
        q = q.where(Post.community_id == community_id)
    if topic_id:
        from .models import PostTopic

        q = q.where(Post.id.in_(select(PostTopic.post_id).where(PostTopic.topic_id == topic_id)))
    q = q.where(PostAnalysis.relevant_comments > 0).order_by(PostAnalysis.relevance_score.desc()).limit(limit)
    return [{
        "id": p.id, "url": p.url, "platform": p.platform, "community": c.name, "country": c.country,
        "title": p.title or (p.text or "")[:120], "published_at": p.published_at,
        "total_comments": a.total_comments, "relevant_comments": a.relevant_comments,
        "question_comments": a.question_comments, "topic_distribution": a.topic_distribution,
        "top_questions": a.top_questions, "top_phrases": a.top_phrases, "dominant_language": a.dominant_language,
        "engagement": a.engagement, "score": a.relevance_score,
    } for p, a, c in db.execute(q)]


@app.get("/api/comments")
def comment_explorer(topic_id: int | None = None, intent: str | None = None, country: str | None = None,
                     platform: str | None = None, community_id: int | None = None, min_relevance: int = 0,
                     q: str | None = None, questions_only: bool = False, limit: int = 50, offset: int = 0,
                     db: Session = Depends(get_db)):
    """Anonymous comment explorer: comment text + analysis + post link. No commenter identity exists."""
    names = {t.id: t.name_en for t in db.scalars(select(Topic))}
    stmt = (select(Comment, CommentAnalysis, Post, Community)
            .join(CommentAnalysis, CommentAnalysis.comment_id == Comment.id)
            .join(Post, Post.id == Comment.post_id).join(Community, Community.id == Post.community_id)
            .where(CommentAnalysis.relevance_score >= min_relevance))
    stmt = _filters(stmt, country, platform)
    if topic_id:
        stmt = stmt.where(CommentAnalysis.id.in_(select(CommentTopic.comment_analysis_id)
                                                 .where(CommentTopic.topic_id == topic_id)))
    if intent:
        stmt = stmt.where(CommentAnalysis.intent == intent)
    if community_id:
        stmt = stmt.where(Community.id == community_id)
    if questions_only:
        stmt = stmt.where(CommentAnalysis.is_question.is_(True))
    if q:
        stmt = stmt.where(Comment.text.contains(q))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(CommentAnalysis.relevance_score.desc(), Comment.id).limit(limit).offset(offset))
    return {"total": total, "items": [{
        "id": cm.id, "comment": cm.text, "topic": names.get(a.primary_topic_id),
        "topics": [names.get(t.topic_id) for t in a.topics], "intent": INTENT_LABELS.get(a.intent, a.intent),
        "intent_key": a.intent, "confidence": round(a.intent_confidence, 2), "relevance": a.relevance_score,
        "language": a.language, "dialect": a.dialect, "country": c.country, "community": c.name,
        "platform": p.platform, "post_url": p.url, "published_at": cm.published_at, "method": a.method,
    } for cm, a, p, c in rows]}


@app.get("/api/scorecards")
def scorecards(country: str | None = None, db: Session = Depends(get_db)):
    q = select(ScorecardOpportunity)
    q = q.where(ScorecardOpportunity.country == country) if country else q.where(ScorecardOpportunity.country.is_(None))
    return [{
        "key": o.key, "country": o.country, "problem_cluster": o.problem_cluster, "discussion_count": o.discussion_count,
        "volume": o.volume_label, "typical_questions": o.typical_questions, "suggested_scorecard": o.suggested_scorecard,
        "hook": o.hook, "cta": o.cta, "score": o.score, "method": o.method,
    } for o in db.scalars(q.order_by(ScorecardOpportunity.score.desc()))]


@app.get("/api/content-ideas")
def content_ideas(db: Session = Depends(get_db)):
    names = {t.id: (t.name_en, t.name_ar) for t in db.scalars(select(Topic))}
    out: dict[int, dict] = {}
    for c in db.scalars(select(ContentIdea).order_by(ContentIdea.id)):
        en, ar = names.get(c.topic_id, ("?", None))
        d = out.setdefault(c.topic_id, {"topic_id": c.topic_id, "topic": en, "topic_ar": ar, "method": c.method,
                                        "ideas": {}})
        d["ideas"].setdefault(c.kind, []).append(c.text)
    return list(out.values())


@app.get("/api/topics")
def topics(db: Session = Depends(get_db)):
    return [{"id": t.id, "slug": t.slug, "name": t.name_en, "name_ar": t.name_ar, "seed": t.is_seed,
             "status": t.status} for t in db.scalars(select(Topic).order_by(Topic.is_seed.desc(), Topic.name_en))]


@app.get("/api/search")
def search(q: str, db: Session = Depends(get_db)):
    return run_search(db, q, threshold=settings.relevance_threshold)


@app.get("/api/trends")
def trends(country: str | None = None, db: Session = Depends(get_db)):
    """Monthly relevant-discussion counts by primary topic."""
    q = (select(Topic.name_en, Comment.published_at).select_from(CommentAnalysis)
         .join(Comment, Comment.id == CommentAnalysis.comment_id).join(Post).join(Community)
         .join(Topic, Topic.id == CommentAnalysis.primary_topic_id)
         .where(CommentAnalysis.relevance_score >= settings.relevance_threshold, Comment.published_at.is_not(None)))
    c: dict[str, Counter] = {}
    for name, dt in db.execute(_filters(q, country, None)):
        c.setdefault(name, Counter())[dt.strftime("%Y-%m")] += 1
    return {k: dict(sorted(v.items())) for k, v in c.items()}


# ---------------------------------------------------------------------- B2B


class BusinessIn(BaseModel):
    business_name: str
    category: str | None = None
    country: str | None = None
    public_email: str | None = None
    website: str | None = None
    social_profiles: list[str] = Field(default_factory=list)
    partnership_relevance: int | None = Field(default=None, ge=0, le=100)
    source_url: str | None = None
    notes: str | None = None


@app.get("/api/business")
def list_business(db: Session = Depends(get_db)):
    return [{c.name: getattr(b, c.name) for c in BusinessAccount.__table__.columns}
            for b in db.scalars(select(BusinessAccount).order_by(BusinessAccount.id.desc()))]


@app.post("/api/business")
def add_business(body: BusinessIn, db: Session = Depends(get_db)):
    b = BusinessAccount(**body.model_dump())
    db.add(b)
    db.commit()
    return {"id": b.id}


@app.post("/api/business/import")
async def import_business(file: UploadFile = File(...), db: Session = Depends(get_db)):
    recs = load_records(await file.read(), file.filename or "")
    n = 0
    for r in recs:
        name = r.get("business_name") or r.get("name")
        if not name:
            continue
        socials = r.get("social_profiles") or ""
        db.add(BusinessAccount(
            business_name=name, category=r.get("category"), country=r.get("country"),
            public_email=r.get("public_email") or r.get("email"), website=r.get("website"),
            social_profiles=socials if isinstance(socials, list) else [x.strip() for x in str(socials).split("|") if x.strip()],
            partnership_relevance=int(r["partnership_relevance"]) if str(r.get("partnership_relevance", "")).isdigit() else None,
            source_url=r.get("source_url"), notes=r.get("notes"),
        ))
        n += 1
    db.commit()
    return {"imported": n}


@app.delete("/api/business/{bid}")
def delete_business(bid: int, db: Session = Depends(get_db)):
    b = db.get(BusinessAccount, bid)
    if not b:
        raise HTTPException(404)
    db.delete(b)
    db.commit()
    return {"deleted": bid}


# -------------------------------------------------------------------- export


@app.get("/api/export/{kind}.csv")
def export(kind: str, db: Session = Depends(get_db)):
    fn = EXPORTS.get(kind)
    if not fn:
        raise HTTPException(404, f"Unknown export. Options: {', '.join(EXPORTS)}")
    stamp = datetime.now().strftime("%Y%m%d")
    return Response(fn(db), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="ghci_{kind}_{stamp}.csv"'})
