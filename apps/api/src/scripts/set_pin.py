"""Set a profile's PIN from the command line. The only way to set the *first* one.

Migration `002` seeds both profiles with ``pin_hash = NULL`` — no credential — so that no
PIN is ever written into a migration, a seed file, or git history. That leaves a
bootstrap problem: ``POST /api/v1/auth/pin`` needs an access token, an access token needs
a login, and a login needs a PIN. This script is the way in, and it is deliberately not
an HTTP route: setting someone's first credential should require database access, not a
request.

Run it against the target database::

    DATABASE_URL=... PYTHONPATH=apps/api \\
      apps/api/.venv/bin/python3.12 -m src.scripts.set_pin Craig

The PIN is read from a hidden prompt and confirmed. It is never a command-line argument,
so it does not reach ``ps``, the shell history, or a CI log.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from getpass import getpass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.auth import PIN_MAX_LENGTH, PIN_MIN_LENGTH, hash_pin, is_weak_pin
from src.config import settings
from src.models.profile import Profile, RefreshToken


def validate_pin(pin: str) -> str | None:
    """Return an error message, or ``None`` when the PIN is acceptable."""
    if not pin.isdigit():
        return "PIN must be digits only."
    if not PIN_MIN_LENGTH <= len(pin) <= PIN_MAX_LENGTH:
        return f"PIN must be {PIN_MIN_LENGTH}-{PIN_MAX_LENGTH} digits."
    if is_weak_pin(pin):
        return "That PIN is among the most commonly chosen — pick another."
    return None


def _read_pin() -> str | None:
    pin = getpass("New PIN: ")
    error = validate_pin(pin)
    if error:
        print(error, file=sys.stderr)
        return None
    if pin != getpass("Confirm PIN: "):
        print("PINs did not match.", file=sys.stderr)
        return None
    return pin


async def set_pin(display_name: str, pin: str) -> int:
    engine = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            result = await session.execute(
                select(Profile).where(
                    func.lower(Profile.display_name) == display_name.lower(),
                    Profile.deleted_at.is_(None),
                )
            )
            profile = result.scalar_one_or_none()
            if profile is None:
                print(f"No profile named {display_name!r}.", file=sys.stderr)
                return 1

            was_unset = profile.pin_hash is None
            profile.pin_hash = hash_pin(pin)
            # Clear any lockout: someone setting a PIN from the database is by definition
            # the owner, and leaving them locked out of the credential they just set
            # would be absurd.
            profile.failed_login_count = 0
            profile.locked_until_utc = None

            # Revoke live sessions on a *change*, for the same reason the HTTP route
            # does: a PIN change is what someone does when they think a credential is
            # compromised. Not on a first set, where there are none.
            existing = await session.execute(
                select(RefreshToken).where(
                    RefreshToken.user_id == profile.id,
                    RefreshToken.revoked_at_utc.is_(None),
                )
            )
            revoked = 0
            for record in existing.scalars():
                record.revoked_at_utc = func.now()
                revoked += 1

            await session.commit()
    finally:
        await engine.dispose()

    action = "set" if was_unset else "changed"
    print(f"PIN {action} for {profile.display_name} ({profile.role}).")
    if revoked:
        print(f"Revoked {revoked} active session(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Set a profile's PIN.")
    parser.add_argument("display_name", help="The profile's display name, e.g. Craig")
    args = parser.parse_args()

    pin = _read_pin()
    if pin is None:
        return 1
    return asyncio.run(set_pin(args.display_name, pin))


if __name__ == "__main__":
    raise SystemExit(main())
