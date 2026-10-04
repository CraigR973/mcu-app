"""§9.2's tool filtering, §9.3's streaming and §9.4's confirmation — Batch 31.

**§9.4 is a safety boundary and these tests treat it as one.** The criterion is *"'add X to
wanted list' prompts confirmation; cancelling aborts"*, and the way to be sure cancelling
aborts is to look at the table afterwards and find nothing there. Several tests below do
exactly that rather than trusting a status code.

The model is stubbed throughout — every real call spends the owner's money.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.ai import AiConversation, AiMessage, AiToolCall
from src.models.collection_item import SECTIONS
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.wanted import WantedItem
from src.routers.ai import set_ai_client
from src.services.ai.chat import ChatEvent, resolve_tool_call, run_turn
from src.services.ai.client import AiReply, ClaudeClient, TurnEvent
from src.services.ai.tools import ADMIN_ONLY, is_write_tool, tools_for


class _Block:
    """A content block shaped like the SDK's, with the `model_dump` the loop calls."""

    def __init__(self, **fields: Any) -> None:
        self._fields = fields
        for key, value in fields.items():
            setattr(self, key, value)

    def model_dump(self) -> dict[str, Any]:
        return dict(self._fields)


class _Message:
    def __init__(self, content: list[_Block], stop_reason: str) -> None:
        self.content = content
        self.stop_reason = stop_reason
        self.model = "claude-sonnet-5"
        self.usage = type("U", (), {"input_tokens": 100, "output_tokens": 20})()


def text_turn(text: str) -> _Message:
    return _Message([_Block(type="text", text=text)], "end_turn")


def tool_turn(name: str, tool_input: dict[str, Any], *, tool_use_id: str | None = None) -> _Message:
    return _Message(
        [
            _Block(
                type="tool_use",
                id=tool_use_id or f"toolu_{uuid.uuid4().hex[:12]}",
                name=name,
                input=tool_input,
            )
        ],
        "tool_use",
    )


class ScriptedClaude(ClaudeClient):
    """Plays a list of turns in order. Records the history it was handed each time."""

    def __init__(self, turns: list[_Message]) -> None:
        super().__init__(client=None)
        self._turns = list(turns)
        self.histories: list[list[Any]] = []
        self.tool_lists: list[list[Any]] = []

    @property
    def configured(self) -> bool:
        return True

    async def stream_turn(  # type: ignore[override]
        self, messages: list[Any], *, tools: list[Any] | None = None, **kwargs: Any
    ) -> AsyncIterator[TurnEvent]:
        self.histories.append(list(messages))
        self.tool_lists.append(list(tools or []))
        message = self._turns.pop(0)
        for block in message.content:
            if getattr(block, "type", "") == "text":
                # Two chunks, so "renders progressively" is a thing a test can observe.
                half = len(block.text) // 2
                yield TurnEvent(kind="text", text=block.text[:half])
                yield TurnEvent(kind="text", text=block.text[half:])
        yield TurnEvent(
            kind="done",
            message=message,
            reply=AiReply(text="", model="claude-sonnet-5", input_tokens=100, output_tokens=20),
        )


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


async def _profile(db: AsyncSession, role: UserRole) -> Profile:
    profile = Profile(
        id=uuid.uuid4(), display_name=f"{role.value}{uuid.uuid4().hex[:6]}", role=role
    )
    db.add(profile)
    await db.flush()
    return profile


@pytest_asyncio.fixture
async def admin(db: AsyncSession) -> Profile:
    return await _profile(db, UserRole.admin)


@pytest_asyncio.fixture
async def conversation(db: AsyncSession, admin: Profile) -> AiConversation:
    row = AiConversation(id=uuid.uuid4(), user_id=admin.id)
    db.add(row)
    await db.flush()
    return row


async def _movie(db: AsyncSession, title: str) -> Movie:
    movie = Movie(
        id=uuid.uuid4(), tmdb_id=None, title=title, original_title=title, media_type="film"
    )
    db.add(movie)
    await db.flush()
    return movie


async def _drain(events: AsyncIterator[ChatEvent]) -> list[ChatEvent]:
    return [event async for event in events]


