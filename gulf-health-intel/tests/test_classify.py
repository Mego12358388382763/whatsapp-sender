from sqlalchemy import func, select

from app.analysis.classify import classify_pending
from app.analysis.llm.mock import MockProvider
from app.connectors.base import FetchRequest
from app.connectors.tabular import TabularImport
from app.ingest import run_connector
from app.models import CommentAnalysis, LLMCache, Topic

ROWS = [
    {"post_url": "https://www.instagram.com/p/P1/", "community_name": "Riyadh Wellness", "comment_text": t}
    for t in [
        "صار لي سنه تعبانه وما فيني حيل، وش الحل؟",
        "ماشاء الله 😍",
        "تعرفون دكتور زين للقولون في الرياض؟",
        "can't sleep for months, any advice?",
        "في الصيام طاقتي تنزل مره وش السبب؟",
        "للطلب تواصل واتساب [phone]",
    ]
] + [{"post_url": "https://www.instagram.com/p/P2/", "community_name": "Riyadh Wellness",
      "comment_text": "صار لي سنه تعبانه وما فيني حيل، وش الحل؟"}]


def _load(db):
    run_connector(db, TabularImport(ROWS, default_platform="instagram"), FetchRequest(country="SA"))


def test_heuristic_only(db):
    _load(db)
    st = classify_pending(db, provider=None)
    assert st["comments"] == 7 and st["heuristic"] == 7 and st["llm_calls"] == 0
    assert db.scalar(select(func.count()).select_from(CommentAnalysis)) == 7


def test_llm_dedupe_prefilter_cache(db):
    _load(db)
    p = MockProvider()
    st = classify_pending(db, provider=p, batch_size=2)
    # 7 comments -> 6 unique texts; greeting + spam prefiltered -> 4 to LLM in 2 batches
    assert st["unique_texts"] == 6
    assert st["prefiltered"] == 2
    assert st["llm_classified"] == 4 and st["llm_calls"] == 2
    assert db.scalar(select(func.count()).select_from(LLMCache)) == 4
    # re-run: all cached, no new calls
    st2 = classify_pending(db, provider=p, reanalyze=True)
    assert st2["cache_hits"] == 4 and st2["llm_calls"] == 0 and len(p.calls) == 2
    # new_topic proposals become candidate topics
    assert db.scalar(select(Topic).where(Topic.slug == "fasting_energy")) is not None


def test_llm_failure_falls_back(db):
    _load(db)
    st = classify_pending(db, provider=MockProvider(fail=True))
    assert st["llm_errors"] >= 1
    assert db.scalar(select(func.count()).select_from(CommentAnalysis)) == 7
    assert all(a.method == "heuristic" for a in db.scalars(select(CommentAnalysis)))


def test_diagnosis_labels_rejected():
    from app.analysis.classify import _validate
    from app.analysis.heuristic import analyze

    r = _validate({"topics": [], "new_topic": "chronic fatigue syndrome", "intent": "sharing_experience",
                   "relevance_score": 80}, analyze("tired"), "m")
    assert r.new_topic is None
