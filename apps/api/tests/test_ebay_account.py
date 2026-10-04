"""Batch T8b — Connect eBay: sealing, the sign-in requests, and reading the lists.

eBay's requests and answers here follow its own documentation (read 4 Oct 2026); the list
fixtures are its documented samples, made well-formed, and one built from its field
reference where it prints no sample (`DECISIONS.md` #245).
"""

from __future__ import annotations

import base64
import json
import uuid
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from src.services.ebay_account import oauth, trading
from src.services.ebay_account.crypto import (
    SealBroken,
    TokenKeyInvalid,
    derive_key,
    open_sealed,
    seal,
)

FIXTURES = Path(__file__).parent / "fixtures"
KEY_B64 = base64.b64encode(bytes(range(32))).decode()
OTHER_KEY_B64 = base64.b64encode(bytes(range(1, 33))).decode()
OWNER = uuid.UUID("3f2504e0-4f89-41d3-9a0c-0305e82c3401")
SOMEONE_ELSE = uuid.UUID("3f2504e0-4f89-41d3-9a0c-0305e82c3402")
# eBay's own example token shape, from its documentation.
ACCESS = "v^1.1#i^1#p^3#r^1...XzMjRV4xMjg0"
REFRESH = "v^1.1#i^1#p^3#r^1...zYjRV4xMjg0"


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.config.settings.ebay_client_id", "TheReal-MCU-PRD-0123456789")
    monkeypatch.setattr("src.config.settings.ebay_client_secret", "PRD-secret-not-real")
    monkeypatch.setattr("src.config.settings.ebay_runame", "The_Real_MCU-TheReal-TheRea-abcdefgh")
    monkeypatch.setattr("src.config.settings.ebay_token_key", KEY_B64)


class TestSealing:
    """AES-256-GCM, keyed from EBAY_TOKEN_KEY, bound to the owner's profile."""

    def test_a_token_opens_for_its_owner_with_its_key(self) -> None:
        key = derive_key(KEY_B64)
        sealed = seal(ACCESS, owner=OWNER, key=key)

        assert open_sealed(sealed, owner=OWNER, key=key) == ACCESS
        assert ACCESS.encode() not in sealed, "never stored as text"
        assert sealed[:1] == b"\x01"

    def test_the_same_token_seals_differently_each_time(self) -> None:
        key = derive_key(KEY_B64)
        assert seal(ACCESS, owner=OWNER, key=key) != seal(ACCESS, owner=OWNER, key=key)

    def test_a_token_moved_to_another_person_does_not_open(self) -> None:
        key = derive_key(KEY_B64)
        sealed = seal(ACCESS, owner=OWNER, key=key)
        with pytest.raises(SealBroken):
            open_sealed(sealed, owner=SOMEONE_ELSE, key=key)

    def test_a_changed_key_or_an_altered_token_does_not_open(self) -> None:
        sealed = seal(ACCESS, owner=OWNER, key=derive_key(KEY_B64))
        with pytest.raises(SealBroken):
            open_sealed(sealed, owner=OWNER, key=derive_key(OTHER_KEY_B64))
        altered = sealed[:-1] + bytes([sealed[-1] ^ 1])
        with pytest.raises(SealBroken):
            open_sealed(altered, owner=OWNER, key=derive_key(KEY_B64))

    def test_the_key_is_32_bytes_in_base64_and_never_used_raw(self) -> None:
        with pytest.raises(TokenKeyInvalid):
            derive_key("not base64!")
        with pytest.raises(TokenKeyInvalid):
            derive_key(base64.b64encode(b"short").decode())
        assert derive_key(KEY_B64) != bytes(range(32))


