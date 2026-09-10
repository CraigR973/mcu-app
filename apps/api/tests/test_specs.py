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

import uuid
from collections.abc import AsyncIterator
from datetime import datetime

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

#: A release page, shaped like the one #108 measured. The audio block appears **twice** —
#: that is the `(more)`/`(less)` toggle, and it is the reason extraction targets DOM nodes
#: rather than the flattened text.
PAGE = """
<html><body>
  <div id="specs">
    <div class="row"><strong>Codec:</strong> HEVC / H.265</div>
    <div class="row"><strong>Resolution:</strong> Native 4K (2160p)</div>
    <div class="row"><strong>HDR:</strong> Dolby Vision, HDR10+</div>
    <div class="row"><strong>Aspect ratio:</strong> 2.39:1</div>
    <div class="row"><strong>Audio:</strong>
      <div>English: Dolby Atmos</div>
      <div>English: Dolby TrueHD 7.1 (48kHz, 24-bit)</div>
      <div>French: Dolby Digital 5.1</div>
    </div>
    <div class="row more"><strong>Audio:</strong>
      <div>English: Dolby Atmos</div>
      <div>English: Dolby TrueHD 7.1 (48kHz, 24-bit)</div>
      <div>French: Dolby Digital 5.1</div>
    </div>
    <div class="row"><strong>Region:</strong> 4K Blu-ray: Region free</div>
    <div class="row"><strong>Studio:</strong> Universal Studios</div>
  </div>
  <div id="shop">
    <div><strong>Price:</strong> &pound;34.99</div>
    <div><strong>Amazon:</strong> &pound;24.99</div>
    <div><strong>User rating:</strong> 4.6 / 5</div>
    <div><strong>Review:</strong> A terrific transfer.</div>
  </div>
</body></html>
"""

#: #108's third measured fact: `Special Features` was **absent** from a real page.
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


class TestExtraction:
    """§3.7's five fields, from a page shaped like the one #108 measured."""

    def test_the_video_block_is_read(self) -> None:
        specs = extract(PAGE)

        assert specs.video["codec"] == "HEVC / H.265"
        assert specs.video["resolution"] == "2160p"
        assert specs.video["hdr"] == ["Dolby Vision", "HDR10+"]
        assert specs.video["aspect_ratio"] == "2.39:1"

    def test_hdr10_plus_is_not_read_as_hdr10(self) -> None:
        """Longest-first matching. Otherwise every HDR10+ disc is also an HDR10 disc."""
        specs = extract(PAGE)

        assert "HDR10+" in specs.video["hdr"]
        assert "HDR10" not in specs.video["hdr"]

    def test_the_audio_block_is_not_read_twice(self) -> None:
        """**#108's measured fact.** The `(more)`/`(less)` toggle renders it twice."""
        specs = extract(PAGE)

        formats = [track["format"] for track in specs.audio]
        assert formats.count("Dolby Atmos") == 1
        assert len(specs.audio) == 3

    def test_a_track_keeps_its_language_and_channels(self) -> None:
        specs = extract(PAGE)

        truehd = next(t for t in specs.audio if t["format"] == "Dolby TrueHD")
        assert truehd["language"] == "English"
        assert truehd["channels"] == "7.1"

    def test_region_free_is_normalised(self) -> None:
        assert extract(PAGE).region_code == "Free"

    def test_the_studio_becomes_the_release_label(self) -> None:
        assert extract(PAGE).release_label == "Universal Studios"

    def test_absent_special_features_stay_null(self) -> None:
        """#108: the field was missing from a real page, so it is nullable not assumed."""
        assert extract(PAGE_WITHOUT_FEATURES).special_features is None

    def test_no_price_rating_or_review_is_extracted(self) -> None:
        """**#110 forbids it and the page puts it in the same document.**

        #108 calls the temptation "unusually close to hand" — the fixture therefore carries
        a list price, an Amazon price, a user rating and a review, and none of them may
        appear anywhere in the result.
        """
        specs = extract(PAGE)

        assert_no_price_fields(specs)
        blob = repr(specs)
        assert "34.99" not in blob
        assert "24.99" not in blob
        assert "4.6" not in blob
        assert "terrific" not in blob.lower()

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
        assert item.video_specs is not None and item.video_specs["resolution"] == "2160p"
        assert item.region_code == "Free"

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
