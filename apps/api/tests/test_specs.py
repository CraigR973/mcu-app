"""§3.7's parser and #110's bounds — Batch 23.

**The fixture is shaped from the page #108 measured on 2026-09-09**, including the two
things that make a naive parser wrong: the audio block rendered twice behind a
`(more)`/`(less)` toggle, and a list price and an Amazon price sitting in the same document
as the specs.

**No test here makes a request.** §3.7's acceptance is a live run against ten real URLs and
that is an owner action — the site's terms prohibit automated access and `DECISIONS.md` #110
is the owner's risk acceptance, not a permission an agent inherits.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.specs_state import SpecsIntegrationState
from src.services.specs.bluray_com import (
    FORBIDDEN_LABELS,
    OutOfBounds,
    assert_no_price_fields,
    extract,
    is_release_url,
    require_in_bounds,
)
from src.services.specs.runner import (
    apply_specs,
    get_state,
    halt,
    run_specs_fetch,
)

#: **The real page, captured verbatim.** `tests/fixtures/bluray_com_release_page.html` is
#: three regions of https://www.blu-ray.com/movies/Fight-Club-Blu-ray/5587/ as the site
#: actually served it on 2026-09-10, price cell included.
#:
#: What was here before was invented — `<div class="row"><strong>Codec:</strong>` — and
#: matched nothing the site has ever served. Every test below passed against it while the
#: scraper read **nothing at all** from ten real pages. `DECISIONS.md` #122.
FIXTURES = Path(__file__).parent / "fixtures"
PAGE = (FIXTURES / "bluray_com_release_page.html").read_text(encoding="utf-8")

#: The same file with its provenance comment removed. The comment quotes the invented
#: markup it replaced, so a test asserting that shape is absent has to read the body.
PAGE_MARKUP = re.sub(r"<!--.*?-->", "", PAGE, flags=re.S)

#: #108's third measured fact: `Special Features` is **absent** from this real page — the
#: list of extras lives inside the editorial review, which #110 puts out of bounds.
PAGE_WITHOUT_FEATURES = PAGE

RELEASE_URL = "https://www.blu-ray.com/movies/Back-to-the-Future-4K-Blu-ray/327607/"


class TestBounds:
    """`DECISIONS.md` #110 — exact release URLs only, never the search routes."""

    def test_a_release_url_is_allowed(self) -> None:
        assert is_release_url(RELEASE_URL)
        assert is_release_url("https://blu-ray.com/movies/Heat/12345")

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.blu-ray.com/search/?quicksearch=heat",
            "https://www.blu-ray.com/movies/search.php?title=heat",
            "https://www.blu-ray.com/movies/",
            "https://www.blu-ray.com/community/forums.php",
            "https://blu-ray.com.evil.example/movies/Heat/1/",
            "https://example.com/movies/Heat/1/",
            "ftp://blu-ray.com/movies/Heat/1/",
        ],
    )
    def test_everything_else_is_refused(self, url: str) -> None:
        """The search routes by name, and every other host and shape by construction."""
        assert not is_release_url(url)

    def test_require_in_bounds_explains_itself(self) -> None:
        with pytest.raises(OutOfBounds, match="#110"):
            require_in_bounds("https://www.blu-ray.com/search/?quicksearch=heat")

    def test_a_lookalike_host_does_not_slip_through(self) -> None:
        """`blu-ray.com.evil.example` ends with the allowed host as a substring."""
        assert not is_release_url("https://blu-ray.com.evil.example/movies/Heat/1/")


