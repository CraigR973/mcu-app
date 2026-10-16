"""What a spreadsheet title carries — Batch T9, identifying the unmatched films.

On 25 Sep 366 live films had no TMDB match, and their titles say why: typos ("Peepiing
Tom"), library order ("Mummy, The"), a year outside brackets ("Murder by Decree 1979"), a
person in brackets ("Enforcer, The (Humphrey Bogart}"), a franchise after a dash ("Kingdom of
the Crystal Skull, The - Indiana Jones"), brackets that never close ("Kings Row (1942"), and
TV series ("Steptoe & Son - Complete Series").

**This module only reads a title.** Which film it names comes from TMDB, in ``matcher.py``.
Nothing here calls anything, and nothing here decides: a person named in brackets is a
*hint* until a candidate's credits confirm it, and a reading of the title is a *query* until
TMDB answers it.

**Readings come in tiers**, because splitting a title makes short pieces that can match an
unrelated film exactly. "Lock, Stock and Two Smoking Barrles" split at its comma leaves
"Lock", and TMDB holds a film called "Lock". Tier 1 is the whole title, joined up or
reordered; only a tier-1 match can ever be taken without asking Craig.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from src.matching.engine import rotate_trailing_article

#: Years a film can have. A four-digit number outside them is part of the title, as in
#: "Blade Runner 2049".
FIRST_YEAR = 1888
LAST_YEAR = 2035

#: How alike two folded titles must be to count as the same title with a typo in it.
#: "peepiing tom" and "peeping tom" score 0.96, "scandal street" and "scandal sheet" 0.89.
NEAR_EXACT = 0.9

#: Matches that say the two titles are the same title.
STRONG = ("exact", "words", "typo")

# ---------------------------------------------------------------------------
# Folding: the form two spellings of one title share
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
_ARTICLES = {"the", "a", "an"}
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
    if len(words) > 1 and words[0] in _ARTICLES:
        return " ".join(words[1:])
    return folded


def numbers(folded: str) -> tuple[str, ...]:
    """The numbers in a folded title, which must agree: "Part 1" is never "Part 2"."""
    return tuple(re.findall(r"\d+", folded))


@dataclass(frozen=True)
class TitleMatch:
    """How a candidate's title compares with one reading of ours."""

    how: str  #: "exact", "words", "typo", "subtitle", "tail" or "none"
    ratio: float

    @property
    def near_exact(self) -> bool:
        return self.how != "none"

    @property
    def same_title(self) -> bool:
        """The same title, allowing for a typo: not merely one side of a colon."""
        return self.how in STRONG


_NO_MATCH = TitleMatch("none", 0.0)


def _numbers_agree(ours: str, theirs: str) -> bool:
    """Numbers must be the same, except that a first instalment may say "Part 1" and the
    film itself not: "The Godfather Part I" is TMDB's "The Godfather"."""
    a, b = numbers(ours), numbers(theirs)
    if a == b:
        return True
    return a == ("1",) and not b


def _drop_first_number(folded: str) -> str:
    return re.sub(r"\s*\b1\b", "", folded, count=1).strip()


