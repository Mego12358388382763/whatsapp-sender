"""Routes for the Reply queue (manual posting only), the public Scorecard and opt-in leads."""
from __future__ import annotations

import csv
import io
import os
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..analysis.llm.base import get_provider
from ..config import settings
from ..db import get_db
from ..models import Community, Post, ReplyQueueItem, ScorecardSubmission, Topic, utcnow
from ..text.lexicon import INTENT_LABELS
from .replies import build_queue, draft_for, open_url, recently_used, replies_today
from .scorecards import SCORECARDS, public_definition, score

STATIC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

router = APIRouter()
public = APIRouter()


# ------------------------------------------------------------- reply queue


def _item_view(i: ReplyQueueItem, names: dict) -> dict:
    post = i.comment.post
    com = post.community
    return {
        "id": i.id, "comment": i.comment.text, "topic": names.get(i.topic_id), "intent": INTENT_LABELS.get(i.intent, i.intent),
        "relevance": i.relevance, "platform": i.platform, "community": com.name, "country": com.country,
        "post_url": post.url, "post_title": post.title or (post.text or "")[:100], "open_url": open_url(i),
        "published_at": i.comment.published_at, "scorecard": i.scorecard_key, "drafts": i.drafts,
        "drafts_method": i.drafts_method, "status": i.status, "final_reply": i.final_reply,
    }


@router.post("/api/replies/refresh")
def refresh_queue(days: int = 30, db: Session = Depends(get_db)):
    added = build_queue(db, provider=get_provider(), days=max(1, min(days, 3650)))
    db.commit()
    return {"added": added}


@router.get("/api/replies")
def list_replies(status: str = "pending", country: str | None = None, platform: str | None = None,
                 topic_id: int | None = None, limit: int = 50, db: Session = Depends(get_db)):
    from ..models import Comment

    q = (select(ReplyQueueItem).join(Comment, Comment.id == ReplyQueueItem.comment_id)
         .join(Post, Post.id == Comment.post_id).join(Community, Community.id == Post.community_id)
         .where(ReplyQueueItem.status == status))
    if country:
        q = q.where(Community.country == country)
    if platform:
        q = q.where(ReplyQueueItem.platform == platform)
    if topic_id:
        q = q.where(ReplyQueueItem.topic_id == topic_id)
    order = ReplyQueueItem.relevance.desc() if status == "pending" else ReplyQueueItem.acted_at.desc()
    names = {t.id: t.name_en for t in db.scalars(select(Topic))}
    counts = dict(db.execute(select(ReplyQueueItem.status, func.count()).group_by(ReplyQueueItem.status)).all())
    return {
        "items": [_item_view(i, names) for i in db.scalars(q.order_by(order).limit(limit))],
        "counts": counts, "today": replies_today(db), "daily_soft_limit": settings.reply_daily_soft_limit,
    }


class ReplyAction(BaseModel):
    status: str = Field(pattern="^(copied|posted|skipped|pending)$")
    reply: str | None = None


@router.post("/api/replies/{item_id}/status")
def set_reply_status(item_id: int, body: ReplyAction, db: Session = Depends(get_db)):
    """Record what the person did. The tool never posts anything itself."""
    item = db.get(ReplyQueueItem, item_id)
    if not item:
        raise HTTPException(404)
    warnings = []
    if body.reply:
        text = body.reply.strip()[:1000]
        if recently_used(db, text):
            warnings.append("This exact reply was already used in the last 7 days. Vary the wording to avoid looking like spam.")
        item.final_reply = text
    item.status = body.status
    item.acted_at = None if body.status == "pending" else utcnow()
    db.commit()
    today = replies_today(db)
    if today > settings.reply_daily_soft_limit:
        warnings.append(f"{today} replies today. Consider pausing: high reply volume can get an account flagged.")
    return {"id": item.id, "status": item.status, "open_url": open_url(item), "today": today, "warnings": warnings}


@router.post("/api/replies/{item_id}/redraft")
def redraft(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ReplyQueueItem, item_id)
    if not item:
        raise HTTPException(404)
    draft_for(db, item, get_provider())
    db.commit()
    return {"drafts": item.drafts, "method": item.drafts_method}


# ---------------------------------------------------------------- scorecard


@public.get("/s/{key}", include_in_schema=False)
def scorecard_page(key: str):
    if key not in SCORECARDS:
        raise HTTPException(404)
    return FileResponse(os.path.join(STATIC, "scorecard.html"))


@public.get("/api/public/scorecards/{key}")
def scorecard_definition(key: str, lang: str = "ar"):
    d = public_definition(key, lang)
    if not d:
        raise HTTPException(404)
    d["brand"] = settings.brand_name
    return d


_PHONE = re.compile(r"^\+?[0-9 ()-]{8,20}$")


