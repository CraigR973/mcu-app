"""AA10c: the stand-in and today's used median, judged against recorded sales (#394).

The arithmetic runs anywhere. The two selects run against a throwaway Postgres (CI), once
through the session and once as the literal SQL the live script sends, so the live report
reads the rows the tests prove.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.models.deal import Deal
from src.models.ebay_sold import EbayUsedListing
from src.models.movie import Movie
from src.models.valuation import DiscValuation
from src.scripts.stand_in_check import literal_sql, main
from src.services.stand_in_check import (
    LOWER_QUARTILE,
    NEW_SCALED,
    NO_USED_MEDIAN,
    NO_VALUE,
    NOT_PRICED,
    OTHER_BASIS,
    TOO_FEW_SALES,
    USED_MEDIAN,
    DealEvidence,
    DiscEvidence,
    check_deals,
    compare,
    deals_from_rows,
    deals_query,
    discs_from_rows,
    discs_query,
    exclusion,
    gather,
    quantile,
    relative_error,
)

NOW = datetime(2026, 11, 22, 12)
D = Decimal


def disc(
    sales: tuple[str, ...],
    *,
    price: str | None = "10.00",
    used_median: str | None = "10.00",
    basis: str | None = "used_quartile",
    status: str | None = "priced",
) -> DiscEvidence:
    return DiscEvidence(
        movie_id=uuid.uuid4(),
        format_code="blu_ray",
        sales=tuple(D(sale) for sale in sales),
        status=status,
        value_basis=basis,
        price=None if price is None else D(price),
        used_median=None if used_median is None else D(used_median),
    )


# ---------------------------------------------------------------------------
# The arithmetic
# ---------------------------------------------------------------------------


def test_an_error_is_the_figures_distance_from_the_sales_median_as_a_fraction() -> None:
    assert relative_error(D("11.00"), D("10.00")) == D("0.1")
    assert relative_error(D("9.00"), D("10.00")) == D("-0.1")
    with pytest.raises(ValueError):
        relative_error(D("1.00"), D("0"))


def test_a_quantile_interpolates_between_the_nearest_ranks() -> None:
    values = [D(v) for v in ("4", "1", "3", "2")]
    assert quantile(values, D("0.5")) == D("2.5")
    assert quantile(values, D("0.25")) == D("1.75")
    assert quantile([D("7")], D("0.75")) == D("7")


def test_each_reason_a_disc_is_left_out() -> None:
    three = ("10", "11", "12")
    assert exclusion(disc(three, status=None, basis=None, price=None)) == NO_VALUE
    assert exclusion(disc(three, status="not_priced", basis=None, price=None)) == NOT_PRICED
    assert exclusion(disc(three, basis="new_scaled")) == NEW_SCALED
    assert exclusion(disc(three, basis="used")) == OTHER_BASIS
    assert exclusion(disc(three, used_median=None)) == NO_USED_MEDIAN
    assert exclusion(disc(("10", "11"))) == TOO_FEW_SALES
    assert exclusion(disc(("10", "11")), min_sales=2) is None
    assert exclusion(disc(three)) is None


def test_the_lower_quartile_is_kept_when_its_typical_miss_is_smaller() -> None:
    # Sales median 10 on each. The quartile misses by 5%, 5%, 20%; the median by 2%, 30%, 30%.
    # The median's bias is nearer zero (+2% against +5%), but its typical miss is larger.
    discs = [
        disc(("9", "10", "11"), price="10.50", used_median="10.20"),
        disc(("9", "10", "11"), price="10.50", used_median="13.00"),
        disc(("9", "10", "11"), price="8.00", used_median="7.00"),
    ]
    found = compare(discs)
    assert found.keep == LOWER_QUARTILE
    assert found.lower_quartile is not None and found.used_median is not None
    assert found.lower_quartile.median_absolute == D("0.0500")
    assert found.used_median.median_absolute == D("0.3000")
    assert found.lower_quartile.median == D("0.0500")
    assert found.used_median.median == D("0.0200")
    assert (found.lower_quartile_closer, found.used_median_closer) == (2, 1)
    # 29 over 30, and 30.2 over 30.
    assert found.lower_quartile.total_ratio == D("0.9667")
    assert found.used_median.total_ratio == D("1.0067")
    assert (found.compared, found.sales_used) == (3, 9)


def test_the_used_median_is_kept_only_when_its_typical_miss_is_smaller() -> None:
    discs = [
        disc(("9", "10", "11"), price="12.00", used_median="10.10"),
        disc(("19", "20", "21"), price="24.00", used_median="20.00"),
    ]
    found = compare(discs)
    assert found.keep == USED_MEDIAN
    assert found.used_median is not None and found.used_median.median_absolute == D("0.0050")


def test_a_level_typical_miss_keeps_the_figure_in_place() -> None:
    found = compare([disc(("9", "10", "11"), price="11.00", used_median="9.00")])
    assert found.lower_quartile is not None and found.used_median is not None
    assert found.lower_quartile.median_absolute == found.used_median.median_absolute
    assert found.keep == LOWER_QUARTILE
    assert (found.lower_quartile_closer, found.used_median_closer) == (0, 0)


def test_the_sales_median_counts_each_sale_once_with_the_valuations_rounding() -> None:
    # Median of 10.00 and 10.01 is 10.005, which the valuation rounds half up to 10.01.
    found = compare([disc(("10.00", "10.01", "9.00", "20.00"), price="10.01")])
    assert found.lower_quartile is not None and found.lower_quartile.median == D("0")


def test_the_counts_cover_every_disc_with_sales_and_nothing_compared_keeps_the_quartile() -> None:
    discs = [
        disc(("10",), status=None, basis=None, price=None),
        disc(("10", "12"), basis="new_scaled"),
        disc(()),  # no sales: not a disc with sales at all
    ]
    found = compare(discs)
    assert (found.discs_with_sales, found.sales_recorded, found.compared) == (2, 3, 0)
    assert found.excluded == {NO_VALUE: 1, NEW_SCALED: 1}
    assert found.lower_quartile is None and found.used_median is None
    assert found.keep == LOWER_QUARTILE


def test_a_deal_at_or_above_its_discs_sales_median_is_counted() -> None:
    deals = [
        DealEvidence(D("10.00"), (D("9"), D("10"), D("11"))),  # at: counted
        DealEvidence(D("12.00"), (D("10"), D("11"))),  # above, on two sales
        DealEvidence(D("8.00"), (D("9"), D("10"), D("11"))),  # under: a real saving
        DealEvidence(D("5.00"), ()),  # no sales: not checkable
    ]
    found = check_deals(deals)
    assert (found.live, found.checkable, found.at_or_above) == (4, 3, 2)
    assert (found.checkable_min, found.at_or_above_min) == (2, 1)


def test_rows_from_postgres_text_and_from_the_driver_read_the_same() -> None:
    movie = uuid.uuid4()
    as_text = {
        "movie_id": str(movie),
        "format_code": "dvd",
        "sales": "{12.50,3.00}",
        "status": "priced",
        "value_basis": "used_quartile",
        "price": "4.00",
        "used_median": None,
    }
    as_driver = as_text | {"movie_id": movie, "sales": [D("3.00"), D("12.50")], "price": D("4")}
    assert discs_from_rows([as_text]) == discs_from_rows([as_driver])
    assert discs_from_rows([as_text])[0].sales == (D("3.00"), D("12.50"))
    assert deals_from_rows([{"price": "7.99", "sales": None}]) == [DealEvidence(D("7.99"), ())]


# ---------------------------------------------------------------------------
# What it reads
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as session:
        yield session


def _film(title: str, tmdb_id: int) -> Movie:
    return Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        year=1975,
        media_type="film",
    )


def _listing(
    film: Movie,
    item: str,
    price: str,
    *,
    status: str = "sold",
    sold: int | None = 1,
    ended: datetime,
) -> EbayUsedListing:
    return EbayUsedListing(
        id=uuid.uuid4(),
        legacy_item_id=item,
        movie_id=film.id,
        format_code="blu_ray",
        price=D(price),
        postage=D("2.00"),
        condition_code="5000",
        first_seen_utc=ended - timedelta(days=7),
        last_seen_utc=ended,
        status=status,
        ended_at_utc=None if status == "active" else ended,
        sold_count=sold,
        found_for=f"film:{film.tmdb_id}",
    )


def _value(film: Movie, *, price: str, used_median: str) -> DiscValuation:
    return DiscValuation(
        id=uuid.uuid4(),
        movie_id=film.id,
        format_code="blu_ray",
        status="priced",
        price=D(price),
        currency="GBP",
        sample_size=5,
        condition_label="Used",
        value_basis="used_quartile",
        used_median=D(used_median),
        used_count=5,
        new_count=0,
        basis="current asking prices",
        search_query=f"{film.title} Blu-ray",
        checked_utc=NOW - timedelta(days=3),
        found_for=f"film:{film.tmdb_id}",
    )


def _deal(film: Movie, price: str, *, expires: datetime, source: str) -> Deal:
    return Deal(
        id=uuid.uuid4(),
        retailer_name_snapshot="eBay",
        movie_id=film.id,
        title_snapshot=f"{film.title} Blu-ray",
        url=f"https://www.ebay.co.uk/itm/{uuid.uuid4().int % 10**12}",
        format_code="blu_ray",
        price=D(price),
        was_price=D("20.00"),
        usual_sources=[{"source": source, "price": "20.00"}],
        expires_at_utc=expires,
        first_seen_at_utc=NOW - timedelta(days=1),
        last_seen_at_utc=NOW - timedelta(days=1),
    )


async def _seed(db: AsyncSession) -> tuple[Movie, Movie]:
    owned = _film("Jaws", 990_002_001)
    tracked = _film("Duel", 990_002_002)
    db.add_all([owned, tracked])
    await db.flush()
    recent = NOW - timedelta(days=5)
    db.add_all(
        [
            _value(owned, price="11.00", used_median="10.00"),
            # Sold: 10+2, 12+2, 14+2. Postage in, each listing once.
            _listing(owned, "1", "10.00", ended=recent),
            _listing(owned, "2", "12.00", sold=4, ended=recent),
            _listing(owned, "3", "14.00", ended=recent),
            # Not sales: ended unsold, sold count zero, still for sale, and one past 90 days.
            _listing(owned, "4", "1.00", status="ended", sold=None, ended=recent),
            _listing(owned, "5", "1.00", sold=0, ended=recent),
            _listing(owned, "6", "1.00", status="active", sold=None, ended=recent),
            _listing(owned, "7", "1.00", ended=NOW - timedelta(days=91)),
            # A film tracked for deals only: sales, no stored value.
            _listing(tracked, "8", "6.00", ended=recent),
            _deal(
                owned,
                "14.00",
                expires=NOW + timedelta(days=2),
                source="3 observed sales, postage in",
            ),
            _deal(
                tracked,
                "7.00",
                expires=NOW + timedelta(days=2),
                source="Lower quartile of used asks, postage in",
            ),
            # Expired, and one judged before AA10b: neither is live.
            _deal(
                owned,
                "1.00",
                expires=NOW - timedelta(hours=1),
                source="3 observed sales, postage in",
            ),
            _deal(owned, "1.00", expires=NOW + timedelta(days=2), source="eBay asking median"),
        ]
    )
    await db.flush()
    return owned, tracked


async def test_it_reads_the_sales_the_valuation_counts_and_only_live_deals(
    db: AsyncSession,
) -> None:
    owned, tracked = await _seed(db)
    discs, deals = await gather(db, now=NOW)
    by_film = {found.movie_id: found for found in discs}
    assert set(by_film) == {owned.id, tracked.id}
    assert by_film[owned.id].sales == (D("12.00"), D("14.00"), D("16.00"))
    assert (by_film[owned.id].price, by_film[owned.id].used_median) == (D("11.00"), D("10.00"))
    assert by_film[tracked.id].status is None and by_film[tracked.id].sales == (D("8.00"),)

    found = compare(discs)
    assert (found.discs_with_sales, found.sales_recorded, found.compared) == (2, 4, 1)
    assert found.excluded == {NO_VALUE: 1}
    assert found.lower_quartile is not None and found.lower_quartile.median == D("-0.2143")
    assert found.used_median is not None and found.used_median.median == D("-0.2857")
    assert found.keep == LOWER_QUARTILE

    assert sorted(deal.price for deal in deals) == [D("7.00"), D("14.00")]
    checked = check_deals(deals)
    assert (checked.live, checked.checkable, checked.at_or_above) == (2, 2, 1)
    assert (checked.checkable_min, checked.at_or_above_min) == (1, 1)


async def test_the_live_scripts_literal_sql_reads_the_same_rows(db: AsyncSession) -> None:
    await _seed(db)
    for query, read in ((discs_query(NOW), discs_from_rows), (deals_query(NOW), deals_from_rows)):
        through_session = read((await db.execute(query)).mappings().all())
        connection = await db.connection()
        through_text = read((await connection.exec_driver_sql(literal_sql(query))).mappings().all())
        assert through_session == through_text
        assert through_session


# ---------------------------------------------------------------------------
# The script
# ---------------------------------------------------------------------------

URL = "postgresql://mcu_readonly:s3cret-pass@ep-quiet-lake-a1b2c3-pooler.eu-west-2.aws.neon.tech/neondb"


def _answers(
    disc_rows: list[dict[str, Any]], deal_rows: list[dict[str, Any]]
) -> httpx.MockTransport:
    replies = iter([disc_rows, deal_rows])
    sent: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent.append(body["query"])
        assert body["query"].lstrip().upper().startswith("SELECT")
        assert "'%% " not in body["query"]  # a LIKE pattern is sent as written
        return httpx.Response(200, json={"command": "SELECT", "fields": [], "rows": next(replies)})

    return httpx.MockTransport(handle)


DISC_ROW = {
    "movie_id": str(uuid.uuid4()),
    "format_code": "blu_ray",
    "sales": "{12.00,14.00,16.00}",
    "status": "priced",
    "value_basis": "used_quartile",
    "price": "13.00",
    "used_median": "10.00",
}


def test_the_script_reports_both_figures_and_the_deals(capsys: pytest.CaptureFixture[str]) -> None:
    transport = _answers([DISC_ROW], [{"price": "15.00", "sales": "{12.00,14.00,16.00}"}])
    assert main([], environ={"NEON_READONLY_URL": URL}, transport=transport, now=NOW) == 0
    out = capsys.readouterr().out
    assert "Compared: 1 discs (3 sales)" in out
    assert "typical miss 7.1%, bias -7.1%" in out
    assert "typical miss 28.6%, bias -28.6%" in out
    assert "Keep: lower quartile" in out
    assert "with recorded sales 1, of which at or above the sales median 1" in out
    assert "s3cret" not in out


def test_the_script_prints_json(capsys: pytest.CaptureFixture[str]) -> None:
    transport = _answers([DISC_ROW], [])
    assert main(["--json"], environ={"NEON_READONLY_URL": URL}, transport=transport, now=NOW) == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer["comparison"]["keep"] == "lower_quartile"
    assert answer["comparison"]["lower_quartile"]["median"] == "-0.0714"
    assert answer["deals"]["live"] == 0


def test_without_the_variable_the_script_sends_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
        raise AssertionError("sent")

    assert main([], environ={}, transport=httpx.MockTransport(refuse)) == 2
    assert "NEON_READONLY_URL is not set" in capsys.readouterr().err
