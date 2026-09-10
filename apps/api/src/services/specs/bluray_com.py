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
        # The heading the live site prints the region under: "Playback" → "2K Blu-ray:
        # Region free". Without it on the allow-list the region is silently dropped, which
        # is what the first real run measured.
        "playback",
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
    """The bolded label a spec row starts with, lower-cased.

    Kept for a page that does mark a row up this way. **The live site does not**, which is
    what :func:`_section_rows` is for — see `DECISIONS.md` #122.
    """
    strong = node.find(["strong", "b"])
    text = strong.get_text(" ", strip=True) if isinstance(strong, Tag) else ""
    return text.rstrip(":").strip().lower()


#: The section headings Blu-ray.com prints above each block of specifications, rendered as
#: `<span class="subheading">`. The fields beneath them are plain `Label: value` text
#: separated by `<br>` — **not** `<strong>`-labelled rows, which is what the original
#: parser looked for and why it read nothing from ten real pages.
SECTION_HEADINGS = frozenset({"video", "audio", "subtitles", "discs", "packaging", "playback"})


def _subheadings(soup: BeautifulSoup) -> list[Tag]:
    return [
        node
        for node in soup.find_all("span")
        if isinstance(node, Tag) and "subheading" in (node.get("class") or [])
    ]


def _is_subheading(node: object) -> bool:
    return (
        isinstance(node, Tag) and node.name == "span" and "subheading" in (node.get("class") or [])
    )


def _section_body(heading: Tag) -> list[Tag | str]:
    """Everything between one subheading and the next, as raw siblings."""
    body: list[Tag | str] = []
    for sibling in heading.next_siblings:
        if _is_subheading(sibling):
            break
        if isinstance(sibling, Tag):
            body.append(sibling)
        else:
            text = str(sibling).strip()
            if text:
                body.append(text)
    return body


def _lines(body: list[Tag | str]) -> list[str]:
    """One string per `<br>`-separated line, which is how the site lays a section out."""
    lines: list[str] = []
    current: list[str] = []
    for part in body:
        if isinstance(part, Tag) and part.name == "br":
            joined = " ".join(current).strip()
            if joined:
                lines.append(joined)
            current = []
            continue
        text = part.get_text(" ", strip=True) if isinstance(part, Tag) else part
        if text:
            current.append(text)
    joined = " ".join(current).strip()
    if joined:
        lines.append(joined)
    return lines


def _forbidden(name: str) -> bool:
    """`Price` is a subheading exactly as `Video` is, so this is checked first, always."""
    return name in FORBIDDEN_LABELS or any(bad in name for bad in FORBIDDEN_LABELS)


def _audio_block(body: list[Tag | str]) -> list[str]:
    """The audio track lines, preferring the untruncated `(more)` copy.

    #108's measured fact was that the tracks appear twice, behind a `(more)`/`(less)`
    toggle. Reading only the longer block is why this returns each track once.
    """
    long_block: Tag | None = None
    short_block: Tag | None = None
    for part in body:
        if not isinstance(part, Tag):
            continue
        candidates = ([part] if part.name == "div" else []) + part.find_all("div")
        for node in candidates:
            node_id = str(node.get("id") or "")
            if node_id.startswith("long") and long_block is None:
                long_block = node
            elif node_id.startswith("short") and short_block is None:
                short_block = node

    chosen = long_block or short_block
    source: list[Tag | str] = body
    if chosen is not None:
        source = [child if isinstance(child, Tag) else str(child) for child in chosen.children]
    return [line for line in _lines(source) if line.strip("() ").lower() not in ("more", "less")]


def _section_rows(soup: BeautifulSoup) -> list[tuple[str, str]]:
    """Every readable `(label, value)` on a live release page.

    The label that matters is sometimes the section heading (`Playback`) and sometimes the
    prefix of a line under it (`Codec:`). Both are checked against
    :data:`READABLE_LABELS`, so a heading this code has never seen is ignored rather than
    guessed at, and :data:`FORBIDDEN_LABELS` is checked first — `List price:` is a line
    shaped exactly like `Codec:`.
    """
    rows: list[tuple[str, str]] = []
    for heading in _subheadings(soup):
        name = heading.get_text(" ", strip=True).rstrip(":").strip().lower()
        if _forbidden(name) or name not in SECTION_HEADINGS:
            continue

        body = _section_body(heading)
        if name == "audio":
            rows.extend(("audio", line) for line in _audio_block(body))
            continue

        for line in _lines(body):
            label, _, value = line.partition(":")
            label = label.strip().lower()
            value = value.strip()
            if _forbidden(label):
                continue
            if value and label in READABLE_LABELS:
                rows.append((label, value))
            elif name in READABLE_LABELS:
                # A line with no label of its own, under a heading that has one:
                # "Playback" → "2K Blu-ray: Region free" is the region.
                rows.append((name, line.strip()))
    return rows


def _release_label(soup: BeautifulSoup) -> str | None:
    """The studio, from the grey `Studio | Year | Runtime | Rating | Date` line.

    Read from the studio **link** rather than by splitting that text on `|`, because the
    same line carries the year and the release date and a split would silently take
    whichever came first if the site reordered them.
    """
    for heading in _subheadings(soup):
        if "grey" not in (heading.get("class") or []):
            continue
        link = heading.find("a", href=re.compile(r"studioid="))
        if isinstance(link, Tag):
            text = link.get_text(" ", strip=True)
            if text:
                return text
    return None


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

    for label, value in _section_rows(soup):
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
            track = _parse_audio_line(value)
            # Still de-duplicated: `_audio_block` prefers the untruncated copy, but a page
            # that lists the tracks only once must not depend on that having worked. Keyed
            # on the whole track, not the language, so English Atmos and English TrueHD
            # 7.1 are both kept.
            key = f"{track.get('language')}|{track.get('format')}|{track.get('channels')}"
            if track.get("format") and key not in seen_audio:
                seen_audio.add(key)
                specs.audio.append(track)
        elif label in ("region", "playback"):
            # "Playback" is the heading the live site prints the region under; "Region" is
            # the label a page may put on the line itself. Either can arrive, never both.
            specs.region_code = specs.region_code or _parse_region(value)
        elif label == "special features":
            features = [part.strip() for part in re.split(r"\n|;|•", value) if part.strip()]
            specs.special_features = features or None
        elif label in ("studio", "distributor"):
            specs.release_label = specs.release_label or value.split(",")[0].strip()

    # The live page prints no "Studio:" label at all — the studio is a link in the grey
    # header line, so this is where a real release label actually comes from.
    specs.release_label = specs.release_label or _release_label(soup)
    return specs


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
