"""RFC 8291 / RFC 8292 conformance for the Web Push transport.

**Why the round trip is written from the receiver's side.** A test that encrypts and then
decrypts by calling the encryptor's own helpers proves only that the code agrees with
itself — and a Web Push failure of that kind is completely silent, because the push
service accepts ciphertext it cannot read and answers ``201``. So
:func:`src.services.webpush.decrypt` derives its keys the way a browser does, from the
subscription's private key and the sender's public key read out of the message header, and
the tests below pin the three ``info`` strings and the header framing separately — those
are the constants that a from-memory implementation gets wrong.
"""

from __future__ import annotations

import os

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)

from src.services import webpush


def _subscription() -> tuple[ec.EllipticCurvePrivateKey, bytes, bytes]:
    """Stand in for a browser: a P-256 keypair and a 16-byte auth secret."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    return private_key, webpush.vapid_public_key_bytes(private_key), os.urandom(16)


def test_info_strings_are_exactly_what_the_rfcs_specify() -> None:
    """The three constants an implementation written from memory gets wrong.

    Each is ASCII plus a single NUL separator. A wrong byte here derives a different key,
    which fails **silently** — the push is accepted and never displayed.
    """
    assert webpush.WEBPUSH_INFO == b"WebPush: info\x00"
    assert webpush.CEK_INFO == b"Content-Encoding: aes128gcm\x00"
    assert webpush.NONCE_INFO == b"Content-Encoding: nonce\x00"


def test_a_browser_can_decrypt_what_the_server_encrypted() -> None:
    """The property that actually matters: the receiver's derivation reaches our key."""
    ua_private, ua_public, auth = _subscription()
    plaintext = b'{"title":"Deep Red","body":"\xc2\xa315.00 at Arrow"}'

    body = webpush.encrypt(plaintext, ua_public=ua_public, auth_secret=auth)

    assert webpush.decrypt(body, ua_private=ua_private, auth_secret=auth) == plaintext


def test_the_body_is_framed_the_way_rfc_8188_specifies() -> None:
    """``salt(16) || rs(4) || idlen(1) || keyid(65) || ciphertext``."""
    _, ua_public, auth = _subscription()

    body = webpush.encrypt(b"x", ua_public=ua_public, auth_secret=auth)

    assert int.from_bytes(body[16:20], "big") == webpush.RECORD_SIZE
    assert body[20] == 65, "keyid is an uncompressed P-256 point"
    assert body[21] == 0x04, "…which starts with the uncompressed-point marker"
    # Header, then one record: the plaintext, its 0x02 delimiter and the GCM tag.
    assert len(body) == 16 + 4 + 1 + 65 + (1 + 1 + 16)


def test_two_messages_to_one_subscription_never_share_a_nonce() -> None:
    """A reused salt or ephemeral key would reuse the AES-GCM nonce, which is fatal."""
    _, ua_public, auth = _subscription()

    first = webpush.encrypt(b"same", ua_public=ua_public, auth_secret=auth)
    second = webpush.encrypt(b"same", ua_public=ua_public, auth_secret=auth)

    assert first[:16] != second[:16], "salt must be fresh"
    assert first[21:86] != second[21:86], "ephemeral key must be fresh"
    assert first != second


def test_a_payload_that_will_not_fit_one_record_is_refused() -> None:
    """Better a raised error here than a push service's opaque 413."""
    _, ua_public, auth = _subscription()

    with pytest.raises(ValueError, match="too large"):
        webpush.encrypt(b"x" * webpush.RECORD_SIZE, ua_public=ua_public, auth_secret=auth)


@pytest.mark.parametrize(
    ("p256dh", "auth_length", "message"),
    [
        (b"\x04" + b"\x00" * 63, 16, "65-byte"),
        (b"\x02" + b"\x00" * 64, 16, "uncompressed"),
        (None, 15, "16 bytes"),
    ],
)
def test_a_malformed_subscription_is_refused_before_any_crypto(
    p256dh: bytes | None, auth_length: int, message: str
) -> None:
    """A truncated key must fail loudly, not encrypt to something nobody can read."""
    _, valid_public, _ = _subscription()

    with pytest.raises(ValueError, match=message):
        webpush.encrypt(
            b"x",
            ua_public=p256dh if p256dh is not None else valid_public,
            auth_secret=os.urandom(auth_length),
        )


def test_vapid_private_keys_load_from_a_raw_scalar_and_from_a_pem() -> None:
    """`web-push` emits the raw scalar; other tooling emits PEM. Both must work."""
    key = ec.generate_private_key(ec.SECP256R1())
    raw = key.private_numbers().private_value.to_bytes(32, "big")
    pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()

    from_raw = webpush.load_vapid_private_key(webpush.b64url_encode(raw))
    from_pem = webpush.load_vapid_private_key(pem)

    expected = webpush.vapid_public_key_bytes(key)
    assert webpush.vapid_public_key_bytes(from_raw) == expected
    assert webpush.vapid_public_key_bytes(from_pem) == expected


def test_a_key_that_is_neither_form_is_refused_at_load() -> None:
    """Configuration should fail where it can be read, not at the first push."""
    with pytest.raises(ValueError, match="32-byte P-256 scalar or a PEM"):
        webpush.load_vapid_private_key(webpush.b64url_encode(b"too short"))


def test_the_vapid_assertion_is_signed_over_the_push_services_origin() -> None:
    """``aud`` is the origin. Signing the full endpoint is the classic mistake."""
    key = ec.generate_private_key(ec.SECP256R1())
    issued_at = 1_757_000_000

    header = webpush.vapid_authorization(
        endpoint="https://fcm.googleapis.com/fcm/send/abc123?x=1",
        private_key=key,
        subject="mailto:owner@example.com",
        issued_at=issued_at,
    )

    scheme, _, parameters = header.partition(" ")
    assert scheme == "vapid"
    token = parameters.split("t=")[1].split(",")[0].strip()
    advertised = parameters.split("k=")[1].strip()

    claims = jwt.decode(
        token,
        key.public_key(),
        algorithms=["ES256"],
        audience="https://fcm.googleapis.com",
        options={"verify_exp": False},
    )
    assert claims["aud"] == "https://fcm.googleapis.com"
    assert claims["sub"] == "mailto:owner@example.com"
    assert claims["exp"] == issued_at + webpush.VAPID_TOKEN_LIFETIME_SECONDS
    # The advertised key must be the one that signed, or the service rejects the push.
    assert advertised == webpush.b64url_encode(webpush.vapid_public_key_bytes(key))


def test_the_vapid_assertion_expires_inside_the_rfc_8292_ceiling() -> None:
    """RFC 8292 §2 caps ``exp`` at 24 hours ahead; services enforce it."""
    assert 0 < webpush.VAPID_TOKEN_LIFETIME_SECONDS <= 24 * 60 * 60


def test_an_endpoint_that_is_not_an_absolute_url_is_refused() -> None:
    with pytest.raises(ValueError, match="absolute URL"):
        webpush.audience_for("/fcm/send/abc")


def test_base64url_round_trips_without_padding() -> None:
    """Every value in a subscription arrives unpadded; decoding must not need the ``=``."""
    for length in range(1, 34):
        raw = os.urandom(length)
        encoded = webpush.b64url_encode(raw)
        assert "=" not in encoded
        assert webpush.b64url_decode(encoded) == raw
