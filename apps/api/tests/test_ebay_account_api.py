"""Batch T8b — Connect eBay end to end, against Postgres (CI).

eBay is a mock transport answering as its documentation shows: the token endpoint, and the
Trading API's three calls with its documented samples. Two people, as the app has: each
connects their own eBay and sees only their own (`DECISIONS.md` #245).
"""

from __future__ import annotations

import base64
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.admin_action import AdminAction
from src.models.ebay_account import EbayAccount, EbayConnectState
from src.models.profile import Profile, UserRole
from src.routers.ebay_account import get_ebay_http
from src.services.ebay_account.accounts import state_hash
from src.services.ebay_account.crypto import derive_key, open_sealed

pytestmark = pytest.mark.asyncio

FIXTURES = Path(__file__).parent / "fixtures"
KEY_B64 = base64.b64encode(bytes(range(32))).decode()
ACTOR = "x-test-actor"
NOW = datetime(2026, 10, 4, 9, 0)
ACCESS = "v^1.1#i^1#p^3#r^1...access-for-mark"
REFRESH = "v^1.1#i^1#p^3#r^1...refresh-for-mark"
TOKEN_ERROR = (
    b'<?xml version="1.0" encoding="utf-8"?>'
    b'<GetMyeBayBuyingResponse xmlns="urn:ebay:apis:eBLBaseComponents"><Ack>Failure</Ack>'
    b"<Errors><LongMessage>IAF token supplied is invalid.</LongMessage>"
    b"<ErrorCode>21916984</ErrorCode></Errors></GetMyeBayBuyingResponse>"
)


class FakeEbay:
    """eBay's token endpoint and Trading API, answering as documented, recording each call."""

    def __init__(self) -> None:
        self.refresh_refused = False
        self.lists_refused = False
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if str(request.url) == "https://api.ebay.com/identity/v1/oauth2/token":
            form = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
            if form["grant_type"] == "authorization_code":
                return httpx.Response(
                    200,
                    json={
                        "access_token": ACCESS,
                        "expires_in": 7200,
                        "refresh_token": REFRESH,
                        "refresh_token_expires_in": 47304000,
                    },
                )
            if self.refresh_refused:
                return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": ACCESS + "-fresh", "expires_in": 7200})
        call = request.headers.get("X-EBAY-API-CALL-NAME")
        if call == "GetUser":
            return httpx.Response(
                200,
                content=(
                    b'<GetUserResponse xmlns="urn:ebay:apis:eBLBaseComponents"><Ack>Success</Ack>'
                    b"<User><UserID>mark_at_the_movies</UserID></User></GetUserResponse>"
                ),
            )
        if self.lists_refused:
            return httpx.Response(200, content=TOKEN_ERROR)
        if call == "GetMyeBayBuying":
            return httpx.Response(
                200, content=(FIXTURES / "ebay_trading_buying_doc_sample.xml").read_bytes()
            )
        if call == "GetMyeBaySelling":
            return httpx.Response(
                200, content=(FIXTURES / "ebay_trading_selling_doc_sample.xml").read_bytes()
            )
        return httpx.Response(404)

    def calls(self) -> list[str]:
        return [
            request.headers.get("X-EBAY-API-CALL-NAME")
            or parse_qs(request.content.decode()).get("grant_type", ["?"])[0]
            for request in self.requests
        ]


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


async def _person(db: AsyncSession, role: UserRole, name: str) -> Profile:
    profile = Profile(
        id=uuid.uuid4(), display_name=f"{name} {uuid.uuid4().hex[:6]}", pin_hash=None, role=role
    )
    db.add(profile)
    await db.flush()
    return profile


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.config.settings.ebay_client_id", "TheReal-MCU-PRD-0123456789")
    monkeypatch.setattr("src.config.settings.ebay_client_secret", "PRD-secret-not-real")
    monkeypatch.setattr("src.config.settings.ebay_runame", "The_Real_MCU-TheReal-TheRea-abcdefgh")
    monkeypatch.setattr("src.config.settings.ebay_token_key", KEY_B64)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[datetime], None]:
    def set_now(now: datetime) -> None:
        monkeypatch.setattr("src.routers.ebay_account.utcnow", lambda: now)

    set_now(NOW)
    return set_now


@pytest_asyncio.fixture
async def people(db: AsyncSession) -> tuple[Profile, Profile]:
    return (
        await _person(db, UserRole.admin, "Craig"),
        await _person(db, UserRole.viewer, "Mark"),
    )


@pytest_asyncio.fixture
async def ebay(db: AsyncSession, people: tuple[Profile, Profile]) -> AsyncIterator[FakeEbay]:
    craig, mark = people
    fake = FakeEbay()

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user(request: Request) -> Profile:
        return craig if request.headers.get(ACTOR) == "craig" else mark

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_ebay_http] = lambda: (
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(fake.handler))
    )
    try:
        yield fake
    finally:
        app.dependency_overrides.clear()


