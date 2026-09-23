"""Reply queue: find public questions worth answering and draft helpful replies.

Design rules:
* The queue points at a comment on a post. It never stores or shows who wrote it.
* The tool only DRAFTS. A person reviews, edits and posts each reply by hand on
  the platform, which keeps the account within platform rules.
* Replies help first and link second, never diagnose, and vary their wording.
"""
from __future__ import annotations

import hashlib
import json
import random
from datetime import timedelta
from urllib.parse import urlencode

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Comment, CommentAnalysis, LLMCache, Post, ReplyQueueItem, Topic, utcnow
from .scorecards import scorecard_for_topic

REPLY_INTENTS = {"asking_for_help", "asking_question", "looking_for_information", "looking_for_practitioner",
                 "did_not_work"}
REPLY_PROMPT_VERSION = "r1"


def scorecard_link(key: str, lang: str, platform: str) -> str:
    q = urlencode({"lang": lang, "utm_source": platform, "utm_campaign": f"reply_{key}"})
    return f"{settings.public_base_url}/s/{key}?{q}"


def _group(language: str | None, dialect: str | None) -> str:
    if language in ("en",):
        return "en"
    if dialect == "egyptian":
        return "eg"
    if language in ("ar", "mixed", "arabizi"):
        return "gulf"
    return "en"


OPENERS = {
    "gulf": ["سؤالك في محله 🌿", "كثير يمرون بنفس الشي، ولست لحالك 🤍", "الله يعطيك العافية، سؤال مهم",
             "تسلم على السؤال، وهذا شي يتكرر كثير", "أتفهمك، والموضوع يستاهل نفهمه صح"],
    "eg": ["سؤال مهم جداً 🌿", "كتير بيمروا بنفس الحاجة، مش لوحدك 🤍", "ربنا يديك الصحة، سؤالك في محله"],
    "en": ["Great question 🌿", "You're definitely not alone in this 🤍", "Really common question, and an important one",
           "Thanks for asking this, so many people feel the same"],
}

INSIGHTS = {
    "energy": {
        "gulf": ["التعب المستمر له أسباب كثيرة، أشهرها النوم وتوقيت الأكل وشرب الماء والضغط اليومي.",
                 "الطاقة ما تعتمد على شي واحد، النوم والأكل والحركة والضغط كلها تأثر مع بعض."],
        "eg": ["التعب المستمر ليه أسباب كتير، أشهرها النوم ومواعيد الأكل والمية والضغط.",
               "الطاقة مش بتعتمد على حاجة واحدة، النوم والأكل والحركة والضغط كلهم بيأثروا."],
        "en": ["Ongoing tiredness can have many causes: sleep, meal timing, hydration and daily stress are the usual suspects.",
               "Energy rarely depends on just one thing. Sleep, food, movement and stress all interact."],
    },
    "sleep": {
        "gulf": ["النوم يتأثر بروتين اليوم كله: وقت القهوة، الشاشات، ضوء الصباح، والتوتر.",
                 "تثبيت وقت النوم والصحيان وتقليل الشاشات قبل النوم من أكثر الأشياء اللي تفرق."],
        "eg": ["النوم بيتأثر بروتين اليوم كله: القهوة، الموبايل، نور الصبح، والتوتر.",
               "تثبيت مواعيد النوم والصحيان وتقليل الموبايل قبل النوم بيفرق جداً."],
        "en": ["Sleep is shaped by the whole day: caffeine timing, screens, morning light and stress all play a part.",
               "Consistent sleep/wake times and fewer screens before bed are two of the most helpful changes."],
    },
    "stress": {
        "gulf": ["الضغط المتراكم يأثر على النوم والطاقة والتركيز، ووقفات بسيطة خلال اليوم تفرق.",
                 "الاستنزاف شي شائع خصوصاً مع ضغط الدوام، وأول خطوة إنك تعرف وش أكثر شي يضغطك."],
        "eg": ["الضغط المتراكم بيأثر على النوم والطاقة والتركيز، ووقفات بسيطة في اليوم بتفرق.",
               "الإرهاق من الشغل حاجة شائعة، وأول خطوة إنك تعرف إيه أكتر حاجة بتضغطك."],
        "en": ["Built-up stress affects sleep, energy and focus, and small pauses during the day really do help.",
               "Burnout is very common with work pressure. A good first step is spotting what drains you most."],
    },
    "digestive": {
        "gulf": ["الانتفاخ وعدم الراحة كثير يرتبطون بتوقيت الأكل وسرعته والضغط، وتسجيل الأكل والأعراض أسبوعين يكشف أشياء مفيدة.",
                 "راحة الهضم تتأثر بالروتين والأكل المتأخر والتوتر، مو بس بنوع الأكل."],
        "eg": ["الانتفاخ كتير بيرتبط بمواعيد الأكل وسرعته والتوتر، وتسجيل الأكل والأعراض أسبوعين بيوضح حاجات مفيدة.",
               "راحة الهضم بتتأثر بالروتين والأكل المتأخر والتوتر، مش بس بنوع الأكل."],
        "en": ["Bloating and discomfort are often linked to meal timing, eating speed and stress. A two-week food & symptom diary can reveal a lot.",
               "Digestive comfort depends on routine, late eating and stress, not just what you eat."],
    },
    "pain": {
        "gulf": ["الآلام اليومية كثير ترتبط بالجلسة الطويلة وقلة الحركة والنوم، والألم المستمر لازم يشوفه مختص.",
                 "كسر الجلوس الطويل والحركة الخفيفة اليومية تساعد كثير، وإذا الألم مستمر أو يزيد راجع مختص."],
        "eg": ["الآلام اليومية كتير بترتبط بالقعدة الطويلة وقلة الحركة والنوم، والألم المستمر لازم يشوفه متخصص.",
               "كسر القعدة الطويلة والحركة الخفيفة بتساعد، ولو الألم مستمر أو بيزيد روح لمتخصص."],
        "en": ["Everyday aches are often linked to long sitting, low movement and sleep. Persistent pain should be checked by a professional.",
               "Breaking up sitting time and gentle daily movement help a lot. If pain persists or worsens, please see a professional."],
    },
    "lifestyle": {
        "gulf": ["العادات الصغيرة المستمرة تفرق أكثر من الحلول السريعة: أكل منتظم، حركة، نوم، وتقليل الضغط.",
                 "التوازن بين الأكل والحركة والنوم والضغط هو الأساس، والأهم تعرف وين تبدأ."],
        "eg": ["العادات الصغيرة المستمرة بتفرق أكتر من الحلول السريعة: أكل منتظم، حركة، نوم، وضغط أقل.",
               "التوازن بين الأكل والحركة والنوم والضغط هو الأساس، والمهم تعرف تبدأ منين."],
        "en": ["Small consistent habits beat quick fixes: regular meals, movement, sleep and less stress.",
               "Balance across food, movement, sleep and stress is the foundation. The key is knowing where to start."],
    },
    "health360": {
        "gulf": ["الطاقة والنوم والضغط والهضم كلها مرتبطة ببعض، وغالباً السبب مو شي واحد.",
                 "أحياناً المشكلة تكون مزيج من النوم والأكل والضغط، ويفيد تشوف الصورة كاملة."],
        "eg": ["الطاقة والنوم والضغط والهضم كلهم مرتبطين ببعض، وغالباً السبب مش حاجة واحدة.",
               "ساعات المشكلة بتكون مزيج من النوم والأكل والضغط، ومفيد تشوف الصورة كاملة."],
        "en": ["Energy, sleep, stress and digestion are all connected, and it's rarely just one thing.",
               "Often it's a mix of sleep, food and stress, so it helps to see the whole picture."],
    },
}

