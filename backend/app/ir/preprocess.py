"""
Text preprocessing (lecture topic: term vocabulary and postings).

Pipeline for every field value and every query:
  1. Unicode folding   "Wrocław" -> "Wroclaw"  (the v1 regex silently split it into "wroc aw")
  2. Tokenization      split on anything that is not a letter or digit
  3. Case folding      lower-case, EXCEPT that all-caps acronyms survive stop-word
                       removal: "IT Development" keeps "it", which v1 deleted
                       because "it" is a stop word
  4. Stop-word removal general list (+ a small query-only list such as "jobs")
  5. Stemming          Porter stemmer (NLTK implementation), switchable for ablation
  6. Biwords           adjacent-term pairs inside one comma-separated segment,
                       e.g. "United Kingdom" -> "unit_kingdom", used for phrase matching

`legacy_preprocess` is the ORIGINAL v1 function, kept unchanged so the
baselines in the evaluation are exactly the system we started from.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from nltk.stem import PorterStemmer

# Original v1 list, extended with a few more function words.
STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "is", "are", "to", "of", "in", "for", "with",
    "on", "as", "at", "by", "be", "this", "that", "from", "it", "its", "was",
    "were", "will", "can", "has", "have", "had",
    "i", "me", "my", "we", "our", "you", "your", "into", "about", "than", "so",
    "not", "no", "but", "if", "who", "what", "where", "how", "any", "some",
    "also", "very", "just", "do", "does",
})

# Words that are noise in a job QUERY but are never part of a job's content.
# Applied to queries only.
QUERY_STOPWORDS = frozenset({
    "job", "jobs", "role", "roles", "position", "positions", "opening", "openings",
    "vacancy", "vacancies", "looking", "want", "wanted", "find", "search", "need",
    "career", "careers", "opportunity", "opportunities", "near", "based", "like",
    "please", "show", "give", "best", "good",
})

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_stemmer = PorterStemmer()


# Letters that NFKD does not decompose into base letter + accent
_TRANSLIT = str.maketrans({"ł": "l", "Ł": "L", "ı": "i", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D",
                           "ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "þ": "th", "ð": "d"})


def fold(text) -> str:
    """Unicode -> closest ASCII (accents removed). Non-strings become ''."""
    if not isinstance(text, str):
        return ""
    text = text.translate(_TRANSLIT)
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def raw_tokens(text) -> list[str]:
    """Tokenize WITHOUT lower-casing, so acronyms can still be recognised."""
    return _TOKEN_RE.findall(fold(text))


def is_acronym(token: str) -> bool:
    return len(token) >= 2 and token.isalpha() and token.isupper()


@lru_cache(maxsize=None)
def stem(token: str) -> str:
    return _stemmer.stem(token)


def normalize_tokens(tokens, *, query: bool = False, stemming: bool = True, removed: list | None = None) -> list[str]:
    """Case folding + stop-word removal + stemming on already-split tokens.

    If `removed` is a list, (token, reason) pairs are appended to it so the
    query-analysis panel can show exactly what was dropped and why.
    """
    out = []
    for tok in tokens:
        low = tok.lower()
        if len(low) < 2 and not low.isdigit():
            if removed is not None:
                removed.append((low, "too short"))
            continue
        if low in STOPWORDS and not is_acronym(tok):
            if removed is not None:
                removed.append((low, "stop word"))
            continue
        if query and low in QUERY_STOPWORDS:
            if removed is not None:
                removed.append((low, "query stop word"))
            continue
        out.append(stem(low) if stemming else low)
    return out


def make_biwords(terms: list[str]) -> list[str]:
    return [f"{a}_{b}" for a, b in zip(terms, terms[1:])]


def field_terms(value, *, stemming: bool = True, biwords: bool = True) -> tuple[list[str], list[str]]:
    """Unigrams and biwords of one field value.

    Biwords are only formed inside a comma-separated segment, so
    "Berlin, Berlin, Germany" does not produce the false phrase "berlin_berlin".
    """
    unigrams, bis = [], []
    for segment in fold(value).split(","):
        terms = normalize_tokens(_TOKEN_RE.findall(segment), stemming=stemming)
        unigrams.extend(terms)
        if biwords:
            bis.extend(make_biwords(terms))
    return unigrams, bis


# ---------------------------------------------------------------------------
# v1 pipeline, preserved verbatim for the baselines
# ---------------------------------------------------------------------------
LEGACY_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "is", "are", "to", "of", "in", "for", "with",
    "on", "as", "at", "by", "be", "this", "that", "from", "it", "its", "was",
    "were", "will", "can", "has", "have", "had",
})


def legacy_preprocess(text) -> list[str]:
    """The original CareerLens v1 `preprocess` function (unchanged)."""
    if not isinstance(text, str):
        return []
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [t for t in text.split() if t not in LEGACY_STOPWORDS]
