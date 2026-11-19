"""AG8 — the assistant, kept (AI51-01, AI51-03, AI51-04).

The refusal guard drives the **real** SDK and client over a scripted wire, as Batch X7's tests
do (``tests/test_ai_repair.py``): a refusal before any output, after part of an answer, and
after only an empty thinking block. Each says so, stores the declined sentence rather than an
empty or cut-off turn, leaves a usage row the daily check counts, and the next message in the
chat replays a valid conversation. No call leaves the machine.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ai import AiConversation, AiMessage, AiToolCall, AiUsageLogEntry
from src.models.profile import Profile
from src.models.wanted import WantedItem
from src.models.watch_log import WatchLog
from src.services import health_checks
from src.services.ai import chat as chat_module
from src.services.ai.chat import resolve_tool_call
from src.services.ai.client import BASE_PROMPT, DECLINED
from src.services.ai.tools import prepare_write
from tests.test_ai_repair import (
    Wire,
    _film,
    _pending,
    _turn,
    assert_request_shaped,
    streamed,
    text,
    thinking,
    tool_use,
)
from tests.test_ai_repair import chat as chat
from tests.test_ai_repair import craig as craig
from tests.test_ai_repair import db as db

# ---------------------------------------------------------------------------
# AI51-01 — a refusal says so, in three shapes
# ---------------------------------------------------------------------------

SHAPES = {
    "before any output": [],
    "mid-answer": [text("Heat is on shelf A3 and the")],
    "after an empty thinking block": [thinking("")],
}


async def _assistant_turns(db: AsyncSession, chat: AiConversation) -> list[AiMessage]:
    return list(
        (
            await db.execute(
                select(AiMessage)
                .where(AiMessage.conversation_id == chat.id, AiMessage.role == "assistant")
                .order_by(AiMessage.sequence)
            )
        ).scalars()
    )


@pytest.mark.parametrize("shape", list(SHAPES))
async def test_a_refusal_says_so_stores_no_empty_turn_and_the_chat_goes_on(
    db: AsyncSession, chat: AiConversation, craig: Profile, shape: str
) -> None:
    wire = Wire(
        [
            streamed(SHAPES[shape], stop_reason="refusal"),
            streamed([text("Alien is on shelf C2.")]),
        ]
    )
    client = wire.client()

    events = await _turn(db, chat, craig, client, "Where is Heat?")

    assert events[-1].kind == "declined" and events[-1].text == DECLINED
    [stored] = await _assistant_turns(db, chat)
    assert stored.content == [{"type": "text", "text": DECLINED}]
    assert stored.text == DECLINED
    assert "shelf A3" not in str(stored.content), "the cut-off answer is discarded"
    [usage] = (
        await db.execute(select(AiUsageLogEntry).where(AiUsageLogEntry.user_id == craig.id))
    ).scalars()
    assert usage.stop_reason == "refusal" and usage.error is None

    # The next message replays user → assistant (one text block) → user: no empty turn.
    follow_up = await _turn(db, chat, craig, client, "Where is Alien?")
    assert follow_up[-1].kind == "done"
    messages = wire.requests[1]["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert messages[1]["content"] == [{"type": "text", "text": DECLINED}]
    assert all(message["content"] for message in messages)
    assert_request_shaped(messages)


async def test_a_refusal_after_a_tool_round_drops_the_round_s_answer_too(
    db: AsyncSession, chat: AiConversation, craig: Profile
) -> None:
    wire = Wire(
        [
            streamed([tool_use("collection_stats", {})], stop_reason="tool_use"),
            streamed([text("You own")], stop_reason="refusal"),
        ]
    )
    events = await _turn(db, chat, craig, wire.client(), "How many?")
    assert events[-1].kind == "declined"
    turns = await _assistant_turns(db, chat)
    assert turns[-1].content == [{"type": "text", "text": DECLINED}]


async def test_the_daily_check_counts_a_refusal(db: AsyncSession, craig: Profile) -> None:
    now = datetime(2026, 11, 20, 8, 0)
    db.add(
        AiUsageLogEntry(
            id=uuid.uuid4(),
            user_id=craig.id,
            model="claude-sonnet-5",
            stop_reason="refusal",
            created_at_utc=now - timedelta(minutes=20),
        )
    )
    await db.flush()

    [(key, message)] = await health_checks.check_assistant(db, now)
    assert key == "assistant:failures"
    assert message is not None and "declined to answer once" in message

    db.add(
        AiUsageLogEntry(
            id=uuid.uuid4(),
            user_id=craig.id,
            model="claude-sonnet-5",
            error="402 billing_error: no credit",
            created_at_utc=now - timedelta(minutes=10),
        )
    )
    await db.flush()
    [(_key, both)] = await health_checks.check_assistant(db, now)
    assert both is not None and "failed once" in both and "declined to answer once" in both
    assert await health_checks.check_assistant(db, now + timedelta(days=2)) == [
        ("assistant:failures", None)
    ]


async def test_the_give_up_leaves_a_row_the_daily_check_counts(
    db: AsyncSession,
    chat: AiConversation,
    craig: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The last round is told to answer (AI45-05), so a give-up needs a model that ignores it."""
    monkeypatch.setattr(chat_module, "MAX_TOOL_ROUNDS", 2)
    wire = Wire(
        [streamed([tool_use("collection_stats", {})], stop_reason="tool_use") for _ in range(2)]
    )
    events = await _turn(db, chat, craig, wire.client(), "Count, again and again")

    assert events[-1].kind == "error" and "round in circles" in events[-1].text
    rows = list(
        (
            await db.execute(select(AiUsageLogEntry).where(AiUsageLogEntry.user_id == craig.id))
        ).scalars()
    )
    [gave_up] = [row for row in rows if row.stop_reason == "gave_up"]
    assert gave_up.error is not None and gave_up.error.startswith("gave up")
    assert gave_up.cost_usd == 0
    [(_key, message)] = await health_checks.check_assistant(db, gave_up.created_at_utc)
    assert message is not None and "(gave up)" in message