class TestTheFixtureIsReal:
    """The guard for the bug that made every other test in this file meaningless.

    A parser can only be trusted against markup the site actually serves. The previous
    fixture was hand-written to match the parser, so the two agreed with each other and
    disagreed with reality — and ten live fetches returned "no specs found on the page"
    while the suite stayed green.
    """

    def test_the_fixture_is_captured_markup_not_an_approximation(self) -> None:
        assert "Captured verbatim from https://www.blu-ray.com/" in PAGE

    def test_the_fixture_uses_the_sites_own_structure(self) -> None:
        """`<span class="subheading">` sections with `<br>`-separated `Label: value` text.

        If a future edit reintroduces `<strong>`-labelled rows, it is writing fiction again.
        """
        assert '<span class="subheading">Video</span>' in PAGE_MARKUP
        assert "Codec: MPEG-4 AVC" in PAGE_MARKUP
        assert "<strong>Codec:" not in PAGE_MARKUP

    def test_the_fixture_still_carries_a_price(self) -> None:
        """#108 calls the temptation "unusually close to hand".

        A fixture with the price cell trimmed out could not prove the parser leaves it.
        """
        assert '<span class="subheading">Price</span>' in PAGE_MARKUP
        assert "List price:" in PAGE_MARKUP


class TestExtraction:
    """§3.7's five fields, read from the page the site really serves."""

    def test_the_video_block_is_read(self) -> None:
        specs = extract(PAGE)

        assert specs.video["codec"] == "MPEG-4 AVC (23.45 Mbps)"
        assert specs.video["resolution"] == "1080p"
        assert specs.video["aspect_ratio"] == "2.40:1"

    def test_nothing_is_read_when_the_markup_is_unrecognised(self) -> None:
        """The failure that should have been loud, made loud.

        `is_empty` is what `apply_specs` checks before writing, so a parser that stops
        matching the site writes nothing rather than blanking a row.
        """
        assert extract("<html><body><p>Codec: HEVC</p></body></html>").is_empty

    def test_hdr_is_read_when_the_page_has_it(self) -> None:
        """Longest-first matching: otherwise every HDR10+ disc is also an HDR10 disc.

        This 2009 Blu-ray has no HDR block at all, so the patterns are exercised directly
        rather than pretending the fixture carries one.
        """
        from src.services.specs.bluray_com import _HDR_PATTERNS, _all_matches

        assert _all_matches("Dolby Vision, HDR10+", _HDR_PATTERNS) == ["Dolby Vision", "HDR10+"]
        assert "HDR10" not in _all_matches("HDR10+", _HDR_PATTERNS)

    def test_the_audio_block_is_not_read_twice(self) -> None:
        """**#108's measured fact**, now against the real toggle.

        The page ships `#shortaudio` and `#longaudio`; the fixture carries both.
        """
        specs = extract(PAGE)

        formats = [track["format"] for track in specs.audio]
        assert formats.count("DTS-HD MA") == 1
        assert len(specs.audio) == 5

    def test_a_track_keeps_its_language_and_channels(self) -> None:
        specs = extract(PAGE)

        lossless = next(t for t in specs.audio if t["format"] == "DTS-HD MA")
        assert lossless["language"] == "English"
        assert lossless["channels"] == "5.1"

    def test_the_more_and_less_toggles_are_not_read_as_tracks(self) -> None:
        """They are anchor text inside the same block, and they are not audio."""
        specs = extract(PAGE)

        assert all(track.get("language") not in ("more", "less") for track in specs.audio)

    def test_region_free_is_normalised(self) -> None:
        """Read from the `Playback` heading — the live page prints no `Region:` label."""
        assert extract(PAGE).region_code == "Free"

    def test_the_studio_becomes_the_release_label(self) -> None:
        """From the studio **link** in the grey header line, not from a `Studio:` label,
        because the live page has no such label."""
        assert extract(PAGE).release_label == "20th Century Fox"

    def test_absent_special_features_stay_null(self) -> None:
        """#108: the field is missing from this real page, so it is nullable not assumed.

        The extras are listed only inside the editorial review, which #110 rules out.
        """
        assert extract(PAGE_WITHOUT_FEATURES).special_features is None

    def test_no_price_rating_or_review_is_extracted(self) -> None:
        """**#110 forbids it and the page puts it in the same document.**

        The fixture carries the site's own price cell — `List price: $7.49` — laid out in
        exactly the shape the parser reads specs from, so this is now a real test of the
        allow-list rather than of a straw man.
        """
        specs = extract(PAGE)

        assert_no_price_fields(specs)
        blob = repr(specs)
        assert "7.49" not in blob
        assert "$" not in blob
        assert "price" not in blob.lower()

    def test_a_price_line_is_refused_even_in_a_readable_section(self) -> None:
        """The allow-list is checked per line, not only per section."""
        from bs4 import BeautifulSoup

        from src.services.specs.bluray_com import _section_rows

        html = '<span class="subheading">Video</span><br>Codec: HEVC<br>List price: $24.99<br>'
        rows = _section_rows(BeautifulSoup(html, "html.parser"))
        assert ("codec", "HEVC") in rows
        assert not any("24.99" in value for _, value in rows)

    def test_the_readable_and_forbidden_label_sets_do_not_overlap(self) -> None:
        """The mechanism, not the intention: a label can be one or the other."""
        from src.services.specs.bluray_com import READABLE_LABELS

        assert READABLE_LABELS.isdisjoint(FORBIDDEN_LABELS)

    def test_an_empty_page_yields_nothing_rather_than_guesses(self) -> None:
        specs = extract("<html><body><p>Nothing here.</p></body></html>")

        assert specs.is_empty


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def item(db: AsyncSession) -> CollectionItem:
    movie = Movie(
        id=uuid.uuid4(), tmdb_id=None, title="Heat", original_title="Heat", media_type="film"
    )
    db.add(movie)
    await db.flush()
    row = CollectionItem(id=uuid.uuid4(), movie_id=movie.id)
    db.add(row)
    await db.flush()
    return row


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class TestPersistence:
    async def test_specs_are_written_with_their_provenance(
        self, db: AsyncSession, item: CollectionItem
    ) -> None:
        """**#110 makes provenance a condition, not a nicety.**

        Without the source URL and fetch time, "remove everything derived from that site"
        is not a query anybody can write — and deletion is what the acceptance rests on.
        """
        now = datetime(2026, 9, 10, 12, 0)

        wrote = await apply_specs(db, item, PAGE, url=RELEASE_URL, now=now)

        assert wrote is True
        assert item.specs_source_url == RELEASE_URL
        assert item.specs_fetched_at_utc == now
        assert item.region_code == "Free"

        # The whole block, not one key. The fixture is a real 1080p Blu-ray now rather
        # than an invented 4K page (#122), and asserting every field is what stops a
        # future parser change from quietly dropping one and still passing.
        assert item.video_specs == {
            "codec": "MPEG-4 AVC (23.45 Mbps)",
            "resolution": "1080p",
            "resolution_raw": "1080p",
            "aspect_ratio": "2.40:1",
        }
        assert item.audio_specs is not None
        assert [track["format"] for track in item.audio_specs] == [
            "DTS-HD MA",
            "DTS",
            "Dolby Digital",
            "Dolby Digital",
            "Dolby Digital",
        ]

    async def test_a_page_with_no_specs_writes_nothing(
        self, db: AsyncSession, item: CollectionItem
    ) -> None:
        wrote = await apply_specs(
            db, item, "<html><body>nope</body></html>", url=RELEASE_URL, now=datetime.now()
        )

        assert wrote is False
        assert item.specs_source_url is None


