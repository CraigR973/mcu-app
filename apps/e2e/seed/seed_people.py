"""Give Craig and Mark a PIN and a finished first-run, through the app's own hash.

usage: seed_people.py        (reads DATABASE_URL, a throwaway database)
Migration 002 seeds both people with no PIN; there is no sign-up route, so a PIN is the one
thing a database row has to carry for a browser to sign in.
"""

import os
import sys

import psycopg2

from src.auth import hash_pin
from src.services.collection_additions import MARK_PROFILE_ID

PINS = {"Craig": "4827", "Mark": "7391"}


def main() -> None:
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg", "postgresql")
    conn = psycopg2.connect(url)
    conn.autocommit = True
    with conn.cursor() as cur:
        # AB3: the fixture binds Mark explicitly, as production does; never by role.
        cur.execute("UPDATE profiles SET id = %s WHERE display_name = %s", (str(MARK_PROFILE_ID), "Mark"))
        for name, pin in PINS.items():
            cur.execute(
                "UPDATE profiles SET pin_hash = %s, failed_login_count = 0, locked_until_utc = NULL, "
                "onboarding_completed_at_utc = now() AT TIME ZONE 'utc' "
                "WHERE lower(display_name) = lower(%s)",
                (hash_pin(pin), name),
            )
            if cur.rowcount != 1:
                sys.exit(f"expected one profile named {name}, updated {cur.rowcount}")
    conn.close()


if __name__ == "__main__":
    main()
