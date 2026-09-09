"""Web Push: RFC 8291 payload encryption and RFC 8292 VAPID authorisation.

This is the transport half of Batch 11. It knows how to turn a payload and a browser's
subscription into an encrypted HTTP request to a push service, and nothing about what a
notification *means* — that is :mod:`src.services.notifications`.

**Why this is written here rather than pulled from `pywebpush`.** The encryption is about
sixty lines against a published specification, and writing it means the test can derive
the keys from the **receiver** side — running the browser's half of the algorithm against
our sender's half. A library test can only prove the library agrees with itself. The
trade is that these three info strings are load-bearing and are pinned by their own test:
get one byte wrong and every push is silently undecryptable, because a push service
accepts the ciphertext it cannot read and answers ``201``.

**The shape of a message.** RFC 8188 frames the body as
``salt(16) || rs(4, big-endian) || idlen(1) || keyid || ciphertext``, where for Web Push
the ``keyid`` is the sender's ephemeral P-256 public key and there is exactly one record.
RFC 8291 §4 supplies the key derivation that turns the ECDH secret and the subscription's
``auth`` secret into that record's content-encryption key and nonce.
"""

from __future__ import annotations

import base64
import hmac
import os
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import urlsplit

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_pem_private_key,
)

#: RFC 8291 §3.4. The ``\x00`` is a required separator, not padding.
WEBPUSH_INFO = b"WebPush: info\x00"
#: RFC 8188 §2.2, the content-encryption key.
CEK_INFO = b"Content-Encoding: aes128gcm\x00"
#: RFC 8188 §2.2, the nonce.
NONCE_INFO = b"Content-Encoding: nonce\x00"

#: The single record's declared size. Push services cap a message at 4096 bytes, so one
#: record is always enough and multi-record framing is dead code this never writes.
RECORD_SIZE = 4096
#: AES-GCM's authentication tag, which counts towards the record.
_TAG_LENGTH = 16
#: An uncompressed P-256 point: ``0x04`` then two 32-byte coordinates.
_P256_POINT_LENGTH = 65
#: RFC 8291 §3.1 — the subscription's ``auth`` secret.
_AUTH_SECRET_LENGTH = 16

#: How long a VAPID assertion is good for. RFC 8292 §2 caps it at 24 hours; twelve leaves
#: room for a clock that disagrees with ours without ever presenting an expired token.
VAPID_TOKEN_LIFETIME_SECONDS = 12 * 60 * 60


def b64url_decode(value: str) -> bytes:
    """Decode unpadded base64url, which is how every value in a subscription arrives."""
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def b64url_encode(value: bytes) -> str:
    """Encode as unpadded base64url, which is what push services and browsers expect."""
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    """HKDF-SHA256 (RFC 5869) for the one output length this protocol ever asks for.

    Every derivation here wants 32 bytes or fewer, so Expand is a single HMAC round and
    the counter is always ``0x01``. Written out rather than reached for through a library
    so the three ``info`` strings above sit next to the function that consumes them.
    """
    if length > sha256().digest_size:
        raise ValueError("this HKDF only emits one block")
    prk = hmac.new(salt, ikm, sha256).digest()
    return hmac.new(prk, info + b"\x01", sha256).digest()[:length]


@dataclass(frozen=True)
class DerivedKeys:
    """The content-encryption key and nonce for one message. Exposed for the tests."""

    content_encryption_key: bytes
    nonce: bytes


def derive_keys(
    *,
    ua_public: bytes,
    auth_secret: bytes,
    as_public: bytes,
    shared_secret: bytes,
    salt: bytes,
) -> DerivedKeys:
    """RFC 8291 §3.4's derivation, from whichever side already holds the shared secret.

    Both the sender and the receiver run this — the sender reaches ``shared_secret`` with
    its ephemeral private key and the browser's public key, the receiver with the reverse.
    Keeping it in one function is what lets the test play the browser.
    """
    ikm = _hkdf(
        salt=auth_secret,
        ikm=shared_secret,
        info=WEBPUSH_INFO + ua_public + as_public,
        length=32,
    )
    return DerivedKeys(
        content_encryption_key=_hkdf(salt=salt, ikm=ikm, info=CEK_INFO, length=16),
        nonce=_hkdf(salt=salt, ikm=ikm, info=NONCE_INFO, length=12),
    )