def compare(reading: str, candidate_title: str) -> TitleMatch:
    """Whether a candidate's title is this reading of ours, and how closely.

    - ``exact``: equal once folded, or once a leading article is ignored.
    - ``words``: the same words in another order ("Dracula Bram Stokers").
    - ``typo``: alike to :data:`NEAR_EXACT` or better, with the same numbers.
    - ``subtitle``: ours is the candidate's title before its colon ("Dr. Strangelove" and
      "Dr. Strangelove or: How I Learned…"), or the candidate's is ours before our colon
      ("Bird: The Charlie Parker Story" and "Bird"). The ``or`` form counts as a colon.
    - ``tail``: ours is the part after the candidate's colon ("Live Baby Live" and "INXS:
      Live Baby Live"). Weakest of all: it is also how a documentary about a film is named
      ("Unseen + Untold: National Lampoon's Animal House").

    Anything else is ``none``, including one title merely containing the other: "Speed" is
    not "Speed 2: Cruise Control".
    """
    ours, theirs = fold(reading), fold(candidate_title)
    if not ours or not theirs:
        return _NO_MATCH
    ratio = SequenceMatcher(None, ours, theirs).ratio()
    if not _numbers_agree(ours, theirs):
        return TitleMatch("none", ratio)
    if numbers(ours) != numbers(theirs):
        ours = _drop_first_number(ours)
        ratio = SequenceMatcher(None, ours, theirs).ratio()
    if ours == theirs or bare(ours) == bare(theirs):
        return TitleMatch("exact", 1.0)
    if sorted(ours.split()) == sorted(theirs.split()):
        return TitleMatch("words", 0.99)
    if ratio >= NEAR_EXACT or SequenceMatcher(None, bare(ours), bare(theirs)).ratio() >= NEAR_EXACT:
        return TitleMatch("typo", max(ratio, 0.9))
    sides = _colon_sides(candidate_title)
    if sides and _same(sides[0], ours):
        return TitleMatch("subtitle", 0.95)
    if len(sides) > 1 and _same(sides[1], ours):
        return TitleMatch("tail", 0.9)
    mine = _colon_sides(reading)
    if mine and _same(mine[0], theirs):
        return TitleMatch("subtitle", 0.95)
    return TitleMatch("none", ratio)


def _same(side: str, folded: str) -> bool:
    """One side of a colon is the whole of the other title. A side that is only a number or
    a word or two of fewer than four letters is too little to say so ("A todo gas: 7")."""
    folded_side = fold(side)
    if len(folded_side.replace(" ", "")) < 4 or folded_side.isdigit():
        return False
    return folded_side == folded or bare(folded_side) == bare(folded)


def _colon_sides(title: str) -> list[str]:
    parts = re.split(r":|\s+or\s*:\s*|\s[-–—]\s", title, maxsplit=1, flags=re.I)
    if len(parts) != 2:
        return []
    head, tail = parts[0].strip(), parts[1].strip()
    head = re.sub(r"\s+or$", "", head, flags=re.I)
    return [side for side in (head, tail) if side]


# ---------------------------------------------------------------------------
# Reading a title
# ---------------------------------------------------------------------------

_HINT_WORDS = {
    "original": "original",
    "the original": "original",
    "remake": "remake",
    "prequel": "prequel",
    "sequel": "sequel",
    "animation": "animation",
    "animated": "animation",
    "live action": "live action",
    "live action movie": "live action",
    "live action film": "live action",
    "movie": "film",
    "the movie": "film",
    "film": "film",
    "tv": "tv",
}

_EDITION = re.compile(
    r"^(?:"
    r"(?:arrow\s+)?blu[\s-]?ray|4k(?:\s+uhd)?|uhd|dvd|3d|"
    r"(?:\d+(?:st|nd|rd|th)\s+)?anniversary(?:\s+edition)?|"
    r"(?:special|collector'?s|limited|extended|ultimate|definitive|deluxe)\s+edition|"
    r"director'?s\s+cut|extended(?:\s+cut)?|theatrical\s+cut|final\s+cut|remastered|restored|"
    r"english\s+version|steelbook|"
    r"(?:itv\s+)?(?:dvd\s+)?box\s*set|boxset"
    r")$",
    re.I,
)
#: Trailing words that say which copy, not which film.
_TRAILING_EDITION = re.compile(
    r"\s+(?:(?:arrow\s+)?blu[\s-]?ray|(?:\d+(?:st|nd|rd|th)\s+)?anniversary(?:\s+edition)?"
    r"|(?:\d+(?:st|nd|rd|th)\s+)?3d)$",
    re.I,
)
_TRAILING_HINT = re.compile(r"\s+(original|remake|prequel)$", re.I)

