"""Prompts and JSON schemas. Bump the *_VERSION constants when a prompt changes (it invalidates the cache)."""
from __future__ import annotations

from ...text.lexicon import INTENTS, SEED_TOPICS

CLASSIFY_VERSION = "c1"
SYNTH_VERSION = "s1"

_TOPIC_LIST = "\n".join(f"- {slug}: {en} / {ar}" for slug, (en, ar, _) in SEED_TOPICS.items())

CLASSIFY_SYSTEM = f"""You analyse PUBLIC social-media comments from Gulf health & wellness communities
(Saudi Arabia, UAE, Kuwait, Qatar, Bahrain, Oman). Comments may be in Modern Standard Arabic,
Gulf/Saudi/Egyptian Arabic, English, mixed Arabic-English, or Arabizi (Arabic in Latin letters/digits).

Your job is AUDIENCE RESEARCH about discussion themes. It is not an assessment of any person.

Strict rules:
1. NEVER diagnose. Do not name medical conditions the commenter did not literally write, and do not
   turn symptoms into diagnoses. "I'm exhausted every morning" → topic fatigue_low_energy,
   intent sharing_experience. It must NOT become "ME/CFS", "anaemia", "thyroid", etc.
2. Topics are discussion THEMES. Use these slugs when they fit:
{_TOPIC_LIST}
   If a clear recurring theme fits none of them, put a short neutral English theme label
   (2-4 words, e.g. "hair loss", "postpartum recovery", "fasting energy") in new_topic.
   Never use a diagnosis as new_topic.
3. intent is exactly one of: {", ".join(INTENTS)}.
   looking_for_practitioner = asking for a doctor/clinic/coach/service recommendation.
   worked / did_not_work = reports that a remedy or approach helped / did not help.
4. relevance_score (0-100) measures how useful the COMMENT is for understanding audience needs:
   clarity of the problem, question intent, depth, health/wellness relevance, and suitability for
   educational content or a general wellness self-assessment. Greetings, praise, tagging friends,
   spam and promotions score under 10.
5. question: if the comment asks something, restate the question briefly in its original language
   WITHOUT any names, handles, or identifying details. Otherwise null.
6. key_phrases: up to 5 short natural phrases the commenter used to describe the problem, copied
   verbatim in the original language (no names, handles or numbers).
7. Never output names, usernames, phone numbers, or locations more specific than a city.
Return one item per input id."""

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "topics": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"slug": {"type": "string"}, "confidence": {"type": "number"}},
                            "required": ["slug", "confidence"],
                        },
                    },
                    "new_topic": {"type": ["string", "null"]},
                    "intent": {"type": "string", "enum": INTENTS},
                    "intent_confidence": {"type": "number"},
                    "relevance_score": {"type": "integer"},
                    "is_question": {"type": "boolean"},
                    "question": {"type": ["string", "null"]},
                    "language": {"type": "string", "enum": ["ar", "en", "mixed", "arabizi", "other"]},
                    "dialect": {"type": "string",
                                "enum": ["saudi", "gulf", "egyptian", "levantine", "msa", "unknown"]},
                    "key_phrases": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "topics", "intent", "intent_confidence", "relevance_score", "is_question",
                             "language", "dialect"],
            },
        }
    },
    "required": ["items"],
}

SYNTH_SYSTEM = """You are a health-education content strategist for Gulf audiences (Arabic and English).
You receive ANONYMISED, aggregated discussion patterns: themes, counts, typical questions and the
natural phrases people use. Produce educational, non-diagnostic, culturally appropriate ideas.
Rules: no medical claims or cures, no diagnosis, no fear-based messaging, and no reference to any
individual. Encourage professional advice where appropriate. Write in the language mix the
phrases show (Arabic ideas in Gulf-friendly Arabic, and English where English dominates)."""

CONTENT_SCHEMA = {
    "type": "object",
    "properties": {
        k: {"type": "array", "items": {"type": "string"}}
        for k in ("reels", "hooks", "faqs", "carousels", "articles", "lead_magnets", "scorecards")
    },
    "required": ["reels", "hooks", "faqs", "carousels", "articles", "lead_magnets", "scorecards"],
}

SCORECARD_SCHEMA = {
    "type": "object",
    "properties": {
        "suggested_scorecard": {"type": "string"},
        "hook": {"type": "string"},
        "cta": {"type": "string"},
    },
    "required": ["suggested_scorecard", "hook", "cta"],
}
