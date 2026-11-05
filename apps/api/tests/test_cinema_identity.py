"""AC3 (#335): identity and run, case by case — the regression list in the ledger."""

from datetime import date, timedelta

from src.services.cinemas.identity import Candidate, Facts, classify, identify, read_title

SHOWN = date(2026, 11, 5)


def film(
    tmdb_id: int,
    title: str,
    released: str | None,
    *uk: str,
    directors=(),
    runtime=None,
    original=None,
    imdb=None,
):
    return Candidate(
        tmdb_id=tmdb_id,
        title=title,
        original_title=original or title,
        release_date=date.fromisoformat(released) if released else None,
        uk_cinema=tuple(sorted(date.fromisoformat(d) for d in uk)),
        directors=tuple(directors),
        runtime=runtime,
        imdb_id=imdb,
    )


def test_a_current_release_links_on_its_uk_date_and_is_a_first_run():
    clayface = film(
        1400940, "Clayface", "2026-10-19", "2026-10-23", directors=["James Watkins"], runtime=109
    )
    decision = identify(read_title("Clayface", SHOWN), Facts(), [clayface], SHOWN)
    assert decision.outcome == "linked"
    assert decision.corroboration == ("a UK cinema release on 2026-10-23, matching the programme",)
    assert classify(clayface.first_uk_release, SHOWN, read_title("Clayface", SHOWN)) == (
        "newRelease",
        "UK release 23 Oct 2026 · first run",
    )


def test_remakes_sharing_a_title_need_a_fact_to_tell_them_apart():
    original = film(1, "Resident Evil", "2002-03-15", "2002-07-12")
    remake = film(2, "Resident Evil", "2026-09-18", "2026-09-18")
    # Nothing but the title, and only the remake is in cinemas now: the programme decides.
    plain = identify(read_title("Resident Evil", SHOWN), Facts(), [original, remake], SHOWN)
    assert plain.outcome == "linked" and plain.candidate == remake
    # A rerun label rules out "in cinemas now"; with no other fact, Craig decides.
    rerun = identify(
        read_title("Resident Evil (4K Restoration)", SHOWN), Facts(), [original, remake], SHOWN
    )
    assert (
        rerun.outcome == "review" and rerun.reason == "the title matches, but nothing else agrees"
    )
    # The cinema's own year settles it.
    dated = identify(
        read_title("Resident Evil (4K Restoration)", SHOWN),
        Facts(year=2002),
        [original, remake],
        SHOWN,
    )
    assert dated.outcome == "linked" and dated.candidate == original


def test_two_corroborated_films_go_to_review_not_a_guess():
    a = film(1, "Wicker", "2026-10-30", "2026-10-30")
    b = film(2, "Wicker", "2026-10-02", "2026-10-02")
    decision = identify(read_title("Wicker", SHOWN), Facts(), [a, b], SHOWN)
    assert decision.outcome == "review" and decision.reason == "more than one film matches"
    assert set(decision.others) == {1, 2}


def test_foreign_and_alternative_titles_match_on_the_original_title():
    candidate = film(
        3,
        "Raise the Red Lantern",
        "1991-09-10",
        "1992-03-27",
        original="大红灯笼高高挂",
        directors=["Zhang Yimou"],
    )
    decision = identify(
        read_title("Raise the Red Lantern", SHOWN),
        Facts(director="Zhang Yimou"),
        [candidate],
        SHOWN,
    )
    assert decision.outcome == "linked" and decision.corroboration == ("the director",)
    original = identify(
        read_title("大红灯笼高高挂", SHOWN), Facts(director="Zhang Yimou"), [candidate], SHOWN
    )
    assert original.outcome == "linked"


def test_an_anniversary_label_dates_the_film_and_makes_a_rerun():
    rocky = film(1366, "Rocky", "1976-11-21", "1977-03-31")
    remake = film(9, "Rocky", "2025-08-01")
    title = read_title("Throwback: Rocky (50th Anniversary)", SHOWN)
    decision = identify(title, Facts(), [rocky, remake], SHOWN)
    assert decision.outcome == "linked" and decision.candidate == rocky
    assert decision.corroboration == ("the anniversary's year 1976",)
    assert classify(rocky.first_uk_release, SHOWN, title) == (
        "olderFilm",
        "UK release 1977 · the cinema calls it an anniversary showing · rerun",
    )