#: Strong signs of a TV series: the words a box of episodes is sold under. A range of
#: series ("Series 1 - 3"), "Seasons", "Complete Series", "Complete 1st Season".
_TV = re.compile(
    r"\b(?:complete\s+(?:tv\s+)?series|seasons\s+\d|"
    r"(?:series|season)\s+\d+\s*(?:-|&|to)\s*\d+|"
    r"complete\s+(?:\d+(?:st|nd|rd|th)|first|second|third)\s+season|"
    r"\d+(?:st|nd|rd|th)\s+season)\b",
    re.I,
)
#: A part after a dash that is only "Series 5" or "Season 2".
_TV_PART = re.compile(r"^(?:series|seasons?)\s+\d+(?:\s*(?:-|&|to)\s*\d+)?$", re.I)
#: Weaker signs, which need TMDB to agree before a title is set aside as TV. "Season 2" on
#: its own is one: "Game of Thrones Season 1" is TV and "Open Season 2" is a film.
_TV_WEAK = re.compile(r"\b(?:complete\s+collection|bbc|(?:series|season)\s+\d+)\b", re.I)
_TV_TAIL = re.compile(
    r"\s*\b(?:the\s+)?(?:complete\b|series\s+\d|seasons?\s+\d|\d+(?:st|nd|rd|th)\s+season).*$",
    re.I,
)
_LEADING_COMPLETE = re.compile(r"^(?:the\s+)?complete\s+(?=\w)", re.I)
_TEST_ROW = re.compile(r"^test\b.*\d", re.I)

_COMPANION = re.compile(r"^(?:box\s*set\s+)?with\s+", re.I)
_COLLECTION_WORDS = re.compile(
    r"\b(?:the|collection|classics?|coll|vol|volume|box|set|boxset|definitive|early|"
    r"western|complete|series|films?|noir|house|of|out|order|next|to|nb|and)\b|\d+|#",
    re.I,
)
#: Grouping words that are never a person, though they look like a name.
_NOT_PEOPLE = {
    "marvel",
    "ealing",
    "universal",
    "monsters",
    "dinosaurs",
    "star wars",
    "tv",
    "pixar",
    "disney",
    "hammer",
    "digital",
}
_NAME = re.compile(r"^[A-Z](?:[A-Za-z'\-\.]+)?(?:\s+[A-Z](?:[A-Za-z'\-\.]+)?){0,2}$")
_BAND = re.compile(r"^[A-Z0-9/]{2,5}$")
_YEAR_IN = re.compile(r"\b(\d{4})\b")
_DASH = re.compile(r"\s+[-–—]\s*|\s*[-–—]\s+")


def fix_brackets(text: str) -> str:
    """Close what the title opened, the way it opened it.

    "Kings Row (1942" becomes "Kings Row (1942)", "(1940}" becomes "(1940)" and "[Movie}"
    becomes "[Movie]". A brace is read as a mistyped round bracket, and a closing bracket
    with nothing open is dropped.
    """
    out: list[str] = []
    expected: list[str] = []
    for ch in text:
        if ch in "([{":
            expected.append("]" if ch == "[" else ")")
            out.append("(" if ch == "{" else ch)
        elif ch in ")]}":
            if expected:
                out.append(expected.pop())
        else:
            out.append(ch)
    out.extend(reversed(expected))
    return "".join(out)


def _as_year(text: str) -> int | None:
    if re.fullmatch(r"\d{4}", text.strip()):
        year = int(text)
        if FIRST_YEAR <= year <= LAST_YEAR:
            return year
    return None


def _person(text: str) -> str | None:
    """A name, if the text reads like one: capitalised words, not led by an article."""
    cleaned = re.sub(r"'s$", "", text.strip())
    if not cleaned or cleaned.split()[0].lower() in _ARTICLES:
        return None
    if cleaned.lower() in _NOT_PEOPLE:
        return None
    if _NAME.match(cleaned) and len(cleaned.split()) >= 2:
        return cleaned
    return None


def grouping_people(grouping: str | None) -> tuple[str, ...]:
    """Names a disc's grouping carries: "Clint Eastwood", "Powell & Pressburger", "Hitchcock".

    A grouping is Craig's own shelf heading, so it often names the director or star the
    shelf is built around. These are hints like any other: they count only when a
    candidate's credits confirm them, and a surname alone ("Hitchcock") is matched against
    surnames only.
    """
    if not grouping:
        return ()
    found: list[str] = []
    for chunk in re.split(r"\s*(?:/|&|,|\+|\band\b|\s-\s|#)\s*", grouping):
        words = _COLLECTION_WORDS.sub(" ", chunk)
        words = re.sub(r"\s+", " ", words).strip()
        if not words or words.lower() in _NOT_PEOPLE:
            continue
        tokens = words.split()
        if not all(token[:1].isupper() for token in tokens) or len(tokens) > 3:
            continue
        if any(token.lower() in _NOT_PEOPLE for token in tokens):
            continue
        name = " ".join(tokens)
        if name not in found:
            found.append(name)
    return tuple(found)


