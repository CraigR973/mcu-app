"""Parsing a Blu-ray.com release page — §3.7.

**Read `DECISIONS.md` #110 before changing anything here.** It is the governing decision and
it is a *risk acceptance*, not a permission: the site's Legal Notices prohibit automated
reuse, and #108's earlier claim that absence from `robots.txt` made this allowed was wrong.
The owner accepted the stated consequences within strict bounds, and several of those bounds
are enforced by this module rather than merely described by it:

- **Exact release URLs only.** :func:`is_release_url` refuses anything else, and the
  disallowed search routes are refused by name.
- **No prices, reviews, ratings or member content.** The page carries a list price and an
  Amazon price in the same document — #91 ruled those out as third-party numbers nobody can
  pay, and #110 forbids extracting them. :func:`extract` never reads them, and
  :func:`assert_no_price_fields` is the test's way of proving it.

**Three facts measured against a real page on 2026-09-09** (#108), each of which changes the
code:

1. **Audio and subtitles appear twice** in the flattened text, behind `(more)`/`(less)`
   toggles. Extraction targets the DOM node, never the page's text — reading the text gives
   every track twice.
2. **`Special Features` was absent** from that page despite being one of §3.7's five fields.
   It is nullable, not assumed.
3. The page is UK-specific, which is the region this collection is in — so `region_code`
   means something here rather than being an American artifact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag

#: The only host this module will look at.
ALLOWED_HOST = "blu-ray.com"

#: `robots.txt` disallows these, and #110 forbids them independently of that. Named
#: explicitly so a future "just search for the title" is a refusal rather than a diff.
DISALLOWED_PATH_PREFIXES = ("/search/", "/movies/search.php", "/search")

#: A release page: `/movies/<Slug>/<id>/`. Anything else — a person's profile, a forum
#: thread, a review — is out of bounds.
_RELEASE_PATH = re.compile(r"^/movies/[^/]+/\d+/?$")

#: What the video block can say. Order matters: "Native 4K" must be tested before "4K".
_RESOLUTION_PATTERNS = (
    ("2160p", re.compile(r"2160p|native 4k|4k \(2160p\)", re.I)),
    ("1080p", re.compile(r"1080p", re.I)),
    ("1080i", re.compile(r"1080i", re.I)),
    ("720p", re.compile(r"720p", re.I)),
    ("480p", re.compile(r"480[ip]", re.I)),
)

#: HDR formats, longest-first so "HDR10+" is never matched as "HDR10".
_HDR_PATTERNS = (
    ("Dolby Vision", re.compile(r"dolby vision", re.I)),
    ("HDR10+", re.compile(r"hdr10\+", re.I)),
    ("HDR10", re.compile(r"hdr10(?!\+)", re.I)),
    ("HLG", re.compile(r"\bHLG\b")),
)

_AUDIO_PATTERNS = (
    ("Dolby Atmos", re.compile(r"dolby atmos", re.I)),
    ("DTS:X", re.compile(r"dts:\s?x", re.I)),
    ("Dolby TrueHD", re.compile(r"dolby truehd", re.I)),
    ("DTS-HD MA", re.compile(r"dts-hd (master audio|ma)", re.I)),
    ("Dolby Digital Plus", re.compile(r"dolby digital plus|ddp|e-ac-3", re.I)),
    ("Dolby Digital", re.compile(r"dolby digital(?! plus)", re.I)),
    ("DTS", re.compile(r"\bDTS\b(?!-HD|:)")),
    ("LPCM", re.compile(r"lpcm|linear pcm", re.I)),
)

_CHANNELS = re.compile(r"\b(\d\.\d(?:\.\d)?)\b")

#: Every label this module will ever read out of the page. **Anything not on this list is
#: not extracted**, which is how "no prices, reviews, ratings" stays true as the parser
#: grows rather than being a promise in a docstring.
READABLE_LABELS = frozenset(
    {
        "codec",
        "resolution",
        "hdr",
        "aspect ratio",
        "original aspect ratio",
        "video",
        "audio",
        "subtitles",
        "discs",
        "region",
        "special features",
        "studio",
        "distributor",
        "release date",
    }
)

#: Labels present on the page that must never be read. Named so the intent is testable.
FORBIDDEN_LABELS = frozenset(
    {
        "price",
        "amazon",
        "list price",
        "user rating",
        "critic rating",
        "review",
        "overall",
        "video rating",
        "audio rating",
        "extras rating",
        "forum",
        "members",
        "wishlist",
    }
)


class OutOfBounds(Exception):
    """The URL is outside what #110 permits. Never fetched."""


def is_release_url(url: str) -> bool:
    """Is this an exact Blu-ray.com release page?

    The whole of #110's "exact release URLs only, never the search routes", in one
    predicate — so there is one place to read and one place to test.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme not in ("http", "https"):
        return False
    host = (parts.hostname or "").lower().removeprefix("www.")
    if host != ALLOWED_HOST:
        return False
    path = parts.path
    if any(path.lower().startswith(prefix) for prefix in DISALLOWED_PATH_PREFIXES):
        return False
    return bool(_RELEASE_PATH.match(path))


def require_in_bounds(url: str) -> None:
    """Raise unless the URL is one #110 allows. Called before any request."""
    if not is_release_url(url):
        raise OutOfBounds(
            f"{url!r} is not an exact Blu-ray.com release URL. DECISIONS.md #110 permits "
            "only those, and never the site's search routes."
        )


