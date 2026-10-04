"""§9.1's logging and §9.7's caps, through the real endpoints.

**The model is stubbed and that is not negotiable.** Every real call spends the owner's
money on the owner's key, and `docs/phase-batches.md` says one live call is enough for
§9.1's acceptance and *"do not loop"*. A test suite is a loop. So the transport is a stub
here, and the live call is an owner action — recorded as deferred rather than implied.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.ai import AiUsageLogEntry
from src.models.profile import Profile, UserRole
from src.routers.ai import set_ai_client
from src.services.ai.caps import local_day_bounds, usage_today
from src.services.ai.client import AiReply, ClaudeClient


class StubClaude(ClaudeClient):
    """Answers without a network. Records what it was asked, so "the model was never
    called" is a thing a test can assert rather than infer."""

    def __init__(self, reply: AiReply | None = None, *, configured: bool = True) -> None:
        super().__init__(client=None)
        self.prompts: list[str] = []
        self._configured = configured
        self._reply = reply or AiReply(
            text="Heat is on the Front 2nd shelf, on 4K.",
            model="claude-sonnet-5",
            input_tokens=1200,
            output_tokens=45,
            cost_usd=Decimal("0.002850"),
            stop_reason="end_turn",
            latency_ms=900,
        )

    @property
    def configured(self) -> bool:
        return self._configured

    async def ask(self, prompt: str, **kwargs: object) -> AiReply:  # type: ignore[override]
        self.prompts.append(prompt)
        return self._reply


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
async def person(db: AsyncSession) -> Profile:
    profile = Profile(id=uuid.uuid4(), display_name=f"P{uuid.uuid4().hex[:8]}", role=UserRole.admin)
    db.add(profile)
    await db.flush()
    return profile


@pytest_asyncio.fixture
async def claude() -> AsyncIterator[StubClaude]:
    stub = StubClaude()
    set_ai_client(stub)
    try:
        yield stub
    finally:
        set_ai_client(None)


@pytest_asyncio.fixture
async def client(db: AsyncSession, person: Profile) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user() -> Profile:
        return person

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http_client:
            yield http_client
    finally:
        app.dependency_overrides.clear()


async def _log(
    db: AsyncSession,
    person: Profile,
    *,
    when: datetime,
    cost: str = "0.003",
    error: str | None = None,
) -> AiUsageLogEntry:
    entry = AiUsageLogEntry(
        id=uuid.uuid4(),
        user_id=person.id,
        model="claude-sonnet-5",
        input_tokens=1000,
        output_tokens=50,
        cost_usd=Decimal(cost),
        error=error,
        created_at_utc=when,
    )
    db.add(entry)
    await db.flush()
    return entry


class TestAsking:
    """§9.1 — *"Simple text prompt returns a response; tokens logged"*."""

    async def test_a_prompt_returns_an_answer(
        self, client: AsyncClient, claude: StubClaude
    ) -> None:
        response = await client.post("/api/v1/ai/ask", json={"prompt": "Where is Heat?"})

        assert response.status_code == 200
        body = response.json()
        assert body["text"].startswith("Heat is on the Front")
        assert claude.prompts == ["Where is Heat?"]

    async def test_the_tokens_and_cost_are_logged(
        self, client: AsyncClient, db: AsyncSession, person: Profile, claude: StubClaude
    ) -> None:
        """The second half of §9.1's acceptance, in the table rather than only on the wire."""
        body = (await client.post("/api/v1/ai/ask", json={"prompt": "Where is Heat?"})).json()

        assert body["inputTokens"] == 1200
        assert body["outputTokens"] == 45
        assert body["costUsd"] == "0.002850"
        row = (
            (await db.execute(select(AiUsageLogEntry).where(AiUsageLogEntry.user_id == person.id)))
            .scalars()
            .one()
        )
        assert row.input_tokens == 1200
        assert row.output_tokens == 45
        assert row.cost_usd == Decimal("0.002850")
        assert row.model == "claude-sonnet-5"

    async def test_a_failed_call_is_still_logged(
        self, client: AsyncClient, db: AsyncSession, person: Profile
    ) -> None:
        """A log holding only successes cannot explain an outage.

        The TMDB failure is the standing example: calls failed for an unknown length of
        time and nothing recorded why.
        """
        set_ai_client(
            StubClaude(
                AiReply(
                    text="The assistant is rate limited right now. Try again in a minute.",
                    model="claude-sonnet-5",
                    error="api error 429: rate limited",
                    latency_ms=120,
                )
            )
        )
        try:
            body = (await client.post("/api/v1/ai/ask", json={"prompt": "hi"})).json()
        finally:
            set_ai_client(None)

        assert body["error"] is not None
        assert "rate limited" in body["text"]
        row = (
            (await db.execute(select(AiUsageLogEntry).where(AiUsageLogEntry.user_id == person.id)))
            .scalars()
            .one()
        )
        assert row.error is not None

    async def test_an_unconfigured_deployment_says_so(self, client: AsyncClient) -> None:
        """The TMDB shape. The front end has to be able to say which part is missing."""
        set_ai_client(StubClaude(configured=False))
        try:
            body = (await client.get("/api/v1/ai/status")).json()
        finally:
            set_ai_client(None)

        assert body["configured"] is False
        assert body["model"] == "claude-sonnet-5"

    async def test_the_history_is_caller_scoped(
        self, client: AsyncClient, db: AsyncSession, claude: StubClaude
    ) -> None:
        other = Profile(
            id=uuid.uuid4(), display_name=f"O{uuid.uuid4().hex[:8]}", role=UserRole.viewer
        )
        db.add(other)
        await db.flush()
        db.add(
            AiUsageLogEntry(
                id=uuid.uuid4(),
                user_id=other.id,
                model="claude-sonnet-5",
                cost_usd=Decimal("1.0"),
                created_at_utc=datetime(2026, 9, 10, 12, 0),
            )
        )
        await db.flush()

        history = (await client.get("/api/v1/ai/history")).json()

        assert history == []