@dataclass(frozen=True)
class Reading:
    """One way to read the title, as a search and as a comparison."""

    text: str
    tier: int


@dataclass(frozen=True)
class ParsedTitle:
    """Everything a spreadsheet title carries, separated out."""

    raw: str
    #: The title itself: notes, year and edition removed, library order undone.
    main: str
    #: The title as TMDB's TV index would know it: "Game of Thrones", not "... Season 1".
    tv_title: str = ""
    year: int | None = None
    #: The year stood bare at the end ("Cape Fear 1962"), so it may belong to the title.
    year_is_bare: bool = False
    #: Names from brackets or after a dash. The title's own; they must agree with a match.
    people: tuple[str, ...] = ()
    #: Names from the disc's grouping. Weaker: a shelf of Bette Davis films may hold one she
    #: is not in.
    grouping_people: tuple[str, ...] = ()
    #: Name-like parts after a dash ("Indiana Jones", "INXS"). Often a franchise or a band,
    #: so they count if TMDB confirms them and are no objection if it does not.
    weak_people: tuple[str, ...] = ()
    #: "original", "remake", "prequel", "animation", "live action", "film".
    hints: tuple[str, ...] = ()
    #: Other titles the brackets give ("[The Contact Man]").
    alternates: tuple[str, ...] = ()
    #: Why this looks like TV: strong enough to set it aside on its own.
    tv: str | None = None
    #: A weaker sign of TV, which needs TMDB's TV index to agree.
    tv_hint: str | None = None
    not_film: str | None = None
    readings: tuple[Reading, ...] = field(default_factory=tuple)

    @property
    def first_reading(self) -> str:
        return self.readings[0].text if self.readings else self.main


def _rotate(part: str) -> str:
    """Undo library order within one part: "Mummy, The" and "Karate Kid The" both lead with
    their article again. "Godfather, The Part II" keeps its part number at the end."""
    part = re.sub(r"\.\s+(The|A|An)$", r", \1", part.strip())
    numbered = re.match(r"^(.+?),\s*(The|A|An)\s+(Part\s+\S+)$", part, re.I)
    if numbered:
        return f"{numbered.group(2).capitalize()} {numbered.group(1)} {numbered.group(3)}"
    part = re.sub(r"\s*,\s*$", "", part)
    return rotate_trailing_article(part).strip()


_LIBRARY_ORDER = re.compile(r"\s*[,.]\s*(?:The|A|An)(?:\s+Part\s+\S+)?\s*$", re.I)


def _split_at_comma(part: str) -> list[str]:
    """One part, or two when a comma joins two halves of a title.

    "Jurassic Park, The Lost World" is two halves TMDB writes the other way round. "Mummy,
    The" and "Godfather, The Part II" are library order, undone in place, and a comma with
    nothing after it ("Brave,") is dropped.
    """
    part = part.strip().rstrip(",").strip()
    if _LIBRARY_ORDER.search(part) or part.count(",") != 1:
        return [_rotate(part)]
    head, tail = (piece.strip() for piece in part.split(",", 1))
    if not head or not tail:
        return [_rotate(part)]
    return [_rotate(head), _rotate(tail)]


def _note_kind(note: str) -> tuple[str, str]:
    """Classify one bracketed note: ("year"|"hint"|"edition"|"companion"|"person"|"tv"|
    "tv_weak"|"alternate", value)."""
    text = re.sub(r"\s+", " ", note).strip()
    lower = text.lower()
    if not text:
        return "edition", ""
    if (year := _as_year(text)) is not None:
        return "year", str(year)
    if lower in _HINT_WORDS:
        return ("tv", text) if _HINT_WORDS[lower] == "tv" else ("hint", _HINT_WORDS[lower])
    if _EDITION.match(text):
        return "edition", text
    if _COMPANION.match(text):
        return "companion", text
    if _TV.search(text):
        return "tv", text
    if re.search(r"collection|box\s*set", lower):
        people = grouping_people(text)
        if people and _person(people[0]):
            return "person", people[0]
        if _TV_WEAK.search(text):
            return "tv_weak", text
        return "edition", text
    if (person := _person(text)) is not None:
        return "person", person
    return "alternate", text


