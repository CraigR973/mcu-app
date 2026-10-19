"""The browsers' push services.

Subscriptions registered by the suite point at ``push.e2e.example``. The app encrypts and
signs each message exactly as it does for a real push service; this host decrypts it with the
subscription's private half and logs what the person would have been shown. The keys are in
``devices.json`` beside the log, written by the case that registered the device, and are not
cleared between cases (a device stays registered in the database, so its key must stay known)::

    {"<endpoint>": {"d": "<private scalar, base64url>", "auth": "<base64url>"}}
"""

from __future__ import annotations

import json
from typing import Any

import httpx

HOSTS = ("push.e2e.example",)


def handle(request: httpx.Request, world: Any) -> httpx.Response:
    from cryptography.hazmat.primitives.asymmetric import ec

    from src.services import webpush

    endpoint = str(request.url)
    try:
        keys = json.loads((world.directory / "devices.json").read_text()).get(endpoint)
    except (OSError, ValueError):
        keys = None
    if keys is None:
        world.log(
            kind="unknown", host=request.url.host, path=request.url.path, why="no key for endpoint"
        )
        return httpx.Response(410)
    private = ec.derive_private_key(
        int.from_bytes(webpush.b64url_decode(keys["d"]), "big"), ec.SECP256R1()
    )
    plain = webpush.decrypt(
        request.content, ua_private=private, auth_secret=webpush.b64url_decode(keys["auth"])
    )
    try:
        payload: Any = json.loads(plain)
    except ValueError:
        payload = plain.decode("utf-8", "replace")
    world.log(
        kind="push",
        endpoint=endpoint,
        payload=payload,
        authorization_scheme=request.headers.get("authorization", "").split(" ")[0],
    )
    return httpx.Response(201)
