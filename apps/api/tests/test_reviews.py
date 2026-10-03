"""Batch V9 — a film's reviews, found with Brave and read within #110 (`DECISIONS.md` #228, #241).

**Every page and answer here is real**, captured on 3 Oct before any code: Blu-ray.com's
US 4K page for Dog Soldiers (the review) and its UK 4K page (no review, linking the editions
that have one), and Brave's answers for Dog Soldiers on Blu-ray.com and AVForums.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.models.reviews import FilmReview
from src.services.reviews.batch import PhaseEnd, _status, _year_problem
from src.services.reviews.bluray_com import format_of, review_scores, reviewed_editions
from src.services.reviews.finding import (
    avforums_hits,
    avforums_query,
    bluray_com_hits,
    bluray_com_query,
    choose,
    choose_bluray_com,
    normalise,
)
from src.services.reviews.read import (
    AVFORUMS_NOTE,
    WAITING_NOTE,
    for_want,
    review_response,
)
from src.services.specs.bluray_com import assert_no_price_fields, extract, extract_year
from src.services.specs.search import SearchHit, hits_from_payload

FIXTURES = Path(__file__).parent / "fixtures"
REVIEW_PAGE = (FIXTURES / "bluray_com_review_page_4k.html").read_text(encoding="utf-8")
NO_REVIEW_PAGE = (FIXTURES / "bluray_com_release_page_no_review.html").read_text(encoding="utf-8")
BRAVE_BLURAY_COM = hits_from_payload(
    json.loads((FIXTURES / "brave_bluray_com_dog_soldiers_4k.json").read_text(encoding="utf-8"))
)
BRAVE_AVFORUMS = hits_from_payload(
    json.loads((FIXTURES / "brave_avforums_dog_soldiers_4k.json").read_text(encoding="utf-8"))
)

US_4K = "https://www.blu-ray.com/movies/Dog-Soldiers-4K-Blu-ray/314666/"
AVFORUMS_4K = "https://www.avforums.com/reviews/dog-soldiers-4k-blu-ray-review-dolby-vision.20024/"


class TestTheFixturesAreCapturedPages:
    """A parser can only be trusted against markup the site serves (#122)."""

    def test_both_pages_say_where_and_when_they_were_captured(self) -> None:
        assert (
            "Captured verbatim from https://www.blu-ray.com/movies/Dog-Soldiers-4K-Blu-ray/314666/"
            in REVIEW_PAGE
        )
        assert (
            "Captured verbatim from https://www.blu-ray.com/movies/Dog-Soldiers-4K-Blu-ray/315545/"
            in NO_REVIEW_PAGE
        )

    def test_the_members_rating_is_kept_so_its_refusal_is_tested(self) -> None:
        assert 'id="user_rating"' in REVIEW_PAGE
        assert "Blu-ray user rating" in REVIEW_PAGE

    def test_the_brave_answers_are_brave_s_own(self) -> None:
        assert len(BRAVE_BLURAY_COM) == 15
        assert len(BRAVE_AVFORUMS) == 18


class TestReadingBlurayComsScores:
    """#228 widened #110 by one thing: the review's own scores, from an exact page."""

    def test_the_review_s_scores_under_the_site_s_headings_out_of_5(self) -> None:
        scores = review_scores(REVIEW_PAGE)

        assert scores is not None
        assert scores.scores == (
            ("Movie", Decimal("3.5")),
            ("Video 4K", Decimal("4.0")),
            ("Video 2K", Decimal("4.5")),
            ("Audio", Decimal("3.5")),
            ("Extras", Decimal("5.0")),
            ("Overall", Decimal("4.0")),
        )
        assert scores.overall == Decimal("4.0")

    def test_a_release_without_a_review_prints_noughts_and_is_read_as_none(self) -> None:
        """The UK page carries the block with every score 0.0: no review."""
        assert 'id="review_rating"' in NO_REVIEW_PAGE
        assert review_scores(NO_REVIEW_PAGE) is None

    def test_the_members_rating_is_never_read(self) -> None:
        """Only `div#review_rating`: a page with the members' block and no review has none."""
        members_only = """
        <div id="user_rating"><table>
          <tr><td>Overall</td><td></td><td><b>4.5</b></td></tr>
        </table></div>
        <div id="bluray_rating"><table>
          <tr><td>Video 4K</td><td></td><td>4.0</td></tr>
        </table></div>
        """
        assert review_scores(members_only) is None

    def test_a_score_off_the_scale_is_not_a_score(self) -> None:
        page = """<div id="review_rating"><table>
          <tr><td>Movie</td><td></td><td>7.5</td></tr>
          <tr><td>Overall</td><td></td><td>4.0</td></tr>
        </table></div>"""
        scores = review_scores(page)
        assert scores is not None
        assert scores.scores == (("Overall", Decimal("4.0")),)

    def test_the_page_s_year_is_still_read_for_the_film_check(self) -> None:
        assert extract_year(REVIEW_PAGE) == 2002
        assert extract_year(NO_REVIEW_PAGE) == 2002

    def test_the_specs_parser_still_reads_no_review(self) -> None:
        """The two parsers never overlap: specs refuse every rating and review label."""
        assert_no_price_fields(extract(REVIEW_PAGE))


class TestTheEditionsAPageLinksAsReviewed:
    def test_the_uk_page_links_two_blu_rays_and_the_us_4k(self) -> None:
        editions = reviewed_editions(NO_REVIEW_PAGE)

        assert [(edition.url, edition.format_code, edition.year) for edition in editions] == [
            ("https://www.blu-ray.com/movies/Dog-Soldiers-Blu-ray/4011/", "blu_ray", 2002),
            ("https://www.blu-ray.com/movies/Dog-Soldiers-Blu-ray/90487/", "blu_ray", 2002),
            (US_4K, "4k_uhd", 2002),
        ]

    def test_the_reviewed_page_links_none(self) -> None:
        assert reviewed_editions(REVIEW_PAGE) == []

    def test_only_exact_release_pages_inside_the_block_are_kept(self) -> None:
        page = """
        <a href="https://www.blu-ray.com/movies/Heat-Blu-ray/1/">outside the block</a>
        <div id="movie_review_other">
          <a href="https://www.blu-ray.com/search/?q=heat" title="Heat (1995)">a search</a>
          <a href="https://forum.blu-ray.com/showthread.php?t=1" title="Heat (1995)">the forum</a>
          <a href="https://blu-ray.com/movies/Heat-4K-Blu-ray/2" title="Heat 4K (1995)">the 4K</a>
        </div>
        """
        editions = reviewed_editions(page)
        assert [(edition.url, edition.format_code) for edition in editions] == [
            ("https://www.blu-ray.com/movies/Heat-4K-Blu-ray/2/", "4k_uhd")
        ]

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            (US_4K, "4k_uhd"),
            ("https://www.blu-ray.com/movies/Dog-Soldiers-Blu-ray/4011/", "blu_ray"),
            ("https://www.blu-ray.com/dvd/Dog-Soldiers-DVD/1/", None),
            ("https://www.blu-ray.com/search/?q=dog", None),
        ],
    )
    def test_a_page_s_format_is_read_from_its_address(self, url: str, expected: str | None) -> None:
        assert format_of(url) == expected