class TestToolFiltering:
    """§9.2 — *"the tool list differs correctly between admin and viewer"*."""

    def test_an_admin_gets_every_tool(self) -> None:
        names = {tool["name"] for tool in tools_for(UserRole.admin)}

        assert "search_collection" in names
        assert "add_to_wanted" in names

    def test_a_viewer_does_not_get_the_admin_only_ones(self) -> None:
        names = {tool["name"] for tool in tools_for(UserRole.viewer)}

        assert ADMIN_ONLY.isdisjoint(names)
        assert "add_to_wanted" not in names

    def test_a_viewer_still_gets_the_reads(self) -> None:
        names = {tool["name"] for tool in tools_for(UserRole.viewer)}

        assert "search_collection" in names
        assert "collection_stats" in names

    def test_a_viewer_keeps_their_own_watch_log(self) -> None:
        """**"Write" and "admin-only" are different questions.**

        Watch history is personal — Batch 6 and Batch 37 both scope it to the caller — so
        `log_watch` writes *and* belongs to both people. Collapsing the two axes would have
        taken it from Mark for no reason.
        """
        names = {tool["name"] for tool in tools_for(UserRole.viewer)}

        assert "log_watch" in names
        assert is_write_tool("log_watch")

    def test_the_two_lists_actually_differ(self) -> None:
        assert len(tools_for(UserRole.admin)) > len(tools_for(UserRole.viewer))

    async def test_the_browse_tool_names_every_section_the_collection_has(self) -> None:
        """Batch V4: "Craig's house" and the cabinets, spelt as the filter expects them."""
        tools = {tool["name"]: tool for tool in tools_for(UserRole.viewer)}
        schema = tools["browse_collection"]["input_schema"]
        described = schema["properties"]["section"]["description"]

        for name in SECTIONS:
            assert name in described

    def test_every_tool_declares_a_strict_schema(self) -> None:
        """`strict` is what keeps a malformed argument out of a confirmed write."""
        for tool in tools_for(UserRole.admin):
            assert tool["strict"] is True
            assert tool["input_schema"]["additionalProperties"] is False


class TestStreaming:
    """§9.3 — *"user sends message, streamed response renders progressively"*."""

    async def test_the_answer_arrives_in_pieces(
        self, db: AsyncSession, conversation: AiConversation, admin: Profile
    ) -> None:
        client = ScriptedClaude([text_turn("You own 1,857 discs.")])

        events = await _drain(
            run_turn(db, conversation=conversation, user=admin, client=client, prompt="How many?")
        )

        text_events = [event for event in events if event.kind == "text"]
        assert len(text_events) > 1, "more than one chunk is what 'progressively' means"
        assert "".join(event.text for event in text_events) == "You own 1,857 discs."
        assert events[-1].kind == "done"

    async def test_the_turn_is_stored_so_it_can_be_replayed(
        self, db: AsyncSession, conversation: AiConversation, admin: Profile
    ) -> None:
        client = ScriptedClaude([text_turn("Hello.")])

        await _drain(
            run_turn(db, conversation=conversation, user=admin, client=client, prompt="Hi")
        )

        rows = list(
            (
                await db.execute(
                    select(AiMessage)
                    .where(AiMessage.conversation_id == conversation.id)
                    .order_by(AiMessage.sequence)
                )
            )
            .scalars()
            .all()
        )
        assert [row.role for row in rows] == ["user", "assistant"]
        assert rows[0].sequence == 1 and rows[1].sequence == 2
        assert rows[1].content[0]["type"] == "text", "blocks, not just rendered text"

    async def test_the_conversation_titles_itself(
        self, db: AsyncSession, conversation: AiConversation, admin: Profile
    ) -> None:
        client = ScriptedClaude([text_turn("Sure.")])

        await _drain(
            run_turn(
                db,
                conversation=conversation,
                user=admin,
                client=client,
                prompt="Which 4Ks have I not watched?",
            )
        )

        assert conversation.title == "Which 4Ks have I not watched?"

    async def test_the_history_grows_across_turns(
        self, db: AsyncSession, conversation: AiConversation, admin: Profile
    ) -> None:
        """The API is stateless, so a second question must re-send the first exchange."""
        client = ScriptedClaude([text_turn("First."), text_turn("Second.")])

        await _drain(
            run_turn(db, conversation=conversation, user=admin, client=client, prompt="one")
        )
        await _drain(
            run_turn(db, conversation=conversation, user=admin, client=client, prompt="two")
        )

        assert len(client.histories[0]) == 1
        assert len(client.histories[1]) == 3, "user, assistant, user"

    async def test_a_viewers_turn_is_offered_fewer_tools(
        self, db: AsyncSession, admin: Profile
    ) -> None:
        viewer = await _profile(db, UserRole.viewer)
        row = AiConversation(id=uuid.uuid4(), user_id=viewer.id)
        db.add(row)
        await db.flush()
        client = ScriptedClaude([text_turn("ok")])

        await _drain(run_turn(db, conversation=row, user=viewer, client=client, prompt="hi"))

        offered = {tool["name"] for tool in client.tool_lists[0]}
        assert "add_to_wanted" not in offered

    async def test_an_sse_event_ends_with_a_blank_line(self) -> None:
        """The record separator. Without it the browser holds the last event for ever."""
        rendered = ChatEvent(kind="text", text="hello").to_sse()

        assert rendered.startswith("data: ")
        assert rendered.endswith("\n\n")
        assert json.loads(rendered[len("data: ") :])["text"] == "hello"


