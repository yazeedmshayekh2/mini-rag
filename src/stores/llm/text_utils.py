import re
import unicodedata

_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_TATWEEL = "\u0640"
_ALEF_VARIANTS = re.compile(r"[إأآٱ]")
_ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_WHITESPACE = re.compile(r"\s+")


def normalize_arabic(text: str) -> str:
    text = _ARABIC_DIACRITICS.sub("", text)  # remove tashkeel
    text = text.replace(_TATWEEL, "")  # remove tatweel ـ
    text = _ALEF_VARIANTS.sub("ا", text)  # unify alef forms
    text = text.replace("ى", "ي")  # alef maqsura → ya
    text = text.replace("ة", "ه")  # ta marbuta → ha
    return text


def normalize_for_embedding(text: str) -> str:
    """Normalization applied to BOTH indexed chunks and user queries."""
    text = unicodedata.normalize(
        "NFKC", text
    )  # fold Arabic presentation forms that PDFs often contain
    text = text.translate(
        _ARABIC_INDIC_DIGITS
    )  # ٣ → 3, so numbers match across languages
    text = normalize_arabic(text)  # leaves English untouched
    return _WHITESPACE.sub(" ", text).strip()