def _as(person: str) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={ACTOR: person}
    )


async def _connect(person: str) -> httpx.Response:
    async with _as(person) as client:
        started = await client.post("/api/v1/ebay/account/connect")
        assert started.status_code == 200, started.text
        state = parse_qs(urlsplit(started.json()["authorizeUrl"]).query)["state"][0]
        return await client.post(
            "/api/v1/ebay/account/complete", json={"code": "v^1.1#code-from-ebay", "state": state}
        )


async def test_connecting_says_what_is_missing_and_sends_nobody_to_eBay(
    ebay: FakeEbay, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("src.config.settings.ebay_runame", "")
    monkeypatch.setattr("src.config.settings.ebay_token_key", "")
    async with _as("mark") as client:
        status = (await client.get("/api/v1/ebay/account")).json()
        started = await client.post("/api/v1/ebay/account/connect")

    assert (status["configured"], status["connected"]) == (False, False)
    assert {"EBAY_RUNAME", "EBAY_TOKEN_KEY"} <= set(status["missing"])
    assert started.status_code == 503
    assert ebay.requests == []


async def test_a_connection_seals_the_tokens_for_that_person_alone(
    ebay: FakeEbay,
    configured: None,
    clock: Callable[[datetime], None],
    db: AsyncSession,
    people: tuple[Profile, Profile],
) -> None:
    del configured, clock
    _, mark = people
    mark_id = mark.id

    response = await _connect("mark")

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["connected"], body["accountName"]) == (True, "mark_at_the_movies")
    account = (
        await db.execute(select(EbayAccount).where(EbayAccount.profile_id == mark_id))
    ).scalar_one()
    assert ACCESS.encode() not in account.access_token_sealed
    assert REFRESH.encode() not in account.refresh_token_sealed
    key = derive_key(KEY_B64)
    assert open_sealed(account.refresh_token_sealed, owner=mark_id, key=key) == REFRESH
    assert account.scopes == "https://api.ebay.com/oauth/api_scope"
    assert account.access_expires_utc == NOW + timedelta(hours=2)
    # The state is kept only as its hash, and is spent.
    held = (await db.execute(select(EbayConnectState))).scalars().all()
    assert all(len(row.state_hash) == 64 and row.used_utc == NOW for row in held)
    audit = (
        (await db.execute(select(AdminAction).where(AdminAction.target_table == "ebay_accounts")))
        .scalars()
        .all()
    )
    assert [entry.changes for entry in audit] == [
        {"connected": True, "scopes": "https://api.ebay.com/oauth/api_scope"}
    ]


async def test_a_state_works_once_and_only_for_whoever_started_it(
    ebay: FakeEbay, configured: None, clock: Callable[[datetime], None], db: AsyncSession
) -> None:
    del configured, clock
    async with _as("mark") as mark:
        started = await mark.post("/api/v1/ebay/account/connect")
    state = parse_qs(urlsplit(started.json()["authorizeUrl"]).query)["state"][0]
    finish = {"code": "v^1.1#code-from-ebay", "state": state}
    # Kept only as its hash: the state itself, which could finish the sign-in, is not stored.
    held = (await db.execute(select(EbayConnectState))).scalars().all()
    assert [row.state_hash for row in held] == [state_hash(state)]

    async with _as("craig") as craig:
        stolen = await craig.post("/api/v1/ebay/account/complete", json=finish)
    async with _as("mark") as mark:
        first = await mark.post("/api/v1/ebay/account/complete", json=finish)
        again = await mark.post("/api/v1/ebay/account/complete", json=finish)

    assert stolen.status_code == 400
    assert "not started from your Settings" in stolen.json()["detail"]
    assert first.status_code == 200
    assert again.status_code == 400
    assert "already been used" in again.json()["detail"]
    assert ebay.calls().count("authorization_code") == 1, "only Mark's own swap reached eBay"


async def test_a_state_lasts_ten_minutes(
    ebay: FakeEbay, configured: None, clock: Callable[[datetime], None]
) -> None:
    del configured
    async with _as("mark") as mark:
        started = await mark.post("/api/v1/ebay/account/connect")
        state = parse_qs(urlsplit(started.json()["authorizeUrl"]).query)["state"][0]
        clock(NOW + timedelta(minutes=11))
        late = await mark.post(
            "/api/v1/ebay/account/complete", json={"code": "v^1.1#code", "state": state}
        )

    assert late.status_code == 400
    assert "over ten minutes" in late.json()["detail"]
    assert "authorization_code" not in ebay.calls()


