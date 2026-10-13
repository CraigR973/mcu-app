"""Batch X7 — the assistant answers more than once (AI45-01 to AI45-08).

**The guard this batch exists for is the first class.** Every follow-up failed for a month
because each answer was stored as the SDK's full dump, `parsed_output` and all, and replayed;
the old tests' stand-in blocks dumped only the fields they were given, so CI could not see
it. These drive the **real** SDK and the real client over a stubbed HTTP transport — the SDK
assembles its own blocks from a stream, exactly as in production — and read the request the
second turn sends. No call leaves the machine.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import anthropic
import httpx2 as httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.models.ai import AiConversation, AiMessage, AiSettings, AiToolCall, AiUsageLogEntry
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.wanted import WantedItem
from src.models.watch_log import WatchLog
from src.services import health_checks
from src.services.ai import tools as tools_module
from src.services.ai.chat import (
    MAX_TOOL_CALLS_PER_ROUND,
    MAX_TOOL_ROUNDS,
    ChatEvent,
    history_for,
    request_block,
    resolve_tool_call,
    run_turn,
)
from src.services.ai.client import (
    BASE_PROMPT,
    CRAIG_HAS_BEEN_TOLD,
    ClaudeClient,
    _friendly,
    system_prompt,
)
from src.services.ai.tools import (
    MAX_RESULT_CHARS,
    READ_TOOLS,
    WRITE_TOOLS,
    _fit,
    execute_tool,
    prepare_write,
)

# ---------------------------------------------------------------------------
# A real SDK over a fake wire
# ---------------------------------------------------------------------------


def _sse(events: list[dict[str, Any]]) -> bytes:
    return "".join(
        f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events
    ).encode()


def _stream_body(blocks: list[dict[str, Any]], *, stop_reason: str, model: str) -> bytes:
    """A Messages stream as the API sends it: thinking, text and tool-use blocks."""
    events: list[dict[str, Any]] = [
        {
            "type": "message_start",
            "message": {
                "id": f"msg_{uuid.uuid4().hex[:12]}",
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 1000, "output_tokens": 1},
            },
        }
    ]
    for index, block in enumerate(blocks):
        kind = block["type"]
        if kind == "thinking":
            start = {"type": "thinking", "thinking": "", "signature": ""}
            deltas = [
                {"type": "thinking_delta", "thinking": block["thinking"]},
                {"type": "signature_delta", "signature": block["signature"]},
            ]
        elif kind == "text":
            start = {"type": "text", "text": ""}
            half = len(block["text"]) // 2
            deltas = [
                {"type": "text_delta", "text": block["text"][:half]},
                {"type": "text_delta", "text": block["text"][half:]},
            ]
        else:
            start = {"type": "tool_use", "id": block["id"], "name": block["name"], "input": {}}
            deltas = [{"type": "input_json_delta", "partial_json": json.dumps(block["input"])}]
        events.append({"type": "content_block_start", "index": index, "content_block": start})
        events += [
            {"type": "content_block_delta", "index": index, "delta": delta} for delta in deltas
        ]
        events.append({"type": "content_block_stop", "index": index})
    events.append(
        {
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason, "stop_sequence": None},
            "usage": {"output_tokens": 40},
        }
    )
    events.append({"type": "message_stop"})
    return _sse(events)


class Wire:
    """Answers each request with the next scripted response; keeps every request body."""

    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        return self.responses.pop(0)

    def client(self) -> ClaudeClient:
        sdk = anthropic.AsyncAnthropic(
            api_key="test-key",
            max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(self)),
        )
        return ClaudeClient(client=sdk)


def streamed(
    blocks: list[dict[str, Any]], *, stop_reason: str = "end_turn", model: str = "claude-sonnet-5"
) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        content=_stream_body(blocks, stop_reason=stop_reason, model=model),
    )


def refused(status: int, error_type: str, *, retry_after: str | None = None) -> httpx.Response:
    headers = {"retry-after": retry_after} if retry_after else {}
    return httpx.Response(
        status,
        headers=headers,
        json={"type": "error", "error": {"type": error_type, "message": "no"}},
    )


def thinking(text: str = "") -> dict[str, Any]:
    return {"type": "thinking", "thinking": text, "signature": "sig-" + uuid.uuid4().hex}


def text(value: str) -> dict[str, Any]:
    return {"type": "text", "text": value}


def tool_use(name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "tool_use",
        "id": f"toolu_{uuid.uuid4().hex[:12]}",
        "name": name,
        "input": tool_input,
    }


#: The fields the API accepts back for each block type: the SDK's own request types.
def _request_keys(block_type: str) -> set[str]:
    from anthropic.types import (
        TextBlockParam,
        ThinkingBlockParam,
        ToolResultBlockParam,
        ToolUseBlockParam,
    )

    param = {
        "text": TextBlockParam,
        "thinking": ThinkingBlockParam,
        "tool_use": ToolUseBlockParam,
        "tool_result": ToolResultBlockParam,
    }[block_type]
    return set(param.__required_keys__ | param.__optional_keys__)


def assert_request_shaped(messages: list[dict[str, Any]]) -> None:
    for message in messages:
        content = message["content"]
        for block in content if isinstance(content, list) else []:
            extra = set(block) - _request_keys(block["type"])
            assert not extra, f"{block['type']} block carries {extra}, which the API refuses"
            assert None not in block.values()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


async def _profile(
    db: AsyncSession, role: UserRole = UserRole.admin, name: str = "Craig"
) -> Profile:
    profile = Profile(id=uuid.uuid4(), display_name=f"{name}{uuid.uuid4().hex[:4]}", role=role)
    db.add(profile)
    await db.flush()
    return profile


@pytest_asyncio.fixture
async def craig(db: AsyncSession) -> Profile:
    return await _profile(db)


@pytest_asyncio.fixture
async def chat(db: AsyncSession, craig: Profile) -> AiConversation:
    row = AiConversation(id=uuid.uuid4(), user_id=craig.id)
    db.add(row)
    await db.flush()
    return row


async def _film(
    db: AsyncSession,
    title: str,
    *,
    year: int | None = None,
    formats: list[str] | None = None,
    tmdb_id: int | None = None,
) -> Movie:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        year=year,
        media_type="film",
    )
    db.add(movie)
    await db.flush()
    if formats is not None:
        db.add(
            CollectionItem(
                id=uuid.uuid4(),
                movie_id=movie.id,
                formats=formats,
                location="Front 2nd",
                section="Front",
                shelf="2nd",
            )
        )
        await db.flush()
    return movie


async def _drain(events: AsyncIterator[ChatEvent]) -> list[ChatEvent]:
    return [event async for event in events]


async def _turn(
    db: AsyncSession, chat: AiConversation, user: Profile, client: ClaudeClient, prompt: str
) -> list[ChatEvent]:
    return await _drain(run_turn(db, conversation=chat, user=user, client=client, prompt=prompt))


async def _pending(db: AsyncSession, chat: AiConversation) -> AiToolCall:
    return (
        await db.execute(
            select(AiToolCall).where(
                AiToolCall.conversation_id == chat.id, AiToolCall.status == "pending"
            )
        )
    ).scalar_one()


# ---------------------------------------------------------------------------
# AI45-01 — store and replay only what the API accepts
# ---------------------------------------------------------------------------


class TestReplay:
    async def test_a_follow_up_replays_only_request_fields(
        self, db: AsyncSession, chat: AiConversation, craig: Profile
    ) -> None:
        """**The guard (CI).** Real SDK blocks — thinking, a streamed text block, a tool
        call — through store and replay: the second request carries no SDK-only key."""
        await _film(db, "Heat", year=1995, formats=["4k_uhd"])
        wire = Wire(
            [
                streamed(
                    [thinking(), tool_use("search_collection", {"query": "Heat"})],
                    stop_reason="tool_use",
                ),
                streamed([thinking(), text("Yes, Heat on 4K.")]),
                streamed([text("Front, 2nd shelf.")]),
            ]
        )
        client = wire.client()

        first = await _turn(db, chat, craig, client, "Do we own Heat on 4K?")
        second = await _turn(db, chat, craig, client, "Thanks. Which shelf is it on?")

        assert first[-1].kind == "done" and second[-1].kind == "done"
        replayed = wire.requests[2]["messages"]
        assert [m["role"] for m in replayed] == ["user", "assistant", "user", "assistant", "user"]
        assert_request_shaped(replayed)
        assert "parsed_output" not in json.dumps(replayed)

    async def test_an_answer_stored_before_x7_replays_clean(
        self, db: AsyncSession, chat: AiConversation
    ) -> None:
        """The six stored conversations continue: the dump is cleaned on read too."""
        db.add_all(
            [
                AiMessage(
                    id=uuid.uuid4(),
                    conversation_id=chat.id,
                    role="user",
                    content=[{"type": "text", "text": "Do we own Heat?"}],
                    text="Do we own Heat?",
                    sequence=1,
                ),
                AiMessage(
                    id=uuid.uuid4(),
                    conversation_id=chat.id,
                    role="assistant",
                    content=[
                        {"type": "text", "text": "Yes.", "citations": None, "parsed_output": None},
                        {"type": "thinking", "thinking": "", "signature": "abc"},
                    ],
                    text="Yes.",
                    sequence=2,
                ),
            ]
        )
        await db.flush()

        history = await history_for(db, chat)

        assert_request_shaped([dict(message) for message in history])
        assert history[1]["content"][1] == {"type": "thinking", "thinking": "", "signature": "abc"}

    def test_a_thinking_block_passes_unchanged(self) -> None:
        """A thinking block must go back exactly as received, empty text and all."""
        block = {"type": "thinking", "thinking": "", "signature": "s"}

        assert request_block(block) == block


# ---------------------------------------------------------------------------
# AI45-02 — the card, the date, the person, and a card answered in words
# ---------------------------------------------------------------------------


class TestTheCard:
    def test_each_write_tool_says_the_app_shows_a_card(self) -> None:
        for tool in WRITE_TOOLS:
            assert "Yes/No card" in tool["description"]
            assert "do not ask them to confirm in words" in tool["description"]

    def test_the_prompt_names_the_person_and_their_date(self) -> None:
        prompt = system_prompt("Mark", date(2026, 10, 13))

        assert "You are talking to Mark." in prompt
        assert "Today is Tuesday 13 October 2026." in prompt
        assert "Yes/No card" in prompt

    def test_the_prompt_holds_no_stale_disc_count(self) -> None:
        assert "1,857" not in BASE_PROMPT
        assert "discs" in BASE_PROMPT  # the formats, not a count

    async def test_each_call_carries_the_person_and_the_date(
        self, db: AsyncSession, chat: AiConversation, craig: Profile
    ) -> None:
        wire = Wire([streamed([text("Hello.")])])

        await _drain(
            run_turn(
                db,
                conversation=chat,
                user=craig,
                client=wire.client(),
                prompt="Hi",
                now=datetime(2026, 6, 30, 23, 30),  # 00:30 on 1 Jul in London
            )
        )

        system = wire.requests[0]["system"]
        assert craig.display_name in system
        assert "Wednesday 1 July 2026" in system

    async def test_typing_while_a_card_waits_declines_it_and_the_chat_goes_on(
        self, db: AsyncSession, chat: AiConversation, craig: Profile
    ) -> None:
        """Probe E's 400: a tool call with no result straight after it. Now the card is
        closed as declined, its result is sent, and the new message follows."""
        await _film(db, "Nosferatu", year=1922)
        wire = Wire(
            [
                streamed(
                    [tool_use("add_to_wanted", {"title": "Nosferatu"})], stop_reason="tool_use"
                ),
                streamed([text("Fine, I won't.")]),
            ]
        )
        client = wire.client()
        await _turn(db, chat, craig, client, "Add Nosferatu")
        call = await _pending(db, chat)

        events = await _turn(db, chat, craig, client, "Actually, never mind.")

        assert events[-1].kind == "done"
        await db.refresh(call)
        assert call.status == "cancelled"
        assert list((await db.execute(select(WantedItem))).scalars()) == []
        sent = wire.requests[1]["messages"]
        assert sent[2]["content"][0]["type"] == "tool_result"
        assert sent[2]["content"][0]["is_error"] is True
        assert sent[3]["content"][0]["text"] == "Actually, never mind."


# ---------------------------------------------------------------------------
# AI45-03 — a compact view, totals first, a page at a time
# ---------------------------------------------------------------------------


class TestCompactResults:
    async def test_each_read_tools_text_carries_its_total(
        self, db: AsyncSession, craig: Profile, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """**The guard (CI):** the totals come first, so no cut can remove them."""
        for index in range(3):
            await _film(db, f"Alien {index}", year=1980 + index, formats=["4k_uhd"])

        totals = {
            "search_collection": {"query": "Alien"},
            "browse_collection": {},
            "list_wanted": {},
            "upcoming_releases": {},
        }
        for tool in READ_TOOLS:
            name = str(tool["name"])
            outcome = await execute_tool(name, totals.get(name, {}), user=craig, db=db)
            assert outcome.ok, outcome.text
            first_key = next(iter(json.loads(outcome.text)))
            assert first_key in {"query", "filters", "total", "from", "films"}, name
            assert "total" in json.loads(outcome.text) or name == "collection_stats"

    async def test_a_film_is_title_year_formats_place_and_watched(
        self, db: AsyncSession, craig: Profile
    ) -> None:
        await _film(db, "Heat", year=1995, formats=["blu_ray", "4k_uhd"])

        outcome = await execute_tool("search_collection", {"query": "Heat"}, user=craig, db=db)

        film = json.loads(outcome.text)["films"][0]
        assert set(film) == {"id", "title", "year", "formats", "place", "watched"}
        assert film["formats"] == ["4k_uhd", "blu_ray"]
        assert film["place"] == "Front 2nd"
        assert json.loads(outcome.text)["total"] == 1

    async def test_browse_pages(self, db: AsyncSession, craig: Profile) -> None:
        for index in range(30):
            await _film(db, f"Film {index:02d}", year=1990, formats=["dvd"])

        first = json.loads((await execute_tool("browse_collection", {}, user=craig, db=db)).text)
        second = json.loads(
            (await execute_tool("browse_collection", {"page": 2}, user=craig, db=db)).text
        )

        assert first["total"] == 30 and first["pages"] == 2
        assert len(first["films"]) == 25 and "page 2" in first["more"]
        assert len(second["films"]) == 5
        assert {f["title"] for f in first["films"]}.isdisjoint(f["title"] for f in second["films"])

    async def test_a_cut_says_how_many_it_left_out(self) -> None:
        items = [{"title": "x" * 500} for _ in range(30)]

        result = json.loads(_fit({"total": 30}, "films", items))

        assert len(json.dumps(result)) <= MAX_RESULT_CHARS
        assert result["total"] == 30
        left_out = 30 - len(result["films"])
        assert left_out > 0 and f"{left_out} more" in result["leftOut"]

    async def test_a_decade_is_asked_for_as_a_decade(
        self, db: AsyncSession, craig: Profile
    ) -> None:
        """AI45-07: "1985" was a 422; it now reads as the 1980s."""
        await _film(db, "Heat", year=1995, formats=["dvd"])
        await _film(db, "Brazil", year=1985, formats=["dvd"])

        outcome = await execute_tool(
            "browse_collection", {"decadeFrom": 1985, "decadeTo": 1985}, user=craig, db=db
        )

        assert outcome.ok
        assert [film["title"] for film in json.loads(outcome.text)["films"]] == ["Brazil"]


# ---------------------------------------------------------------------------
# AI45-04 — failures logged, said plainly, and counted for the daily check
# ---------------------------------------------------------------------------


class TestFailures:
    @pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 413])
    def test_a_fault_only_craig_can_fix_says_so(self, status: int) -> None:
        assert _friendly(status) == CRAIG_HAS_BEEN_TOLD

    def test_a_spend_cap_429_is_not_try_again_in_a_minute(self) -> None:
        assert _friendly(429, None) == CRAIG_HAS_BEEN_TOLD
        assert "minute" in _friendly(429, "30")

    async def test_a_failed_call_leaves_a_usage_row_with_status_and_type(
        self, db: AsyncSession, chat: AiConversation, craig: Profile
    ) -> None:
        wire = Wire([refused(400, "invalid_request_error")])

        events = await _turn(db, chat, craig, wire.client(), "Hello?")

        assert events[-1].kind == "error"
        assert events[-1].text == CRAIG_HAS_BEEN_TOLD
        row = (
            await db.execute(select(AiUsageLogEntry).where(AiUsageLogEntry.user_id == craig.id))
        ).scalar_one()
        assert row.error is not None and row.error.startswith("400 invalid_request_error")
        assert row.cost_usd == 0

    async def test_the_daily_check_names_the_failures(
        self, db: AsyncSession, craig: Profile
    ) -> None:
        now = datetime(2026, 10, 13, 8, 0)
        for minutes in (30, 10):
            db.add(
                AiUsageLogEntry(
                    id=uuid.uuid4(),
                    user_id=craig.id,
                    model="claude-sonnet-5",
                    error="402 billing_error: no credit",
                    created_at_utc=now - timedelta(minutes=minutes),
                )
            )
        await db.flush()

        [(key, message)] = await health_checks.check_assistant(db, now)

        assert key == "assistant:failures"
        assert message is not None and "2 times" in message and "402 billing_error" in message
        assert await health_checks.check_assistant(db, now + timedelta(days=2)) == [
            ("assistant:failures", None)
        ]


# ---------------------------------------------------------------------------
# AI45-05 — caps before every call, the last round answers, tool calls bounded
# ---------------------------------------------------------------------------


class TestCaps:
    async def _cap(self, db: AsyncSession, user: Profile, messages: int) -> None:
        db.add(
            AiSettings(user_id=user.id, daily_message_cap=messages, daily_cost_cap_usd=Decimal("2"))
        )
        await db.flush()

    async def test_a_tool_loop_stops_at_the_cap(
        self, db: AsyncSession, chat: AiConversation, craig: Profile
    ) -> None:
        """P3c: one question made 5 calls with 3 left. Now it stops at the third."""
        await self._cap(db, craig, 3)
        wire = Wire(
            [
                streamed([tool_use("collection_stats", {})], stop_reason="tool_use")
                for _ in range(MAX_TOOL_ROUNDS)
            ]
        )

        events = await _turn(db, chat, craig, wire.client(), "Count everything, again and again")

        assert len(wire.requests) == 3
        assert events[-1].kind == "error" and "all 3" in events[-1].text

    async def test_a_resume_at_the_cap_does_not_call_the_model(
        self, db: AsyncSession, chat: AiConversation, craig: Profile
    ) -> None:
        """P3b: a confirmation tapped at the cap still called the model."""
        from src.services.ai.chat import resume_after_confirmation

        await _film(db, "Nosferatu", year=1922)
        await self._cap(db, craig, 1)
        wire = Wire(
            [streamed([tool_use("add_to_wanted", {"title": "Nosferatu"})], stop_reason="tool_use")]
        )
        client = wire.client()
        await _turn(db, chat, craig, client, "Add Nosferatu")
        call = await _pending(db, chat)
        assert await resolve_tool_call(db, conversation=chat, call=call, user=craig, confirm=True)

        events = await _drain(
            resume_after_confirmation(db, conversation=chat, user=craig, client=client)
        )

        assert len(wire.requests) == 1
        assert events[-1].kind == "error"

    async def test_the_last_round_is_made_to_answer(
        self, db: AsyncSession, chat: AiConversation, craig: Profile
    ) -> None:
        wire = Wire(
            [
                streamed([tool_use("collection_stats", {})], stop_reason="tool_use")
                for _ in range(MAX_TOOL_ROUNDS - 1)
            ]
            + [streamed([text("About 1,900 films.")])]
        )

        events = await _turn(db, chat, craig, wire.client(), "How many?")

        assert events[-1].kind == "done"
        assert all("tool_choice" not in body for body in wire.requests[:-1])
        assert wire.requests[-1]["tool_choice"] == {"type": "none"}

    async def test_tool_calls_per_round_are_capped(
        self, db: AsyncSession, chat: AiConversation, craig: Profile
    ) -> None:
        calls = [tool_use("collection_stats", {}) for _ in range(MAX_TOOL_CALLS_PER_ROUND + 2)]
        wire = Wire([streamed(calls, stop_reason="tool_use"), streamed([text("Done.")])])

        await _turn(db, chat, craig, wire.client(), "Stats, six times")

        rows = list((await db.execute(select(AiToolCall))).scalars())
        assert sum(row.status == "confirmed" for row in rows) == MAX_TOOL_CALLS_PER_ROUND
        assert sum(row.status == "failed" for row in rows) == 2
        results = wire.requests[1]["messages"][-1]["content"]
        assert len(results) == len(calls), "every call still gets its result"

    async def test_cost_is_priced_by_the_configured_id(
        self, db: AsyncSession, chat: AiConversation, craig: Profile
    ) -> None:
        """AI45-08: an alias answering under a dated id was priced at $0."""
        wire = Wire([streamed([text("Hi.")], model="claude-sonnet-5-20990101")])

        await _turn(db, chat, craig, wire.client(), "Hello")

        row = (await db.execute(select(AiUsageLogEntry))).scalar_one()
        assert row.cost_usd > 0


# ---------------------------------------------------------------------------
# AI45-06 — one confirmation writes once; a failed write says so
# ---------------------------------------------------------------------------


class TestOneWrite:
    async def _propose(
        self,
        db: AsyncSession,
        chat: AiConversation,
        craig: Profile,
        name: str,
        args: dict[str, Any],
    ) -> AiToolCall:
        wire = Wire([streamed([tool_use(name, args)], stop_reason="tool_use")])
        events = await _turn(db, chat, craig, wire.client(), "please")
        assert events[-1].kind == "confirm", events[-1]
        return await _pending(db, chat)

    async def test_a_second_yes_writes_nothing(
        self, db: AsyncSession, chat: AiConversation, craig: Profile
    ) -> None:
        await _film(db, "Heat", year=1995)
        call = await self._propose(db, chat, craig, "log_watch", {"title": "Heat"})

        first = await resolve_tool_call(db, conversation=chat, call=call, user=craig, confirm=True)
        second = await resolve_tool_call(db, conversation=chat, call=call, user=craig, confirm=True)

        assert (first, second) == (True, False)
        assert len(list((await db.execute(select(WatchLog))).scalars())) == 1

    async def test_a_write_that_fails_is_marked_failed(
        self,
        db: AsyncSession,
        chat: AiConversation,
        craig: Profile,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await _film(db, "Heat", year=1995)
        call = await self._propose(db, chat, craig, "log_watch", {"title": "Heat"})

        async def broken(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("the database went away")

        monkeypatch.setattr(tools_module, "_run_write", broken)
        await resolve_tool_call(db, conversation=chat, call=call, user=craig, confirm=True)

        assert call.status == "failed"
        assert call.result is not None and "did not work" in call.result


# ---------------------------------------------------------------------------
# AI45-07 — decades, a TMDB match for the wanted list, and shared titles
# ---------------------------------------------------------------------------


class _Result:
    def __init__(self, tmdb_id: int, title: str, year: int) -> None:
        self.id, self.title, self.year = tmdb_id, title, year


def _tmdb(results: list[_Result]) -> Callable[..., Any]:
    class FakeTMDB:
        async def __aenter__(self) -> FakeTMDB:
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def search_movie(self, query: str, year: int | None = None) -> Any:
            return type("R", (), {"results": [r for r in results if year in (None, r.year)]})()

    return FakeTMDB


class TestWhichFilm:
    async def test_a_shared_title_asks_instead_of_guessing(
        self, db: AsyncSession, craig: Profile
    ) -> None:
        older = await _film(db, "Halloween", year=1978)
        await _film(db, "Halloween", year=2018)

        proposal = await prepare_write(
            "log_watch", {"title": "Halloween"}, user=craig, db=db, today=date(2026, 10, 13)
        )

        assert proposal.input is None
        assert proposal.refusal is not None and "2 films" in proposal.refusal
        assert str(older.id) in proposal.refusal

    async def test_the_film_id_the_model_saw_settles_it(
        self, db: AsyncSession, craig: Profile
    ) -> None:
        await _film(db, "Halloween", year=1978)
        newer = await _film(db, "Halloween", year=2018)

        proposal = await prepare_write(
            "log_watch",
            {"title": "Halloween", "movieId": str(newer.id)},
            user=craig,
            db=db,
            today=date(2026, 10, 13),
        )

        assert proposal.input is not None
        assert proposal.input["resolved"]["label"] == "Halloween (2018)"
        assert proposal.input["watchedAt"] == "2026-10-13", "the card shows the date"

    async def test_a_film_nobody_owns_is_added_from_tmdb(
        self,
        db: AsyncSession,
        chat: AiConversation,
        craig: Profile,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.tmdb.client as tmdb_client

        monkeypatch.setattr(tmdb_client, "TMDBClient", _tmdb([_Result(949, "Heat", 1995)]))
        proposal = await prepare_write(
            "add_to_wanted", {"title": "Heat"}, user=craig, db=db, today=date(2026, 10, 13)
        )

        assert proposal.input is not None
        assert proposal.input["resolved"] == {
            "movieId": None,
            "tmdbId": 949,
            "label": "Heat (1995)",
        }

    async def test_an_unclear_tmdb_title_asks(
        self, db: AsyncSession, craig: Profile, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import src.tmdb.client as tmdb_client

        monkeypatch.setattr(
            tmdb_client,
            "TMDBClient",
            _tmdb([_Result(1, "Heat", 1986), _Result(2, "Heat", 1995)]),
        )
        proposal = await prepare_write(
            "add_to_wanted", {"title": "Heat"}, user=craig, db=db, today=date(2026, 10, 13)
        )

        assert proposal.input is None
        assert proposal.refusal is not None and "Heat (1986)" in proposal.refusal

    async def test_a_future_watch_is_refused_before_the_card(
        self, db: AsyncSession, craig: Profile
    ) -> None:
        await _film(db, "Heat", year=1995)

        proposal = await prepare_write(
            "log_watch",
            {"title": "Heat", "watchedAt": "2026-10-14"},
            user=craig,
            db=db,
            today=date(2026, 10, 13),
        )

        assert proposal.refusal is not None and "future" in proposal.refusal


class TestPricing:
    def test_the_five_point_five_family_is_allowed(self) -> None:
        from src.services.ai.pricing import SUPPORTED_MODELS

        assert {"claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"} <= set(SUPPORTED_MODELS)

    def test_fable_five_one_cache_reads_are_a_quarter(self) -> None:
        from src.services.ai.pricing import MODEL_PRICING

        assert MODEL_PRICING["claude-fable-5-1"].cache_read_per_mtok == Decimal("0.25")


class TestCanary:
    """The monthly canary spends money and must never touch a real database."""

    @pytest.mark.parametrize(
        "url", ["", "postgresql://u@ep-x.neon.tech/db", "postgresql://u@x.railway.internal/db"]
    )
    async def test_it_refuses_anything_but_a_throwaway_database(
        self, url: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.scripts import assistant_canary

        monkeypatch.setenv("DATABASE_URL", url)

        assert await assistant_canary.main() == 2