class TestHaltConditions:
    """#110: a 403, 429 or objection halts **the whole integration**, stickily."""

    async def test_a_403_halts_everything(self, db: AsyncSession, item: CollectionItem) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, text="no")

        async with _client(handler) as client:
            result = await run_specs_fetch(db, [(item.id, RELEASE_URL)], client=client, pause=0)

        assert result.halted is True
        state = await get_state(db)
        assert state.halted is True
        assert "403" in (state.halted_reason or "")

    async def test_a_429_halts_everything(self, db: AsyncSession, item: CollectionItem) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, text="slow down")

        async with _client(handler) as client:
            result = await run_specs_fetch(db, [(item.id, RELEASE_URL)], client=client, pause=0)

        assert result.halted is True

    async def test_a_halt_abandons_the_rest_of_the_batch(
        self, db: AsyncSession, item: CollectionItem
    ) -> None:
        """ "Halts the whole integration" — not "skips this one and carries on"."""
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(403, text="no")

        second = CollectionItem(id=uuid.uuid4(), movie_id=item.movie_id)
        db.add(second)
        await db.flush()

        async with _client(handler) as client:
            await run_specs_fetch(
                db,
                [(item.id, RELEASE_URL), (second.id, RELEASE_URL)],
                client=client,
                pause=0,
            )

        assert len(calls) == 1, "the second URL was never requested"

    async def test_a_halted_integration_fetches_nothing(
        self, db: AsyncSession, item: CollectionItem
    ) -> None:
        """Sticky across runs, because it is a row rather than a variable."""
        await halt(db, "an objection arrived by email")
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(200, text=PAGE)

        async with _client(handler) as client:
            result = await run_specs_fetch(db, [(item.id, RELEASE_URL)], client=client, pause=0)

        assert calls == []
        assert result.halted is True

    async def test_an_ordinary_network_error_does_not_halt(
        self, db: AsyncSession, item: CollectionItem
    ) -> None:
        """A timeout is not being told to stop. Halting on one would be its own outage."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("timed out")

        async with _client(handler) as client:
            result = await run_specs_fetch(db, [(item.id, RELEASE_URL)], client=client, pause=0)

        assert result.halted is False
        assert len(result.failed) == 1
        assert (await get_state(db)).halted is False

    async def test_nothing_in_the_runner_clears_a_halt(self, db: AsyncSession) -> None:
        """#110: resuming needs a new owner decision, not a code path."""
        import src.services.specs.runner as runner

        source = (runner.__file__ or "").rstrip("c")
        with open(source) as handle:
            text = handle.read()

        assert "halted = False" not in text
        assert "halted=False" not in text.replace("halted=False, fetch_count=0", "")


