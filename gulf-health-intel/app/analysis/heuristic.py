"""Zero-cost bilingual heuristic classifier.

Used (a) as the prefilter before the LLM and (b) as the full classifier when no
LLM provider is configured. It outputs discussion *themes* and *intent*, never
a diagnosis.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from functools import lru_cache

from ..text.lang import detect_dialect, detect_language
from ..text.lexicon import (
    INTENT_KEYWORDS,
    QUESTION_WORDS_AR,
    QUESTION_WORDS_EN,
    SEED_TOPICS,
    SPAM_MARKERS,
    WEAK_TOPICS,
)
from ..text.normalize import ARABIC_LETTER, normalize

_AR = "ء-ي"
_AR_SUFFIX = r"(?:ي|ه|ها|ك|كم|نا|هم|ت|تي|ان|انه|ات|ين|و|وا)?"
_DURATION = re.compile(
    r"(for (years|months|weeks)|since|من (سنه|سنين|شهور|شهر|فتره|زمان)|صار ?لي|every (day|morning|night)|كل (يوم|صباح|ليله))"
)


def _pattern(keyword: str) -> str:
    kw = normalize(keyword)
    esc = re.escape(kw)
    if ARABIC_LETTER.search(kw):
        prefix = rf"(?<![{_AR}])(?:[وفبلك]?(?:ال)?|لل)?"
        if len(kw.replace(" ", "")) <= 3:
            return prefix + esc + _AR_SUFFIX + rf"(?![{_AR}])"
        return prefix + esc
    tail = r"[a-z]*" if len(kw) >= 5 else ""
    return rf"(?<![a-z0-9]){esc}{tail}(?![a-z0-9])"


@lru_cache(maxsize=None)
def _compiled(group: str, key: str) -> re.Pattern:
    kws = SEED_TOPICS[key][2] if group == "topic" else INTENT_KEYWORDS[key]
    return re.compile("|".join(_pattern(k) for k in sorted(set(kws), key=len, reverse=True)))


_SPAM = re.compile("|".join(re.escape(normalize(s)) for s in SPAM_MARKERS))


@dataclass
class HeuristicResult:
    topics: list[tuple[str, float]] = field(default_factory=list)
    primary_topic: str | None = None
    intent: str = "not_relevant"
    intent_confidence: float = 0.5
    relevance_score: int = 0
    is_question: bool = False
    question_text: str | None = None
    language: str = "unknown"
    dialect: str = "unknown"
    key_phrases: list[str] = field(default_factory=list)
    is_spam: bool = False

    @property
    def health_signal(self) -> bool:
        return any(s not in WEAK_TOPICS for s, _ in self.topics) or self.intent == "looking_for_practitioner"

    @property
    def needs_llm(self) -> bool:
        """Obvious noise is settled here and never sent to the (paid) LLM."""
        if self.is_spam:
            return False
        return bool(self.topics) or self.is_question or self.intent in {
            "sharing_experience", "did_not_work", "asking_for_help", "looking_for_practitioner"}


def _is_question(norm: str) -> bool:
    if "?" in norm:
        return True
    words = norm.split()
    if not words:
        return False
    if words[0] in QUESTION_WORDS_EN or words[0] in QUESTION_WORDS_AR:
        return True
    return bool(set(words) & {"هل", "كيف", "ليش", "شلون", "ازاي", "ليه", "وش", "ايش", "anyone", "anybody"})


def _question_text(original: str) -> str:
    parts = re.split(r"(?<=[?؟.!\n])\s+", original.strip())
    q = next((p for p in parts if "?" in p or "؟" in p), original.strip())
    return q[:220]


def analyze(text: str, like_count: int | None = None) -> HeuristicResult:
    norm = normalize(text)
    res = HeuristicResult(language=detect_language(text))
    if res.language in ("ar", "mixed", "arabizi"):
        res.dialect = detect_dialect(text)
    if not norm:
        return res

    # Topics
    phrases: list[str] = []
    for slug in SEED_TOPICS:
        found = _compiled("topic", slug).findall(norm)
        if found:
            conf = min(0.95, 0.6 + 0.12 * (len(found) - 1))
            res.topics.append((slug, round(conf, 2)))
            phrases.extend(f.strip() for f in found)
    strong = [t for t in res.topics if t[0] not in WEAK_TOPICS]
    ranked = sorted(res.topics, key=lambda t: (t[0] not in WEAK_TOPICS, t[1]), reverse=True)
    res.topics = [(s, c if s not in WEAK_TOPICS or not strong else round(c * 0.8, 2)) for s, c in ranked]
    res.primary_topic = ranked[0][0] if ranked else None

    # Intent: match negated/positive outcome phrases first and blank them so
    # "didn't help" is not also counted as a request for help.
    work = norm
    hits: dict[str, int] = {}
    for intent in ("did_not_work", "worked", "looking_for_practitioner", "asking_for_help",
                   "looking_for_information", "sharing_experience", "general_conversation"):
        pat = _compiled("intent", intent)
        found = pat.findall(work)
        hits[intent] = len(found)
        if found and intent in ("did_not_work", "worked"):
            work = pat.sub(" ", work)
            phrases.extend(f.strip() for f in found)

    res.is_question = _is_question(norm)
    res.is_spam = bool(_SPAM.search(norm)) and not strong
    has_topic = bool(res.topics)

    if res.is_spam:
        intent, conf = "not_relevant", 0.8
    elif hits["looking_for_practitioner"] and (has_topic or res.is_question):
        intent, conf = "looking_for_practitioner", 0.8
    elif hits["asking_for_help"] and (has_topic or res.is_question):
        intent, conf = "asking_for_help", 0.8
    elif hits["did_not_work"]:
        intent, conf = "did_not_work", 0.8
    elif hits["worked"] and has_topic:
        intent, conf = "worked", 0.75
    elif res.is_question and hits["looking_for_information"]:
        intent, conf = "looking_for_information", 0.75
    elif res.is_question and (has_topic or len(norm.split()) >= 4):
        intent, conf = "asking_question", 0.75 if has_topic else 0.55
    elif hits["sharing_experience"] and (has_topic or len(norm.split()) >= 4):
        # without a known topic this may be a new theme: keep it (low confidence) for discovery
        intent, conf = "sharing_experience", 0.75 if has_topic else 0.45
    elif strong:
        intent, conf = "sharing_experience", 0.55
    elif hits["general_conversation"] or has_topic or len(norm.split()) <= 3:
        intent, conf = "general_conversation", 0.6
    else:
        intent, conf = "not_relevant", 0.5
    res.intent, res.intent_confidence = intent, conf

    if res.is_question and intent != "not_relevant":
        res.question_text = _question_text(text)

    res.relevance_score = relevance_score(res, norm, like_count)
    seen: list[str] = []
    for p in phrases:
        if p and p not in seen:
            seen.append(p)
    res.key_phrases = seen[:8]
    return res


INTENT_WEIGHT = {
    "asking_for_help": 25,
    "looking_for_practitioner": 22,
    "asking_question": 22,
    "did_not_work": 20,
    "sharing_experience": 18,
    "looking_for_information": 18,
    "worked": 18,
    "general_conversation": 3,
    "not_relevant": 0,
}


def relevance_score(res: HeuristicResult, norm: str, like_count: int | None) -> int:
    """How useful is this *comment* for understanding the audience (0-100)."""
    if res.is_spam:
        return 0
    strong = [t for t in res.topics if t[0] not in WEAK_TOPICS]
    score = 0.0
    if strong:
        score += 35 + min(10, 5 * (len(strong) - 1))
    elif res.topics:
        score += 20
    score += INTENT_WEIGHT.get(res.intent, 0)
    words = len(norm.split())
    score += 0 if words < 3 else 5 if words < 8 else 12 if words <= 25 else 16
    if _DURATION.search(norm):
        score += 6  # describes pattern/duration -> clearer problem statement
    if like_count:
        score += min(6, 2 * math.log10(1 + like_count))
    if not res.topics:
        score = min(score, 30 if res.is_question else 15)
    return int(max(0, min(100, round(score))))