def encrypt(
    payload: bytes,
    *,
    ua_public: bytes,
    auth_secret: bytes,
    as_private: ec.EllipticCurvePrivateKey | None = None,
    salt: bytes | None = None,
) -> bytes:
    """Encrypt ``payload`` into an ``aes128gcm`` body for one subscription.

    ``as_private`` and ``salt`` are injectable **only so a test can be deterministic**;
    production always takes the random path, and reusing either across two messages to
    the same subscription would reuse a nonce.
    """
    if len(ua_public) != _P256_POINT_LENGTH or ua_public[0] != 0x04:
        raise ValueError("p256dh must be a 65-byte uncompressed P-256 point")
    if len(auth_secret) != _AUTH_SECRET_LENGTH:
        raise ValueError("auth must be 16 bytes")

    as_private = as_private or ec.generate_private_key(ec.SECP256R1())
    salt = salt or os.urandom(16)
    as_public = as_private.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)

    shared_secret = as_private.exchange(
        ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    )
    keys = derive_keys(
        ua_public=ua_public,
        auth_secret=auth_secret,
        as_public=as_public,
        shared_secret=shared_secret,
        salt=salt,
    )

    # RFC 8188 §2: every record ends with a delimiter, ``0x02`` on the last one. There is
    # no separate padding here — the payload is JSON we control the size of.
    record = payload + b"\x02"
    if len(record) + _TAG_LENGTH > RECORD_SIZE:
        raise ValueError(f"payload too large for one {RECORD_SIZE}-byte record")

    ciphertext = AESGCM(keys.content_encryption_key).encrypt(keys.nonce, record, None)
    header = salt + RECORD_SIZE.to_bytes(4, "big") + len(as_public).to_bytes(1, "big") + as_public
    return header + ciphertext


def decrypt(body: bytes, *, ua_private: ec.EllipticCurvePrivateKey, auth_secret: bytes) -> bytes:
    """The receiver's half — what the browser does with the body :func:`encrypt` produced.

    **Production never calls this.** It exists so the round-trip test derives keys the way
    a user agent does, from the subscription's private key and the sender's public key
    read out of the header, rather than by re-running the sender's own code.
    """
    salt, id_length = body[:16], body[20]
    as_public = body[21 : 21 + id_length]
    ciphertext = body[21 + id_length :]

    ua_public = ua_private.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    shared_secret = ua_private.exchange(
        ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public)
    )
    keys = derive_keys(
        ua_public=ua_public,
        auth_secret=auth_secret,
        as_public=as_public,
        shared_secret=shared_secret,
        salt=salt,
    )
    record = AESGCM(keys.content_encryption_key).decrypt(keys.nonce, ciphertext, None)
    return record.rstrip(b"\x02")


def load_vapid_private_key(value: str) -> ec.EllipticCurvePrivateKey:
    """Load a VAPID private key from either of the two forms tools emit.

    ``web-push generate-vapid-keys`` and `py-vapid` both hand back the raw 32-byte private
    scalar as unpadded base64url; other tooling writes a PEM. Accepting both means the
    Railway variable can hold whatever the owner generated without a migration of the
    credential itself — and a wrong guess here fails at boot rather than at send time.
    """
    stripped = value.strip()
    if "-----BEGIN" in stripped:
        key = load_pem_private_key(stripped.encode("ascii"), password=None)
        if not isinstance(key, ec.EllipticCurvePrivateKey):
            raise ValueError("VAPID private key must be an EC key")
        return key

    raw = b64url_decode(stripped)
    if len(raw) != 32:
        raise ValueError("VAPID private key must be a 32-byte P-256 scalar or a PEM")
    return ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())


def vapid_public_key_bytes(private_key: ec.EllipticCurvePrivateKey) -> bytes:
    """The uncompressed public point, which is what a browser passes to ``subscribe()``."""
    return private_key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)


def audience_for(endpoint: str) -> str:
    """RFC 8292's ``aud``: the push service's origin, never the full endpoint path.

    Signing the whole endpoint is the common mistake and it is rejected by Firefox's
    service with a 401 that says nothing useful.
    """
    parts = urlsplit(endpoint)
    if not parts.scheme or not parts.netloc:
        raise ValueError(f"push endpoint is not an absolute URL: {endpoint!r}")
    return f"{parts.scheme}://{parts.netloc}"


def vapid_authorization(
    *,
    endpoint: str,
    private_key: ec.EllipticCurvePrivateKey,
    subject: str,
    issued_at: int,
) -> str:
    """The ``Authorization`` header value for one push, in RFC 8292's single-header form."""
    token = jwt.encode(
        {
            "aud": audience_for(endpoint),
            "exp": issued_at + VAPID_TOKEN_LIFETIME_SECONDS,
            "sub": subject,
        },
        private_key,
        algorithm="ES256",
    )
    public_key = b64url_encode(vapid_public_key_bytes(private_key))
    return f"vapid t={token}, k={public_key}"
