"""Bilingual (English / Arabic incl. Gulf & Egyptian / Arabizi) lexicons.

Topics are *discussion themes*, never diagnoses. A comment saying "I'm
exhausted every morning" maps to `fatigue_low_energy`, not to a condition.
"""
from __future__ import annotations

# slug -> (English name, Arabic name, keywords). Keywords are normalised at load time.
SEED_TOPICS: dict[str, tuple[str, str, list[str]]] = {
    "fatigue_low_energy": (
        "Fatigue / low energy", "التعب وقلة الطاقة",
        ["tired", "exhausted", "exhaustion", "fatigue", "no energy", "low energy", "drained",
         "lethargic", "always sleepy", "wiped out", "worn out",
         "تعب", "تعبان", "تعبانه", "تعبت", "ارهاق", "مرهق", "مرهقه", "خمول", "كسل", "خمل",
         "ما فيني حيل", "مافيني حيل", "طاقتي", "بدون طاقه", "ما عندي طاقه", "هبوط", "دايخ", "دوخه",
         "ta3ban", "ta3bana", "ta3b", "mafeeni 7eil", "mafini 7eil"],
    ),
    "sleep_problems": (
        "Sleep problems", "مشاكل النوم",
        ["sleep", "insomnia", "can't sleep", "cant sleep", "wake up at night", "waking up",
         "sleepless", "restless nights", "melatonin", "nap",
         "نوم", "النوم", "ارق", "ما انام", "ما اقدر انام", "مااقدر انام", "سهر", "اصحى", "قلق بالليل",
         "ميلاتونين", "نومي",
         "nom", "ma anam", "ara2"],
    ),
    "chronic_pain": (
        "Chronic pain", "الألم المزمن",
        ["chronic pain", "pain everywhere", "constant pain", "fibromyalgia", "body aches",
         "hurts all the time", "painkiller", "painkillers",
         "الم مزمن", "الام مزمنه", "الم في كل جسمي", "الم بكل جسمي", "فيبروميالجيا", "مسكنات",
         "جسمي يوجعني", "جسمي مكسر", "تكسير"],
    ),
    "muscle_pain": (
        "Muscle pain", "آلام العضلات",
        ["muscle pain", "muscle ache", "sore muscles", "cramps", "cramp", "muscle spasm", "tight muscles",
         "عضلات", "العضلات", "شد عضلي", "تشنج", "تشنجات", "الم العضل", "عضلي"],
    ),
    "joint_pain": (
        "Joint & back pain", "آلام المفاصل والظهر",
        ["joint pain", "joints", "knee", "knees", "back pain", "lower back", "neck pain", "shoulder pain",
         "arthritis", "stiff joints",
         "مفاصل", "المفاصل", "ركبه", "ركبتي", "ركبي", "ظهري", "الم الظهر", "اسفل الظهر", "رقبتي",
         "كتفي", "خشونه", "ديسك", "انزلاق غضروفي",
         "rkba", "dahri"],
    ),
    "brain_fog": (
        "Brain fog / focus", "ضعف التركيز والتشتت",
        ["brain fog", "can't focus", "cant focus", "concentration", "forgetful", "memory",
         "can't think", "foggy", "focus",
         "تشتت", "ضعف التركيز", "التركيز", "تركيزي", "ما اقدر اركز", "نسيان", "انسى", "ضبابيه", "سرحان"],
    ),
    "digestive": (
        "Digestive problems", "مشاكل الهضم",
        ["bloating", "bloated", "gut", "gut health", "digestion", "constipation", "diarrhea",
         "diarrhoea", "acid reflux", "reflux", "heartburn", "stomach", "gas",
         "انتفاخ", "نفخه", "هضم", "الهضم", "امساك", "اسهال", "حموضه", "ارتجاع", "معده", "معدتي",
         "غازات", "بطني", "المعده"],
    ),
    "ibs": (
        "IBS-type discussions", "القولون العصبي",
        ["ibs", "irritable bowel", "colon", "colitis",
         "القولون", "القولون العصبي", "قولون", "تهيج القولون", "قولوني",
         "2olon", "qolon"],
    ),
    "stress": (
        "Stress", "التوتر والضغط",
        ["stress", "stressed", "overwhelmed", "pressure", "tension",
         "توتر", "متوتر", "متوتره", "ضغط نفسي", "ضغوط", "مضغوط", "مضغوطه", "عصبيه", "معصب"],
    ),
    "burnout": (
        "Burnout", "الاحتراق النفسي",
        ["burnout", "burned out", "burnt out", "no motivation", "can't anymore",
         "احتراق", "احتراق وظيفي", "استنزاف", "مستنزف", "مستنزفه", "ما عندي دافع", "فقدت الشغف", "ملل"],
    ),
    "anxiety": (
        "Anxiety discussions", "القلق",
        ["anxiety", "anxious", "panic", "panic attack", "worry", "worried", "overthinking",
         "قلق", "قلقان", "خوف", "هلع", "نوبات هلع", "نوبه هلع", "وسواس", "تفكير زايد", "اوفر ثينكنق",
         "qala2"],
    ),
    "mobility": (
        "Mobility problems", "صعوبات الحركة",
        ["mobility", "stiffness", "stiff", "can't walk", "difficulty walking", "flexibility", "balance",
         "حركه", "الحركه", "تيبس", "صعوبه المشي", "ما اقدر امشي", "مرونه", "توازن"],
    ),
    "headaches": (
        "Headaches", "الصداع",
        ["headache", "headaches", "migraine", "migraines", "head pain",
         "صداع", "الصداع", "شقيقه", "راسي يوجعني", "الم الراس", "وجع راس",
         "suda3"],
    ),
    "nutrition": (
        "Nutrition", "التغذية",
        ["diet", "nutrition", "food", "eating", "vitamin", "vitamins", "deficiency", "vitamin d",
         "iron", "b12", "supplement", "supplements", "protein", "sugar",
         "اكل", "الاكل", "غذاء", "تغذيه", "رجيم", "دايت", "فيتامين", "فيتامينات", "نقص", "حديد",
         "مكملات", "بروتين", "سكريات", "فيتامين د", "magnesium", "omega 3", "collagen",
         "مغنيسيوم", "ماغنيسيوم", "مغنيزيوم", "اوميغا", "اوميقا", "كولاجين",
         "akl"],
    ),
    "exercise": (
        "Exercise", "الرياضة",
        ["exercise", "workout", "workouts", "gym", "training", "walking", "running", "pilates",
         "yoga", "steps",
         "رياضه", "الرياضه", "تمارين", "تمرين", "جيم", "الجيم", "نادي", "مشي", "المشي", "يوقا", "بيلاتس"],
    ),
    "recovery": (
        "Recovery", "الاستشفاء",
        ["recovery", "recover", "rest day", "stretching", "massage", "sauna", "cold plunge",
         "استشفاء", "تعافي", "راحه", "استرخاء", "مساج", "تمدد", "ساونا"],
    ),
    "work_stress": (
        "Work stress", "ضغط العمل",
        ["work stress", "stress at work", "my job", "my boss", "deadlines", "long hours", "office",
         "ضغط الشغل", "ضغط العمل", "الدوام", "دوامي", "شغلي", "مديري", "الوظيفه", "ساعات العمل",
         "dawam", "shughl"],
    ),
    "weight_management": (
        "Weight management", "إدارة الوزن",
        ["weight", "lose weight", "weight loss", "gained weight", "belly fat", "metabolism",
         "وزن", "الوزن", "وزني", "انزل وزن", "نزول الوزن", "زياده الوزن", "كرش", "الحرق", "حرق"],
    ),
    "general_wellness": (
        "General wellness", "الصحة العامة",
        ["health", "healthy", "wellness", "wellbeing", "lifestyle", "habits", "routine",
         "صحه", "صحي", "صحتي", "نمط حياه", "عادات", "روتين"],
    ),
}

