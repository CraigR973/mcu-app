"""api.anthropic.com — a recorded model.

It speaks the real Messages streaming format (``message_start`` … ``message_stop``) so the real
``anthropic`` SDK parses it, and it checks what it is sent the way the real API does: an
assistant block carrying a field the API does not accept (the SDK-only ``parsed_output`` that
broke every follow-up until Batch X7) is refused with the API's own 400.

What it says comes from the scenario, else it echoes the question::

    {"anthropic": {"rules": [
        {"lastUserContains": "i watched", "toolUse": {"name": "log_watch",
                                                      "input": {"title": "...", "rating": 4}}},
        {"lastIsToolResult": true, "text": "Done."}]}}

Every request is logged as ``kind: "model"`` with the roles and block types it carried, so a
case can say the second message really carried the first answer.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import httpx

HOSTS = ("api.anthropic.com",)

#: The only fields the API accepts on a text block it is sent back. Anything else is a 400.
_TEXT_FIELDS = {"type", "text", "cache_control", "citations"}


def _blocks(message: dict[str, Any]) -> list[dict[str, Any]]:
    content = message.get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [block for block in content or [] if isinstance(block, dict)]


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        texts = [b.get("text", "") for b in _blocks(message) if b.get("type") == "text"]
        if texts:
            return " ".join(texts)
    return ""


def _refusal(messages: list[dict[str, Any]]) -> str | None:
    for index, message in enumerate(messages):
        if message.get("role") != "assistant":
            continue
        for position, block in enumerate(_blocks(message)):
            if block.get("type") == "text":
                extra = sorted(set(block) - _TEXT_FIELDS)
                if extra:
                    where = f"messages.{index}.content.{position}.text.{extra[0]}"
                    return f"{where}: Extra inputs are not permitted"
    return None


def _sse(events: list[tuple[str, dict[str, Any]]]) -> bytes:
    return "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events).encode()


def _stream(model: str, text: str | None, tool: dict[str, Any] | None) -> bytes:
    events: list[tuple[str, dict[str, Any]]] = [
        (
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "id": "msg_e2e",
                    "type": "message",
                    "role": "assistant",
                    "model": model,
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 120, "output_tokens": 1},
                },
            },
        )
    ]
    index = 0
    if text:
        events.append(
            (
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": index,
                    "content_block": {"type": "text", "text": ""},
                },
            )
        )
        third = max(1, len(text) // 3)
        for start in range(0, len(text), third):
            events.append(
                (
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": index,
                        "delta": {"type": "text_delta", "text": text[start : start + third]},
                    },
                )
            )
        events.append(("content_block_stop", {"type": "content_block_stop", "index": index}))
        index += 1
    if tool:
        events.append(
            (
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": index,
                    "content_block": {
                        "type": "tool_use",
                        "id": f"toolu_e2e_{uuid4().hex}",
                        "name": tool["name"],
                        "input": {},
                    },
                },
            )
        )
        events.append(
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": index,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": json.dumps(tool["input"]),
                    },
                },
            )
        )
        events.append(("content_block_stop", {"type": "content_block_stop", "index": index}))
    events.append(
        (
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": "tool_use" if tool else "end_turn", "stop_sequence": None},
                "usage": {"output_tokens": 40},
            },
        )
    )
    events.append(("message_stop", {"type": "message_stop"}))
    return _sse(events)


def handle(request: httpx.Request, world: Any) -> httpx.Response:
    if request.url.path != "/v1/messages" or request.method != "POST":
        world.log(kind="unknown", host=request.url.host, path=request.url.path)
        return httpx.Response(
            404,
            json={"type": "error", "error": {"type": "not_found_error", "message": "not faked"}},
        )

    body: dict[str, Any] = json.loads(request.content)
    messages: list[dict[str, Any]] = body.get("messages", [])
    world.log(
        kind="model",
        roles=[m.get("role") for m in messages],
        blocks=[[b.get("type") for b in _blocks(m)] for m in messages],
        lastUser=_last_user_text(messages)[:200],
        toolChoice=body.get("tool_choice"),
        stream=bool(body.get("stream")),
    )

    problem = _refusal(messages)
    if problem:
        return httpx.Response(
            400,
            json={"type": "error", "error": {"type": "invalid_request_error", "message": problem}},
        )

    last = messages[-1] if messages else {}
    last_is_result = any(b.get("type") == "tool_result" for b in _blocks(last))
    question = _last_user_text(messages)

    text: str | None = None
    tool: dict[str, Any] | None = None
    for rule in world.scenario().get("anthropic", {}).get("rules", []):
        if rule.get("lastIsToolResult") and not last_is_result:
            continue
        needle = rule.get("lastUserContains")
        if needle and (last_is_result or needle.lower() not in question.lower()):
            continue
        text, tool = rule.get("text"), rule.get("toolUse")
        break
    else:
        text = (
            "Done."
            if last_is_result
            else f"You asked: {question.strip()[:120]}. This answer is recorded."
        )

    model = body.get("model", "claude-sonnet-5")
    if not body.get("stream"):
        content: list[dict[str, Any]] = []
        if text:
            content.append({"type": "text", "text": text})
        if tool:
            content.append(
                {
                    "type": "tool_use",
                    "id": f"toolu_e2e_{uuid4().hex}",
                    "name": tool["name"],
                    "input": tool["input"],
                }
            )
        return httpx.Response(
            200,
            json={
                "id": "msg_e2e",
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": content,
                "stop_reason": "tool_use" if tool else "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 120, "output_tokens": 40},
            },
        )
    return httpx.Response(
        200, content=_stream(model, text, tool), headers={"content-type": "text/event-stream"}
    )
