"""Scorecard opportunity detection from aggregated topic clusters (per country and overall)."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import LLMCache, ScorecardOpportunity, Topic, utcnow
from .aggregate import NEED_INTENTS, community_country, load_rows
from .llm.base import LLMError, LLMProvider
from .llm.prompts import SCORECARD_SCHEMA, SYNTH_SYSTEM, SYNTH_VERSION
from .textstats import top_phrases, top_questions

# core topics trigger the template; support topics enrich the cluster name
TEMPLATES = [
    {
        "key": "energy", "name": "Energy & Fatigue Scorecard",
        "title": "3-Minute Energy & Recovery Assessment",
        "core": ["fatigue_low_energy", "brain_fog"],
        "support": ["sleep_problems", "stress", "nutrition", "work_stress", "recovery"],
        "hook": "Your energy isn't controlled by one thing. See which areas of your lifestyle may deserve more attention.",
        "cta": "Take the free 3-minute assessment.",
    },
    {
        "key": "stress", "name": "Stress & Burnout Scorecard",
        "title": "5-Minute Stress & Burnout Check-In",
        "core": ["stress", "burnout", "work_stress", "anxiety"],
        "support": ["sleep_problems", "fatigue_low_energy", "headaches"],
        "hook": "Feeling stretched thin isn't a personal failing. See which everyday pressures may be adding up.",
        "cta": "Get your free stress balance score.",
    },
    {
        "key": "sleep", "name": "Sleep & Recovery Scorecard",
        "title": "Sleep & Recovery Scorecard",
        "core": ["sleep_problems", "recovery"],
        "support": ["fatigue_low_energy", "stress", "anxiety", "exercise"],
        "hook": "Good sleep is built across the whole day, not only at bedtime. Find out which habits may be helping or hurting yours.",
        "cta": "Check your sleep & recovery score in 3 minutes.",
    },
    {
        "key": "digestive", "name": "Digestive Wellness Scorecard",
        "title": "Gut & Digestive Wellness Check",
        "core": ["digestive", "ibs"],
        "support": ["nutrition", "stress", "fatigue_low_energy"],
        "hook": "Bloating and digestive discomfort are often linked to routine, food timing and stress. See which areas stand out for you.",
        "cta": "Take the free digestive wellness check.",
    },
    {
        "key": "pain", "name": "Pain & Mobility Scorecard",
        "title": "Move Better: Pain & Mobility Self-Check",
        "core": ["chronic_pain", "muscle_pain", "joint_pain", "mobility", "headaches"],
        "support": ["exercise", "recovery", "sleep_problems", "work_stress"],
        "hook": "Daily aches often connect to posture, movement, recovery and sleep. See which of these areas may need attention.",
        "cta": "Start the 3-minute mobility self-check.",
    },
    {
        "key": "lifestyle", "name": "Lifestyle Balance Scorecard",
        "title": "Lifestyle Balance Scorecard",
        "core": ["nutrition", "exercise", "weight_management", "general_wellness"],
        "support": ["sleep_problems", "recovery", "stress"],
        "hook": "Small, consistent habits add up. See how balanced your nutrition, movement, sleep and stress really are.",
        "cta": "Get your lifestyle balance score.",
    },
]
HEALTH_360 = {
    "key": "health360", "name": "Health 360 Scorecard", "title": "Health 360: Whole-Lifestyle Scorecard",
    "hook": "Energy, sleep, stress, digestion and movement are all connected. See your whole picture in one place.",
    "cta": "Take the free Health 360 assessment.",
}


def _volume_label(count: int, total: int) -> str:
    if count >= max(30, 0.15 * total):
        return "High"
    if count >= max(10, 0.05 * total):
        return "Medium"
    return "Low"


def _refine(provider: LLMProvider, s: Session, tpl: dict, cluster: str, questions: list, phrases: list) -> dict | None:
    summary = {"scorecard_theme": tpl["name"], "problem_cluster": cluster,
               "typical_questions": [q["question"] for q in questions], "natural_phrases": [p["phrase"] for p in phrases]}
    user = ("Write a scorecard title, an educational hook (1-2 sentences, non-diagnostic, no promises) and a CTA "
            "for this anonymised discussion cluster:\n" + json.dumps(summary, ensure_ascii=False))
    key = hashlib.sha256(f"{provider.name}|{provider.strong_model}|{SYNTH_VERSION}|sc|{user}".encode()).hexdigest()
    if cached := s.get(LLMCache, key):
        return cached.response
    try:
        out = provider.complete_json(SYNTH_SYSTEM, user, SCORECARD_SCHEMA, model=provider.strong_model, max_tokens=600)
    except LLMError:
        return None
    s.merge(LLMCache(key=key, response=out))
    return out


def build_scorecards(s: Session, threshold: int = 40, min_count: int = 3, provider: LLMProvider | None = None) -> int:
    s.execute(delete(ScorecardOpportunity))
    slug_by_id = {t.id: t.slug for t in s.scalars(select(Topic))}
    name_by_slug = {t.slug: t.name_en for t in s.scalars(select(Topic))}
    countries = community_country(s)
    rel = [r for r in load_rows(s) if r.relevance >= threshold]
    scopes: dict[str | None, list] = {None: rel}
    for r in rel:
        if c := countries.get(r.community_id):
            scopes.setdefault(c, []).append(r)

    created = 0
    for country, rows in scopes.items():
        total = len(rows)
        found = []
        for tpl in TEMPLATES:
            core, allowed = set(tpl["core"]), set(tpl["core"]) | set(tpl["support"])
            members = [r for r in rows if core & {slug_by_id.get(t) for t in r.topics}]
            if len(members) < min_count:
                continue
            co = Counter(sl for r in members for sl in {slug_by_id.get(t) for t in r.topics} if sl in allowed)
            cluster_slugs = [sl for sl, _ in co.most_common(3)]
            multi = sum(1 for r in members if len({slug_by_id.get(t) for t in r.topics} & allowed) >= 2) / len(members)
            need = sum(1 for r in members if r.intent in NEED_INTENTS) / len(members)
            found.append((tpl, members, cluster_slugs, multi, need))
        max_count = max([len(f[1]) for f in found] or [1])
        scored = []
        for tpl, members, cluster_slugs, multi, need in found:
            volume = math.log10(1 + len(members)) / math.log10(1 + max_count)
            scored.append((tpl, members, cluster_slugs, round(50 * volume + 30 * need + 20 * multi)))
        if len(found) >= 4:
            # Health 360 fits when discussion is spread across many themes: score = average of
            # the top-3 theme scores scaled by how evenly volume is spread (normalised entropy).
            sizes = [len(f[1]) for f in found]
            tot = sum(sizes)
            spread = -sum(n / tot * math.log(n / tot) for n in sizes) / math.log(len(sizes))
            top3 = sorted((x[3] for x in scored), reverse=True)[:3]
            cluster = [f[2][0] for f in sorted(found, key=lambda f: -len(f[1]))[:4]]
            scored.append((HEALTH_360, rows, cluster, round(sum(top3) / 3 * spread)))
        for tpl, members, cluster_slugs, score in scored:
            core = set(tpl.get("core", []))
            focused = [r for r in members if slug_by_id.get(r.primary_topic) in core] or members
            questions = top_questions([(r.question or r.text, r.relevance) for r in focused if r.is_question], n=5)
            cluster = " + ".join(name_by_slug.get(sl, sl) for sl in cluster_slugs)
            title, hook, cta, method = tpl["title"], tpl["hook"], tpl["cta"], "heuristic"
            if provider is not None:
                phrases = top_phrases([r.text for r in members], [r.key_phrases for r in members], n=8)
                if ref := _refine(provider, s, tpl, cluster, questions, phrases):
                    title, hook, cta, method = ref["suggested_scorecard"], ref["hook"], ref["cta"], "llm"
            s.add(ScorecardOpportunity(
                key=tpl["key"], country=country, problem_cluster=cluster, topics=cluster_slugs,
                discussion_count=len(members), volume_label=_volume_label(len(members), total),
                typical_questions=questions, suggested_scorecard=title, hook=hook, cta=cta,
                score=score, method=method, generated_at=utcnow(),
            ))
            created += 1
    s.flush()
    return created
