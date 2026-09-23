"""One-call orchestration: classify → discover topics → aggregate → scorecards → content ideas."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..config import settings
from .aggregate import compute_all
from .classify import classify_pending
from .content import generate_content_ideas
from .llm.base import LLMProvider, get_provider
from .scorecard import build_scorecards
from .topics import discover_topics


def run_analysis(s: Session, provider: LLMProvider | None = "default", reanalyze: bool = False,  # type: ignore[assignment]
                 synthesize: bool = True) -> dict:
    if provider == "default":
        provider = get_provider()
    thr = settings.relevance_threshold
    out = {"classification": classify_pending(s, provider, reanalyze=reanalyze, batch_size=settings.llm_batch_size)}
    out["discovered_topics"] = [t.name_en for t in discover_topics(s)]
    out["aggregate"] = compute_all(s, threshold=thr)
    synth = provider if synthesize else None
    out["scorecards"] = build_scorecards(s, threshold=thr, provider=synth)
    out["content_ideas"] = generate_content_ideas(s, threshold=thr, provider=synth)
    out["llm_provider"] = provider.name if provider else "none (heuristic)"
    s.commit()
    return out