class TestTheSignIn:
    """eBay's authorization code grant, as its documentation describes it."""

    def test_the_consent_address_asks_for_the_fewest_scopes_and_a_fresh_sign_in(
        self, configured: None
    ) -> None:
        del configured
        url = urlsplit(oauth.authorize_url("a-one-time-state-0123456789"))
        query = {key: values[0] for key, values in parse_qs(url.query).items()}

        assert f"{url.scheme}://{url.netloc}{url.path}" == "https://auth.ebay.com/oauth2/authorize"
        assert query == {
            "client_id": "TheReal-MCU-PRD-0123456789",
            "redirect_uri": "The_Real_MCU-TheReal-TheRea-abcdefgh",
            "response_type": "code",
            "scope": "https://api.ebay.com/oauth/api_scope",
            "state": "a-one-time-state-0123456789",
            "prompt": "login",
        }

    def test_nothing_is_sent_without_every_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.config.settings.ebay_runame", "")
        monkeypatch.setattr("src.config.settings.ebay_token_key", "")
        with pytest.raises(oauth.EbayConnectNotConfigured, match="EBAY_RUNAME, EBAY_TOKEN_KEY"):
            oauth.authorize_url("state")

    async def test_the_code_is_swapped_with_the_runame_and_the_app_s_own_credentials(
        self, configured: None
    ) -> None:
        del configured
        sent: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent.append(request)
            return httpx.Response(
                200,
                json={
                    "access_token": ACCESS,
                    "expires_in": 7200,
                    "refresh_token": REFRESH,
                    "refresh_token_expires_in": 47304000,
                    "token_type": "User Access Token",
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            grant = await oauth.exchange_code(client, "v^1.1#i^1#f^0#code")

        assert grant == oauth.Grant(ACCESS, 7200, REFRESH, 47304000)
        request = sent[0]
        assert str(request.url) == "https://api.ebay.com/identity/v1/oauth2/token"
        expected = base64.b64encode(b"TheReal-MCU-PRD-0123456789:PRD-secret-not-real").decode()
        assert request.headers["Authorization"] == f"Basic {expected}"
        form = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
        assert form == {
            "grant_type": "authorization_code",
            "code": "v^1.1#i^1#f^0#code",
            "redirect_uri": "The_Real_MCU-TheReal-TheRea-abcdefgh",
        }

    async def test_a_spent_code_is_a_refusal_and_says_nothing_it_was_sent(
        self, configured: None
    ) -> None:
        del configured

        def handler(request: httpx.Request) -> httpx.Response:
            del request
            return httpx.Response(
                400,
                json={
                    "error": "invalid_grant",
                    "error_description": "the provided authorization grant code is invalid",
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(oauth.EbayAuthError) as raised:
                await oauth.exchange_code(client, "the-secret-code")

        assert raised.value.refused
        assert "invalid_grant" in str(raised.value)
        assert "the-secret-code" not in str(raised.value)

    async def test_a_refresh_asks_for_the_scopes_consented_to(self, configured: None) -> None:
        del configured
        sent: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent.append(request)
            return httpx.Response(200, json={"access_token": "fresh", "expires_in": 7200})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            refreshed = await oauth.refresh_access(
                client, REFRESH, "https://api.ebay.com/oauth/api_scope"
            )

        assert refreshed == oauth.Refreshed("fresh", 7200)
        form = {key: values[0] for key, values in parse_qs(sent[0].content.decode()).items()}
        assert form == {
            "grant_type": "refresh_token",
            "refresh_token": REFRESH,
            "scope": "https://api.ebay.com/oauth/api_scope",
        }


def _trading(content: bytes, status: int = 200) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(status, content=content)

    return httpx.MockTransport(handler), sent


class TestReadingTheLists:
    async def test_a_call_carries_the_token_and_eBay_s_four_headers(self) -> None:
        transport, sent = _trading((FIXTURES / "ebay_trading_buying_doc_sample.xml").read_bytes())
        async with httpx.AsyncClient(transport=transport) as client:
            await trading.watching(client, ACCESS)

        request = sent[0]
        assert str(request.url) == "https://api.ebay.com/ws/api.dll"
        assert request.headers["X-EBAY-API-IAF-TOKEN"] == ACCESS
        assert request.headers["X-EBAY-API-CALL-NAME"] == "GetMyeBayBuying"
        assert request.headers["X-EBAY-API-SITEID"] == "3"
        assert request.headers["X-EBAY-API-COMPATIBILITY-LEVEL"] == "1477"
        body = trading.parse(request.content)
        assert trading._one(body, "WatchList/Include") is not None
        assert trading._text(body, "FavoriteSearches/Include") == "true"

    def test_the_watch_list_from_eBay_s_documented_sample(self) -> None:
        root = trading.parse((FIXTURES / "ebay_trading_buying_doc_sample.xml").read_bytes())
        watching = trading.read_watching(root)

        auction, fixed = watching.items
        assert (auction.item_id, auction.title, auction.price, auction.currency) == (
            "1**********4",
            "Mint Titleist AP2 Iron",
            Decimal("227.5"),
            "USD",
        )
        assert (auction.is_auction, auction.bid_count, auction.postage) == (
            True,
            12,
            Decimal("17.0"),
        )
        assert auction.url == "https://www.ebay.co.uk/itm/1**********4"
        assert (fixed.is_auction, fixed.price, fixed.bid_count) == (False, Decimal("64.99"), None)
        assert watching.total_items == 2

    def test_saved_searches_keep_their_words(self) -> None:
        root = trading.parse((FIXTURES / "ebay_trading_buying_doc_sample.xml").read_bytes())
        searches = trading.read_watching(root).saved_searches

        assert [(search.name, search.keywords) for search in searches] == [
            ("koa, Taylor Completed listings", "koa"),
            ("titleist 735 irons, Iron Set", "titleist 735 irons"),
        ]
        # The sample's addresses are plain http, which the app does not link to.
        assert [search.url for search in searches] == [None, None]

    def test_the_selling_list_from_eBay_s_documented_sample(self) -> None:
        root = trading.parse((FIXTURES / "ebay_trading_selling_doc_sample.xml").read_bytes())
        selling = trading.read_selling(root)

        assert [(item.item_id, item.price, item.currency) for item in selling.active] == [
            ("1**********3", Decimal("11.0"), "MYR"),
            ("1**********9", Decimal("1.0"), "USD"),
            ("1**********2", Decimal("1.0"), "USD"),
        ]
        assert selling.total_active == 3
        assert selling.sold == []

    def test_sold_items_in_both_of_eBay_s_shapes_and_never_their_buyers(self) -> None:
        content = (FIXTURES / "ebay_trading_soldlist_from_field_reference.xml").read_bytes()
        selling = trading.read_selling(trading.parse(content))

        assert [(sold.title, sold.price, sold.currency) for sold in selling.sold] == [
            ("Heat Blu-ray 2-Disc Edition", Decimal("12.50"), "GBP"),
            ("Alien 4K UHD", Decimal("18.00"), "GBP"),
        ]
        assert selling.total_sold == 2
        assert "must_not_appear" not in repr(selling)
        assert "example.invalid" not in repr(selling)

    async def test_a_failure_says_what_eBay_said(self) -> None:
        failure = (
            b'<?xml version="1.0" encoding="utf-8"?>'
            b'<GetMyeBayBuyingResponse xmlns="urn:ebay:apis:eBLBaseComponents">'
            b"<Ack>Failure</Ack><Errors><ShortMessage>Invalid IAF token.</ShortMessage>"
            b"<LongMessage>IAF token supplied is invalid.</LongMessage>"
            b"<ErrorCode>21916984</ErrorCode></Errors></GetMyeBayBuyingResponse>"
        )
        transport, _ = _trading(failure)
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(trading.TradingError) as raised:
                await trading.watching(client, ACCESS)

        assert raised.value.token_rejected
        assert str(raised.value) == (
            "eBay refused GetMyeBayBuying: IAF token supplied is invalid. (error 21916984)"
        )

    async def test_a_401_is_a_token_eBay_will_not_take(self) -> None:
        transport, _ = _trading(b"", status=401)
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(trading.TradingError) as raised:
                await trading.selling(client, ACCESS)
        assert raised.value.token_rejected

    @pytest.mark.parametrize(
        "bomb",
        [
            # Entity expansion ("billion laughs").
            b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]>'
            b"<x>&b;</x>",
            # An external entity reading a file.
            b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>',
        ],
    )
    def test_an_answer_with_entities_is_refused_not_expanded(self, bomb: bytes) -> None:
        with pytest.raises(trading.TradingError, match="could not be read"):
            trading.parse(bomb)

    def test_the_account_name_is_read_from_get_user(self) -> None:
        answer = (
            b'<GetUserResponse xmlns="urn:ebay:apis:eBLBaseComponents"><Ack>Success</Ack>'
            b"<User><UserID>mark_at_the_movies</UserID></User></GetUserResponse>"
        )
        assert trading.read_user_id(trading.parse(answer)) == "mark_at_the_movies"

    def test_the_requests_are_well_formed_and_ask_for_one_page(self) -> None:
        buying = trading.parse(trading.buying_request().encode())
        selling = trading.parse(trading.selling_request().encode())
        assert trading._text(buying, "WatchList/Pagination/EntriesPerPage") == "100"
        assert trading._text(selling, "SoldList/DurationInDays") == "60"
        assert json.dumps(trading._text(selling, "ActiveList/Include")) == '"true"'
