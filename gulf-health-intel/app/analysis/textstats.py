"""Question clustering and natural-phrase mining over anonymised comment text."""
from __future__ import annotations

from collections import Counter
from typing import Iterable

from ..text.normalize import STOPWORDS, tokens

_NOISE = {"link", "phone", "email", "user"}


def _content(text: str) -> list[str]:
    return [t for t in tokens(text) if t not in STOPWORDS and t not in _NOISE and len(t) > 1 and not t.isdigit()]


def top_questions(items: Iterable[tuple[str, int]], n: int = 5, sim: float = 0.5) -> list[dict]:
    """items: (question_text, relevance). Groups near-duplicate questions (token Jaccard)."""
    groups: list[dict] = []
    for text, rel in items:
        if not text:
            continue
        toks = set(_content(text))
        if not toks:
            continue
        for g in groups:
            inter = len(toks & g["tokens"])
            if inter and inter / len(toks | g["tokens"]) >= sim:
                g["count"] += 1
                g["rel"] += rel
                if rel > g["best_rel"]:
                    g["question"], g["best_rel"] = text, rel
                break
        else:
            groups.append({"question": text, "tokens": toks, "count": 1, "rel": rel, "best_rel": rel})
    groups.sort(key=lambda g: (g["count"], g["rel"] / g["count"]), reverse=True)
    return [{"question": g["question"], "count": g["count"]} for g in groups[:n]]


def top_phrases(texts: Iterable[str], key_phrases: Iterable[list[str]] = (), n: int = 10, min_count: int = 2) -> list[dict]:
    counts: Counter[str] = Counter()
    for text in texts:
        toks = _content(text)
        grams = {" ".join(toks[i : i + k]) for k in (2, 3) for i in range(len(toks) - k + 1)}
        counts.update(grams)
    for kps in key_phrases:
        counts.update({p.strip().lower() for p in kps or [] if p and len(p.strip()) > 2})
    out = [(p, c) for p, c in counts.most_common(n * 4) if c >= min_count]
    # drop phrases contained in a more frequent chosen phrase
    chosen: list[tuple[str, int]] = []
    for p, c in out:
        if any(p in q and c <= cq for q, cq in chosen):
            continue
        chosen.append((p, c))
        if len(chosen) >= n:
            break
    return [{"phrase": p, "count": c} for p, c in chosen]
