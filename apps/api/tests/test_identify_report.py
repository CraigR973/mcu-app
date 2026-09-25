"""The dry run's report — Batch T9. Pure rendering, so these run anywhere.

**What this proves:** the report Craig approves states the counts for each outcome, lists
every film that would merge into one he already has with both films named, escapes titles
rather than trusting them, and dates itself the way he reads dates.
"""

from __future__ import annotations

from src.services.identify.plan import PLAN_VERSION, Disc, Item, MergeTarget, Offered, Plan
from src.services.identify.report import render_report


def _offered(title: str, year: int) -> Offered:
    return Offered(
        tmdb_id=year,
        title=title,
        year=year,
        poster_path=None,
        overview="",
        votes=10,
        origin="search",
        notes=["10 TMDB votes"],
    )


def _plan() -> Plan:
    disc = [Disc("blu_ray", "Clint Eastwood", "Back")]
    return Plan(
        version=PLAN_VERSION,
        made_utc="2026-09-25T15:58:04",
        films=4,
        tmdb_calls=1585,
        brave_searches=24,
        brave_budget=60,
        items=[
            Item(
                "a",
                "Beguiled the",
                disc,
                0,
                "identify",
                chosen=_offered("The Beguiled", 1971),
                evidence=["The title matches."],
            ),
            Item(
                "b",
                "Misery",
                disc,
                2,
                "ask",
                reason="Choosing it merges the two.",
                chosen=_offered("Misery", 1990),
                candidates=[_offered("Misery", 1990)],
                merge_into=MergeTarget("m", "Misery", 1990),
            ),
            Item("c", "<script>alert(1)</script>", disc, 0, "ask", reason="No film."),
            Item("d", "Dynasties", disc, 0, "set_aside", set_aside_as="tv", reason="TV."),
        ],
    )


def test_the_report_counts_each_outcome_and_dates_itself_as_craig_reads_dates() -> None:
    page = render_report(_plan(), ceiling_left=1186)

    assert "Made 25 Sep 2026, 15:58 UTC. Nothing has been written." in page
    assert "24 Brave searches; 1,186 of this month" in page
    assert "<b class='ok'>1</b>identified automatically" in page
    assert "<b class='warn'>2</b>wait for you, 1 of them merges" in page
    assert "set aside: 1 TV, 0 not a film" in page


def test_every_merge_is_listed_with_both_films() -> None:
    page = render_report(_plan())

    merges = page.split("Would merge into a film you already have (1)")[1].split("<h2>")[0]
    assert "Would merge into:</b> Misery (1990)" in merges
    assert "This row:</b> Misery" in merges


def test_titles_are_escaped() -> None:
    page = render_report(_plan())

    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page