class TestCaching:
    async def test_a_disc_that_already_has_specs_is_not_refetched(
        self, db: AsyncSession, item: CollectionItem
    ) -> None:
        """#110: "cached indefinitely rather than refreshed automatically"."""
        item.specs_source_url = RELEASE_URL
        await db.flush()
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(200, text=PAGE)

        async with _client(handler) as client:
            result = await run_specs_fetch(db, [(item.id, RELEASE_URL)], client=client, pause=0)

        assert calls == []
        assert result.skipped == 1

    async def test_refresh_is_available_but_must_be_asked_for(
        self, db: AsyncSession, item: CollectionItem
    ) -> None:
        item.specs_source_url = RELEASE_URL
        await db.flush()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=PAGE)

        async with _client(handler) as client:
            result = await run_specs_fetch(
                db, [(item.id, RELEASE_URL)], client=client, pause=0, refresh=True
            )

        assert result.updated == 1

    async def test_an_out_of_bounds_url_is_never_requested(
        self, db: AsyncSession, item: CollectionItem
    ) -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(200, text=PAGE)

        async with _client(handler) as client:
            result = await run_specs_fetch(
                db,
                [(item.id, "https://www.blu-ray.com/search/?quicksearch=heat")],
                client=client,
                pause=0,
            )

        assert calls == []
        assert len(result.failed) == 1
        assert "#110" in result.failed[0]["reason"]

    async def test_a_successful_fetch_counts_itself(
        self, db: AsyncSession, item: CollectionItem
    ) -> None:
        """#110 bounds the access; a number nobody counted cannot be shown to be inside it."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=PAGE)

        before = (await get_state(db)).fetch_count
        async with _client(handler) as client:
            await run_specs_fetch(db, [(item.id, RELEASE_URL)], client=client, pause=0)

        assert (await get_state(db)).fetch_count == before + 1


class TestSingletonState:
    async def test_there_is_exactly_one_state_row(self, db: AsyncSession) -> None:
        """A settings table that can grow a second row grows one, and then "is it halted?"
        has two answers."""
        rows = (await db.execute(select(SpecsIntegrationState))).scalars().all()

        assert len(list(rows)) == 1
        assert list(rows)[0].id == 1
