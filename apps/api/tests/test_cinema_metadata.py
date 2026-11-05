"""Approved saved metadata, exact mapping review, cached enrichment and budget isolation."""

import copy
import hashlib
import json
import time
from dataclasses import replace
from datetime import date, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from src.models.cinema import CinemaFilm, CinemaRefreshRun, CinemaScreening
from src.services.cinemas import collect, identity, metadata, refresh, store
from src.services.cinemas.domain import Snapshot, SourceError, release_category
from src.services.cinemas.fetch import METADATA_CAP, Budget, Refused
from src.services.cinemas.metadata import Candidate, MappingPick, Metadata, ReleaseEvent
from src.services.cinemas.parsers import parse_vue
from src.services.cinemas.venues import BY_SLUG
from tests.test_cinema_sources import FIXTURES, body
from tests.test_cinemas import api_session as api_session
from tests.test_cinemas import clock as clock
from tests.test_cinemas import run as run

NOW = datetime(2026, 11, 2, 8)
DAY = date(2026, 11, 2)
VENUE = BY_SLUG["vue-st-enoch"]
VUE_PAGE = (
    "<html><title>Vue Glasgow St Enoch Lux Cinema Film Listings &amp; Times | Vue</title></html>"
)
SAMPLES = json.loads(body("tmdb-gap-samples.json"))


@pytest.fixture(autouse=True)
def metadata_clock(monkeypatch):
    monkeypatch.setattr(metadata, "utcnow", lambda: NOW)
    monkeypatch.setattr(collect, "utcnow", lambda: NOW)


def vue_rows():
    data = json.loads(body("vue.json"))
    facts = json.loads(body("vue-film-facts.json"))
    for film in data["result"]:
        film.update(facts[film["filmId"]])
    return parse_vue(data, date(2026, 10, 31), VENUE).rows


def film(title):
    row = next(r for r in vue_rows() if r.title.startswith(title))
    return replace(
        row,
        start=row.start + timedelta(days=2),
        end=row.end + timedelta(days=2) if row.end else None,
        source_local="2026-11-02T20:00:00+00:00",
    )


def snapshot(row):
    return Snapshot(rows=[row], observed_dates={DAY}, complete_dates={DAY}, observed_utc=NOW)


def saved_record(row, index=0):
    """The record AC3's lookup stores for ``row``: one exact-title film, read in detail."""
    sample = SAMPLES[index]
    d = sample["details"]
    return Metadata(
        source="vue",
        film_key=row.film_key,
        fingerprint=metadata.fingerprint(row),
        fetched_utc=NOW,
        state="candidate",
        rule="ac3",
        candidates=[
            Candidate(
                tmdb_id=d["id"],
                title=d["title"],
                original_title=d["original_title"],
                directors=[p["name"] for p in d["directors"]],
                runtime=d["runtime"],
                imdb_id=d["imdb_id"],
                primary_release_date=date.fromisoformat(d["release_date"]),
                gb_theatrical=[
                    ReleaseEvent(
                        date=date.fromisoformat(e["release_date"][:10]),
                        type=e["type"],
                        note=e["note"],
                    )
                    for e in sample["gbReleaseEvents"]
                    if e["type"] in (2, 3)
                ],
            ),
        ],
    )


def handler_for(sample, seen):
    """Build the known API envelope around captured normalised fields, not invented films."""

    def handler(request):
        seen.append(request)
        if request.url.path.endswith("/search/movie"):
            return httpx.Response(200, json={"results": sample["candidates"]})
        if request.url.path.endswith("/release_dates"):
            return httpx.Response(
                200,
                json={
                    "id": sample["candidateId"],
                    "results": [{"iso_3166_1": "GB", "release_dates": sample["gbReleaseEvents"]}],
                },
            )
        d = copy.deepcopy(sample["details"])
        d["credits"] = {
            "crew": [{"name": p["name"], "job": "Director"} for p in d.pop("directors")]
        }
        if "release_dates" in request.url.params.get("append_to_response", ""):
            d["release_dates"] = {
                "results": [{"iso_3166_1": "GB", "release_dates": sample["gbReleaseEvents"]}]
            }
        return httpx.Response(200, json=d)

    return handler


