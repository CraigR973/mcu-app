"""One rule for "is this the same title?" — Batch X10 (CR43-03, `DECISIONS.md` #280).

Until X10 four features each reduced a title their own way: the catalogue matcher's
``canonical_title``, T9's ``fold``, the Letterboxd matcher's ``normalise_title`` and review
finding's ``normalise``. On R1's eight pairs they disagreed on seven: one read "&" as "and" and
another did not, one dropped accents and another turned "é" into a gap, one dropped a leading
article. Each feature relearned the same lessons ("Lampoon's" was handled in two files), and the
spec check patched "&" before calling a rule Search called unpatched.

Now there is one fold, T9's, moved here unchanged, and two named levels of strictness built on
it. Every site picks a level; none reduces a title itself.

- :attr:`Strictness.WORDS` — the title's words, spelled alike: accents, apostrophes and full
  stops gone, "&" and "v" read as "and", numbers as digits. Order and the article are kept, so
  a page title can be read as the film's words followed by its own ("Dog Soldiers 4K Blu-ray
  Review").
- :attr:`Strictness.TITLE` — a catalogue entry's key: brackets, a trailing year, edition words
  ("Director's Cut") and library order ("Mummy, The") removed, then folded, then the leading
  article dropped. "The Collector", "Collector, The" and "Collector" are one key; so are "The
  Mummy (Brendan Fraser)" and "The Mummy". A key says two entries may be one film; the year is
  what tells namesakes apart, and every caller checks it.

Identification decides with :func:`src.services.identify.titles.compare`, which reads the same
:func:`fold` and adds what a match needs on top (typos, colon sides, a first "Part 1").

**Nothing here can make two titles equal unless they differ only in these ways**: both sides
of every comparison are reduced by the same function. ``tests/test_title_key.py`` holds R1's
pair table and checks every site gives the table's answer.
"""

from __future__ import annotations

import enum
import re
import unicodedata

# ---------------------------------------------------------------------------
# Cleaning a catalogue entry: what a sheet or a page adds to a title
# ---------------------------------------------------------------------------

_YEAR_RE = re.compile(r"\s*\((\d{4})\)\s*$")
_BRACKET_RE = re.compile(r"\s*[\[(][^\[\]()]*[\])]\s*")
_WHITESPACE_RE = re.compile(r"\s+")
_TRAILING_ARTICLE_RE = re.compile(r"^(.+?),?\s+(the|a|an)\s*$", re.IGNORECASE)

# Trailing edition / cut markers that are not part of the canonical TMDB title.
_EDITION_SUFFIXES = [
    r"director'?s cut",
    r"the final cut",
    r"final cut",
    r"extended edition",
    r"extended cut",
    r"extended",
    r"special edition",
    r"theatrical cut",
    r"unrated(?: edition| cut)?",
    r"uncut",
    r"remastered",
    r"anniversary edition",
]
_EDITION_RE = re.compile(
    r"(?:\s*[:\-–]\s*|\s+)(?:" + "|".join(_EDITION_SUFFIXES) + r")\s*$",
    re.IGNORECASE,
)


def extract_year(title: str) -> tuple[str, int | None]:
    """Strip a trailing ``(YYYY)`` from the title and return (clean_title, year)."""
    stripped = title.strip()
    m = _YEAR_RE.search(stripped)
    if not m:
        return stripped, None
    cleaned = _YEAR_RE.sub("", stripped).rstrip()
    return cleaned, int(m.group(1))


def strip_annotations(title: str) -> str:
    """Remove ``[...]`` and ``(...)`` annotations such as edition or box-set tags."""
    cleaned = _BRACKET_RE.sub(" ", title)
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def rotate_trailing_article(title: str) -> str:
    """Rewrite library-card titles like 'Eiger Sanction, The' as 'The Eiger Sanction'."""
    m = _TRAILING_ARTICLE_RE.match(title)
    if not m:
        return title
    body = m.group(1).rstrip(",").strip()
    article = m.group(2).capitalize()
    return f"{article} {body}"


def strip_edition_suffix(title: str) -> str:
    """Drop trailing edition / cut markers (e.g. 'The Final Cut', 'Director's Cut')."""
    return _EDITION_RE.sub("", title).strip()


