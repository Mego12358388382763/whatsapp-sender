"""Arabic/English text normalisation used for matching, hashing and n-grams."""
from __future__ import annotations

import re
import unicodedata

_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
_TATWEEL = "ـ"
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_CHAR_MAP = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ة": "ه",
        "ؤ": "و",
        "ئ": "ي",
        "گ": "ك",
        "چ": "ج",
        "ڤ": "ف",
        "؟": "?",
        "،": ",",
        "؛": ";",
        "\u2019": "'",
        "\u2018": "'",
    }
)
_ARABIC_RUN = re.compile(r"([ء-ي])\1{2,}")
_LATIN_RUN = re.compile(r"([a-z])\1{2,}")
_WS = re.compile(r"\s+")

ARABIC_LETTER = re.compile(r"[ء-ي]")
LATIN_LETTER = re.compile(r"[A-Za-z]")


def normalize(text: str) -> str:
    """Lower-case, unify Arabic letter variants, strip diacritics/elongation."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = _DIACRITICS.sub("", t).replace(_TATWEEL, "")
    t = t.translate(_ARABIC_DIGITS).translate(_CHAR_MAP).lower()
    t = _ARABIC_RUN.sub(r"\1", t)  # تعبااااان -> تعبان
    t = _LATIN_RUN.sub(r"\1\1", t)  # soooo -> soo
    return _WS.sub(" ", t).strip()


_TOKEN = re.compile(r"[ء-يa-z0-9']+")


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(normalize(text))


STOPWORDS = set(
    """
    a an the and or but if of to in on at for with from by is are was were be been being am i me my
    we our you your he she it its they them their this that these those there here so very just
    do does did have has had can could will would should not no yes too also than then as about
    what how why when where who which im i'm dont don't its it's any some all more most like get got
    ya u ur lol ok okay
    و في من على الى عن مع هذا هذه ذلك تلك هو هي هم انا انت احنا نحن كان كانت يكون ما لا لم لن
    ان اني انه انها او ثم قد كل بعض اي ايش وش شو هل كيف ليش لماذا متى وين اللي الي التي الذي
    عند عندي بس يا مره كثير جدا شي شيء حتى لو اذا الله ماشاء ماشاءالله والله يعني عشان علشان
    """.split()
)