class TestReadToolsRunImmediately:
    async def test_a_read_tool_executes_without_asking(
        self, db: AsyncSession, conversation: AiConversation, admin: Profile
    ) -> None:
        """A confirmation prompt for "search my collection" trains people to click yes."""
        await _movie(db, "Heat")
        client = ScriptedClaude(
            [tool_turn("search_collection", {"query": "Heat"}), text_turn("You own Heat.")]
        )

        events = await _drain(
            run_turn(
                db, conversation=conversation, user=admin, client=client, prompt="Do I own Heat?"
            )
        )

        assert events[-1].kind == "done"
        assert not any(event.kind == "confirm" for event in events)
        call = (await db.execute(select(AiToolCall))).scalars().one()
        assert call.status == "confirmed"
        assert call.result is not None


class TestWriteConfirmation:
    """§9.4 — *"'Add X to wanted list' prompts confirmation; cancelling aborts"*."""

    async def test_a_write_tool_suspends_the_turn(
        self, db: AsyncSession, conversation: AiConversation, admin: Profile
    ) -> None:
        await _movie(db, "Nosferatu")
        client = ScriptedClaude([tool_turn("add_to_wanted", {"title": "Nosferatu"})])

        events = await _drain(
            run_turn(
                db,
                conversation=conversation,
                user=admin,
                client=client,
                prompt="Add Nosferatu to the wanted list",
            )
        )

        assert events[-1].kind == "confirm"
        payload = events[-1].payload or {}
        assert payload["toolCalls"][0]["toolName"] == "add_to_wanted"
        assert payload["toolCalls"][0]["input"]["title"] == "Nosferatu"

    async def test_nothing_is_written_before_confirmation(
        self, db: AsyncSession, conversation: AiConversation, admin: Profile
    ) -> None:
        """**The safety boundary, checked against the table rather than the response.**"""
        await _movie(db, "Nosferatu")
        client = ScriptedClaude([tool_turn("add_to_wanted", {"title": "Nosferatu"})])

        await _drain(
            run_turn(db, conversation=conversation, user=admin, client=client, prompt="add it")
        )

        wanted = (await db.execute(select(WantedItem))).scalars().all()
        assert list(wanted) == [], "the write must not have happened yet"
        call = (await db.execute(select(AiToolCall))).scalars().one()
        assert call.status == "pending"
        assert call.result is None

    async def test_confirming_performs_the_write(
        self, db: AsyncSession, conversation: AiConversation, admin: Profile
    ) -> None:
        movie = await _movie(db, "Nosferatu")
        client = ScriptedClaude([tool_turn("add_to_wanted", {"title": "Nosferatu"})])
        await _drain(
            run_turn(db, conversation=conversation, user=admin, client=client, prompt="add it")
        )
        call = (await db.execute(select(AiToolCall))).scalars().one()

        await resolve_tool_call(db, conversation=conversation, call=call, user=admin, confirm=True)

        assert call.status == "confirmed"
        wanted = (await db.execute(select(WantedItem))).scalars().all()
        assert len(list(wanted)) == 1
        assert list(wanted)[0].movie_id == movie.id

    async def test_cancelling_aborts_and_leaves_nothing_behind(
        self, db: AsyncSession, conversation: AiConversation, admin: Profile
    ) -> None:
        """**§9.4's acceptance criterion, stated exactly.**"""
        await _movie(db, "Nosferatu")
        client = ScriptedClaude([tool_turn("add_to_wanted", {"title": "Nosferatu"})])
        await _drain(
            run_turn(db, conversation=conversation, user=admin, client=client, prompt="add it")
        )
        call = (await db.execute(select(AiToolCall))).scalars().one()

        await resolve_tool_call(db, conversation=conversation, call=call, user=admin, confirm=False)

        assert call.status == "cancelled"
        wanted = (await db.execute(select(WantedItem))).scalars().all()
        assert list(wanted) == [], "cancelling aborts"

    async def test_a_cancelled_call_tells_the_model_it_did_not_happen(
        self, db: AsyncSession, conversation: AiConversation, admin: Profile
    ) -> None:
        """Otherwise the next sentence cheerfully reports success."""
        await _movie(db, "Nosferatu")
        client = ScriptedClaude([tool_turn("add_to_wanted", {"title": "Nosferatu"})])
        await _drain(
            run_turn(db, conversation=conversation, user=admin, client=client, prompt="add it")
        )
        call = (await db.execute(select(AiToolCall))).scalars().one()

        await resolve_tool_call(db, conversation=conversation, call=call, user=admin, confirm=False)

        assert call.result is not None
        assert "declined" in call.result

    async def test_a_resolved_call_cannot_be_resolved_twice(
        self, db: AsyncSession, conversation: AiConversation, admin: Profile
    ) -> None:
        """A double-tapped Confirm would otherwise add the film to the list twice."""
        await _movie(db, "Nosferatu")
        client = ScriptedClaude([tool_turn("add_to_wanted", {"title": "Nosferatu"})])
        await _drain(
            run_turn(db, conversation=conversation, user=admin, client=client, prompt="add it")
        )
        call = (await db.execute(select(AiToolCall))).scalars().one()

        await resolve_tool_call(db, conversation=conversation, call=call, user=admin, confirm=True)
        await resolve_tool_call(db, conversation=conversation, call=call, user=admin, confirm=True)

        wanted = (await db.execute(select(WantedItem))).scalars().all()
        assert len(list(wanted)) == 1, "the second resolve is a no-op"

    async def test_a_viewer_cannot_reach_an_admin_only_tool(self, db: AsyncSession) -> None:
        """The tool list is a hint to the model; this is the boundary that holds.

        A model can name a tool it was never offered, so the execution-time check stays
        even though the filtering already removed it.
        """
        viewer = await _profile(db, UserRole.viewer)
        row = AiConversation(id=uuid.uuid4(), user_id=viewer.id)
        db.add(row)
        await _movie(db, "Nosferatu")
        await db.flush()
        client = ScriptedClaude([tool_turn("add_to_wanted", {"title": "Nosferatu"})])

        await _drain(run_turn(db, conversation=row, user=viewer, client=client, prompt="add it"))
        call = (await db.execute(select(AiToolCall))).scalars().one()
        await resolve_tool_call(db, conversation=row, call=call, user=viewer, confirm=True)

        wanted = (await db.execute(select(WantedItem))).scalars().all()
        assert list(wanted) == []
        assert call.result is not None and "admin" in call.result.lower()