# ---------------------------------------------------------------------------
# AI51-03 — model arguments are checked against their types
# ---------------------------------------------------------------------------

TODAY = date(2026, 11, 19)


@pytest.mark.parametrize(
    ("name", "arguments", "refusal"),
    [
        ("log_watch", {"rating": "four"}, "half stars"),
        ("log_watch", {"rating": "4"}, "half stars"),
        ("log_watch", {"rating": True}, "half stars"),
        ("log_watch", {"rating": 4.3}, "half stars"),
        ("log_watch", {"watchedAt": 20261101}, "YYYY-MM-DD"),
        ("log_watch", {"year": "1995"}, "whole number"),
        ("log_watch", {"title": ["Heat"]}, "as text"),
        ("add_to_wanted", {"maxPrice": 19.99}, "like '19.99'"),
        ("add_to_wanted", {"maxPrice": "19.999"}, "pounds and pence"),
        ("add_to_wanted", {"maxPrice": "0"}, "more than £0"),
        ("add_to_wanted", {"preferredFormat": "laserdisc"}, "one of"),
        ("add_to_wanted", {"movieId": 42}, "earlier result"),
    ],
)
async def test_a_wrong_type_is_a_refusal_the_model_reads_never_a_card(
    db: AsyncSession, craig: Profile, name: str, arguments: dict[str, Any], refusal: str
) -> None:
    await _film(db, "Heat", year=1995, formats=["blu_ray"])
    proposal = await prepare_write(
        name, {"title": "Heat", **arguments}, user=craig, db=db, today=TODAY
    )
    assert proposal.input is None
    assert proposal.refusal is not None and refusal in proposal.refusal


