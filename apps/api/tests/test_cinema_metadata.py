"""Approved saved metadata, exact mapping review, cached enrichment and budget isolation."""

import copy
import hashlib
import json
from dataclasses import replace
from datetime import date, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from src.models.cinema import CinemaFilm, CinemaRefreshRun, CinemaScreening
from src.services.cinemas import collect, metadata, refresh, store
from src.services.cinemas.domain import Snapshot, SourceError, release_category
from src.services.cinemas.fetch import Budget, Refused
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
    sample = SAMPLES[index]
    d = sample["details"]
    return Metadata(
        source="vue",
        film_key=row.film_key,
        fingerprint=metadata.fingerprint(row),
        fetched_utc=NOW,
        state="candidate",
        candidate=Candidate(
            tmdb_id=d["id"],
            title=d["title"],
            original_title=d["original_title"],
            directors=[p["name"] for p in d["directors"]],
            runtime=d["runtime"],
            imdb_id=d["imdb_id"],
            primary_release_date=date.fromisoformat(d["release_date"]),
            gb_theatrical=[
                ReleaseEvent(
                    date=date.fromisoformat(e["release_date"][:10]), type=e["type"], note=e["note"]
                )
                for e in sample["gbReleaseEvents"]
                if e["type"] in (2, 3)
            ],
        ),
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
        return httpx.Response(200, json={"responseCode": 0, "result": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetch = Budget(client)
        result = await collect.collect_venue(VENUE, DAY, DAY + timedelta(days=13), fetch)
        assert result.complete_dates == {DAY, DAY + timedelta(days=1)}
        assert len(seen) == 2
        assert "T00:00:00" in str(seen[0].url) and "%3A" not in str(seen[0].url)
        assert seen[0].headers["Accept"] == "text/html,application/xhtml+xml"
        result = await collect.collect_venue(
            VENUE, DAY + timedelta(days=2), DAY + timedelta(days=3), fetch
        )
        assert result.rows == [] and result.observed_dates == set() and len(seen) == 2


async def test_vue_refusal_does_not_publish_successful_prefix():
    seen = []

    def handler(request):
        seen.append(request)
        return (
            httpx.Response(200, json={"responseCode": 0, "result": []})
            if len(seen) == 1
            else httpx.Response(401)
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect.collect_venue(VENUE, DAY, DAY + timedelta(days=13), Budget(client))
    assert result.failed and result.refused_host == "www.myvue.com"
    assert result.complete_dates == set() and len(seen) == 2


async def test_search_is_candidate_only_and_metadata_is_separately_corroborated():
    row = film("Clayface")
    seen = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler_for(SAMPLES[0], seen))
    ) as client:
        fetch = Budget(client)
        records, report = await metadata.enrich(
            {VENUE.slug: snapshot(row)}, fetch, "fixture-token", {}
        )
    assert fetch.requests == fetch.metadata_requests == 3 and report["pending"] == 0
    record = records[0]
    assert record.state == "candidate" and record.candidate.tmdb_id == 1400940
    assert row.tmdb_id is None
    assert metadata.corroboration(row, record.candidate) == ["director"]
    assert metadata.corroboration(replace(row, identity_facts={}), record.candidate) == []
    assert all(r.headers["authorization"] == "Bearer fixture-token" for r in seen)
    assert all(r.url.host == "api.themoviedb.org" for r in seen)
    assert metadata.category_evidence(row, record) == {}
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
            (positive.model_copy(update={"state": "missing", "candidate": None}), 7),
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


async def test_metadata_subcap_shared_cap_and_token_host_isolation():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"results": []})

    rows = [replace(film("Clayface"), key=f"show-{i}", film_key=f"film-{i}") for i in range(13)]
    snaps = {VENUE.slug: Snapshot(rows=rows, observed_utc=NOW)}
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetch = Budget(client)
        records, report = await metadata.enrich(snaps, fetch, "fixture-token", {})
        assert len(records) == 12 and report["pending"] == 1 and fetch.requests == 12
        with pytest.raises(SourceError, match="credential sent"):
            await fetch.metadata("https://www.myvue.com/3/test", "fixture-token")
        await fetch.get("https://www.myvue.com/programme")
        assert "authorization" not in seen[-1].headers
        fetch.requests = 120
        with pytest.raises(SourceError, match="limit"):
            await fetch.get("https://www.glasgowfilm.org/")
        assert len(seen) == 13


