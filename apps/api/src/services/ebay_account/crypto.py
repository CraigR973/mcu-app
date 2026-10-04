"""Sealing a person's eBay token at rest — Batch T8b, `DECISIONS.md` #142, #227, #245.

**AES-256-GCM, with a key derived from ``EBAY_TOKEN_KEY`` and the owner's profile as the
associated data.** GCM authenticates as well as encrypts, so a sealed token that has been
altered, or moved onto another person's row, does not open: the profile id is part of what
the tag covers. The 32 bytes in ``EBAY_TOKEN_KEY`` are never used directly; HKDF-SHA256
derives the key under a label naming its one purpose, so the same bytes could never seal
anything else by accident.

A sealed value is one version byte, a fresh 12-byte nonce, then the ciphertext and its tag.
The version byte lets a later key or scheme be told apart without guessing.

**Losing the key loses nothing but the connections**: every sealed token stops opening, and
each person presses Connect eBay again.
"""

from __future__ import annotations

import base64
import binascii
import os
import uuid

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from src.config import settings

VERSION = b"\x01"
NONCE_BYTES = 12
#: The derived key's one purpose, written into the derivation.
INFO = b"mcu-app ebay user token v1"


class TokenKeyMissing(RuntimeError):
    """``EBAY_TOKEN_KEY`` is not set in this deployment."""


class TokenKeyInvalid(RuntimeError):
    """``EBAY_TOKEN_KEY`` is not 32 bytes in base64."""


class SealBroken(RuntimeError):
    """A sealed token would not open: the key changed, or the row was altered or moved."""


def derive_key(raw_b64: str) -> bytes:
    """The sealing key, from the 32 random bytes in ``EBAY_TOKEN_KEY``."""
    try:
        raw = base64.b64decode(raw_b64.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise TokenKeyInvalid("EBAY_TOKEN_KEY is not base64.") from exc
    if len(raw) != 32:
        raise TokenKeyInvalid("EBAY_TOKEN_KEY must be 32 random bytes in base64.")
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=INFO).derive(raw)


def key_from_settings() -> bytes:
    if not settings.ebay_token_key:
        raise TokenKeyMissing("EBAY_TOKEN_KEY is not set in this deployment.")
    return derive_key(settings.ebay_token_key)


def seal(plain: str, *, owner: uuid.UUID, key: bytes) -> bytes:
    """Encrypt and authenticate one token for one person."""
    nonce = os.urandom(NONCE_BYTES)
    return VERSION + nonce + AESGCM(key).encrypt(nonce, plain.encode("utf-8"), owner.bytes)


def open_sealed(sealed: bytes, *, owner: uuid.UUID, key: bytes) -> str:
    """The token, or :class:`SealBroken` if it does not open for this person and key."""
    if len(sealed) <= 1 + NONCE_BYTES or sealed[:1] != VERSION:
        raise SealBroken("The stored eBay token is not in a form this app can open.")
    nonce, body = sealed[1 : 1 + NONCE_BYTES], sealed[1 + NONCE_BYTES :]
    try:
        return AESGCM(key).decrypt(nonce, body, owner.bytes).decode("utf-8")
    except InvalidTag as exc:
        raise SealBroken("The stored eBay token would not open with this key.") from exc
