"""Natural search such as "fatigue Saudi Arabia", "burnout Riyadh" or "gut health Dubai".

The query is parsed into topics, a country, a city and free-text terms. Results
are aggregated to communities and posts. Matching comments are shown without
identity.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from .analysis.aggregate import load_rows
from .analysis.heuristic import analyze
from .analysis.textstats import top_questions
from .models import Community, Post, Topic
from .text.lexicon import TOPIC_ALIASES
from .text.normalize import STOPWORDS, normalize

COUNTRY_TERMS = {
    "SA": ["saudi arabia", "saudi", "ksa", "السعوديه", "المملكه"],
    "AE": ["united arab emirates", "uae", "emirates", "الامارات"],
    "KW": ["kuwait", "الكويت"],
    "QA": ["qatar", "قطر"],
    "BH": ["bahrain", "البحرين"],
    "OM": ["oman", "سلطنه عمان"],
}
CITY_TERMS = {
    "Riyadh": ("SA", ["riyadh", "الرياض"]), "Jeddah": ("SA", ["jeddah", "jedda", "جده"]),
    "Dammam": ("SA", ["dammam", "الدمام"]), "Khobar": ("SA", ["khobar", "الخبر"]),
    "Makkah": ("SA", ["makkah", "mecca", "مكه"]), "Madinah": ("SA", ["madinah", "medina", "المدينه"]),
    "Dubai": ("AE", ["dubai", "دبي"]), "Abu Dhabi": ("AE", ["abu dhabi", "ابوظبي", "ابو ظبي"]),
    "Sharjah": ("AE", ["sharjah", "الشارقه"]), "Doha": ("QA", ["doha", "الدوحه"]),
    "Manama": ("BH", ["manama", "المنامه"]), "Muscat": ("OM", ["muscat", "مسقط"]),
    "Kuwait City": ("KW", ["kuwait city"]),
}


def parse_query(q: str) -> dict:
    text = f" {normalize(q)} "
    out: dict = {"topics": [], "country": None, "city": None, "city_terms": [], "terms": []}

    def take(term: str) -> bool:
        nonlocal text
        pat = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)")
        if pat.search(text):
            text = pat.sub(" ", text)
            return True
        return False

    for city, (cc, terms) in CITY_TERMS.items():
        if any(take(t) for t in terms):
            out["city"], out["country"], out["city_terms"] = city, cc, terms
            break
    for cc, terms in COUNTRY_TERMS.items():
        if any(take(t) for t in terms):
            out["country"] = out["country"] or cc
    for alias in sorted(TOPIC_ALIASES, key=len, reverse=True):
        if take(alias) and TOPIC_ALIASES[alias] not in out["topics"]:
            out["topics"].append(TOPIC_ALIASES[alias])
    rest = text.strip()
    for slug, _ in analyze(rest).topics if rest else []:
        if slug not in out["topics"]:
            out["topics"].append(slug)
            rest = ""
    out["terms"] = [w for w in rest.split() if w not in STOPWORDS and w not in {"problems", "problem", "issues", "مشاكل"}]
    return out


def search(s: Session, q: str, threshold: int = 40, limit: int = 20) -> dict:
    parsed = parse_query(q)
    topics = {t.id: t for t in s.scalars(select(Topic))}
    want = {t.id for t in topics.values() if t.slug in parsed["topics"]}
    comms = {c.id: c for c in s.scalars(select(Community))}
    posts = {p.id: p for p in s.scalars(select(Post))}

    rows = [r for r in load_rows(s) if r.relevance >= threshold]
    if want:
        rows = [r for r in rows if r.topics & want]
    if parsed["country"]:
        rows = [r for r in rows if comms[r.community_id].country == parsed["country"]]
    note = None
    if parsed["city"]:
        city_rows = [r for r in rows if (comms[r.community_id].city or "").lower() == parsed["city"].lower()
                     or any(t in normalize(r.text) for t in parsed["city_terms"])]
        if city_rows:
            rows = city_rows
        else:
            note = f"No communities tagged or comments mentioning {parsed['city']}; showing {parsed['country']} results."
    if parsed["terms"]:
        rows = [r for r in rows if all(t in normalize(r.text) for t in parsed["terms"])]

    by_comm, by_post = defaultdict(list), defaultdict(list)
    for r in rows:
        by_comm[r.community_id].append(r)
        by_post[r.post_id].append(r)
    trend: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        if r.published_at:
            for t in (r.topics & want) if want else ({r.primary_topic} if r.primary_topic else set()):
                trend[topics[t].name_en][r.published_at.strftime("%Y-%m")] += 1
    intents = Counter(r.intent for r in rows)

    def _topics(rs):
        c = Counter(r.primary_topic for r in rs if r.primary_topic)
        return [topics[t].name_en for t, _ in c.most_common(3)]

    return {
        "query": q, "parsed": {k: v for k, v in parsed.items() if k != "city_terms"}, "note": note,
        "discussion_volume": len(rows),
        "communities": sorted(({
            "id": cid, "name": comms[cid].name, "platform": comms[cid].platform, "country": comms[cid].country,
            "url": comms[cid].url, "relevant_discussions": len(rs), "top_topics": _topics(rs),
        } for cid, rs in by_comm.items()), key=lambda x: -x["relevant_discussions"])[:limit],
        "posts": sorted(({
            "id": pid, "url": posts[pid].url, "title": posts[pid].title or (posts[pid].text or "")[:100],
            "platform": posts[pid].platform, "community": comms[posts[pid].community_id].name,
            "relevant_discussions": len(rs), "top_topics": _topics(rs),
        } for pid, rs in by_post.items()), key=lambda x: -x["relevant_discussions"])[:limit],
        "common_questions": top_questions([(r.question or r.text, r.relevance) for r in rows if r.is_question], n=10),
        "intents": dict(intents.most_common()),
        "topic_trends": {k: dict(sorted(v.items())) for k, v in trend.items()},
        "sample_comments": [{"text": r.text, "relevance": r.relevance, "intent": r.intent,
                             "post_url": posts[r.post_id].url}
                            for r in sorted(rows, key=lambda r: -r.relevance)[:10]],
    }