async def test_ambiguous_titles_refusals_and_budget_failure_do_not_guess_or_negative_cache():
    row = film("Clayface")
    seen = []

    def ambiguous(request):
        seen.append(request)
        candidate = SAMPLES[0]["candidates"][0]
        return httpx.Response(200, json={"results": [candidate, {**candidate, "id": 123}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(ambiguous)) as client:
        fetch = Budget(client)
        records, report = await metadata.enrich(
            {VENUE.slug: snapshot(row)}, fetch, "fixture-token", {}
        )
        assert records[0].state == "ambiguous" and records[0].candidate is None and len(seen) == 1
    seen = []

    def refused(request):
        seen.append(request)
        return httpx.Response(403)

    async with httpx.AsyncClient(transport=httpx.MockTransport(refused)) as client:
        fetch = Budget(client)
        snaps = {
            VENUE.slug: Snapshot(rows=[row, replace(row, key="2", film_key="2")], observed_utc=NOW)
        }
        records, report = await metadata.enrich(snaps, fetch, "fixture-token", {})
        assert not records and report["refused"] and report["pending"] == 2 and len(seen) == 1
        with pytest.raises(Refused):
            await fetch.metadata("https://api.themoviedb.org/3/search/movie", "fixture-token")
        assert len(seen) == 1
    async with httpx.AsyncClient(transport=httpx.MockTransport(ambiguous)) as client:
        fetch = Budget(client)
        fetch.requests = 120
        records, report = await metadata.enrich(
            {VENUE.slug: snapshot(row)}, fetch, "fixture-token", {}
        )
        assert not records and report["pending"] == 1 and report["errors"] == ["SourceError"]


def test_mapping_review_requires_exact_fresh_correlated_identity_and_does_not_guess_run():
    row = film("Pan's Labyrinth")
    record = saved_record(row, 2)
    pick = MappingPick(source="vue", film_key=row.film_key, tmdb_id=1417)
    snaps = {VENUE.slug: snapshot(row)}
    assert metadata.validate_picks(snaps, [record], [pick]) == {("vue", row.film_key): record}
    assert metadata.corroboration(row, record.candidate) == ["director", "distinct original title"]
    evidence = metadata.category_evidence(row, record)
    assert release_category(evidence, identity_verified=True) == "olderFilm"
    assert release_category(evidence, identity_verified=False) == "unclassified"
    assert metadata.category_evidence(film("Clayface"), saved_record(film("Clayface"))) == {}
    for picks, records in [
        ([pick, pick], [record]),
        ([pick.model_copy(update={"tmdb_id": 157336})], [record]),
        ([pick], [record.model_copy(update={"fetched_utc": NOW - timedelta(days=30)})]),
    ]:
        with pytest.raises(SourceError):
            metadata.validate_picks(snaps, records, picks)
    bare = replace(row, identity_facts={})
    with pytest.raises(SourceError, match="corroboration"):
        metadata.validate_picks(
            {VENUE.slug: snapshot(bare)},
            [record.model_copy(update={"fingerprint": metadata.fingerprint(bare)})],
            [pick],
        )
    # A past TMDB reissue without a current source label cannot classify a showing.
    interstellar = replace(row, title="Interstellar", identity_facts={})
    assert (
        metadata.category_evidence(
            replace(interstellar, evidence={}), saved_record(interstellar, 1)
        )
        == {}
    )


async def test_candidate_import_review_persistence_conflict_and_atomic_refusal(api_session, run):
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
    assert (
        stored.identity_status == "unverified"
        and stored.evidence["metadata"]["candidate"]["tmdb_id"] == 1417
    )
    assert showing.release_category == "unclassified" and stored.movie_id is None
    await store.promote(api_session, VENUE, snap, DAY, DAY, run.id, {key: record}, {key})
    assert stored.identity_status == "verified" and showing.release_category == "olderFilm"
    assert stored.evidence["reviewedMapping"]["corroboration"] == [
        "director",
        "distinct original title",
    ]
    # Missing metadata/provider failure cannot erase a reviewed stable identity/cache.
    await store.promote(api_session, VENUE, snap, DAY, DAY, run.id)
    assert stored.identity_status == "verified" and stored.evidence["tmdbId"] == 1417
    assert showing.release_category == "olderFilm"
    assert (await refresh.metadata_cache(api_session))[key] == record
    changed = replace(row, identity_facts={**row.identity_facts, "director": "Another director"})
    await store.promote(api_session, VENUE, snapshot(changed), DAY, DAY, run.id)
    assert stored.identity_status == "conflict" and stored.movie_id is None
    assert showing.release_category == "unclassified" and "metadata" not in stored.evidence
    failed = snapshot(row)
    failed.failed = True
    failed.refused_host = "www.myvue.com"
    await store.promote(api_session, VENUE, failed, DAY, DAY, run.id, {key: record}, {key})
    assert stored.identity_status == "conflict" and showing.release_category == "unclassified"


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
        assert prepared.metadata_report["requests"] == 6
        assert prepared.requests == 8
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


async def test_metadata_never_overruns_remaining_programme_budget():
    row = film("Clayface")
    seen = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler_for(SAMPLES[0], seen))
    ) as client:
        fetch = Budget(client)
        fetch.requests = 118
        records, report = await metadata.enrich(
            {VENUE.slug: snapshot(row)}, fetch, "fixture-token", {}
        )
    assert fetch.requests == 120 and fetch.metadata_requests == len(seen) == 2
    assert not records and report["pending"] == 1


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
