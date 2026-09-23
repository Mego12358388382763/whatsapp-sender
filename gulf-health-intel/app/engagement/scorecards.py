"""Bilingual wellness Scorecards: general lifestyle self-assessments, not diagnostic tools.

Every question uses the same 5-point frequency scale. `good_when_often` marks
questions where answering "Always" is healthy (e.g. "I get morning daylight").
Area scores are 0-100, where higher means more balanced.
"""
from __future__ import annotations

SCALE = {
    "en": ["Never", "Rarely", "Sometimes", "Often", "Always"],
    "ar": ["أبداً", "نادراً", "أحياناً", "غالباً", "دائماً"],
}

DISCLAIMER = {
    "en": "This is a general lifestyle self-check for education only. It is not a medical assessment or diagnosis. "
          "If symptoms are severe, persistent or worrying, please speak to a qualified healthcare professional.",
    "ar": "هذا تقييم ذاتي عام لنمط الحياة لأغراض توعوية فقط، وليس تقييماً طبياً أو تشخيصاً. "
          "إذا كانت الأعراض شديدة أو مستمرة أو مقلقة، يُرجى مراجعة مختص صحي مؤهل.",
}

# area key -> (en name, ar name, tip_en, tip_ar)
AREAS = {
    "sleep_rhythm": ("Sleep rhythm", "انتظام النوم",
                     "Aim for consistent sleep and wake times, even on weekends, and dim screens an hour before bed.",
                     "حاول تثبّت وقت النوم والصحيان حتى في الإجازات، وخفّف الشاشات قبل النوم بساعة."),
    "sleep_quality": ("Sleep quality", "جودة النوم",
                      "A cool, dark room and less caffeine after mid-afternoon often help sleep feel more restful.",
                      "غرفة باردة ومظلمة وتقليل القهوة بعد العصر غالباً تساعد إن نومك يكون مريح أكثر."),
    "daily_energy": ("Daily energy", "الطاقة اليومية",
                     "Notice when your energy dips. Meal timing, hydration and short movement breaks often make a difference.",
                     "لاحظ متى تنزل طاقتك. توقيت الوجبات وشرب الماء وفواصل الحركة القصيرة غالباً تفرق."),
    "nutrition": ("Nutrition & hydration", "التغذية وشرب الماء",
                  "Regular balanced meals with protein, vegetables and enough water support steady energy, especially in the heat.",
                  "وجبات منتظمة ومتوازنة فيها بروتين وخضار وماء كافي تساعد على طاقة ثابتة، خصوصاً مع الحر."),
    "movement": ("Movement", "الحركة",
                 "Short daily walks and breaking up long sitting time are a simple place to start.",
                 "المشي اليومي ولو قليل، وكسر الجلوس الطويل، بداية بسيطة ومفيدة."),
    "stress_load": ("Stress load", "مستوى الضغط",
                    "Frequent pressure is common. Small daily pauses, clear boundaries and support from others can help.",
                    "الضغط المتكرر شائع. وقفات قصيرة يومية وحدود واضحة ودعم من حولك ممكن تساعد."),
    "recovery": ("Recovery & switching off", "الاستشفاء والفصل",
                 "Protecting time to rest and switch off from work is part of staying well, not a luxury.",
                 "تخصيص وقت للراحة والفصل عن الشغل جزء من صحتك وليس رفاهية."),
    "focus": ("Focus & mood", "التركيز والمزاج",
              "Focus often follows sleep, stress and breaks. If low mood persists, talking to a professional helps.",
              "التركيز غالباً مرتبط بالنوم والضغط والفواصل. وإذا استمر المزاج المنخفض، الحديث مع مختص يساعد."),
    "digestive_comfort": ("Digestive comfort", "راحة الجهاز الهضمي",
                          "Keeping a simple food & symptom diary for two weeks can reveal useful patterns to discuss with a professional.",
                          "تسجيل الأكل والأعراض لمدة أسبوعين يكشف أنماط مفيدة تناقشها مع مختص."),
    "eating_habits": ("Eating habits", "عادات الأكل",
                      "Eating slowly, regular meal times and not eating late at night support digestive comfort.",
                      "الأكل بهدوء وانتظام الوجبات وتجنب الأكل المتأخر يساعد راحة الهضم."),
    "body_comfort": ("Body comfort", "راحة الجسم",
                     "Persistent or worsening pain should be checked by a professional. Gentle movement often helps everyday stiffness.",
                     "الألم المستمر أو اللي يزيد لازم يشوفه مختص. والحركة الخفيفة غالباً تساعد في التيبس اليومي."),
    "posture_work": ("Posture & desk habits", "الجلسة وعادات المكتب",
                     "Adjust screen height, get up every 30–45 minutes and change position often.",
                     "عدّل ارتفاع الشاشة، وقم كل ٣٠–٤٥ دقيقة، وغيّر وضعيتك باستمرار."),
}