def test_new_metadata_fixtures_retain_recorded_provenance_and_uncertainty():
    for name, record in json.loads(body("metadata-provenance.json")).items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == record["fixtureSha256"]
        assert len(record["sourceSha256"]) == 64
    assert all(s["identity"].startswith("unverified") for s in SAMPLES)
    row = film("Pan's Labyrinth")
    assert row.identity_facts == {
        "director": "Guillermo del Toro",
        "originalTitle": "El Laberinto del Fauno",
        "runtimeMinutes": 119,
    }
    assert row.source_release == date(2026, 10, 30)
    assert row.evidence["returningLabel"] is True
    assert release_category(row.evidence, identity_verified=True) == "unclassified"
    assert film("Clayface").identity_facts["runtimeMinutes"] == 108


async def test_vue_only_today_tomorrow_literal_format_and_later_selection_no_request():
    seen = []

    def handler(request):
        seen.append(request)
        if str(request.url) == VENUE.programme_url:
            return httpx.Response(
                200, text=VUE_PAGE, headers={"Set-Cookie": "vue-anonymous=fixture-cookie; Path=/"}
            )
        return httpx.Response(200, json={"responseCode": 0, "result": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetch = Budget(client)
        result = await collect.collect_venue(VENUE, DAY, DAY + timedelta(days=13), fetch)
        assert result.complete_dates == {DAY, DAY + timedelta(days=1)}
        assert fetch.requests == len(seen) == 3
        assert str(seen[0].url) == VENUE.programme_url
        assert "T00:00:00" in str(seen[1].url) and "%3A" not in str(seen[1].url)
        assert seen[0].headers["Accept"] == "text/html,application/xhtml+xml"
        assert all(r.method == "GET" and "authorization" not in r.headers for r in seen)
        assert all(r.headers["cookie"] == "vue-anonymous=fixture-cookie" for r in seen[1:])
        assert [r.url.params["showingDate"] for r in seen[1:]] == [
            f"{DAY}T00:00:00",
            f"{DAY + timedelta(days=1)}T00:00:00",
        ]
        result = await collect.collect_venue(
            VENUE, DAY + timedelta(days=2), DAY + timedelta(days=3), fetch
        )
        assert result.rows == [] and result.observed_dates == set() and len(seen) == 3
        await fetch.get("https://www.glasgowfilm.org/")
        assert "cookie" not in seen[-1].headers


async def test_vue_refusal_does_not_publish_successful_prefix():
    seen = []

    def handler(request):
        seen.append(request)
        if str(request.url) == VENUE.programme_url:
            return httpx.Response(200, text=VUE_PAGE)
        if request.url.params["showingDate"] == f"{DAY}T00:00:00":
            return httpx.Response(
                200,
                json={
                    "responseCode": 0,
                    "result": [
                        {
                            "filmId": "film-one",
                            "filmTitle": "Film",
                            "showingGroups": [
                                {
                                    "date": str(DAY),
                                    "sessions": [
                                        {
                                            "sessionId": "show-one",
                                            "showTimeWithTimeZone": f"{DAY}T20:00:00+00:00",
                                            "bookingUrl": (
                                                "/book-tickets/summary/10097/film-one/show-one"
                                            ),
                                            "isBookingAvailable": True,
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                },
            )
        return httpx.Response(401)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect.collect_venue(VENUE, DAY, DAY + timedelta(days=13), Budget(client))
    assert result.failed and result.refused_host == "www.myvue.com"
    assert result.complete_dates == set() and len(seen) == 3
    assert len(result.rows) == 1  # Diagnostic only: failed prefixes cannot enrich or replace data.
    assert metadata.selected_rows({VENUE.slug: result}) == {}


@pytest.mark.parametrize("status", [401, 403, 429, 302, 500])
async def test_vue_public_page_failure_never_requests_a_date(status):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(status, headers={"Location": "https://elsewhere.example/"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetch = Budget(client)
        result = await collect.collect_venue(VENUE, DAY, DAY + timedelta(days=1), fetch)
    assert result.failed and not result.rows and not result.complete_dates
    assert fetch.requests == len(seen) == 1 and str(seen[0].url) == VENUE.programme_url


@pytest.mark.parametrize(
    "page", ["<title>Just a moment</title>", "<title>Vue Another Cinema</title>"]
)
async def test_vue_challenge_or_wrong_public_page_never_requests_a_date(page):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, text=page)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect.collect_venue(VENUE, DAY, DAY, Budget(client))
    assert result.failed and not result.rows and not result.complete_dates and len(seen) == 1


@pytest.mark.parametrize("limit", ["requests", "bytes", "deadline", "response"])
async def test_vue_public_page_consumes_existing_limits_before_dates(limit):
    seen = []

    def handler(request):
        seen.append(request)
        if limit == "deadline":
            fetch.started = time.monotonic() - 301
        return httpx.Response(
            200, text="x" * (2 * 1024 * 1024 + 1) if limit == "response" else VUE_PAGE
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetch = Budget(client)
        if limit == "requests":
            fetch.requests = 119
        if limit == "bytes":
            fetch.bytes_read = 64 * 1024 * 1024 - (2 * 1024 * 1024 + 65536) - 1
        result = await collect.collect_venue(VENUE, DAY, DAY, fetch)
    assert result.failed and not result.rows and not result.complete_dates
    assert len(seen) == 1 and str(seen[0].url) == VENUE.programme_url
    if limit == "requests":
        assert fetch.requests == 120


async def test_vue_session_values_never_enter_the_prepared_artifact():
    seen = []

    def handler(request):
        seen.append(request)
        if str(request.url) == VENUE.programme_url:
            return httpx.Response(
                200, text=VUE_PAGE, headers={"Set-Cookie": "vue-anonymous=fixture-cookie; Path=/"}
            )
        return httpx.Response(200, json={"responseCode": 0, "result": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        prepared = await refresh.prepare([VENUE], DAY, DAY, client)
    assert prepared.requests == len(seen) == 2
    assert seen[1].headers["cookie"] == "vue-anonymous=fixture-cookie"
    assert "fixture-cookie" not in prepared.model_dump_json()
    assert "vue-anonymous" not in prepared.model_dump_json()
    old_protocol = json.loads(prepared.model_dump_json())
    old_protocol["adapter_version"] = "ab6-2"
    with pytest.raises(ValueError, match="adapter_version"):
        refresh.PreparedRun.model_validate(old_protocol)


async def test_a_search_and_one_details_call_and_an_agreeing_fact_identify_a_film():
    """AC3 (#335): two requests per film, and a fact must agree before a film is linked."""
    row = film("Clayface")
    seen = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler_for(SAMPLES[0], seen))
    ) as client:
        fetch = Budget(client)
        records, report = await metadata.enrich(
            {VENUE.slug: snapshot(row)}, fetch, "fixture-token", {}
        )
    assert fetch.requests == fetch.metadata_requests == 2 and report["pending"] == 0
    assert seen[1].url.params["append_to_response"] == "credits,release_dates"
    record = records[0]
    assert record.state == "candidate" and [c.tmdb_id for c in record.candidates] == [1400940]
    assert row.tmdb_id is None  # Looking a film up is not linking it.
    shown = row.start.date()
    decision = identity.identify(
        identity.read_title(row.title, shown), metadata.facts_of(row), record.identities(), shown
    )
    assert decision.outcome == "linked" and "the director" in decision.corroboration
    # Title only: no director, running time or release date from the listing.
    bare = replace(row, identity_facts={}, source_release=None)
    alone = identity.identify(
        identity.read_title(bare.title, shown), metadata.facts_of(bare), record.identities(), shown
    )
    # With nothing but the title, the UK release in the programme's weeks still agrees.
    assert alone.outcome == "linked" and alone.corroboration == (
        "a UK cinema release on 2026-10-19, matching the programme",
    )
    assert all(r.headers["authorization"] == "Bearer fixture-token" for r in seen)
    assert all(r.url.host == "api.themoviedb.org" for r in seen)
    assert release_category({"run": "2026"}, identity_verified=True) == "unclassified"


async def test_positive_negative_cache_expiry_fingerprint_and_no_token():
    row = film("Clayface")
    positive = saved_record(row)
    seen = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler_for(SAMPLES[0], seen))
    ) as client:
        fetch = Budget(client)
        records, report = await metadata.enrich(
            {VENUE.slug: snapshot(row)}, fetch, "", {("vue", row.film_key): positive}
        )
        assert records == [positive] and report["cached"] == 1 and not seen
        for record, age in [
            (positive, 30),
            (positive.model_copy(update={"state": "missing", "candidates": []}), 7),
        ]:
            expired = record.model_copy(update={"fetched_utc": NOW - timedelta(days=age)})
            assert not expired.fresh()
            valid = record.model_copy(
                update={"fetched_utc": NOW - timedelta(days=age) + timedelta(seconds=1)}
            )
            assert valid.fresh()
            records, report = await metadata.enrich(
                {VENUE.slug: snapshot(row)}, fetch, "", {("vue", row.film_key): expired}
            )
            assert not records and report["pending"] == 1 and report["status"] == "noToken"
        changed = replace(
            row, identity_facts={**row.identity_facts, "director": "Another director"}
        )
        records, report = await metadata.enrich(
            {VENUE.slug: snapshot(changed)}, fetch, "", {("vue", row.film_key): positive}
        )
        assert not records and report["pending"] == 1 and not seen


async def test_one_lookup_per_film_a_48_request_subcap_and_token_host_isolation():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"results": []})

    # One film listed per showing, as cinematimes and GFT key it, is still one search.
    same = [replace(film("Clayface"), key=f"show-{i}", film_key=f"film-{i}") for i in range(13)]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetch = Budget(client)
        records, report = await metadata.enrich(
            {VENUE.slug: Snapshot(rows=same, observed_utc=NOW)}, fetch, "fixture-token", {}
        )
        assert len(records) == 13 and fetch.requests == 1 and report["lookups"] == 1
        assert {r.state for r in records} == {"missing"}
        # Sixty different films: the sub-cap stops the run, and the rest wait for the next one.
        many = [
            replace(film("Clayface"), key=f"many-{i}", film_key=f"many-{i}", title=f"Film {i}")
            for i in range(60)
        ]
        fetch = Budget(client)
        records, report = await metadata.enrich(
            {VENUE.slug: Snapshot(rows=many, observed_utc=NOW)}, fetch, "fixture-token", {}
        )
        assert METADATA_CAP == 48 and fetch.metadata_requests <= METADATA_CAP
        assert len(records) + report["pending"] == 60 and report["pending"] > 0
        with pytest.raises(SourceError, match="credential sent"):
            await fetch.metadata("https://www.myvue.com/3/test", "fixture-token")
        await fetch.get("https://www.myvue.com/programme")
        assert "authorization" not in seen[-1].headers
        fetch.requests = 120
        with pytest.raises(SourceError, match="limit"):
            await fetch.get("https://www.glasgowfilm.org/")


async def test_a_lookup_keeps_the_votes_of_exact_matches_it_did_not_read():
    """#339: the lookup reads three exact-title films; a fourth it found still counts against
    the famous-classic rule, by its votes from the search."""
    row = replace(film("Clayface"), title="Hamlet")
    found = [
        {"id": 900 + n, "title": "Hamlet", "original_title": "Hamlet", "vote_count": votes}
        for n, votes in enumerate([50, 3000, 20, 150])
    ]

    def handler(request):
        if request.url.path.endswith("/search/movie"):
            return httpx.Response(200, json={"results": found})
        movie_id = int(request.url.path.rsplit("/", 1)[1])
        votes = next(m["vote_count"] for m in found if m["id"] == movie_id)
        return httpx.Response(
            200,
            json={
                "id": movie_id,
                "title": "Hamlet",
                "original_title": "Hamlet",
                "vote_count": votes,
                "credits": {"crew": []},
                "release_dates": {"results": []},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records, _ = await metadata.enrich(
            {VENUE.slug: snapshot(row)}, Budget(client), "fixture-token", {}
        )
    [record] = records
    assert [c.tmdb_id for c in record.candidates] == [900, 901, 902]
    assert [c.vote_count for c in record.identities()] == [50, 3000, 20]
    assert record.unread_votes == 150
    shown = row.start.date()
    title = identity.read_title(row.title, shown)
    facts = metadata.facts_of(replace(row, identity_facts={}, source_release=None))
    unread = identity.identify(
        title, facts, record.identities(), shown, unread_votes=record.unread_votes
    )
    assert unread.outcome == "review"
    # Without the unread film, the 3,000-vote Hamlet is the only famous one, and links.
    alone = identity.identify(title, facts, record.identities(), shown)
    assert alone.outcome == "linked" and alone.candidate.tmdb_id == 901


async def test_two_matching_films_refusals_and_a_spent_budget_never_guess_or_negative_cache():
    row = film("Clayface")
    seen = []
    detailed = handler_for(SAMPLES[0], [])

    def two_films(request):
        seen.append(request)
        if request.url.path.endswith("/search/movie"):
            candidate = SAMPLES[0]["candidates"][0]
            return httpx.Response(200, json={"results": [candidate, {**candidate, "id": 123}]})
        answer = detailed(request)
        body = json.loads(answer.content)
        body["id"] = int(request.url.path.rsplit("/", 1)[-1])
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(two_films)) as client:
        fetch = Budget(client)
        records, report = await metadata.enrich(
            {VENUE.slug: snapshot(row)}, fetch, "fixture-token", {}
        )
    assert [c.tmdb_id for c in records[0].candidates] == [1400940, 123] and len(seen) == 3
    shown = row.start.date()
    decision = identity.identify(
        identity.read_title(row.title, shown),
        metadata.facts_of(replace(row, identity_facts={})),
        records[0].identities(),
        shown,
    )
    assert decision.outcome == "review" and decision.reason == "more than one film matches"
    seen = []

    def refused(request):
        seen.append(request)
        return httpx.Response(403)

    async with httpx.AsyncClient(transport=httpx.MockTransport(refused)) as client:
        fetch = Budget(client)
        snaps = {
            VENUE.slug: Snapshot(
                rows=[row, replace(row, key="2", film_key="2", title="Another")],
                observed_utc=NOW,
            )
        }
        records, report = await metadata.enrich(snaps, fetch, "fixture-token", {})
        assert not records and report["refused"] and report["pending"] == 2 and len(seen) == 1
        with pytest.raises(Refused):
            await fetch.metadata("https://api.themoviedb.org/3/search/movie", "fixture-token")
        assert len(seen) == 1
    async with httpx.AsyncClient(transport=httpx.MockTransport(two_films)) as client:
        fetch = Budget(client)
        fetch.requests = 120
        records, report = await metadata.enrich(
            {VENUE.slug: snapshot(row)}, fetch, "fixture-token", {}
        )
        # Nothing left to spend: no request at all, and nothing cached as "missing".
        assert not records and report["pending"] == 1 and fetch.metadata_requests == 0


def test_a_reviewed_pick_names_a_current_candidate_and_dates_label_the_run():
    row = film("Pan's Labyrinth")
    record = saved_record(row, 2)
    pick = MappingPick(source="vue", film_key=row.film_key, tmdb_id=1417)
    snaps = {VENUE.slug: snapshot(row)}
    assert metadata.validate_picks(snaps, [record], [pick]) == {("vue", row.film_key): 1417}
    for picks, records in [
        ([pick, pick], [record]),
        ([pick.model_copy(update={"tmdb_id": 157336})], [record]),
        ([pick], [record.model_copy(update={"fetched_utc": NOW - timedelta(days=30)})]),
    ]:
        with pytest.raises(SourceError):
            metadata.validate_picks(snaps, records, picks)
    # Craig's pick is the corroboration (#335): a listing with no facts can still be mapped.
    bare = replace(row, identity_facts={})
    assert metadata.validate_picks(
        {VENUE.slug: snapshot(bare)},
        [record.model_copy(update={"fingerprint": metadata.fingerprint(bare)})],
        [pick],
    ) == {("vue", bare.film_key): 1417}
    # The run comes from the UK cinema release, and the cinema's anniversary label.
    shown = row.start.date()
    category, reason = identity.classify(
        record.identities()[0].first_uk_release, shown, identity.read_title(row.title, shown)
    )
    assert category == "olderFilm" and reason.startswith("UK release 2006 · the cinema calls it")
    # #335 supersedes #326/#327/#330: a 2014 film shown in 2026 is a rerun on its date alone.
    interstellar = saved_record(replace(row, title="Interstellar", identity_facts={}), 1)
    first = interstellar.identities()[0].first_uk_release
    assert identity.classify(first, shown, identity.read_title("Interstellar", shown)) == (
        "olderFilm",
        "UK release 2014 · rerun",
    )


async def test_identity_is_linked_kept_through_a_missing_lookup_and_dropped_on_a_changed_listing(
    api_session, run
):
    row = film("Pan's Labyrinth")
    record = saved_record(row, 2)
    key = ("vue", row.film_key)
    snap = snapshot(row)
    await store.promote(api_session, VENUE, snap, DAY, DAY, run.id, {key: record})
    stored = await api_session.scalar(
        select(CinemaFilm).where(CinemaFilm.source == "vue", CinemaFilm.source_key == row.film_key)
    )
    showing = await api_session.scalar(
        select(CinemaScreening).where(CinemaScreening.film_id == stored.id)
    )
    # The Vue listing's director agrees with TMDB's: linked on its own (#335), and a rerun.
    assert stored.identity_status == "verified" and stored.evidence["tmdbId"] == 1417
    assert "the director" in stored.evidence["identity"]["corroboration"]
    assert stored.original_year == 2006 and stored.first_uk_release_date == date(2006, 11, 24)
    assert showing.release_category == "olderFilm"
    assert showing.category_evidence["runReason"].startswith("UK release 2006")
    # A reviewed pick from the refresh CLI is remembered with the listing.
    await store.promote(api_session, VENUE, snap, DAY, DAY, run.id, {key: record}, {key: 1417})
    assert stored.evidence["reviewed"]["tmdbId"] == 1417
    # A run whose lookup is missing keeps the identity while the listing is unchanged.
    await store.promote(api_session, VENUE, snap, DAY, DAY, run.id)
    assert stored.identity_status == "verified" and stored.evidence["tmdbId"] == 1417
    assert showing.release_category == "olderFilm"
    assert (await refresh.metadata_cache(api_session))[key] == record
    # A changed listing is a new question: the old answer and the old review do not carry over.
    changed = replace(row, identity_facts={**row.identity_facts, "director": "Another director"})
    await store.promote(api_session, VENUE, snapshot(changed), DAY, DAY, run.id)
    assert stored.identity_status == "unverified" and stored.movie_id is None
    assert showing.release_category == "unclassified" and "metadata" not in stored.evidence
    assert "reviewed" not in stored.evidence
    failed = snapshot(row)
    failed.failed = True
    failed.refused_host = "www.myvue.com"
    await store.promote(api_session, VENUE, failed, DAY, DAY, run.id, {key: record}, {key: 1417})
    assert stored.identity_status == "unverified" and showing.release_category == "unclassified"


async def test_an_ab6_lookup_is_asked_again_and_never_read_back_as_an_answer(api_session, run):
    """AB6 read at most one film, by a narrower title match, so its records cannot answer #335's
    rule: a run looks the film up again, and a run that cannot leaves it unlinked, never "not
    found" (5 Nov: 15 live films held one, 10 still showing)."""
    row = film("Clayface")
    ac3 = saved_record(row)
    ab6 = Metadata.model_validate(
        {
            **ac3.model_dump(mode="json", exclude={"candidates", "rule"}),
            "candidate": ac3.candidates[0],
        }
    )
    assert ab6.rule == "ab6" and ab6.identities() == ac3.identities()
    key = ("vue", row.film_key)
    seen = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler_for(SAMPLES[0], seen))
    ) as client:
        records, report = await metadata.enrich(
            {VENUE.slug: snapshot(row)}, Budget(client), "fixture-token", {key: ab6}
        )
    assert report["cached"] == 0 and report["lookups"] == 1 and len(seen) == 2
    assert [r.rule for r in records] == ["ac3"]
    # A film stored with AB6's record, on a run with no lookup for it: unlinked, record dropped.
    stored = CinemaFilm(
        source="vue",
        source_key=row.film_key,
        title=row.title,
        identity_status="verified",
        evidence={"metadata": ab6.model_dump(mode="json"), "sourceFingerprint": ab6.fingerprint},
    )
    api_session.add(stored)
    await api_session.flush()
    await store.promote(api_session, VENUE, snapshot(row), DAY, DAY, run.id)
    assert stored.identity_status == "unverified" and stored.movie_id is None
    assert stored.evidence["identity"]["reason"] == "not yet looked up on TMDB"
    assert "metadata" not in stored.evidence
    assert key not in await refresh.metadata_cache(api_session)


async def test_persisted_metadata_refusal_pauses_until_owner_reviewed_new_artifact(
    api_session, run
):
    run.status = "partial"
    run.finished_utc = NOW
    run.report = {"metadata": {"refused": True}}
    await api_session.flush()
    assert await refresh.metadata_is_paused(api_session)
    later = CinemaRefreshRun(
        trigger="test",
        adapter_version="ab6-2",
        status="partial",
        started_utc=NOW,
        finished_utc=NOW + timedelta(seconds=1),
        heartbeat_utc=NOW,
        lease_expires_utc=NOW + timedelta(minutes=10),
        report={"metadata": {"status": "noToken", "successfulRequests": 0}},
    )
    api_session.add(later)
    await api_session.flush()
    assert await refresh.metadata_is_paused(api_session)
    later.report = {"metadata": {"status": "complete", "successfulRequests": 3}}
    await api_session.flush()
    assert not await refresh.metadata_is_paused(api_session)


async def test_programmes_precede_metadata_and_no_token_or_pause_never_sends_auth(monkeypatch):
    row = film("Clayface")
    seen = []
    tmdb_handler = handler_for(SAMPLES[0], seen)

    def handler(request):
        if request.url.host == "api.themoviedb.org":
            return tmdb_handler(request)
        seen.append(request)
        assert "authorization" not in request.headers
        return httpx.Response(200, text="fixture programme")

    async def collect_fixture(venue, start, end, fetch):
        await fetch.get(venue.programme_url)
        return snapshot(row)

    monkeypatch.setattr(refresh, "collect_venue", collect_fixture)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        prepared = await refresh.prepare(
            [VENUE, BY_SLUG["gft"]], DAY, DAY, client, token="fixture-token"
        )
        # One film at two venues is one lookup: a search and a details call.
        assert prepared.metadata_report["requests"] == 2
        assert prepared.requests == 4
        assert [r.url.host for r in seen[:2]] == ["www.myvue.com", "www.glasgowfilm.org"]
        assert all(r.url.host == "api.themoviedb.org" for r in seen[2:])
        for token, paused, state in [("", False, "noToken"), ("fixture-token", True, "paused")]:
            seen.clear()
            prepared = await refresh.prepare(
                [VENUE], DAY, DAY, client, token=token, metadata_paused=paused
            )
            assert len(seen) == 1 and prepared.requests == 1
            assert prepared.metadata_report["status"] == state
            assert prepared.metadata_report["pending"] == 1
            assert not prepared.metadata


async def test_metadata_never_overruns_the_runs_120_request_ceiling():
    row = film("Clayface")
    seen = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler_for(SAMPLES[0], seen))
    ) as client:
        fetch = Budget(client)
        fetch.requests = 116  # The programme has spent all but the margin of four.
        records, report = await metadata.enrich(
            {VENUE.slug: snapshot(row)}, fetch, "fixture-token", {}
        )
        assert fetch.requests == 116 and not seen and not records and report["pending"] == 1
        fetch = Budget(client)
        fetch.requests = 114  # Room for exactly one film's search and details.
        records, report = await metadata.enrich(
            {VENUE.slug: snapshot(row)}, fetch, "fixture-token", {}
        )
    assert fetch.requests == 116 and fetch.metadata_requests == len(seen) == 2
    assert len(records) == 1 and report["pending"] == 0


def test_metadata_artifact_scope_and_mapping_cli_controls():
    from src.scripts.refresh_cinemas import arguments

    row = film("Clayface")
    record = saved_record(row)
    kwargs = dict(
        prepared_utc=NOW,
        date_from=DAY,
        date_to=DAY,
        snapshots={VENUE.slug: snapshot(row)},
        requests=3,
        decoded_bytes=100,
    )
    prepared = refresh.PreparedRun(**kwargs, metadata=[record])
    assert refresh.PreparedRun.model_validate_json(prepared.model_dump_json()) == prepared
    for bad in [
        record.model_copy(update={"film_key": "another-film"}),
        record.model_copy(update={"fetched_utc": NOW + timedelta(seconds=1)}),
        record.model_copy(update={"fingerprint": "0" * 64}),
    ]:
        with pytest.raises(ValueError):
            refresh.PreparedRun(**kwargs, metadata=[bad])
    for argv in [
        ["--enable", "--resume-metadata"],
        ["--dry-run", "--snapshot", "review.json", "--reviewed-mappings", "picks.json"],
        [
            "--write",
            "--snapshot",
            "review.json",
            "--actor-profile-id",
            "00000000-0000-0000-0000-000000000001",
            "--confirm-count",
            "1",
            "--confirm-digest",
            "digest",
            "--confirm-mapping-count",
            "1",
        ],
    ]:
        with pytest.raises(SystemExit):
            arguments(argv)


def test_a_film_named_restoration_is_not_a_returning_label():
    from src.services.cinemas.parsers import _returning_label

    assert _returning_label("Restoration", VENUE.programme_url) == {}
    assert _returning_label("Reissue", VENUE.programme_url) == {}
    assert (
        _returning_label("Pan's Labyrinth 20th Anniversary 4K Restoration", VENUE.programme_url)[
            "returningLabel"
        ]
        is True
    )


def test_explicit_external_identity_changes_invalidate_candidate_cache():
    row = film("Pan's Labyrinth")
    assert metadata.fingerprint(row) != metadata.fingerprint(replace(row, tmdb_id=157336))
    assert metadata.fingerprint(row) != metadata.fingerprint(replace(row, imdb_id="tt0816692"))


def test_vue_wrong_day_response_cannot_become_a_complete_empty_day():
    data = json.loads(body("vue.json"))
    wrong_day = parse_vue(data, DAY, VENUE)
    assert wrong_day.errors and not wrong_day.rows and not wrong_day.complete_dates
    data["result"][0]["showingGroups"][0]["date"] = "2026-11-02T00:00:00"
    wrong_group = parse_vue(data, date(2026, 10, 31), VENUE)
    assert any("group date" in e for e in wrong_group.errors)
    assert not wrong_group.complete_dates


async def test_a_short_budget_goes_first_to_a_labelled_film_with_source_facts():
    returning = film("Pan's Labyrinth")
    bare = [
        replace(film("Clayface"), key=f"bare-{i}", film_key=f"bare-{i}", identity_facts={})
        for i in range(5)
    ]
    seen = []
    snaps = {
        BY_SLUG["odeon-braehead"].slug: Snapshot(rows=bare, observed_utc=NOW),
        VENUE.slug: snapshot(returning),
    }
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler_for(SAMPLES[2], seen))
    ) as client:
        fetch = Budget(client)
        fetch.requests = fetch.metadata_requests = METADATA_CAP - 3  # Three left in the sub-cap.
        records, report = await metadata.enrich(snaps, fetch, "fixture-token", {})
    # The labelled Vue film costs two; one left cannot start the next film's search.
    assert len(seen) == 2 and len(records) == 1
    assert records[0].film_key == returning.film_key and records[0].candidates[0].tmdb_id == 1417
    assert report["pending"] == 5
    assert returning.tmdb_id is None  # Prioritisation is not identity approval.