PROFESSIONAL_NOTE = {
    "gulf": "وإذا الأعراض قوية أو مستمرة، الأفضل تراجع طبيب.",
    "eg": "ولو الأعراض شديدة أو مستمرة، الأفضل تروح لدكتور.",
    "en": "If symptoms are strong or persistent, it's best to check with a doctor.",
}
ANXIETY_NOTE = {
    "gulf": "وإذا القلق مأثر على حياتك اليومية، الحديث مع مختص نفسي يفرق كثير 🤍",
    "eg": "ولو القلق مأثر على حياتك، الكلام مع متخصص نفسي بيفرق كتير 🤍",
    "en": "If anxiety is affecting daily life, speaking with a mental-health professional can really help 🤍",
}

CTAS = {
    "gulf": ["سوّينا تقييم مجاني ٣ دقائق يوضح لك وش أكثر شي ممكن يأثر عليك 👈 {link}",
             "جرّب هالتقييم المجاني (٣ دقائق) يعطيك صورة أوضح عن عاداتك 👈 {link}",
             "لو حاب تعرف من وين تبدأ، هذا تقييم مجاني قصير 👇 {link}"],
    "eg": ["عملنا تقييم مجاني ٣ دقايق بيوضحلك إيه أكتر حاجة ممكن تأثر عليك 👈 {link}",
           "جرب التقييم المجاني ده (٣ دقايق) هيديك صورة أوضح 👈 {link}"],
    "en": ["We made a free 3-minute self-check that shows which areas may be affecting you most 👉 {link}",
           "This free 3-minute assessment can help you see where to start 👉 {link}",
           "If it helps, here's a quick free self-check to see the bigger picture 👉 {link}"],
}


def template_drafts(scorecard_key: str, group: str, link: str, seed: int, topic_slug: str | None,
                    n: int = 3) -> list[str]:
    rnd = random.Random(seed)
    openers, insights, ctas = OPENERS[group][:], INSIGHTS[scorecard_key][group][:], CTAS[group][:]
    rnd.shuffle(openers)
    rnd.shuffle(ctas)
    extra = ANXIETY_NOTE[group] if topic_slug == "anxiety" else (
        PROFESSIONAL_NOTE[group] if scorecard_key in ("pain", "digestive") else "")
    out: list[str] = []
    for i in range(n):
        parts = [openers[i % len(openers)], insights[(i + seed) % len(insights)]]
        if extra and i != 1:
            parts.append(extra)
        parts.append(ctas[i % len(ctas)].format(link=link))
        text = " ".join(parts) if group == "en" else "\n".join(parts)
        if text not in out:
            out.append(text)
    return out