def _dash_part_kind(part: str) -> tuple[str, str]:
    """Classify a part after a dash: an edition, a hint, TV words, a person, or title."""
    text = part.strip()
    lower = text.lower()
    if _EDITION.match(text):
        return "edition", text
    if lower in _HINT_WORDS and _HINT_WORDS[lower] != "film":
        return "hint", _HINT_WORDS[lower]
    if _TV.search(text) or _TV_PART.match(text):
        return "tv", text
    trailing = _TRAILING_HINT.search(text)
    if trailing:
        person = _person(text[: trailing.start()])
        if person:
            return "person_hint", f"{person}|{trailing.group(1).lower()}"
    return "title", text


def _readings(parts: list[str]) -> tuple[Reading, ...]:
    """The ways to read the title, whole readings first."""
    found: list[Reading] = []

    def add(text: str, tier: int) -> None:
        text = re.sub(r"\s+", " ", text).strip(" ,")
        if text and all(fold(r.text) != fold(text) for r in found):
            found.append(Reading(text, tier))

    parts = [p for p in parts if p]
    if not parts:
        return ()
    add(" ".join(parts), 1)
    if len(parts) == 2:
        add(f"{parts[1]} {parts[0]}", 1)
        # "Mad Max 3, Beyond Thunderdrome": the sequel number is the sheet's, not the title's.
        head = re.sub(r"\s+\d+$", "", parts[0])
        if head != parts[0]:
            add(f"{head} {parts[1]}", 1)
    if len(parts) > 1:
        add(parts[0], 2)
        for part in parts[1:]:
            add(part, 3)
    return tuple(found)