# Themes that alone are too generic to prove a health problem is being discussed.
WEAK_TOPICS = {"general_wellness", "exercise", "nutrition", "work_stress"}

# Search aliases → topic slug
TOPIC_ALIASES: dict[str, str] = {
    "fatigue": "fatigue_low_energy", "energy": "fatigue_low_energy", "tired": "fatigue_low_energy",
    "sleep": "sleep_problems", "insomnia": "sleep_problems",
    "pain": "chronic_pain", "chronic pain": "chronic_pain",
    "muscle": "muscle_pain", "joint": "joint_pain", "back pain": "joint_pain",
    "brain fog": "brain_fog", "focus": "brain_fog",
    "gut": "digestive", "gut health": "digestive", "digestion": "digestive", "bloating": "digestive",
    "ibs": "ibs", "colon": "ibs",
    "stress": "stress", "burnout": "burnout", "anxiety": "anxiety", "mobility": "mobility",
    "headache": "headaches", "migraine": "headaches", "nutrition": "nutrition", "diet": "nutrition",
    "exercise": "exercise", "fitness": "exercise", "recovery": "recovery",
    "work stress": "work_stress", "weight": "weight_management", "wellness": "general_wellness",
}

# Intent labels (order = priority when several fire)
INTENTS = [
    "looking_for_practitioner",
    "asking_for_help",
    "did_not_work",
    "worked",
    "looking_for_information",
    "asking_question",
    "sharing_experience",
    "general_conversation",
    "not_relevant",
]

