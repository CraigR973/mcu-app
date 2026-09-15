"""Reading the public Letterboxd diary RSS feed — Batch S5, snag 10a.

**Sanctioned, credential-free, and not a scraper.** `letterboxd.com/<user>/rss` is a
public feed Letterboxd publishes for this purpose. `DECISIONS.md` #161 draws the line:
S8 imports a file that already exists, S5 reads this feed, and **no scraper, no Cloudflare
dependency and no stored Letterboxd credential ever ships**.

**What the feed carries**, measured across 100 entries from both diaries on 2026-09-14
(`OWNER-ACTIONS.md` 1f, `DECISIONS.md` #158, #159):

- ``<letterboxd:watchedDate>`` — a plain ``YYYY-MM-DD``, exactly what ``watch_log.watched_at``
  wants. **Not** ``<pubDate>``, which is when the entry was *posted*.
- ``<letterboxd:rewatch>`` — ``Yes``/``No``.
- ``<letterboxd:memberRating>`` — half-stars. **Craig 50 of 50, Mark 0 of 50**, so a null
  here is correct data and must not be treated as missing.
- ``<letterboxd:filmTitle>`` and ``<letterboxd:filmYear>``.
- ``<tmdb:movieId>`` — **on 100 of 100 entries**, which is what lets a sync *identify* a
  film as well as log the watch.
- ``<guid>`` — a stable ``letterboxd-watch-<id>``.

**The guid is the whole point of reusing S8.** The number it wraps is the same
``ViewingId`` the diary CSV carries, so a viewing present in both file and feed becomes
exactly one ``watch_log`` row (#176). This module's only job is to turn XML into the
:class:`~.diary.DiaryEntry` S8 already knows how to match and write.

----

**A caveat that the first live fetch will settle, and nothing else can.** The element
*names* above are a recorded measurement of the real feeds. The exact XML — namespace
URIs, prefixes, nesting — is not, because capturing it needs a live third-party request
and `docs/agent-commands/group-start.md` keeps those out of unattended runs.

So the parser is deliberately built not to care: it matches on **local names**, ignoring
namespace prefixes entirely, and falls back to RSS's own ``<title>`` when the namespaced
title is absent. That is the right shape regardless, but it is chosen here *because* the
fixture is constructed from a measurement rather than captured from the wire. `AGENTS.md`
says to work from real payloads; where that is not available unattended, the honest
substitute is a parser with no opinions about the parts that were not measured — and an
owner action that checks (`OWNER-ACTIONS.md` 1j).
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

import httpx

from src.services.letterboxd.diary import DiaryEntry, DiaryParseError

FEED_URL_TEMPLATE = "https://letterboxd.com/{username}/rss/"

#: Letterboxd's own username alphabet, mirrored from the CHECK on
#: ``profiles.letterboxd_username``. Applied again here because this value is interpolated
#: into a URL, and "validated on the way in" is not a property a URL builder should assume.
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")

#: ``letterboxd-watch-1489750098`` → ``1489750098``. The bare number is what S8 stores, so
#: the two sources cannot double-count (`DECISIONS.md` #176).
_GUID_RE = re.compile(r"letterboxd-watch-(\d+)")

#: `<title>` reads "Film Name, 2017 - ★★★★" or "Film Name, 2017". Only used when the
#: namespaced elements are absent — see the caveat above.
_TITLE_RE = re.compile(r"^(?P<title>.+?),\s*(?P<year>\d{4})\b")

#: The feed returns the most recent 50 viewings and no more. Not a page size to raise:
#: it is Letterboxd's, and it is why the sync interval is a correctness property.
FEED_ENTRY_CAP = 50


def feed_url(username: str) -> str:
    """The public diary feed for a username.

    Refuses anything outside Letterboxd's username alphabet rather than escaping it. A
    username is chosen from a short list by the two people who use this app; a value that
    needed escaping would be a mistake somewhere upstream, and quietly encoding it would
    hide that.
    """
    if not _USERNAME_RE.match(username or ""):
        raise DiaryParseError(f"{username!r} is not a Letterboxd username")
    return FEED_URL_TEMPLATE.format(username=username)


def _local(tag: str) -> str:
    """The tag without its namespace: ``{http://…}filmTitle`` → ``filmTitle``."""
    return tag.rpartition("}")[2]


def _find(item: ElementTree.Element, name: str) -> str | None:
    """First child whose *local* name matches, ignoring namespace prefixes entirely."""
    for child in item:
        if _local(child.tag) == name:
            text = (child.text or "").strip()
            return text or None
    return None


def _parse_rating(raw: str | None) -> Decimal | None:
    """**Mark rates nothing — 0 of 50** (`DECISIONS.md` #159).

    A null here is correct data, so it returns ``None`` rather than raising. A rating that
    is present but unparseable is also ``None``: the watch is worth keeping even when the
    opinion attached to it is malformed, and `watch_log.personal_rating` has a CHECK that
    would refuse a bad value anyway.
    """
    if raw is None:
        return None
    try:
        rating = Decimal(raw)
    except InvalidOperation:
        return None
    if not (Decimal("0.5") <= rating <= Decimal("5.0")) or rating % Decimal("0.5") != 0:
        return None
    return rating


def _parse_item(item: ElementTree.Element) -> DiaryEntry | None:
    """One ``<item>`` as a :class:`DiaryEntry`, or ``None`` if it is not a diary entry.

    **A feed carries more than viewings.** Letterboxd puts list publications and reviews
    of unwatched films in the same channel; those have no ``letterboxd-watch-`` guid and
    no watched date, and skipping them is correct rather than a parse failure.
    """
    guid = _find(item, "guid")
    match = _GUID_RE.search(guid or "")
    if match is None:
        return None

    watched_raw = _find(item, "watchedDate")
    if watched_raw is None:
        return None
    try:
        watched_at = date.fromisoformat(watched_raw)
    except ValueError:
        return None

    title = _find(item, "filmTitle")
    year_raw = _find(item, "filmYear")
    if title is None:
        # RSS's own `<title>`, which reads "Film Name, 2017 - ★★★★".
        fallback = _find(item, "title") or ""
        parsed = _TITLE_RE.match(fallback)
        if parsed is None:
            return None
        title = parsed.group("title").strip()
        year_raw = year_raw or parsed.group("year")

    tmdb_raw = _find(item, "movieId")
    try:
        tmdb_id = int(tmdb_raw) if tmdb_raw else None
    except ValueError:
        tmdb_id = None

    try:
        year = int(year_raw) if year_raw else None
    except ValueError:
        year = None

    return DiaryEntry(
        viewing_id=match.group(1),
        watched_at=watched_at,
        title=title,
        year=year,
        rating=_parse_rating(_find(item, "memberRating")),
        is_rewatch=(_find(item, "rewatch") or "").strip().lower() in {"yes", "true", "1"},
        tmdb_id=tmdb_id,
    )


def parse_feed(xml: str) -> list[DiaryEntry]:
    """Every diary viewing in a feed document, newest first as Letterboxd orders them."""
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise DiaryParseError(f"the feed is not XML: {exc}") from exc

    items = [element for element in root.iter() if _local(element.tag) == "item"]
    entries = [entry for entry in (_parse_item(item) for item in items) if entry is not None]

    # Belt and braces against a feed that repeats a guid: S8's writer skips a repeat, but
    # the count in the sync record should describe viewings rather than lines.
    seen: set[str] = set()
    unique: list[DiaryEntry] = []
    for entry in entries:
        if entry.viewing_id in seen:
            continue
        seen.add(entry.viewing_id)
        unique.append(entry)
    return unique


async def fetch_feed(username: str, *, client: httpx.AsyncClient | None = None) -> list[DiaryEntry]:
    """Fetch and parse one person's public diary feed.

    **This is the one live third-party request in the batch**, and it is why the first real
    sync is an owner action (`OWNER-ACTIONS.md` 1j). Everything above it is tested against
    fixtures and runs unattended.
    """
    url = feed_url(username)
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=20.0, follow_redirects=True)
    try:
        response = await http.get(url, headers={"Accept": "application/rss+xml, application/xml"})
        response.raise_for_status()
        return parse_feed(response.text)
    finally:
        if owns_client:
            await http.aclose()
