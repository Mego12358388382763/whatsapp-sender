"""Content intelligence: ideas generated from aggregated, anonymised discussion patterns.

The heuristic generator fills educational templates with the audience's own
recurring phrases and questions. With an LLM provider, the stronger model
writes the ideas from the same anonymised summary. No individual comment is
attributed.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import ContentIdea, LLMCache, Topic, utcnow
from .aggregate import load_rows
from .llm.base import LLMError, LLMProvider
from .llm.prompts import CONTENT_SCHEMA, SYNTH_SYSTEM, SYNTH_VERSION
from .textstats import top_phrases, top_questions

KINDS = {"reels": "reel", "hooks": "hook", "faqs": "faq", "carousels": "carousel", "articles": "article",
         "lead_magnets": "lead_magnet", "scorecards": "scorecard"}

# topic slug -> (English noun phrase, Arabic noun phrase)
NOUNS = {
    "fatigue_low_energy": ("energy", "الطاقة"), "sleep_problems": ("sleep", "النوم"),
    "chronic_pain": ("everyday aches", "الآلام اليومية"), "muscle_pain": ("muscle aches", "آلام العضلات"),
    "joint_pain": ("back & joint comfort", "راحة الظهر والمفاصل"), "brain_fog": ("focus", "التركيز"),
    "digestive": ("digestion", "الهضم"), "ibs": ("gut comfort", "راحة القولون"), "stress": ("stress", "التوتر"),
    "burnout": ("burnout", "الاحتراق النفسي"), "anxiety": ("worry & overthinking", "القلق والتفكير الزائد"),
    "mobility": ("mobility", "الحركة والمرونة"), "headaches": ("headaches", "الصداع"),
    "nutrition": ("nutrition", "التغذية"), "exercise": ("exercise", "الرياضة"), "recovery": ("recovery", "الاستشفاء"),
    "work_stress": ("work stress", "ضغط الدوام"), "weight_management": ("weight", "الوزن"),
    "general_wellness": ("wellbeing", "الصحة العامة"),
}


def _templates(noun: str, noun_ar: str, phrases: list[str], questions: list[str]) -> dict[str, list[str]]:
    p = (phrases + [noun] * 3)[:3]
    reels = [
        f"3 everyday habits that quietly affect your {noun}",
        f'"{p[0]}": what people in the Gulf say most, and what to look at first',
        f"Morning vs evening routine: small changes that support {noun}",
        f"Myth vs fact: common beliefs about {noun}",
        f"Ramadan & summer heat: adjusting routines for better {noun}",
        f"What a professional usually asks about {noun} (and why)",
        f"5 questions to ask yourself before trying another quick fix for {noun}",
        f"Day-in-the-life: an office worker's routine and {noun}",
        f'Answering your most asked question: "{questions[0] if questions else f"why is my {noun} like this?"}"',
        f"{noun_ar}: 3 عادات يومية تستاهل تنتبه لها",
    ]
    hooks = [
        f'"{p[0]}"? You\'re not the only one. Here\'s what often sits behind it.',
        f"If {noun} feels harder than it should, this is for you.",
        f"Nobody talks about how routine shapes {noun}.",
        f"Before you try another supplement for {noun}, watch this.",
        f"The #1 question we see about {noun} in Gulf communities…",
        f'"{p[1]}": let\'s talk about it.',
        f"3 signs your lifestyle may be affecting your {noun}.",
        f"Stop guessing about {noun}. Start noticing these patterns.",
        f"كثير يقولون \"{p[2]}\"… خلنا نفهم الموضوع",
        f"وش علاقة روتينك اليومي بـ{noun_ar}؟",
    ]
    faqs = questions[:10] or [f"What affects {noun} day to day?", f"When should I speak to a professional about {noun}?"]
    carousels = [
        f"The {noun} checklist: 7 lifestyle areas to review",
        f"What people say vs what it can mean: decoding common {noun} complaints (educational)",
        f"A 7-day {noun} habit tracker",
        f"Top 5 questions about {noun} from our community, answered",
        f"{noun_ar}: خطوات بسيطة تبدأ فيها اليوم",
    ]
    articles = [
        f"A practical guide to {noun} for busy professionals in the Gulf",
        f"How heat, fasting and late nights can affect {noun}",
        f"The lifestyle factors most often linked to {noun}",
        f"When to seek professional advice about {noun}",
        f"What worked and what didn't: common approaches to {noun} people discuss",
    ]
    lead_magnets = [
        f"Free {noun} habit tracker (PDF, Arabic/English)",
        f"7-day {noun} reset guide",
        f"{noun.capitalize()} questions checklist to bring to your practitioner",
        f"Mini e-course: understanding your {noun} patterns",
        f"دليل مجاني: {noun_ar} في 7 أيام",
    ]
    scorecards = [
        f"3-minute {noun} scorecard",
        f"{noun.capitalize()} & lifestyle balance assessment",
        f"Which habits affect your {noun} most? Free self-check",
    ]
    return {"reels": reels, "hooks": hooks, "faqs": faqs, "carousels": carousels, "articles": articles,
            "lead_magnets": lead_magnets, "scorecards": scorecards}


def _llm_ideas(provider: LLMProvider, s: Session, summary: dict) -> dict | None:
    user = ("Generate for this theme: 10 reels, 10 hooks, FAQ topics, 5 carousels, 5 articles, "
            "5 lead magnets, 3 scorecard ideas.\n" + json.dumps(summary, ensure_ascii=False))
    key = hashlib.sha256(f"{provider.name}|{provider.strong_model}|{SYNTH_VERSION}|ci|{user}".encode()).hexdigest()
    if cached := s.get(LLMCache, key):
        return cached.response
    try:
        out = provider.complete_json(SYNTH_SYSTEM, user, CONTENT_SCHEMA, model=provider.strong_model, max_tokens=4000)
    except LLMError:
        return None
    s.merge(LLMCache(key=key, response=out))
    return out


def generate_content_ideas(s: Session, threshold: int = 40, top_n: int = 8, provider: LLMProvider | None = None) -> int:
    s.execute(delete(ContentIdea))
    topics = {t.id: t for t in s.scalars(select(Topic))}
    rel = [r for r in load_rows(s) if r.relevance >= threshold]
    counts = Counter(r.primary_topic for r in rel if r.primary_topic)
    created = 0
    for tid, n in counts.most_common(top_n):
        t = topics[tid]
        members = [r for r in rel if r.primary_topic == tid]
        qs = [q["question"] for q in top_questions([(r.question or r.text, r.relevance) for r in members if r.is_question], n=10)]
        phrases = [p["phrase"] for p in top_phrases([r.text for r in members], [r.key_phrases for r in members], n=10)]
        ideas, method = None, "heuristic"
        if provider is not None:
            langs = Counter(r.language for r in members)
            ideas = _llm_ideas(provider, s, {"theme": t.name_en, "theme_ar": t.name_ar, "discussion_count": n,
                                             "typical_questions": qs, "natural_phrases": phrases,
                                             "language_mix": dict(langs)})
            method = "llm" if ideas else method
        if not ideas:
            noun, noun_ar = NOUNS.get(t.slug, (t.name_en.lower(), t.name_ar or t.name_en))
            ideas = _templates(noun, noun_ar, phrases, qs)
        for key, kind in KINDS.items():
            for text in (ideas.get(key) or [])[:10]:
                s.add(ContentIdea(topic_id=tid, kind=kind, text=str(text)[:500], method=method, generated_at=utcnow()))
                created += 1
    s.flush()
    return created