def normalise_query(raw_title: str) -> tuple[str, int | None]:
    """Apply year extraction, annotation stripping, edition stripping, and article rotation."""
    cleaned, year = extract_year(raw_title)
    cleaned = strip_annotations(cleaned)
    cleaned = strip_edition_suffix(cleaned)
    cleaned = rotate_trailing_article(cleaned)
    return cleaned, year


# ---------------------------------------------------------------------------
# Folding: the form two spellings of one title share (Batch T9)
# ---------------------------------------------------------------------------

_NUMBER_WORDS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
}
_ROMAN = {
    "i": "1",
    "ii": "2",
    "iii": "3",
    "iv": "4",
    "v": "5",
    "vi": "6",
    "vii": "7",
    "viii": "8",
    "ix": "9",
    "x": "10",
}
#: Words after which a roman numeral is a number. Elsewhere "I" is a pronoun.
_NUMBERED_BY = {"part", "episode", "chapter", "volume", "vol"}
ARTICLES = frozenset({"the", "a", "an"})
_CONJUNCTIONS = {"&": " and ", "+": " and "}


def fold(title: str) -> str:
    """Reduce a title to the form two spellings of one title share.

    Accents go ("Léon"), and so do apostrophes ("Lampoon's"), full stops ("U.S.", "Dr.") and
    other punctuation. "&", "+", "v" and "vs" read as "and", so "Cowboys v Aliens" meets
    "Cowboys & Aliens", and "Vol." reads as "Volume". Numbers are written as digits, so "Dune
    2" meets "Dune: Part Two" and "Star Wars Ep IV" meets "Star Wars: Episode IV": number
    words always, roman numerals after "Part", "Episode", "Ep" or "Vol", and a trailing "Part"
    or "Ep" is dropped before them.
    Both sides of every comparison are folded the same way, so none of this can make two
    different titles equal unless they differ only in these ways.
    """
    text = unicodedata.normalize("NFKD", title)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    for symbol, word in _CONJUNCTIONS.items():
        text = text.replace(symbol, word)
    text = re.sub(r"[’'`\.]", "", text)
    text = re.sub(r"[^\w\s]", " ", text).replace("_", " ")
    words = text.split()
    out: list[str] = []
    for index, word in enumerate(words):
        before = words[index - 1] if index else ""
        if word in ("v", "vs", "versus") and 0 < index < len(words) - 1:
            out.append("and")
        elif word == "ep":
            out.append("episode")
        elif word == "vol":
            # Batch X9 (CT46-05): Blu-ray.com's "Kill Bill: Vol. 1" is TMDB's "Volume 1".
            out.append("volume")
        elif word in _NUMBER_WORDS:
            out.append(_NUMBER_WORDS[word])
        elif word in _ROMAN and (
            (index and (before in _NUMBERED_BY or before == "ep"))
            or (index == len(words) - 1 and len(word) > 1)
        ):
            out.append(_ROMAN[word])
        else:
            out.append(word)
    # "Part 2" and "2" are the same instalment; "Episode 4" keeps its word, because TMDB
    # always writes it out.
    joined = " ".join(out)
    return re.sub(r"\bpart (\d+)\b", r"\1", joined)


def bare(folded: str) -> str:
    """A folded title without its leading article: "the sorcerer" and "sorcerer" meet."""
    words = folded.split()
    if len(words) > 1 and words[0] in ARTICLES:
        return " ".join(words[1:])
    return folded


# ---------------------------------------------------------------------------
# The levels
# ---------------------------------------------------------------------------


class Strictness(enum.Enum):
    """How much of a title two spellings may differ in and still be one title."""

    #: The same words, spelled alike; order and article kept.
    WORDS = "words"
    #: The same catalogue entry: notes, year, edition, library order and article aside.
    TITLE = "title"


def title_key(title: str, level: Strictness) -> str:
    """The form of ``title`` that equals another's exactly when they are one title at
    ``level``."""
    if level is Strictness.WORDS:
        return fold(title)
    cleaned, _year = normalise_query(title)
    return bare(fold(cleaned))


def title_key_and_year(title: str) -> tuple[str, int | None]:
    """A catalogue entry's :attr:`Strictness.TITLE` key, and the year its brackets gave."""
    cleaned, year = normalise_query(title)
    return bare(fold(cleaned)), year


def same_title(a: str, b: str, level: Strictness) -> bool:
    """Whether two titles are one title at ``level``. An empty key is no title."""
    key = title_key(a, level)
    return bool(key) and key == title_key(b, level)
