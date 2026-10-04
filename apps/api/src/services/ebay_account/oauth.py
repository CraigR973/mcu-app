"""eBay's sign-in for one person: consent, the code swap, the refresh — Batch T8b, #245.

Built from eBay's own documentation, read 4 Oct 2026 ("The authorization code grant flow"):

- **Consent:** ``GET https://auth.ebay.com/oauth2/authorize`` with ``client_id``,
  ``redirect_uri`` (the app's RuName, not a URL), ``response_type=code``, ``scope`` and
  ``state``. ``prompt=login`` makes eBay ask who is signing in even when the browser is
  already signed in, so one person's eBay session cannot connect to the other's profile.
- **The swap:** ``POST https://api.ebay.com/identity/v1/oauth2/token``, form-encoded, with
  the client id and secret as HTTP Basic auth: ``grant_type=authorization_code``, the
  ``code`` and the same ``redirect_uri``. eBay answers a two-hour access token and an
  18-month refresh token.
- **The refresh:** the same endpoint with ``grant_type=refresh_token``.

**The fewest scopes.** eBay documents no scope for the two Trading API calls T8b makes, so
the token asks for the base scope alone; the first live connection is what proves it is
enough, and a refusal there says so rather than being worked around (`DECISIONS.md` #245).

Nothing here logs or returns a token in an error: eBay's error code and description only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import structlog

from src.config import settings

logger = structlog.get_logger(__name__)

AUTHORIZE_URL = "https://auth.ebay.com/oauth2/authorize"
TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"  # noqa: S105 - a URL, not a secret
#: The fewest scopes: the base one (see the module docstring).
SCOPES = ("https://api.ebay.com/oauth/api_scope",)
TIMEOUT = 20.0


class EbayConnectNotConfigured(RuntimeError):
    """A value connecting needs is missing from this deployment. Raised before any request."""


class EbayAuthError(RuntimeError):
    """eBay refused or failed a sign-in request.

    ``refused`` is true when eBay says the code or refresh token is no good
    (``invalid_grant``): the person must connect again, and a stored token is deleted.
    """

    def __init__(self, message: str, *, status_code: int | None, refused: bool) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.refused = refused


@dataclass(frozen=True)
class Grant:
    """What eBay answers to the code swap."""

    access_token: str
    access_expires_in: int
    refresh_token: str
    refresh_expires_in: int


@dataclass(frozen=True)
class Refreshed:
    access_token: str
    access_expires_in: int


def missing_settings() -> list[str]:
    """The variables connecting needs and this deployment lacks, by name."""
    needed = {
        "EBAY_CLIENT_ID": settings.ebay_client_id,
        "EBAY_CLIENT_SECRET": settings.ebay_client_secret,
        "EBAY_RUNAME": settings.ebay_runame,
        "EBAY_TOKEN_KEY": settings.ebay_token_key,
    }
    return [name for name, value in needed.items() if not value]


def require_configured() -> None:
    missing = missing_settings()
    if missing:
        raise EbayConnectNotConfigured(
            f"Connecting eBay is not set up: {', '.join(missing)} missing."
        )


def authorize_url(state: str) -> str:
    """Where to send a person to sign in to eBay and agree."""
    require_configured()
    query = urlencode(
        {
            "client_id": settings.ebay_client_id,
            "redirect_uri": settings.ebay_runame,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "state": state,
            "prompt": "login",
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def _refusal(response: httpx.Response, action: str) -> EbayAuthError:
    """eBay's error, without anything that was sent."""
    error = description = ""
    try:
        body: Any = response.json()
        if isinstance(body, dict):
            error = str(body.get("error") or "")
            description = str(body.get("error_description") or "")
    except ValueError:
        pass
    detail = f": {error}" if error else ""
    if description:
        detail += f" ({description[:160]})"
    logger.warning("ebay_auth_refused", action=action, status=response.status_code, error=error)
    return EbayAuthError(
        f"eBay refused {action} (HTTP {response.status_code}{detail})",
        status_code=response.status_code,
        refused=error == "invalid_grant",
    )


async def _token_request(
    client: httpx.AsyncClient, form: dict[str, str], action: str
) -> dict[str, Any]:
    require_configured()
    try:
        response = await client.post(
            TOKEN_URL,
            data=form,
            auth=(settings.ebay_client_id, settings.ebay_client_secret),
            headers={"Accept": "application/json"},
            timeout=TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise EbayAuthError(
            f"eBay could not be reached for {action} ({type(exc).__name__})",
            status_code=None,
            refused=False,
        ) from exc
    if response.status_code != 200:
        raise _refusal(response, action)
    body: Any = response.json()
    if not isinstance(body, dict) or not isinstance(body.get("access_token"), str):
        raise EbayAuthError(
            f"eBay's answer to {action} had no access token", status_code=200, refused=False
        )
    return body


async def exchange_code(client: httpx.AsyncClient, code: str) -> Grant:
    """Swap the one-time code eBay sent back for a person's tokens."""
    body = await _token_request(
        client,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.ebay_runame,
        },
        "the sign-in",
    )
    refresh = body.get("refresh_token")
    if not isinstance(refresh, str) or not refresh:
        raise EbayAuthError(
            "eBay's answer to the sign-in had no refresh token", status_code=200, refused=False
        )
    return Grant(
        access_token=str(body["access_token"]),
        access_expires_in=int(body.get("expires_in") or 7200),
        refresh_token=refresh,
        refresh_expires_in=int(body.get("refresh_token_expires_in") or 47_304_000),
    )


async def refresh_access(client: httpx.AsyncClient, refresh_token: str, scopes: str) -> Refreshed:
    """A fresh access token from the refresh token, for the scopes consented to."""
    body = await _token_request(
        client,
        {"grant_type": "refresh_token", "refresh_token": refresh_token, "scope": scopes},
        "the refresh",
    )
    return Refreshed(
        access_token=str(body["access_token"]),
        access_expires_in=int(body.get("expires_in") or 7200),
    )