# (area, en, ar, good_when_often)
Q = tuple[str, str, str, bool]

SCORECARDS: dict[str, dict] = {
    "energy": {
        "title": {"en": "3-Minute Energy & Recovery Assessment", "ar": "تقييم الطاقة والاستشفاء في ٣ دقائق"},
        "intro": {"en": "Your energy isn't controlled by one thing. See which areas of your lifestyle may deserve more attention.",
                  "ar": "طاقتك ما تتحكم فيها حاجة وحدة. اكتشف أي جوانب في نمط حياتك تحتاج اهتمام أكثر."},
        "questions": [
            ("daily_energy", "I wake up feeling refreshed.", "أصحى وأنا مرتاح ونشيط.", True),
            ("daily_energy", "My energy drops sharply in the afternoon.", "طاقتي تنزل بقوة بعد الظهر.", False),
            ("sleep_rhythm", "I go to sleep and wake up at roughly the same times.", "أنام وأصحى تقريباً في نفس الأوقات.", True),
            ("sleep_rhythm", "I stay up late on my phone or screens.", "أسهر على الجوال أو الشاشات.", False),
            ("nutrition", "I skip meals or eat at irregular times.", "أفوّت وجبات أو آكل في أوقات غير منتظمة.", False),
            ("nutrition", "I drink enough water through the day.", "أشرب ماء كافي خلال اليوم.", True),
            ("stress_load", "I feel under pressure most days.", "أحس بضغط أغلب الأيام.", False),
            ("movement", "I move or walk for at least 20 minutes a day.", "أتحرك أو أمشي ٢٠ دقيقة على الأقل يومياً.", True),
            ("focus", "I find it hard to concentrate.", "أجد صعوبة في التركيز.", False),
            ("recovery", "I have time to rest and switch off.", "عندي وقت أرتاح وأفصل فيه.", True),
        ],
    },
    "sleep": {
        "title": {"en": "Sleep & Recovery Scorecard", "ar": "مقياس النوم والاستشفاء"},
        "intro": {"en": "Good sleep is built across the whole day, not only at bedtime. See which habits may be helping or hurting yours.",
                  "ar": "النوم الجيد يُبنى طول اليوم مو بس وقت النوم. اكتشف أي عادات تساعدك وأيها تأثر عليك."},
        "questions": [
            ("sleep_rhythm", "I go to sleep and wake up at roughly the same times.", "أنام وأصحى تقريباً في نفس الأوقات.", True),
            ("sleep_rhythm", "I use screens in bed before sleeping.", "أستخدم الشاشات في السرير قبل النوم.", False),
            ("sleep_quality", "It takes me a long time to fall asleep.", "آخذ وقت طويل لين أنام.", False),
            ("sleep_quality", "I wake up during the night and struggle to get back to sleep.", "أصحى بالليل وأتعب لين أرجع أنام.", False),
            ("sleep_quality", "I have caffeine after 4pm.", "أشرب قهوة أو منبهات بعد الساعة ٤ العصر.", False),
            ("daily_energy", "I feel sleepy during the day.", "أحس بنعاس خلال اليوم.", False),
            ("stress_load", "Worries keep my mind busy at night.", "الأفكار والهموم تشغل بالي بالليل.", False),
            ("movement", "I get daylight or go outside in the morning.", "أتعرض لضوء الشمس أو أطلع برا في الصباح.", True),
            ("recovery", "I have a relaxing routine before bed.", "عندي روتين هادي قبل النوم.", True),
        ],
    },
    "stress": {
        "title": {"en": "5-Minute Stress & Burnout Check-In", "ar": "فحص الضغط والاحتراق في ٥ دقائق"},
        "intro": {"en": "Feeling stretched thin isn't a personal failing. See which everyday pressures may be adding up.",
                  "ar": "الإحساس بالاستنزاف مو ضعف منك. اكتشف أي ضغوط يومية ممكن تكون تتراكم عليك."},
        "questions": [
            ("stress_load", "I feel overwhelmed by my responsibilities.", "أحس إن مسؤولياتي أكثر من طاقتي.", False),
            ("stress_load", "Work pressure follows me home.", "ضغط الشغل يلحقني للبيت.", False),
            ("recovery", "I can switch off from work in the evenings.", "أقدر أفصل عن الشغل في المساء.", True),
            ("recovery", "I take real breaks during the day.", "آخذ فواصل حقيقية خلال اليوم.", True),
            ("focus", "I feel less motivated than I used to.", "أحس إن حماسي أقل من قبل.", False),
            ("focus", "I find it hard to focus on one thing.", "أجد صعوبة أركز على شي واحد.", False),
            ("sleep_quality", "Stress affects my sleep.", "الضغط يأثر على نومي.", False),
            ("movement", "I do something active that helps me unwind.", "أمارس نشاط حركي يساعدني أرتاح.", True),
            ("daily_energy", "I feel drained by the end of the day.", "أحس إني مستنزف آخر اليوم.", False),
        ],
    },
    "digestive": {
        "title": {"en": "Gut & Digestive Wellness Check", "ar": "فحص راحة الجهاز الهضمي"},
        "intro": {"en": "Digestive discomfort is often linked to routine, food timing and stress. See which areas stand out for you.",
                  "ar": "انزعاج الهضم كثير يرتبط بالروتين وتوقيت الأكل والضغط. شوف أي جوانب تبرز عندك."},
        "questions": [
            ("digestive_comfort", "I feel bloated after meals.", "أحس بانتفاخ بعد الأكل.", False),
            ("digestive_comfort", "I notice heartburn or acid after eating.", "ألاحظ حموضة أو حرقة بعد الأكل.", False),
            ("digestive_comfort", "My digestion feels regular and comfortable.", "هضمي منتظم ومريح.", True),
            ("eating_habits", "I eat quickly or while distracted.", "آكل بسرعة أو وأنا مشغول بشي ثاني.", False),
            ("eating_habits", "I eat late at night.", "آكل متأخر بالليل.", False),
            ("nutrition", "I eat vegetables, fruit or fibre daily.", "آكل خضار أو فواكه أو ألياف يومياً.", True),
            ("nutrition", "I drink enough water through the day.", "أشرب ماء كافي خلال اليوم.", True),
            ("stress_load", "My stomach reacts when I'm stressed.", "بطني يتأثر لما أكون متوتر.", False),
        ],
    },
    "pain": {
        "title": {"en": "Move Better: Pain & Mobility Self-Check", "ar": "تحرك أفضل: فحص ذاتي للألم والحركة"},
        "intro": {"en": "Daily aches often connect to posture, movement, recovery and sleep. See which of these areas may need attention.",
                  "ar": "الآلام اليومية كثير ترتبط بالجلسة والحركة والاستشفاء والنوم. شوف أي جانب يحتاج اهتمام."},
        "questions": [
            ("body_comfort", "I feel stiff when I get up in the morning.", "أحس بتيبس لما أقوم الصبح.", False),
            ("body_comfort", "Aches limit what I want to do.", "الآلام تحدّ من اللي أبغى أسويه.", False),
            ("posture_work", "I sit for more than 2 hours without getting up.", "أجلس أكثر من ساعتين بدون ما أقوم.", False),
            ("posture_work", "I look down at my phone for long periods.", "أنزل راسي على الجوال لفترات طويلة.", False),
            ("movement", "I stretch or do mobility exercises.", "أسوي تمارين إطالة أو مرونة.", True),
            ("movement", "I walk or move for at least 20 minutes a day.", "أمشي أو أتحرك ٢٠ دقيقة على الأقل يومياً.", True),
            ("sleep_quality", "Discomfort affects my sleep.", "الانزعاج أو الألم يأثر على نومي.", False),
            ("recovery", "I give my body time to recover after effort.", "أعطي جسمي وقت يرتاح بعد المجهود.", True),
        ],
    },
    "lifestyle": {
        "title": {"en": "Lifestyle Balance Scorecard", "ar": "مقياس توازن نمط الحياة"},
        "intro": {"en": "Small, consistent habits add up. See how balanced your nutrition, movement, sleep and stress really are.",
                  "ar": "العادات الصغيرة المستمرة تفرق. شوف قد إيش نمط حياتك متوازن في الأكل والحركة والنوم والضغط."},
        "questions": [
            ("nutrition", "I eat balanced meals with protein and vegetables.", "آكل وجبات متوازنة فيها بروتين وخضار.", True),
            ("nutrition", "I rely on fast food or sugary snacks.", "أعتمد على الوجبات السريعة أو السكريات.", False),
            ("movement", "I exercise at least 3 times a week.", "أمارس رياضة ٣ مرات في الأسبوع على الأقل.", True),
            ("movement", "I spend most of my day sitting.", "أقضي أغلب يومي جالس.", False),
            ("sleep_rhythm", "I get 7 or more hours of sleep.", "أنام ٧ ساعات أو أكثر.", True),
            ("stress_load", "I feel under pressure most days.", "أحس بضغط أغلب الأيام.", False),
            ("recovery", "I make time for things I enjoy.", "أخصص وقت للأشياء اللي أحبها.", True),
            ("daily_energy", "I have steady energy through the day.", "طاقتي ثابتة خلال اليوم.", True),
        ],
    },
}