class Submission(BaseModel):
    answers: dict[str, int]
    lang: str = "ar"
    name: str | None = Field(default=None, max_length=120)
    whatsapp: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=2)
    consent: bool = False
    consent_text: str | None = Field(default=None, max_length=1000)
    utm_source: str | None = Field(default=None, max_length=60)
    utm_campaign: str | None = Field(default=None, max_length=60)


@public.post("/api/public/scorecards/{key}/submit")
def submit_scorecard(key: str, body: Submission, db: Session = Depends(get_db)):
    if key not in SCORECARDS:
        raise HTTPException(404)
    n = len(SCORECARDS[key]["questions"])
    answers = {k: v for k, v in body.answers.items() if k.isdigit() and int(k) < n and 0 <= v <= 4}
    if len(answers) < n:
        raise HTTPException(400, "Please answer every question")
    result = score(key, answers, body.lang)
    wants_contact = bool(body.name or body.whatsapp or body.email)
    if wants_contact and not body.consent:
        raise HTTPException(400, "Consent is required to save contact details")
    if body.whatsapp and not _PHONE.match(body.whatsapp.strip()):
        raise HTTPException(400, "Please enter a valid WhatsApp number")
    keep = wants_contact and body.consent
    db.add(ScorecardSubmission(
        scorecard_key=key, language="ar" if body.lang == "ar" else "en", answers=answers,
        area_scores={a["area"]: a["score"] for a in result["areas"]}, total_score=result["total"],
        contact_name=body.name.strip() if keep and body.name else None,
        contact_whatsapp=body.whatsapp.strip() if keep and body.whatsapp else None,
        contact_email=body.email.strip() if keep and body.email else None,
        country=(body.country or "").upper() or None, consent=keep,
        consent_text=body.consent_text if keep else None, consent_at=utcnow() if keep else None,
        utm_source=body.utm_source, utm_campaign=body.utm_campaign,
    ))
    db.commit()
    return result


# -------------------------------------------------------------------- leads


def _require_password():
    if not settings.admin_password:
        raise HTTPException(403, "Set ADMIN_PASSWORD to view leads. Lead data is never shown on an unprotected dashboard.")


@router.get("/api/leads")
def list_leads(key: str | None = None, db: Session = Depends(get_db)):
    _require_password()
    q = select(ScorecardSubmission).where(ScorecardSubmission.consent.is_(True))
    if key:
        q = q.where(ScorecardSubmission.scorecard_key == key)
    total = db.scalar(select(func.count()).select_from(ScorecardSubmission))
    return {
        "completions": total,
        "leads": [{
            "id": s.id, "scorecard": s.scorecard_key, "name": s.contact_name, "whatsapp": s.contact_whatsapp,
            "email": s.contact_email, "country": s.country, "total_score": s.total_score, "areas": s.area_scores,
            "language": s.language, "source": s.utm_source, "campaign": s.utm_campaign, "status": s.lead_status,
            "consent_at": s.consent_at, "created_at": s.created_at,
        } for s in db.scalars(q.order_by(ScorecardSubmission.id.desc()).limit(500))],
        "by_source": dict(db.execute(select(ScorecardSubmission.utm_campaign, func.count())
                                     .group_by(ScorecardSubmission.utm_campaign)).all()),
    }


class LeadStatus(BaseModel):
    status: str = Field(pattern="^(new|contacted|converted|closed)$")


@router.post("/api/leads/{lead_id}/status")
def lead_status(lead_id: int, body: LeadStatus, db: Session = Depends(get_db)):
    _require_password()
    s = db.get(ScorecardSubmission, lead_id)
    if not s or not s.consent:
        raise HTTPException(404)
    s.lead_status = body.status
    db.commit()
    return {"id": s.id, "status": s.lead_status}


@router.delete("/api/leads/{lead_id}")
def delete_lead(lead_id: int, db: Session = Depends(get_db)):
    """Right to erasure: removes the person's details and answers completely."""
    _require_password()
    s = db.get(ScorecardSubmission, lead_id)
    if not s:
        raise HTTPException(404)
    db.delete(s)
    db.commit()
    return {"deleted": lead_id}


@router.get("/api/export/leads.csv")
def export_leads(db: Session = Depends(get_db)):
    _require_password()
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf)
    w.writerow(["name", "whatsapp", "email", "country", "scorecard", "total_score", "area_scores", "language",
                "source", "campaign", "lead_status", "consent_at", "created_at"])
    for s in db.scalars(select(ScorecardSubmission).where(ScorecardSubmission.consent.is_(True))
                        .order_by(ScorecardSubmission.id.desc())):
        w.writerow([s.contact_name, s.contact_whatsapp, s.contact_email, s.country, s.scorecard_key, s.total_score,
                    "; ".join(f"{k}={v}" for k, v in s.area_scores.items()), s.language, s.utm_source,
                    s.utm_campaign, s.lead_status, s.consent_at, s.created_at])
    stamp = datetime.now().strftime("%Y%m%d")
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="ghci_leads_{stamp}.csv"'})