async def test_a_wrong_type_in_the_chat_is_read_back_not_raised(
    db: AsyncSession, chat: AiConversation, craig: Profile
) -> None:
    """AI51-03's crash: a rating of "four" raised out of the loop and left a card pending."""
    await _film(db, "Heat", year=1995, formats=["blu_ray"])
    wire = Wire(
        [
            streamed(
                [tool_use("log_watch", {"title": "Heat", "rating": "four"})],
                stop_reason="tool_use",
            ),
            streamed([text("What rating, out of 5?")]),
        ]
    )
    events = await _turn(db, chat, craig, wire.client(), "I watched Heat, four stars")

    assert events[-1].kind == "done"
    [call] = (await db.execute(select(AiToolCall))).scalars()
    assert call.status == "failed" and "half stars" in (call.result or "")


async def test_the_card_holds_what_will_be_stored(
    db: AsyncSession, chat: AiConversation, craig: Profile
) -> None:
    """Each value in the one form the write stores and the card prints."""
    await _film(db, "Heat", year=1995, formats=["blu_ray"])
    await _film(db, "Nosferatu", year=1922)
    watch = await prepare_write(
        "log_watch",
        {"title": "Heat", "rating": 4, "watchedAt": "2026-11-18", "extra": "dropped"},
        user=craig,
        db=db,
        today=TODAY,
    )
    assert watch.input is not None
    assert {k: v for k, v in watch.input.items() if k != "resolved"} == {
        "title": "Heat",
        "rating": 4.0,
        "watchedAt": "2026-11-18",
    }
    want = await prepare_write(
        "add_to_wanted",
        {"title": "Nosferatu", "maxPrice": "£20", "preferredFormat": "4k_uhd"},
        user=craig,
        db=db,
        today=TODAY,
    )
    assert want.input is not None
    assert want.input["maxPrice"] == "20.00" and want.input["preferredFormat"] == "4k_uhd"

    # Through the chat: the card's input is what the Yes writes.
    wire = Wire(
        [
            streamed(
                [tool_use("log_watch", {"title": "Heat", "rating": 4, "watchedAt": "2026-11-18"})],
                stop_reason="tool_use",
            ),
            streamed([text("Logged.")]),
        ]
    )
    client = wire.client()
    events = await _turn(db, chat, craig, client, "Watched Heat yesterday, 4 stars")
    [card] = events[-1].payload["toolCalls"]  # type: ignore[index]
    assert card["input"]["rating"] == 4.0 and card["input"]["watchedAt"] == "2026-11-18"
    call = await _pending(db, chat)
    assert await resolve_tool_call(db, conversation=chat, call=call, user=craig, confirm=True)
    [logged] = (await db.execute(select(WatchLog).where(WatchLog.user_id == craig.id))).scalars()
    assert float(logged.personal_rating) == card["input"]["rating"]  # type: ignore[arg-type]
    assert logged.watched_at.isoformat() == card["input"]["watchedAt"]
    assert (await db.execute(select(WantedItem))).first() is None


# ---------------------------------------------------------------------------
# AI51-04 — the prompt's load-bearing lines are asserted
# ---------------------------------------------------------------------------

LOAD_BEARING = [
    # A wrong shelf costs somebody a trip to the garage.
    "Use the tools for anything about the collection.",
    "Never invent a film, a shelf location, a price or a watch date.",
    "say what you would need rather than guessing",
    # A cut list must say so.
    "When a result says films were left out, say how many, or ask for the next page",
    "never present part of a list as the whole of it",
    # The card is the confirmation (AI45-02).
    "The app shows the person a Yes/No card before either one runs",
    "Do not ask them to confirm in words first; the card is the confirmation.",
    "If a tool says a title matches more than one film, ask which one they mean.",
]


@pytest.mark.parametrize("line", LOAD_BEARING)
def test_the_prompt_keeps_its_load_bearing_line(line: str) -> None:
    """A structural guard, not an eval: deleting one of these fails CI."""
    assert line in " ".join(BASE_PROMPT.replace("**", "").split())