# Health 360 = the first two questions of every other scorecard (duplicates removed)
_h360: list[Q] = []
for _k in ("energy", "sleep", "stress", "digestive", "pain", "lifestyle"):
    for _q in SCORECARDS[_k]["questions"][:2]:
        if all(_q[1] != x[1] for x in _h360):
            _h360.append(_q)
SCORECARDS["health360"] = {
    "title": {"en": "Health 360: Whole-Lifestyle Scorecard", "ar": "صحة ٣٦٠: مقياس نمط الحياة الشامل"},
    "intro": {"en": "Energy, sleep, stress, digestion and movement are all connected. See your whole picture in one place.",
              "ar": "الطاقة والنوم والضغط والهضم والحركة كلها مرتبطة ببعض. شوف الصورة الكاملة في مكان واحد."},
    "questions": _h360,
}

# topic slug -> scorecard key
TOPIC_TO_SCORECARD = {
    "fatigue_low_energy": "energy", "brain_fog": "energy",
    "sleep_problems": "sleep", "recovery": "sleep",
    "stress": "stress", "burnout": "stress", "work_stress": "stress", "anxiety": "stress",
    "digestive": "digestive", "ibs": "digestive",
    "chronic_pain": "pain", "muscle_pain": "pain", "joint_pain": "pain", "mobility": "pain", "headaches": "pain",
    "nutrition": "lifestyle", "exercise": "lifestyle", "weight_management": "lifestyle", "general_wellness": "lifestyle",
}


