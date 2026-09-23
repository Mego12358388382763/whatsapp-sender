from app.analysis.heuristic import analyze
from app.privacy import scrub, strip_identity
from app.text.lang import detect_dialect, detect_language, is_arabizi
from app.text.normalize import normalize


def test_normalize_arabic_variants():
    assert normalize("أَرَقٌ") == "ارق"
    assert normalize("تعبااااانة") == "تعبانه"
    assert normalize("إرهاق ٣") == "ارهاق 3"


def test_language_detection():
    assert detect_language("I am exhausted every morning") == "en"
    assert detect_language("صار لي سنه تعبانه") == "ar"
    assert detect_language("الـ gym ما يساعدني with my back") == "mixed"
    assert detect_language("ana ta3bana wayed") == "arabizi"
    assert is_arabizi("wallah ma anam 3ashan el shughl")
    assert detect_language("😍😍") == "unknown"


def test_dialects():
    assert detect_dialect("شلون اتخلص من التعب؟ وايد تعبانه") == "gulf"
    assert detect_dialect("وش الحل ابغى انام زي الناس") == "saudi"
    assert detect_dialect("عايزة اعرف ازاي اخلص من الصداع ده") == "egyptian"


def test_scrub_pii():
    out = scrub("Ask @dr.sara or mail me a@b.com or call +966 55 123 4567 https://x.com/abc")
    assert "@dr.sara" not in out and "a@b.com" not in out and "4567" not in out and "x.com" not in out
    assert "@user" in out and "[email]" in out and "[phone]" in out and "[link]" in out
    # short numbers (ages, doses) survive
    assert "500" in scrub("I take 500 mg")


def test_strip_identity():
    rec = {"text": "hi", "ownerUsername": "x", "author": "y", "profileUrl": "z", "likesCount": 3}
    assert strip_identity(rec) == {"text": "hi", "likesCount": 3}


def test_no_diagnosis_only_theme():
    r = analyze("I am exhausted every morning.")
    assert r.primary_topic == "fatigue_low_energy"
    assert r.intent == "sharing_experience"
    # Output vocabulary is themes; never condition labels like ME/CFS
    assert all("cfs" not in s and "syndrome" not in s for s, _ in r.topics)


def test_intents():
    assert analyze("صار لي سنه تعبانه وما فيني حيل، وش الحل؟").intent == "asking_for_help"
    assert analyze("تعرفون دكتور زين للقولون في الرياض؟").intent == "looking_for_practitioner"
    assert analyze("جربت المغنيسيوم للنوم وما نفعني ابد").intent == "did_not_work"
    assert analyze("tried magnesium for sleep and it didn't help").intent == "did_not_work"
    assert analyze("Magnesium changed my life, sleep is so much better").intent == "worked"
    assert analyze("Is it normal to feel bloated after every meal?").intent == "looking_for_information"
    assert analyze("ماشاء الله 😍").intent == "general_conversation"


def test_spam_scores_zero():
    r = analyze("للطلب تواصل واتساب [phone]")
    assert r.is_spam and r.relevance_score == 0 and not r.needs_llm


def test_relevance_ordering():
    rich = analyze("صار لي سنه تعبانه وما اقدر انام وما فيني حيل للدوام، وش الحل؟").relevance_score
    thin = analyze("تعب").relevance_score
    noise = analyze("thanks!").relevance_score
    assert rich > thin > noise
    assert 0 <= noise <= 100 and rich <= 100