INTENT_LABELS = {
    "looking_for_practitioner": "Looking for a practitioner/service",
    "asking_for_help": "Asking for help",
    "did_not_work": "Discussing something that did not work",
    "worked": "Discussing something that worked",
    "looking_for_information": "Looking for information",
    "asking_question": "Asking a question",
    "sharing_experience": "Sharing an experience",
    "general_conversation": "General conversation",
    "not_relevant": "Not relevant",
}

INTENT_KEYWORDS: dict[str, list[str]] = {
    "looking_for_practitioner": [
        "recommend a doctor", "any doctor", "good doctor", "which doctor", "clinic", "specialist",
        "nutritionist", "dietitian", "physio", "physiotherapist", "coach", "therapist", "who can help",
        "where can i", "دكتور", "دكتوره", "طبيب", "طبيبه", "عياده", "مستشفى", "اخصائي", "اخصائيه",
        "مركز", "علاج طبيعي", "مدرب", "كوتش", "تنصحوني بدكتور", "تعرفون دكتور", "احد يعرف دكتور",
        "وين اروح", "doctor", "dr",
    ],
    "asking_for_help": [
        "help", "please advise", "what should i do", "any advice", "advice please", "need advice",
        "i need help", "what do i do", "desperate",
        "ساعدوني", "ابي حل", "ابغى حل", "وش الحل", "ايش الحل", "شو الحل", "ايش اسوي", "وش اسوي",
        "شو اسوي", "انصحوني", "نصيحه", "حد يساعدني", "احد يساعدني", "محتاج مساعده", "محتاجه مساعده",
        "تعبت من", "ما عرفت ايش اسوي", "عايز حل", "اعمل ايه",
    ],
    "did_not_work": [
        "didn't work", "did not work", "didnt work", "didn't help", "no results", "no difference",
        "tried everything", "nothing works", "waste of money", "made it worse",
        "ما نفع", "ما نفعني", "ما فاد", "ما فادني", "بدون فايده", "بدون فايدة", "ما استفدت",
        "جربت كل شي", "جربت كل شيء", "ولا شي نفع", "زاد الوضع", "ما تحسنت", "مافي فرق", "ما في فرق",
    ],
    "worked": [
        "worked for me", "helped me", "changed my life", "game changer", "it works", "really helped",
        "i feel better", "feel much better", "improved", "fixed my",
        "نفعني", "فادني", "استفدت", "تحسنت", "صرت احسن", "صار احسن", "فرق معي", "غير حياتي", "جربته ونفع",
        "الحمدلله تحسن", "صرت افضل",
    ],
    "looking_for_information": [
        "what is", "what are", "what causes", "is it normal", "explain", "information", "info",
        "the reason", "difference between", "does it mean", "is it true",
        "ايش هو", "وش هو", "وش يعني", "ايش يعني", "ما هو", "ما هي", "معلومات", "سبب", "اسباب", "الفرق بين",
        "هل صحيح", "طبيعي", "ليش يصير", "من ايش",
    ],
    "sharing_experience": [
        "i have", "i've been", "i feel", "i am", "i'm", "my ", "me too", "same here", "for years",
        "for months", "since", "i suffer", "i struggle", "every morning", "every day",
        "انا", "عندي", "صار لي", "صارلي", "احس", "اعاني", "من سنه", "من سنين", "من شهور", "من فتره",
        "نفس الشي", "نفسي", "كل يوم", "كل صباح", "دايم", "دايما", "حالتي",
    ],
    "general_conversation": [
        "thanks", "thank you", "love this", "great", "amazing", "nice", "wow", "beautiful", "agree",
        "شكرا", "مشكور", "مشكوره", "يعطيك العافيه", "جزاك الله", "ماشاء الله", "ما شاء الله",
        "الله يعطيك", "حلو", "روعه", "صح", "اتفق", "تسلم", "كلام جميل",
    ],
}

QUESTION_WORDS_EN = {
    "how", "why", "what", "when", "where", "which", "who", "is", "are", "does", "do", "can",
    "should", "could", "anyone", "anybody",
}
QUESTION_WORDS_AR = {
    "كيف", "ليش", "لماذا", "هل", "وش", "ايش", "شو", "شلون", "متى", "كم", "وين", "فين", "ازاي",
    "ليه", "ايه", "مين", "احد", "حد", "شنو",
}

SPAM_MARKERS = [
    "dm me", "check my profile", "link in bio", "follow me", "whatsapp me", "promo code",
    "discount", "buy now", "click", "تواصل واتساب", "للطلب", "كود خصم", "خصم", "للتواصل",
    "رابط في البايو", "تابعني", "[link]", "[phone]",
]