def scorecard_for_topic(slug: str | None) -> str:
    return TOPIC_TO_SCORECARD.get(slug or "", "health360")


def public_definition(key: str, lang: str) -> dict | None:
    sc = SCORECARDS.get(key)
    if not sc:
        return None
    lang = "ar" if lang == "ar" else "en"
    return {
        "key": key, "lang": lang, "title": sc["title"][lang], "intro": sc["intro"][lang],
        "scale": SCALE[lang], "disclaimer": DISCLAIMER[lang],
        "questions": [{"id": i, "text": q[2] if lang == "ar" else q[1]} for i, q in enumerate(sc["questions"])],
    }


def score(key: str, answers: dict, lang: str) -> dict:
    """answers: {question_id: 0..4}. Returns per-area 0-100 (higher = more balanced) + tips."""
    sc = SCORECARDS[key]
    lang = "ar" if lang == "ar" else "en"
    per_area: dict[str, list[float]] = {}
    for i, (area, _en, _ar, good_when_often) in enumerate(sc["questions"]):
        v = answers.get(str(i), answers.get(i))
        if v is None:
            continue
        v = max(0, min(4, int(v)))
        per_area.setdefault(area, []).append((v if good_when_often else 4 - v) / 4 * 100)
    areas = []
    for area, vals in per_area.items():
        s = round(sum(vals) / len(vals))
        en, ar, tip_en, tip_ar = AREAS[area]
        level = "good" if s >= 70 else "attention" if s >= 40 else "priority"
        areas.append({"area": area, "name": ar if lang == "ar" else en, "score": s, "level": level,
                      "tip": tip_ar if lang == "ar" else tip_en})
    areas.sort(key=lambda a: a["score"])
    total = round(sum(a["score"] for a in areas) / len(areas)) if areas else 0
    return {"total": total, "areas": areas}