def test_a_preview_before_uk_release_is_a_first_run():
    fjord = film(7, "Fjord", "2026-11-14", "2026-11-14")
    title = read_title("Fjord Unlimited Screening", SHOWN)
    assert title.query == "Fjord" and title.preview
    assert identify(title, Facts(), [fjord], SHOWN).outcome == "linked"
    assert classify(fjord.first_uk_release, SHOWN, title) == (
        "newRelease",
        "UK release 14 Nov 2026 · preview",
    )


def test_four_to_twelve_months_after_release_stays_unclassified():
    shown = date(2026, 11, 5)
    for months in (4, 8, 11):
        released = shown - timedelta(days=30 * months + 5)
        category, reason = classify(released, shown, read_title("A Film", shown))
        assert category == "unclassified", months
        assert reason.endswith("between first run and rerun")
    assert (
        classify(shown - timedelta(weeks=16), shown, read_title("A Film", shown))[0] == "newRelease"
    )
    assert (
        classify(shown - timedelta(days=365), shown, read_title("A Film", shown))[0] == "olderFilm"
    )


def test_events_and_double_bills_never_link():
    for title in (
        "National Theatre Live: Golden Boy",
        "RBO Cinema Season 2026-27: Carmen",
        "Rammstein – Live in Mexico City",
        "Stray Kids World Tour <RUN IT> LIVE VIEWING",
        "Heated Rivalry: Season 01 - Epi 01 & 02",
        "GFF Animated Wednesdays x Manipulate Arts: Horror Shorts",
        "We're Going on a Bear Hunt + The Tiger Who Came to Tea",
    ):
        read = read_title(title, SHOWN)
        assert (
            identify(read, Facts(), [film(1, title, "2026-01-01", "2026-11-01")], SHOWN).outcome
            == "event"
        ), title
    # A discussion after a film is still the film.
    assert read_title("Thorntree + discussion", SHOWN).query == "Thorntree"


def test_a_wrong_year_from_a_source_does_not_corroborate():
    clayface = film(1400940, "Clayface", "2026-10-19", "2026-10-23")
    # The year is wrong, but the UK release still matches the programme on its own.
    decision = identify(read_title("Clayface", SHOWN), Facts(year=1999), [clayface], SHOWN)
    assert "the cinema's year 1999" not in decision.corroboration
    # With a rerun label the programme cannot speak, and the wrong year cannot either.
    labelled = identify(
        read_title("Clayface (Restored)", SHOWN), Facts(year=1999), [clayface], SHOWN
    )
    assert labelled.outcome == "review"


def test_a_source_id_that_disagrees_with_the_title_goes_to_review():
    named = film(55, "Something Else Entirely", "2026-10-01", "2026-10-01")
    decision = identify(read_title("Primetime", SHOWN), Facts(tmdb_id=55), [named], SHOWN)
    assert decision.outcome == "review"
    assert decision.reason == "the cinema's own id names a film with another title"
    agrees = identify(
        read_title("Primetime", SHOWN),
        Facts(tmdb_id=56),
        [film(56, "Primetime", "2026-10-30", "2026-10-30")],
        SHOWN,
    )
    assert agrees.outcome == "linked" and agrees.corroboration == ("the cinema's own id",)


def test_no_uk_cinema_date_stays_unclassified():
    assert classify(None, SHOWN, read_title("A Film", SHOWN)) == (
        "unclassified",
        "no UK cinema release on record",
    )


def test_a_film_named_like_a_label_is_not_a_reissue():
    for title in ("The Restoration", "Reissued Film", "Throwback Thursday", "4K Lives"):
        read = read_title(title, SHOWN)
        assert read.query == title and read.rerun_label is None, title
    labelled = read_title("Reissued Film (4K Restoration)", SHOWN)
    assert labelled.query == "Reissued Film" and labelled.rerun_label == "4k"
    assert read_title("Members' Preview: Fjord", SHOWN).preview
    assert not read_title("The Preview Night", SHOWN).preview