async def test_each_person_sees_only_their_own_eBay(
    ebay: FakeEbay, configured: None, clock: Callable[[datetime], None]
) -> None:
    del configured, clock
    assert (await _connect("mark")).status_code == 200

    async with _as("craig") as craig:
        status = (await craig.get("/api/v1/ebay/account")).json()
        lists = await craig.get("/api/v1/ebay/account/watching")

    assert status["connected"] is False
    assert lists.status_code == 409
    assert "Connect eBay" in lists.json()["detail"]


async def test_the_lists_are_read_from_eBay_when_opened(
    ebay: FakeEbay, configured: None, clock: Callable[[datetime], None]
) -> None:
    del configured, clock
    assert (await _connect("mark")).status_code == 200

    async with _as("mark") as mark:
        watching = (await mark.get("/api/v1/ebay/account/watching")).json()
        selling = (await mark.get("/api/v1/ebay/account/selling")).json()

    assert [item["title"] for item in watching["items"]] == [
        "Mint Titleist AP2 Iron",
        "CLEVELAND LAUNCHER",
    ]
    assert watching["items"][0]["price"] == "227.50"
    assert watching["items"][0]["isAuction"] is True
    assert [search["keywords"] for search in watching["savedSearches"]] == [
        "koa",
        "titleist 735 irons",
    ]
    assert selling["totalActive"] == 3
    assert ebay.calls()[-2:] == ["GetMyeBayBuying", "GetMyeBaySelling"]


async def test_a_spent_access_token_is_refreshed_before_the_list_is_asked_for(
    ebay: FakeEbay,
    configured: None,
    clock: Callable[[datetime], None],
    db: AsyncSession,
    people: tuple[Profile, Profile],
) -> None:
    del configured
    mark_id = people[1].id
    assert (await _connect("mark")).status_code == 200
    clock(NOW + timedelta(hours=3))

    async with _as("mark") as mark:
        response = await mark.get("/api/v1/ebay/account/watching")

    assert response.status_code == 200
    assert ebay.calls()[-2:] == ["refresh_token", "GetMyeBayBuying"]
    assert ebay.requests[-1].headers["X-EBAY-API-IAF-TOKEN"] == ACCESS + "-fresh"
    account = (
        await db.execute(select(EbayAccount).where(EbayAccount.profile_id == mark_id))
    ).scalar_one()
    assert account.refreshed_utc == NOW + timedelta(hours=3)


async def test_a_refused_refresh_ends_the_connection(
    ebay: FakeEbay,
    configured: None,
    clock: Callable[[datetime], None],
    db: AsyncSession,
    people: tuple[Profile, Profile],
) -> None:
    del configured
    mark_id = people[1].id
    assert (await _connect("mark")).status_code == 200
    ebay.refresh_refused = True
    clock(NOW + timedelta(hours=3))

    async with _as("mark") as mark:
        response = await mark.get("/api/v1/ebay/account/selling")

    assert response.status_code == 409
    assert "no longer accepts this connection" in response.json()["detail"]
    remaining = (
        await db.execute(select(EbayAccount).where(EbayAccount.profile_id == mark_id))
    ).scalar_one_or_none()
    assert remaining is None


async def test_a_list_refused_even_with_a_fresh_token_is_reported_not_deleted(
    ebay: FakeEbay,
    configured: None,
    clock: Callable[[datetime], None],
    db: AsyncSession,
    people: tuple[Profile, Profile],
) -> None:
    """The app asking for something its sign-in does not cover: say so, keep the connection."""
    del configured, clock
    mark_id = people[1].id
    assert (await _connect("mark")).status_code == 200
    ebay.lists_refused = True

    async with _as("mark") as mark:
        response = await mark.get("/api/v1/ebay/account/watching")

    assert response.status_code == 502
    assert "even with a fresh sign-in" in response.json()["detail"]
    assert ebay.calls()[-3:] == ["GetMyeBayBuying", "refresh_token", "GetMyeBayBuying"]
    kept = (
        await db.execute(select(EbayAccount).where(EbayAccount.profile_id == mark_id))
    ).scalar_one_or_none()
    assert kept is not None


async def test_disconnecting_deletes_the_tokens(
    ebay: FakeEbay,
    configured: None,
    clock: Callable[[datetime], None],
    db: AsyncSession,
    people: tuple[Profile, Profile],
) -> None:
    del configured, clock
    mark_id = people[1].id
    assert (await _connect("mark")).status_code == 200

    async with _as("mark") as mark:
        gone = await mark.delete("/api/v1/ebay/account")
        status = (await mark.get("/api/v1/ebay/account")).json()

    assert gone.status_code == 204
    assert status["connected"] is False
    assert (
        await db.execute(select(EbayAccount).where(EbayAccount.profile_id == mark_id))
    ).scalar_one_or_none() is None