_SCHEMA = {"type": "object", "properties": {"replies": {"type": "array", "items": {"type": "string"}}},
           "required": ["replies"]}
_SYSTEM = """You draft short public replies that a wellness brand will post under a question in a Gulf social-media thread.
Rules: reply in the SAME language and dialect as the comment (Gulf/Saudi/Egyptian Arabic or English).
Be warm and genuinely helpful first (one practical, general, non-diagnostic insight), then invite them to a free
self-assessment using the exact link given, once. Never diagnose, never name a condition they did not mention,
never promise results, never mention their name or anything personal. Under 280 characters each. Three clearly
different wordings. If the topic involves severe/persistent symptoms or anxiety, gently suggest seeing a professional."""


def llm_drafts(provider, s: Session, comment_text: str, scorecard_key: str, link: str) -> list[str] | None:
    user = json.dumps({"comment": comment_text[:500], "scorecard": scorecard_key, "link": link}, ensure_ascii=False)
    key = hashlib.sha256(f"{provider.name}|{provider.fast_model}|{REPLY_PROMPT_VERSION}|{user}".encode()).hexdigest()
    if cached := s.get(LLMCache, key):
        return cached.response.get("replies")
    try:
        out = provider.complete_json(_SYSTEM, user, _SCHEMA, model=provider.fast_model, max_tokens=800)
    except Exception:  # noqa: BLE001 - any provider failure falls back to templates
        return None
    replies = [r.strip() for r in out.get("replies", []) if isinstance(r, str) and link in r][:3]
    if not replies:
        return None
    s.merge(LLMCache(key=key, response={"replies": replies}))
    return replies


def draft_for(s: Session, item: ReplyQueueItem, provider=None) -> None:
    slug = s.get(Topic, item.topic_id).slug if item.topic_id else None
    group = _group(item.language, item.dialect)
    lang = "en" if group == "en" else "ar"
    link = scorecard_link(item.scorecard_key, lang, item.platform)
    drafts = llm_drafts(provider, s, item.comment.text, item.scorecard_key, link) if provider else None
    if drafts:
        item.drafts, item.drafts_method = drafts, "llm"
    else:
        seed = item.comment_id * 7919 + int(utcnow().timestamp() // 3600)
        item.drafts, item.drafts_method = template_drafts(item.scorecard_key, group, link, seed, slug), "template"


def build_queue(s: Session, provider=None, days: int = 30, limit: int = 100) -> int:
    """Add fresh, high-relevance questions that are not yet queued."""
    since = utcnow() - timedelta(days=days)
    slugs = {t.id: t.slug for t in s.scalars(select(Topic))}
    queued = select(ReplyQueueItem.comment_id)
    rows = s.execute(
        select(Comment, CommentAnalysis)
        .join(CommentAnalysis, CommentAnalysis.comment_id == Comment.id)
        .where(CommentAnalysis.intent.in_(REPLY_INTENTS))
        .where(CommentAnalysis.relevance_score >= settings.reply_min_relevance)
        .where(CommentAnalysis.primary_topic_id.is_not(None))
        .where(func.coalesce(Comment.published_at, Comment.created_at) >= since)
        .where(Comment.id.not_in(queued))
        .order_by(CommentAnalysis.relevance_score.desc(), Comment.published_at.desc())
        .limit(limit)
    ).all()
    added = 0
    for c, a in rows:
        item = ReplyQueueItem(
            comment_id=c.id, platform=c.platform, topic_id=a.primary_topic_id, intent=a.intent,
            relevance=a.relevance_score, language=a.language, dialect=a.dialect,
            scorecard_key=scorecard_for_topic(slugs.get(a.primary_topic_id)),
        )
        item.comment = c
        s.add(item)
        s.flush()
        draft_for(s, item, provider)
        added += 1
    s.flush()
    return added


def open_url(item: ReplyQueueItem) -> str:
    """Where a person goes to post the reply: the post itself."""
    return item.comment.post.url


def replies_today(s: Session) -> int:
    start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return s.scalar(select(func.count()).select_from(ReplyQueueItem)
                    .where(ReplyQueueItem.status.in_(["copied", "posted"]), ReplyQueueItem.acted_at >= start)) or 0


def recently_used(s: Session, text: str, days: int = 7) -> int:
    since = utcnow() - timedelta(days=days)
    return s.scalar(select(func.count()).select_from(ReplyQueueItem)
                    .where(ReplyQueueItem.final_reply == text, ReplyQueueItem.acted_at >= since)) or 0