class TestCaps:
    """§9.7 — *"Sending over the cap blocks with clear messaging; resets next day"*."""

    async def test_under_the_cap_the_question_goes_through(
        self, client: AsyncClient, db: AsyncSession, person: Profile, claude: StubClaude
    ) -> None:
        await client.put("/api/v1/ai/settings", json={"dailyMessageCap": 3})
        for _ in range(2):
            await _log(db, person, when=datetime.now())

        body = (await client.post("/api/v1/ai/ask", json={"prompt": "one more"})).json()

        assert body["stopReason"] != "cap_reached"
        assert claude.prompts == ["one more"]

    async def test_over_the_cap_it_blocks_with_a_clear_message(
        self, client: AsyncClient, db: AsyncSession, person: Profile, claude: StubClaude
    ) -> None:
        """**§9.7's acceptance criterion, stated exactly.**"""
        await client.put("/api/v1/ai/settings", json={"dailyMessageCap": 2})
        for _ in range(2):
            await _log(db, person, when=datetime.now())

        response = await client.post("/api/v1/ai/ask", json={"prompt": "one too many"})

        body = response.json()
        assert response.status_code == 200, "a limit is an answer, not an error to render"
        assert body["stopReason"] == "cap_reached"
        assert "all 2 of today's messages" in body["text"]
        assert "resets at" in body["text"]

    async def test_a_blocked_request_never_reaches_the_model(
        self, client: AsyncClient, db: AsyncSession, person: Profile, claude: StubClaude
    ) -> None:
        """**The whole point of the cap.**

        Checking after the call would still have spent the money, which is the only thing
        the cap exists to prevent. `claude.prompts` staying empty is the assertion that
        the order is right.
        """
        await client.put("/api/v1/ai/settings", json={"dailyMessageCap": 1})
        await _log(db, person, when=datetime.now())

        await client.post("/api/v1/ai/ask", json={"prompt": "should never be sent"})

        assert claude.prompts == [], "the model must not be called once the cap is reached"

    async def test_a_blocked_request_costs_nothing(
        self, client: AsyncClient, db: AsyncSession, person: Profile, claude: StubClaude
    ) -> None:
        await client.put("/api/v1/ai/settings", json={"dailyMessageCap": 0})

        body = (await client.post("/api/v1/ai/ask", json={"prompt": "no"})).json()

        assert body["costUsd"] == "0.000000"
        rows = (
            (await db.execute(select(AiUsageLogEntry).where(AiUsageLogEntry.user_id == person.id)))
            .scalars()
            .all()
        )
        assert list(rows) == [], "a refusal is not a call and is not logged as one"

    async def test_a_zero_cap_means_no_assistant_at_all(
        self, client: AsyncClient, claude: StubClaude
    ) -> None:
        """Zero is a meaningful setting, which is why the constraint floors at 0 not 1."""
        await client.put("/api/v1/ai/settings", json={"dailyMessageCap": 0})

        body = (await client.post("/api/v1/ai/ask", json={"prompt": "hello"})).json()

        assert body["stopReason"] == "cap_reached"
        assert claude.prompts == []

    async def test_yesterdays_messages_do_not_count(
        self, client: AsyncClient, db: AsyncSession, person: Profile, claude: StubClaude
    ) -> None:
        """*"Resets next day"* — the second half of §9.7's acceptance."""
        await client.put("/api/v1/ai/settings", json={"dailyMessageCap": 2})
        two_days_ago = datetime.now() - timedelta(days=2)
        for _ in range(5):
            await _log(db, person, when=two_days_ago)

        body = (await client.post("/api/v1/ai/ask", json={"prompt": "new day"})).json()

        assert body["stopReason"] != "cap_reached"
        assert claude.prompts == ["new day"]

    async def test_the_cost_cap_blocks_on_its_own(
        self, client: AsyncClient, db: AsyncSession, person: Profile, claude: StubClaude
    ) -> None:
        """A message count alone does not bound spend.

        Twenty cheap messages and twenty expensive ones are the same number and very
        different bills, which is why §9.7 names both ceilings.
        """
        await client.put(
            "/api/v1/ai/settings", json={"dailyMessageCap": 1000, "dailyCostCapUsd": 0.5}
        )
        await _log(db, person, when=datetime.now(), cost="0.60")

        body = (await client.post("/api/v1/ai/ask", json={"prompt": "expensive"})).json()

        assert body["stopReason"] == "cap_reached"
        assert "spending limit" in body["text"]
        assert claude.prompts == []

    async def test_a_zero_cost_cap_means_no_cost_ceiling(
        self, client: AsyncClient, db: AsyncSession, person: Profile, claude: StubClaude
    ) -> None:
        """Otherwise "unlimited spend" and "spend nothing" would be the same setting."""
        await client.put("/api/v1/ai/settings", json={"dailyMessageCap": 100, "dailyCostCapUsd": 0})
        await _log(db, person, when=datetime.now(), cost="99.00")

        body = (await client.post("/api/v1/ai/ask", json={"prompt": "still fine"})).json()

        assert body["stopReason"] != "cap_reached"

    async def test_a_failed_call_does_not_use_up_an_allowance(
        self, client: AsyncClient, db: AsyncSession, person: Profile, claude: StubClaude
    ) -> None:
        """Being charged a message for an outage is the wrong way round."""
        await client.put("/api/v1/ai/settings", json={"dailyMessageCap": 2})
        for _ in range(5):
            await _log(db, person, when=datetime.now(), error="api error 500")

        body = (await client.post("/api/v1/ai/ask", json={"prompt": "after an outage"})).json()

        assert body["stopReason"] != "cap_reached"

    async def test_usage_reports_what_is_left(
        self, client: AsyncClient, db: AsyncSession, person: Profile
    ) -> None:
        await client.put("/api/v1/ai/settings", json={"dailyMessageCap": 10})
        for _ in range(3):
            await _log(db, person, when=datetime.now())

        usage = (await client.get("/api/v1/ai/usage")).json()

        assert usage["messages"] == 3
        assert usage["messagesRemaining"] == 7
        assert usage["blocked"] is False
        assert usage["limitMessage"] is None

    async def test_the_cap_is_editable_in_the_app(self, client: AsyncClient) -> None:
        """§9.7: "editable in the app afterwards" — 50 is a starting value, not a promise."""
        updated = (await client.put("/api/v1/ai/settings", json={"dailyMessageCap": 200})).json()

        assert updated["dailyMessageCap"] == 200
        assert (await client.get("/api/v1/ai/settings")).json()["dailyMessageCap"] == 200

    async def test_an_absurd_cap_is_refused(self, client: AsyncClient) -> None:
        assert (
            await client.put("/api/v1/ai/settings", json={"dailyMessageCap": 999999})
        ).status_code == 422

    async def test_the_settings_default_to_the_owners_fifty(self, client: AsyncClient) -> None:
        assert (await client.get("/api/v1/ai/settings")).json()["dailyMessageCap"] == 50

    async def test_usage_is_counted_in_the_persons_own_day(
        self, db: AsyncSession, person: Profile
    ) -> None:
        """**Gotcha 26 applied to §9.7.**

        "Resets next day" is a promise to a person holding a phone. A message sent at
        00:30 BST is 23:30 UTC *yesterday*; counting in UTC would put it in the wrong day
        and the allowance would appear to reset an hour late all summer.
        """
        just_after_midnight_bst = datetime(2026, 7, 15, 23, 30)  # 00:30 on the 16th, local
        await _log(db, person, when=just_after_midnight_bst)

        usage = await usage_today(db, person.id, now=datetime(2026, 7, 16, 8, 0))

        assert usage.messages == 1, "it belongs to the local day it was sent in"


def test_a_local_day_is_twenty_four_hours_even_across_a_dst_change() -> None:
    """The bounds must not silently shorten or lengthen the allowance window."""
    from zoneinfo import ZoneInfo

    start, end = local_day_bounds(datetime(2026, 7, 15, 12, 0), ZoneInfo("Europe/London"))

    assert end - start == timedelta(days=1)
    assert start == datetime(2026, 7, 14, 23, 0), "midnight BST is 23:00 UTC the day before"