class TestFindingWithBrave:
    """Finding sends neither site a request: Brave proposes, and the title decides."""

    def test_blu_ray_com_s_release_pages_for_the_film_in_brave_s_order(self) -> None:
        hits = bluray_com_hits(BRAVE_BLURAY_COM, "Dog Soldiers")

        assert hits[0].url == US_4K
        assert hits[0].format_code == "4k_uhd"
        assert {hit.format_code for hit in hits} == {"4k_uhd", "blu_ray"}
        # The forum thread in Brave's answer is not a release page.
        assert all("forum." not in hit.url for hit in hits)

    def test_blu_ray_com_s_boilerplate_is_cut_from_brave_s_line(self) -> None:
        hits = bluray_com_hits(BRAVE_BLURAY_COM, "Dog Soldiers")
        assert hits[0].description == "Dog Soldiers 4K Blu-ray Release Date August 23, 2022."

    def test_blu_ray_com_s_review_is_of_the_want_s_format(self) -> None:
        hits = bluray_com_hits(BRAVE_BLURAY_COM, "Dog Soldiers")

        assert choose_bluray_com(hits, "4k_uhd").url == US_4K  # type: ignore[union-attr]
        blu_ray = choose_bluray_com(hits, "blu_ray")
        assert blu_ray is not None and blu_ray.format_code == "blu_ray"
        # A want with no format: 4K first.
        assert choose_bluray_com(hits, None).url == US_4K  # type: ignore[union-attr]
        assert choose_bluray_com(hits, "dvd") is None

    def test_another_film_s_pages_are_not_kept(self) -> None:
        assert bluray_com_hits(BRAVE_BLURAY_COM, "Dog Soldier") == []
        sequel = SearchHit(
            "https://www.blu-ray.com/movies/Dog-Soldiers-2-4K-Blu-ray/1/",
            "Dog Soldiers 2 4K Blu-ray",
            "",
        )
        assert bluray_com_hits([sequel], "Dog Soldiers") == []

    def test_avforums_review_pages_and_not_its_forum_threads(self) -> None:
        hits = avforums_hits(BRAVE_AVFORUMS, "Dog Soldiers")

        assert [(hit.url, hit.format_code) for hit in hits] == [
            (AVFORUMS_4K, "4k_uhd"),
            ("https://www.avforums.com/reviews/dog-soldiers-movie-review.6046/", None),
            ("https://www.avforums.com/reviews/dog-soldiers-blu-ray-review.1967/", "blu_ray"),
        ]
        assert hits[0].title == "Dog Soldiers 4K Blu-ray Review | AVForums"
        # Brave's line is a quote from the review, its <strong> marks gone.
        assert "<strong>" not in hits[0].description
        assert "Dolby Vision" in hits[0].description

    def test_avforums_review_is_the_want_s_format_first(self) -> None:
        hits = avforums_hits(BRAVE_AVFORUMS, "Dog Soldiers")

        assert choose(hits, "4k_uhd").url == AVFORUMS_4K  # type: ignore[union-attr]
        assert choose(hits, "blu_ray").format_code == "blu_ray"  # type: ignore[union-attr]
        assert choose(hits, None).url == AVFORUMS_4K  # type: ignore[union-attr]
        # No DVD review: the best there is.
        assert choose(hits, "dvd").url == AVFORUMS_4K  # type: ignore[union-attr]

    def test_a_sequel_s_review_is_not_the_film_s(self) -> None:
        sequel = SearchHit(
            "https://www.avforums.com/reviews/dog-soldiers-2-4k-blu-ray-review.1/",
            "Dog Soldiers 2 4K Blu-ray Review | AVForums",
            "",
        )
        assert avforums_hits([sequel], "Dog Soldiers") == []

    def test_titles_are_compared_as_words(self) -> None:
        assert normalise("Don't Look Now") == normalise("Dont Look Now") == "dont look now"
        assert normalise("Angels & Demons") == "angels and demons"

    def test_each_search_names_its_site_the_film_and_the_format(self) -> None:
        assert (
            bluray_com_query("Dog Soldiers", 2002, "4k_uhd")
            == "site:blu-ray.com Dog Soldiers 2002 4K Blu-ray review"
        )
        assert bluray_com_query("Heat", None, None) == "site:blu-ray.com Heat Blu-ray review"
        assert (
            avforums_query("Dog Soldiers", 2002, None)
            == "site:avforums.com Dog Soldiers 2002 review"
        )
        assert (
            avforums_query("Heat", 1995, "blu_ray") == "site:avforums.com Heat 1995 Blu-ray review"
        )


