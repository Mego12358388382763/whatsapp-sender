"""Generate a SYNTHETIC demo dataset (no real people, pages or comments).

    python sample_data/generate_sample.py  ->  sample_data/synthetic_comments.csv
"""
from __future__ import annotations

import csv
import os
import random
from datetime import datetime, timedelta

random.seed(42)

COMMUNITIES = [
    ("instagram", "Demo Riyadh Wellness Hub", "SA", "Riyadh"),
    ("tiktok", "Demo Jeddah Fitness Talk", "SA", "Jeddah"),
    ("youtube", "Demo Dubai Healthy Living", "AE", "Dubai"),
    ("facebook", "Demo Kuwait Moms Health Group", "KW", None),
    ("instagram", "Demo Doha Nutrition Corner", "QA", "Doha"),
    ("reddit", "Demo r/GulfExpatHealth", "AE", None),
    ("x", "Demo Muscat Wellness", "OM", "Muscat"),
    ("instagram", "Demo Bahrain Active Life", "BH", "Manama"),
]

COMMENTS = {
    "fatigue": [
        "صار لي سنه تعبانه وما فيني حيل، وش الحل؟",
        "اصحى من النوم وانا مرهق كأني ما نمت، ليش؟",
        "طاقتي تنزل بعد الغدا على طول، احد عنده نفس المشكله؟",
        "I'm exhausted every morning even after 8 hours of sleep",
        "Always tired at work by 2pm, what should I do?",
        "ana ta3bana wayed mn el dawam, ma fini 7eil",
        "خمول طول اليوم وما عندي طاقه للرياضه",
        "دايما تعبانه حتى لو نمت بدري، هل هذا طبيعي؟",
        "عايزة اعرف ازاي ارجع طاقتي زي زمان؟ تعبت خالص",
        "low energy for months now, tried vitamins and nothing works",
    ],
    "sleep": [
        "ما اقدر انام قبل الساعه 3 الفجر، كيف اعدل نومي؟",
        "اصحى بالليل اكثر من مره وما ارجع انام",
        "Can't sleep since I started night shifts, any advice?",
        "جربت الميلاتونين وما نفعني ابد",
        "magnesium before bed helped me sleep so much better",
        "النوم عندي خربان من رمضان، شلون ارجعه؟",
        "wake up at night at 3am every day, is it normal?",
        "الارق ذابحني والدوام يبدا 7 الصبح",
    ],
    "stress": [
        "ضغط الشغل مخليني متوتره طول الوقت",
        "stress at work is killing me, I can't switch off",
        "احس اني مضغوط ومستنزف من الدوام، فقدت الشغف",
        "totally burned out, no motivation for anything",
        "كيف اتعامل مع التوتر؟ صار يأثر على نومي",
        "overthinking every night and anxious about everything",
        "القلق والتفكير الزايد يمنعني انام",
        "burnout from long hours, what helped you?",
    ],
    "digestive": [
        "انتفاخ كل يوم بعد الاكل، وش السبب؟",
        "القولون العصبي تعبني، تعرفون دكتور زين في الرياض؟",
        "bloated after every meal, is it normal?",
        "حموضه وارتجاع من فتره، ايش الاكل اللي يساعد؟",
        "gut health is a mess since I moved to Dubai",
        "القولون عندي يزيد مع التوتر، احد جرب شي نفع؟",
        "probiotics helped me with bloating honestly",
        "امساك مستمر وجربت كل شي",
    ],
    "pain": [
        "الم اسفل الظهر من الجلسه الطويله بالمكتب",
        "lower back pain every morning, any physio recommendations in Dubai?",
        "ركبتي توجعني لما امشي، وش التمارين المناسبه؟",
        "صداع يومي بعد الدوام، هل له علاقه بالشاشه؟",
        "migraines every week, tried everything",
        "شد عضلي في الرقبه والكتف من الجوال",
        "جسمي يوجعني كله وتعبانه، من ايش ممكن؟",
    ],
    "lifestyle": [
        "ابي انزل وزن بس ما عندي وقت للجيم، وش تنصحون؟",
        "what's a good diet for more energy?",
        "نقص فيتامين د منتشر عندنا، كم لازم اطلع للشمس؟",
        "walking 10k steps changed my life",
        "رجيم الكيتو نفعني بس رجع الوزن",
        "how do I build a healthy routine with long working hours?",
        "في الصيام طاقتي تنزل مره وش السبب؟",
    ],
    "noise": [
        "ماشاء الله تبارك الله 😍", "شكرا على المعلومات", "🔥🔥🔥", "great video!", "@user @user",
        "للطلب تواصل واتساب [phone]", "follow me for more", "الله يعطيك العافيه", "love this", "مشكوره حبيبتي",
    ],
}

POST_TITLES = {
    "fatigue": "Why you feel tired all the time", "sleep": "5 tips for better sleep",
    "stress": "Dealing with work stress", "digestive": "Gut health basics", "pain": "Office posture & back pain",
    "lifestyle": "Healthy habits for busy people",
}

# country-specific emphasis so communities differ
BIAS = {"SA": ["fatigue", "sleep", "digestive"], "AE": ["stress", "pain", "digestive"], "KW": ["fatigue", "lifestyle"],
        "QA": ["lifestyle", "digestive"], "OM": ["sleep", "stress"], "BH": ["pain", "lifestyle"]}


def main() -> None:
    out = os.path.join(os.path.dirname(__file__), "synthetic_comments.csv")
    start = datetime(2026, 5, 1)
    rows = []
    for ci, (platform, name, country, city) in enumerate(COMMUNITIES):
        for pi in range(random.randint(2, 4)):
            theme = random.choice(BIAS[country] + list(POST_TITLES))
            pdate = start + timedelta(days=random.randint(0, 100))
            url = f"https://demo.example/{platform}/{ci}/post{pi}"
            likes = random.randint(50, 5000)
            n = random.randint(15, 45)
            for _ in range(n):
                bucket = random.choices([theme, random.choice(list(POST_TITLES)), "noise"], weights=[55, 20, 25])[0]
                text = random.choice(COMMENTS[bucket])
                cdate = pdate + timedelta(days=random.randint(0, 20), hours=random.randint(0, 23))
                rows.append({
                    "platform": platform, "community_name": name, "country": country, "city": city or "",
                    "community_url": f"https://demo.example/{platform}/{ci}",
                    "post_url": url, "post_title": f"(demo) {POST_TITLES[theme]}",
                    "post_date": pdate.isoformat(), "post_likes": likes, "post_comments": n,
                    "comment_text": text, "comment_date": cdate.isoformat(),
                    "comment_likes": random.choice([0, 0, 1, 2, 5, 12]),
                    "comment_id": f"demo-{len(rows)}",
                })
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