def parse_title(raw: str, grouping: str | None = None) -> ParsedTitle:
    """Read a spreadsheet title into the parts TMDB can use."""
    text = re.sub(r"\s+", " ", fix_brackets(raw)).strip()
    year: int | None = None
    year_is_bare = False
    people: list[str] = []
    weak_people: list[str] = []
    hints: list[str] = []
    alternates: list[str] = []
    tv: str | None = None
    tv_hint: str | None = None

    if _TEST_ROW.match(text):
        return ParsedTitle(raw=raw, main=text, not_film="It reads as a test row, not a film.")

    # Bracketed notes, innermost first.
    note_pattern = re.compile(r"\s*[\(\[]([^\(\)\[\]]*)[\)\]]\s*")
    while (found := note_pattern.search(text)) is not None:
        note = found.group(1)
        text = (text[: found.start()] + " " + text[found.end() :]).strip()
        kind, value = _note_kind(note)
        if kind == "year" and year is None:
            year = int(value)
        elif kind == "year":
            continue
        elif kind == "hint":
            hints.append(value)
        elif kind == "person":
            people.append(value)
        elif kind == "tv":
            tv = tv or f"'{note.strip()}' in the title"
        elif kind == "tv_weak":
            tv_hint = tv_hint or f"'{note.strip()}' in the title"
        elif kind == "alternate":
            inner_year = _YEAR_IN.search(value)
            if inner_year and _as_year(inner_year.group(1)) and year is None:
                year = int(inner_year.group(1))
                rest = _YEAR_IN.sub("", value).strip()
                if rest and _TV_WEAK.search(rest):
                    tv_hint = tv_hint or f"'{note.strip()}' in the title"
                elif rest:
                    alternates.append(rest)
            else:
                alternates.append(value)
    text = re.sub(r"\s+", " ", text).strip()

    # A bare year at the very end.
    bare_year = re.match(r"^(.*?\S)\s+(\d{4})$", text)
    if bare_year and _as_year(bare_year.group(2)) is not None and year is None:
        year = int(bare_year.group(2))
        year_is_bare = True
        text = bare_year.group(1)

    tv_words = _TV.search(text)
    if tv_words is not None:
        tv = tv or f"'{tv_words.group(0)}' in the title"
    weak_words = _TV_WEAK.search(text)
    if weak_words is not None:
        tv_hint = tv_hint or f"'{weak_words.group(0)}' in the title"
        text = re.sub(r"\s*\b(?:the\s+)?complete\s+collection\b", "", text, flags=re.I).strip()
    if grouping and grouping.strip().lower() == "tv":
        tv = tv or "Craig grouped it under 'TV'"

    # Parts: after a dash, then a comma that is not library order.
    parts: list[str] = []
    for index, piece in enumerate(_DASH.split(text)):
        piece = piece.strip()
        if not piece:
            continue
        if index == 0:
            parts.append(piece)
            continue
        kind, value = _dash_part_kind(piece)
        if kind == "edition":
            continue
        if kind == "hint":
            hints.append(value)
        elif kind == "tv":
            tv = tv or f"'{piece}' in the title"
        elif kind == "person_hint":
            person, hint = value.split("|", 1)
            people.append(person)
            hints.append(hint)
        else:
            parts.append(piece)
            named = _person(piece)
            if named is not None:
                weak_people.append(named)
            elif _BAND.match(piece):
                weak_people.append(piece)

    cleaned: list[str] = []
    for part in parts:
        part = _TRAILING_EDITION.sub("", part).strip()
        trailing = _TRAILING_HINT.search(part)
        if trailing is not None:
            hints.append(trailing.group(1).lower())
            part = part[: trailing.start()].strip()
        cleaned.extend(_split_at_comma(part))

    readings = list(_readings(cleaned))
    for alternate in alternates:
        rotated = _rotate(alternate)
        if all(fold(r.text) != fold(rotated) for r in readings):
            readings.append(Reading(rotated, 3))

    main = readings[0].text if readings else text
    tv_title = main
    if tv or tv_hint:
        tv_title = _TV_TAIL.sub("", cleaned[0] if cleaned else main).strip() or main
    # "The Complete Fingerbobs" is a box of episodes of "Fingerbobs".
    leading_complete = _LEADING_COMPLETE.match(main)
    if leading_complete is not None:
        tv_hint = tv_hint or "'Complete' in the title"
        tv_title = main[leading_complete.end() :].strip() or main
    return ParsedTitle(
        raw=raw,
        main=main,
        tv_title=tv_title,
        year=year,
        year_is_bare=year_is_bare,
        people=tuple(dict.fromkeys(people)),
        grouping_people=grouping_people(grouping),
        weak_people=tuple(dict.fromkeys(weak_people)),
        hints=tuple(dict.fromkeys(hints)),
        alternates=tuple(alternates),
        tv=tv,
        tv_hint=tv_hint,
        readings=tuple(readings),
    )


def simplified(text: str) -> str:
    """A reading as TMDB's search handles best: "Ep" spelt out, "&" and "v" as "and", no
    apostrophes or full stops. TMDB found nothing for "Star Wars Ep IV A New Hope" and one
    film for "Star Wars Episode IV A New Hope"."""
    out = re.sub(r"[’'`\.]", "", text)
    out = re.sub(r"\s*&\s*", " and ", out)
    out = re.sub(r"\s+(?:v|vs)\s+", " and ", out, flags=re.I)
    out = re.sub(r"\bEp\b", "Episode", out)
    return re.sub(r"\s+", " ", out).strip()


def without_article(text: str) -> str:
    """ "The Marathon Man" as "Marathon Man": TMDB's search missed the film with the article."""
    words = text.split()
    if len(words) > 1 and words[0].lower() in _ARTICLES:
        return " ".join(words[1:])
    return text


def leading_words(text: str) -> str | None:
    """The first half of a title, for a search that a typo later in it would defeat.

    "Fantastic Beasts and the Crimes of Grindewald" finds nothing; "Fantastic Beasts and"
    finds the film. None when the half would be a single short word.
    """
    words = without_article(simplified(text)).split()
    if len(words) < 2:
        return None
    half = " ".join(words[: (len(words) + 1) // 2])
    return half if len(half) >= 4 and half != text else None