class TestConversationApi:
    @pytest_asyncio.fixture
    async def client(self, db: AsyncSession, admin: Profile) -> AsyncIterator[AsyncClient]:
        async def override_db() -> AsyncIterator[AsyncSession]:
            yield db

        async def override_user() -> Profile:
            return admin

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user
        set_ai_client(ScriptedClaude([text_turn("hello")]))
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as http_client:
                yield http_client
        finally:
            app.dependency_overrides.clear()
            set_ai_client(None)

    async def test_the_tool_list_endpoint_reports_the_callers_role(
        self, client: AsyncClient
    ) -> None:
        """§9.2's acceptance, asked as the person it is about."""
        body = (await client.get("/api/v1/ai/tools")).json()

        assert body["role"] == "admin"
        assert any(item["name"] == "add_to_wanted" and item["writes"] for item in body["items"])

    async def test_a_conversation_can_be_created_and_listed(self, client: AsyncClient) -> None:
        created = await client.post("/api/v1/ai/conversations")

        assert created.status_code == 201
        listed = (await client.get("/api/v1/ai/conversations")).json()
        assert listed["total"] == 1
        assert listed["items"][0]["id"] == created.json()["id"]

    async def test_another_persons_conversation_is_not_found(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        other = await _profile(db, UserRole.viewer)
        theirs = AiConversation(id=uuid.uuid4(), user_id=other.id)
        db.add(theirs)
        await db.flush()

        response = await client.get(f"/api/v1/ai/conversations/{theirs.id}")

        assert response.status_code == 404

    async def test_the_detail_hides_tool_result_messages(
        self, client: AsyncClient, db: AsyncSession, conversation: AiConversation
    ) -> None:
        """A `tool_result` is a user-role message on the wire and nothing a person said."""
        db.add(
            AiMessage(
                id=uuid.uuid4(),
                conversation_id=conversation.id,
                role="tool_result",
                content=[{"type": "tool_result", "tool_use_id": "toolu_x", "content": "{}"}],
                text="",
                sequence=1,
            )
        )
        await db.flush()

        body = (await client.get(f"/api/v1/ai/conversations/{conversation.id}")).json()

        assert body["messages"] == []

    async def test_a_pending_call_survives_the_stream_that_raised_it(
        self, client: AsyncClient, db: AsyncSession, conversation: AiConversation
    ) -> None:
        """Somebody can close the tab on a confirmation prompt and come back to it."""
        db.add(
            AiToolCall(
                id=uuid.uuid4(),
                conversation_id=conversation.id,
                tool_use_id="toolu_pending",
                tool_name="add_to_wanted",
                tool_input={"title": "Nosferatu"},
            )
        )
        await db.flush()

        body = (await client.get(f"/api/v1/ai/conversations/{conversation.id}")).json()

        assert len(body["pendingToolCalls"]) == 1
        assert body["pendingToolCalls"][0]["input"]["title"] == "Nosferatu"