@dataclass
class DiscSpecs:
    """What §3.7 asks for, and nothing else."""

    video: dict[str, Any] = field(default_factory=dict)
    audio: list[dict[str, Any]] = field(default_factory=list)
    #: Nullable rather than assumed — #108 measured a real page with no such section.
    special_features: list[str] | None = None
    region_code: str | None = None
    release_label: str | None = None

    @property
    def is_empty(self) -> bool:
        return not self.video and not self.audio and not self.region_code


def _label_of(node: Tag) -> str:
    """The bolded label a spec row starts with, lower-cased."""
    strong = node.find(["strong", "b"])
    text = strong.get_text(" ", strip=True) if isinstance(strong, Tag) else ""
    return text.rstrip(":").strip().lower()


def _rows(soup: BeautifulSoup) -> list[tuple[str, Tag]]:
    """Every labelled block on the page, as `(label, node)`.

    **Nodes, not text.** #108's second measured fact: audio and subtitles appear twice in
    the flattened page text because of the `(more)`/`(less)` toggles, so anything reading
    `soup.get_text()` sees every track listed twice and cannot tell which copy is which.
    """
    found: list[tuple[str, Tag]] = []
    for node in soup.find_all(["div", "p", "li", "td"]):
        if not isinstance(node, Tag):
            continue
        label = _label_of(node)
        if label and label in READABLE_LABELS:
            found.append((label, node))
    return found


def _value_of(node: Tag) -> str:
    """The text after the label."""
    strong = node.find(["strong", "b"])
    if isinstance(strong, Tag):
        strong.extract()
    return node.get_text(" ", strip=True).lstrip(":").strip()


def _first_match(text: str, patterns: tuple[tuple[str, re.Pattern[str]], ...]) -> str | None:
    for name, pattern in patterns:
        if pattern.search(text):
            return name
    return None


def _all_matches(text: str, patterns: tuple[tuple[str, re.Pattern[str]], ...]) -> list[str]:
    return [name for name, pattern in patterns if pattern.search(text)]


def extract(html: str) -> DiscSpecs:
    """Pull §3.7's five fields out of one release page.

    Never touches a price, a rating or a review — see :data:`FORBIDDEN_LABELS`. The parser
    reads only the labels on :data:`READABLE_LABELS`, which is the mechanism rather than
    the intention.
    """
    soup = BeautifulSoup(html, "html.parser")
    specs = DiscSpecs()
    seen_audio: set[str] = set()

    for label, node in _rows(soup):
        value = _value_of(node)
        if not value:
            continue

        if label == "codec":
            specs.video["codec"] = value.split(",")[0].strip()
        elif label == "resolution":
            resolution = _first_match(value, _RESOLUTION_PATTERNS)
            if resolution:
                specs.video["resolution"] = resolution
            specs.video.setdefault("resolution_raw", value)
        elif label == "hdr":
            hdr = _all_matches(value, _HDR_PATTERNS)
            if hdr:
                specs.video["hdr"] = hdr
        elif label in ("aspect ratio", "original aspect ratio"):
            specs.video.setdefault("aspect_ratio", value.split(",")[0].strip())
        elif label == "audio":
            for line in _audio_lines(node):
                track = _parse_audio_line(line)
                # De-duplicated because the same block is rendered twice behind the
                # `(more)` toggle. Keyed on the whole track, not the language, so English
                # Atmos and English TrueHD 7.1 are both kept.
                key = f"{track.get('language')}|{track.get('format')}|{track.get('channels')}"
                if track.get("format") and key not in seen_audio:
                    seen_audio.add(key)
                    specs.audio.append(track)
        elif label == "region":
            specs.region_code = _parse_region(value)
        elif label == "special features":
            features = [part.strip() for part in re.split(r"\n|;|•", value) if part.strip()]
            specs.special_features = features or None
        elif label in ("studio", "distributor"):
            specs.release_label = specs.release_label or value.split(",")[0].strip()

    return specs


def _audio_lines(node: Tag) -> list[str]:
    """One string per audio track, from the DOM rather than the flattened text."""
    lines = [
        part.get_text(" ", strip=True)
        for part in node.find_all(["li", "div", "span"])
        if isinstance(part, Tag) and part.get_text(strip=True)
    ]
    if lines:
        return lines
    # A page that lists tracks as `<br>`-separated text rather than elements.
    return [line.strip() for line in _value_of(node).split("\n") if line.strip()]


def _parse_audio_line(line: str) -> dict[str, Any]:
    track: dict[str, Any] = {}
    language, _, rest = line.partition(":")
    if rest:
        track["language"] = language.strip()
        line = rest
    audio_format = _first_match(line, _AUDIO_PATTERNS)
    if audio_format:
        track["format"] = audio_format
    channels = _CHANNELS.search(line)
    if channels:
        track["channels"] = channels.group(1)
    return track


def _parse_region(value: str) -> str | None:
    """ "Region free", "Region B", "A, B, C" — normalised, and never invented."""
    lowered = value.lower()
    if "free" in lowered or "all" in lowered:
        return "Free"
    letters = re.findall(r"\bregion\s*([ABC])\b", value, re.I) or re.findall(r"\b([ABC])\b", value)
    unique = sorted({letter.upper() for letter in letters})
    return "/".join(unique) if unique else None


def assert_no_price_fields(specs: DiscSpecs) -> None:
    """Prove the extraction carries nothing #110 forbids.

    Called by the tests, and cheap enough to call anywhere. The page really does put a list
    price and an Amazon price in the same document as the specs — #108 says the temptation
    is "unusually close to hand", and this is the check that it was resisted.
    """
    blob = repr(specs).lower()
    for forbidden in ("price", "£", "$", "rating", "review", "amazon"):
        if forbidden in blob:
            raise AssertionError(f"extracted specs contain a forbidden field: {forbidden!r}")
