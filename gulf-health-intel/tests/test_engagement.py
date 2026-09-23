import base64
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.analysis.pipeline import run_analysis
from app.config import settings
from app.connectors.base import FetchRequest
from app.connectors.tabular import TabularImport, load_records
from app.db import Base
from app.engagement.replies import build_queue
from app.engagement.scorecards import SCORECARDS, public_definition, score
from app.ingest import run_connector
from app.models import ReplyQueueItem, ScorecardSubmission

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "sample_data", "synthetic_comments.csv")


@pytest.fixture()
def loaded(db):
    recs = load_records(open(SAMPLE, "rb").read(), "s.csv")
    run_connector(db, TabularImport(recs), FetchRequest())
    run_analysis(db, provider=None)
    return db


@pytest.fixture()
def client(db):
    from app.main import app

    yield TestClient(app)
    settings.admin_password = ""


def _auth(pwd="secret"):
    return {"Authorization": "Basic " + base64.b64encode(f"admin:{pwd}".encode()).decode()}


# ------------------------------------------------------------------ queue


def test_queue_has_no_identity_and_links_to_post(db):
    cols = {c.name for c in Base.metadata.tables["reply_queue"].columns}
    assert not cols & {"author", "username", "profile_url", "commenter", "handle"}


def test_build_queue_drafts(loaded):
    settings.public_base_url = "https://example.test"
    # the synthetic comments are dated 2026; widen the window so the test is date-independent
    added = build_queue(loaded, days=3650, limit=10_000)
    assert added > 0
    items = list(loaded.scalars(select(ReplyQueueItem)))
    assert all(i.intent in {"asking_for_help", "asking_question", "looking_for_information",
                            "looking_for_practitioner", "did_not_work"} for i in items)
    for i in items:
        assert len(i.drafts) >= 2 and len(set(i.drafts)) == len(i.drafts)
        assert all(f"https://example.test/s/{i.scorecard_key}?" in d for d in i.drafts)
        joined = " ".join(i.drafts).lower()
        assert "you have" not in joined and "diagnos" not in joined
    # idempotent: questions are queued once
    assert build_queue(loaded, days=3650, limit=10_000) == 0
    arabic = next(i for i in items if i.language == "ar")
    assert any("؀" <= ch <= "ۿ" for ch in arabic.drafts[0])


def test_reply_status_only_records(loaded, client):
    build_queue(loaded, days=3650)
    loaded.commit()
    data = client.get("/api/replies").json()
    item = data["items"][0]
    assert item["open_url"] == item["post_url"]
    r = client.post(f"/api/replies/{item['id']}/status", json={"status": "copied", "reply": item["drafts"][0]}).json()
    assert r["status"] == "copied"
    r = client.post(f"/api/replies/{item['id']}/status", json={"status": "posted", "reply": item["drafts"][0]}).json()
    assert r["status"] == "posted" and r["today"] >= 1
    # reusing the exact same text on another item triggers a spam warning
    other = client.get("/api/replies").json()["items"][0]
    r = client.post(f"/api/replies/{other['id']}/status", json={"status": "posted", "reply": item["drafts"][0]}).json()
    assert r["warnings"]
    assert client.post(f"/api/replies/{other['id']}/redraft").json()["drafts"]


# -------------------------------------------------------------- scorecard


def test_scorecard_definitions_and_scoring():
    for key in SCORECARDS:
        for lang in ("ar", "en"):
            d = public_definition(key, lang)
            assert d["questions"] and len(d["scale"]) == 5 and d["disclaimer"]
    n = len(SCORECARDS["energy"]["questions"])
    best = {str(i): (4 if q[3] else 0) for i, q in enumerate(SCORECARDS["energy"]["questions"])}
    worst = {str(i): (0 if q[3] else 4) for i, q in enumerate(SCORECARDS["energy"]["questions"])}
    assert score("energy", best, "en")["total"] == 100
    r = score("energy", worst, "ar")
    assert r["total"] == 0 and all(a["level"] == "priority" for a in r["areas"])
    assert len(best) == n


def test_submit_requires_consent_for_contact(client, db):
    n = len(SCORECARDS["sleep"]["questions"])
    answers = {str(i): 2 for i in range(n)}
    assert client.get("/s/sleep").status_code == 200
    assert client.get("/s/nope").status_code == 404
    assert client.post("/api/public/scorecards/sleep/submit", json={"answers": {"0": 1}}).status_code == 400
    r = client.post("/api/public/scorecards/sleep/submit", json={"answers": answers, "whatsapp": "+966 55 123 4567"})
    assert r.status_code == 400  # contact details without consent are refused
    r = client.post("/api/public/scorecards/sleep/submit", json={"answers": answers, "utm_campaign": "reply_sleep"})
    assert r.status_code == 200 and "areas" in r.json()
    anon = db.scalar(select(ScorecardSubmission))
    assert anon.contact_whatsapp is None and not anon.consent
    r = client.post("/api/public/scorecards/sleep/submit", json={
        "answers": answers, "name": "Test", "whatsapp": "+966 55 123 4567", "consent": True, "consent_text": "ok"})
    assert r.status_code == 200
    lead = db.scalars(select(ScorecardSubmission).where(ScorecardSubmission.consent.is_(True))).one()
    assert lead.contact_whatsapp == "+966 55 123 4567" and lead.consent_at is not None


def test_leads_require_password_and_auth(client, db):
    assert client.get("/api/leads").status_code == 403  # no password configured
    settings.admin_password = "secret"
    assert client.get("/api/leads").status_code == 401
    assert client.get("/", headers=_auth("wrong")).status_code == 401
    assert client.get("/api/leads", headers=_auth()).status_code == 200
    assert client.get("/api/export/leads.csv", headers=_auth()).status_code == 200
    # the public Scorecard stays reachable without a password
    assert client.get("/s/energy").status_code == 200
    assert client.get("/api/public/scorecards/energy?lang=en").status_code == 200


def test_submissions_not_linked_to_comments(db):
    t = Base.metadata.tables["scorecard_submissions"]
    assert not t.foreign_keys
    assert "consent" in t.columns and "consent_at" in t.columns