def _row(**fields: object) -> FilmReview:
    base: dict[str, object] = {
        "id": uuid.uuid4(),
        "movie_id": uuid.uuid4(),
        "site": "bluray_com",
        "format_code": "4k_uhd",
        "status": "found",
        "url": US_4K,
        "found_via": "brave",
        "found_utc": datetime(2026, 10, 3, 2, 0),
    }
    base.update(fields)
    return FilmReview(**base)  # type: ignore[arg-type]


class TestWhatAPageShows:
    def test_a_want_shows_one_review_per_site_of_its_own_format_first(self) -> None:
        rows = [
            _row(format_code="4k_uhd"),
            _row(
                format_code="blu_ray",
                url="https://www.blu-ray.com/movies/Dog-Soldiers-Blu-ray/4011/",
            ),
            _row(site="avforums", format_code="4k_uhd", url=AVFORUMS_4K),
        ]
        chosen = for_want(rows, "blu_ray")
        assert [(row.site, row.format_code) for row in chosen] == [
            ("bluray_com", "blu_ray"),
            ("avforums", "4k_uhd"),
        ]
        assert [(row.site, row.format_code) for row in for_want(rows, None)] == [
            ("bluray_com", "4k_uhd"),
            ("avforums", "4k_uhd"),
        ]

    def test_a_read_review_carries_its_scores_and_when(self) -> None:
        read_at = datetime(2026, 10, 3, 2, 20)
        response = review_response(
            _row(
                status="scored",
                scores=[{"heading": "Movie", "score": 3.5}, {"heading": "Overall", "score": 4.0}],
                overall=Decimal("4.0"),
                out_of=5,
                scores_read_utc=read_at,
            )
        )
        assert response.siteName == "Blu-ray.com"
        assert [(score.heading, score.score) for score in response.scores] == [
            ("Movie", 3.5),
            ("Overall", 4.0),
        ]
        assert (response.overall, response.outOf, response.note) == (4.0, 5, None)
        assert (
            response.scoresReadAt == read_at.replace(tzinfo=UTC) or response.scoresReadAt == read_at
        )

    def test_a_review_not_yet_read_says_so(self) -> None:
        response = review_response(_row())
        assert response.scores == []
        assert response.overall is None
        assert response.note == WAITING_NOTE

    def test_avforums_says_why_it_has_no_scores(self) -> None:
        response = review_response(_row(site="avforums", url=AVFORUMS_4K))
        assert response.siteName == "AVForums"
        assert response.scores == []
        assert response.note == AVFORUMS_NOTE


class TestTheBatchsSmallRules:
    @pytest.mark.parametrize(
        ("page", "film", "problem"),
        [
            (2002, 2002, None),
            (2003, 2002, None),
            (2004, 2002, "The page is for a 2004 film and this one is from 2002"),
            (None, 2002, "The page shows no year to check"),
            (2002, None, "The film has no year to check the page against"),
        ],
    )
    def test_a_page_must_be_the_film_s_year_give_or_take_one(
        self, page: int | None, film: int | None, problem: str | None
    ) -> None:
        assert _year_problem(page, film) == problem

    def test_a_halt_outranks_a_failure_and_a_failure_a_finish(self) -> None:
        assert _status(PhaseEnd("failed"), PhaseEnd("halted")) == "halted"
        assert _status(PhaseEnd("done"), PhaseEnd("failed")) == "stopped"
        assert _status(PhaseEnd("budget"), PhaseEnd("done")) == "finished"
