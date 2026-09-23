import os

import pytest
from sqlalchemy import func, select

from app.analysis.pipeline import run_analysis
from app.connectors.base import FetchRequest
from app.connectors.tabular import TabularImport, load_records
from app.ingest import run_connector
from app.models import (CommunityAnalysis, ContentIdea, PostAnalysis, ScorecardOpportunity, Topic)
from app.search import parse_query, search

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "sample_data", "synthetic_comments.csv")

HAIR = ["تساقط الشعر عندي صار كثير بعد الولاده", "تساقط الشعر وش الحل؟", "تساقط الشعر من الضغط؟",
        "عندي تساقط الشعر من شهور", "تساقط الشعر مخوفني كل يوم", "ليش تساقط الشعر يزيد بالصيف؟"]


@pytest.fixture()
def analysed(db):
    recs = load_records(open(SAMPLE, "rb").read(), "s.csv")
    recs += [{"post_url": f"https://demo.example/hair/{i % 3}", "community_name": "Demo Hair Talk", "country": "SA",
              "comment_text": t} for i, t in enumerate(HAIR)]
    run_connector(db, TabularImport(recs), FetchRequest())
    out = run_analysis(db, provider=None)
    return db, out


def test_pipeline_outputs(analysed):
    db, out = analysed
    assert out["aggregate"]["relevant"] > 100
    assert db.scalar(select(func.count()).select_from(PostAnalysis)) == out["aggregate"]["posts"]
    ca = db.scalars(select(CommunityAnalysis)).all()
    assert all(0 <= c.opportunity_score <= 100 for c in ca)
    assert any(c.growth for c in ca)


def test_topic_discovery_finds_new_theme(analysed):
    db, out = analysed
    assert any("تساقط" in t or "الشعر" in t for t in out["discovered_topics"])
    t = db.scalar(select(Topic).where(Topic.is_seed.is_(False)))
    assert t is not None


def test_scorecards(analysed):
    db, _ = analysed
    overall = db.scalars(select(ScorecardOpportunity).where(ScorecardOpportunity.country.is_(None))).all()
    keys = {o.key for o in overall}
    assert {"energy", "stress", "digestive"} <= keys
    energy = next(o for o in overall if o.key == "energy")
    assert energy.volume_label in {"High", "Medium", "Low"} and energy.typical_questions and energy.cta
    assert db.scalar(select(func.count()).select_from(ScorecardOpportunity).where(ScorecardOpportunity.country == "SA"))


def test_content_ideas(analysed):
    db, _ = analysed
    kinds = dict(db.execute(select(ContentIdea.kind, func.count()).group_by(ContentIdea.kind)).all())
    assert kinds["reel"] >= 10 and kinds["hook"] >= 10 and kinds["faq"] >= 1
    assert {"carousel", "article", "lead_magnet", "scorecard"} <= set(kinds)


def test_parse_query():
    assert parse_query("fatigue Saudi Arabia") == {"topics": ["fatigue_low_energy"], "country": "SA", "city": None,
                                                   "city_terms": [], "terms": []}
    p = parse_query("burnout Riyadh")
    assert p["topics"] == ["burnout"] and p["country"] == "SA" and p["city"] == "Riyadh"
    assert parse_query("gut health Dubai")["topics"] == ["digestive"]
    assert parse_query("sleep problems UAE")["country"] == "AE"
    assert parse_query("chronic pain Saudi")["topics"] == ["chronic_pain"]


def test_search(analysed):
    db, _ = analysed
    r = search(db, "fatigue Saudi Arabia")
    assert r["discussion_volume"] > 0 and r["communities"] and r["common_questions"]
    assert all(c["country"] == "SA" for c in r["communities"])
    assert r["topic_trends"]
    # results never include identity fields
    assert all(set(c) == {"text", "relevance", "intent", "post_url"} for c in r["sample_comments"])
