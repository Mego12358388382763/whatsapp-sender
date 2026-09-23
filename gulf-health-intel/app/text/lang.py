"""Lightweight language + dialect detection for Arabic / English / Arabizi.

Heuristic by design: zero cost and explainable. The LLM path can override it.
"""
from __future__ import annotations

import re

from .normalize import ARABIC_LETTER, LATIN_LETTER, normalize, tokens

# Arabizi: digits used as Arabic letters inside Latin words (3=ع 7=ح 2=ء 5=خ 9=ص 6=ط)
_ARABIZI_TOKEN = re.compile(r"^(?=.*[a-z])(?=.*[2356789])[a-z2356789']{2,}$")
_ARABIZI_WORDS = {
    "inshallah", "insha'allah", "wallah", "wallahi", "habibi", "habibti", "shukran",
    "yalla", "ana", "enta", "enti", "inta", "inti", "mafi", "mesh", "mish", "shlonik",
    "shlonich", "shlon", "wayed", "wayid", "zain", "zein", "abi", "abgha", "ab8a",
    "ma3", "3ala", "leh", "lesh", "laish", "keef", "kaif", "kif", "esh", "eish", "wesh",
    "shu", "shou", "7aram", "ya3ni", "yani", "tayeb", "khalas", "5alas", "3ashan",
    "3shan", "mashallah", "alhamdulillah", "hamdulillah", "akhi", "ukhti", "marra",
    "kteer", "katheer", "ta3ban", "ta3bana", "ta3b", "sa7a", "3ayez", "3ayza", "ezay",
    "eh", "keda", "delwa2ty", "awi", "gedan",
}

# Dialect marker words (normalised form). Overlaps are intentional; scores decide.
_DIALECT_MARKERS: dict[str, set[str]] = {
    "saudi": {
        "وش", "ابغى", "ابغي", "يبغى", "تبغى", "ودي", "مره", "كذا", "ترا", "ترى", "زي",
        "حق", "دحين", "الحين", "ايش", "عاد", "يعطيك", "مب", "مررره", "هالحين", "بعدين",
    },
    "gulf": {
        "شلون", "وايد", "ابي", "تبي", "يبي", "حيل", "زين", "جذي", "كذي", "شنو", "ماكو",
        "اكو", "شفيني", "شفيك", "هالشي", "الحين", "باجر", "بعد", "يالغالي", "عيل", "شكو",
        "واجد", "مب", "ليش", "دوام",
    },
    "egyptian": {
        "ازاي", "ايه", "عايز", "عايزه", "كده", "دلوقتي", "مش", "بتاع", "اوي", "خالص",
        "ليه", "بقى", "بقي", "ده", "دي", "امبارح", "النهارده", "برضو", "حاجه", "فين",
    },
    "msa": {
        "لماذا", "الذي", "التي", "سوف", "لكن", "جدا", "هل", "ايضا", "حيث", "كيف", "ماذا",
        "لدي", "اشعر", "اعاني",
    },
}


def detect_language(text: str) -> str:
    """Return one of: ar, en, mixed, arabizi, unknown."""
    ar = len(ARABIC_LETTER.findall(text or ""))
    la = len(LATIN_LETTER.findall(text or ""))
    total = ar + la
    if total < 2:
        return "unknown"
    if ar / total >= 0.7:
        return "ar"
    if la / total >= 0.7:
        return "arabizi" if is_arabizi(text) else "en"
    return "mixed"


def is_arabizi(text: str) -> bool:
    toks = tokens(text)
    latin = [t for t in toks if re.search(r"[a-z]", t)]
    if not latin:
        return False
    hits = sum(1 for t in latin if t in _ARABIZI_WORDS or _ARABIZI_TOKEN.match(t))
    return hits >= 2 or (hits >= 1 and len(latin) <= 4)


def detect_dialect(text: str) -> str:
    """Return saudi | gulf | egyptian | msa | unknown for Arabic-script text.

    For Arabizi we only distinguish gulf/egyptian coarsely.
    """
    norm = normalize(text)
    toks = set(norm.split())
    if not ARABIC_LETTER.search(norm):
        latin = set(tokens(text))
        eg = len(latin & {"3ayez", "3ayza", "ezay", "keda", "delwa2ty", "awi", "mesh", "leh"})
        gu = len(latin & {"shlonik", "shlon", "wayed", "wayid", "abi", "abgha", "zain", "wesh"})
        if eg > gu:
            return "egyptian"
        if gu:
            return "gulf"
        return "unknown"
    scores = {d: len(toks & markers) for d, markers in _DIALECT_MARKERS.items()}
    best = max(scores.values())
    if best == 0:
        return "unknown"
    # Colloquial dialect evidence beats MSA function words at a tie.
    for d in ("saudi", "gulf", "egyptian", "msa"):
        if scores[d] == best:
            if d == "saudi" and scores["gulf"] == best:
                return "gulf"
            return d
    return "unknown"
